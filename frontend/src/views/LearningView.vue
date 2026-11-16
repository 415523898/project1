<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import MethodDetail from '@/components/MethodDetail.vue';
import MethodGraph from '@/components/MethodGraph.vue';
import MethodSearch from '@/components/MethodSearch.vue';
import PanelResizeHandle from '@/components/PanelResizeHandle.vue';
import ReferenceOverview from '@/components/ReferenceOverview.vue';
import UiIcon from '@/components/UiIcon.vue';
import { usePanelWidth } from '@/composables/usePanelWidth';
import { useLab } from '@/composables/useLab';
import { useLearning } from '@/composables/useLearning';
import { useMethodGraph } from '@/composables/useMethodGraph';
import { useReferenceNavigation } from '@/composables/useReferenceNavigation';
import { recordLearningSource } from '@/composables/useLearningExploration';
import { connectionError } from '@/services/agent';
import { ApiBase } from '@/utils/api-base';
import { useElementWidth } from '@/composables/useElementWidth';
import { opacityTransition } from '@/utils/opacity-transition';
import type { MethodCard, MethodLayer, RelationKind } from '@/types';

const lab = useLab();
const learning = useLearning();
const library = useMethodGraph();
const referenceNavigation = useReferenceNavigation();
const router = useRouter();
const route = useRoute();
const detailsWidth = usePanelWidth('details');
const workspaceRoot = ref<HTMLElement | null>(null);
const availableWidth = useElementWidth(workspaceRoot);
const narrowDetails = computed(() => availableWidth.value < 900);
const panelFade = opacityTransition(140, 100);

const learned = learning.learned;

const studying = computed(() => {
  const nodes = learning.curriculum.value?.nodes ?? [];
  return nodes.filter((node) => node.studying && node.id).map((node) => String(node.id));
});

const selected = ref<string | null>(null);
const panelOpen = ref(false);
const OVERVIEW_SEEN_KEY = 'forest-reference-overview-seen-v1';
function overviewSeen(owner: string | null): boolean {
  if (!owner) return false;
  try {
    return localStorage.getItem(`${OVERVIEW_SEEN_KEY}:${owner}`) === '1';
  } catch {
    return false;
  }
}
function markOverviewSeen(owner = lab.state.user): void {
  if (!owner) return;
  try {
    localStorage.setItem(`${OVERVIEW_SEEN_KEY}:${owner}`, '1');
  } catch {
    /* The overview still works when browser storage is unavailable. */
  }
}
const showOverview = ref(!route.query.card && !overviewSeen(lab.state.user));
const overviewHeading = ref<HTMLHeadingElement | null>(null);
const methodSearch = ref<InstanceType<typeof MethodSearch> | null>(null);
const launchError = ref('');
const launching = ref(false);
type LaunchIntent = { owner: string; session: string; method: string };
const pendingLaunch = ref<LaunchIntent | null>(restoreLaunch());
function restoreLaunch(): LaunchIntent | null {
  try {
    const value = JSON.parse(
      sessionStorage.getItem('forest-reference-launch-v1') || 'null',
    ) as LaunchIntent | null;
    return value &&
      value.owner === lab.state.user &&
      typeof value.session === 'string' &&
      typeof value.method === 'string'
      ? value
      : null;
  } catch {
    return null;
  }
}
watch(pendingLaunch, (value) => {
  try {
    if (value) sessionStorage.setItem('forest-reference-launch-v1', JSON.stringify(value));
    else sessionStorage.removeItem('forest-reference-launch-v1');
  } catch {
    /* The current view still retains the retry intent. */
  }
});
watch(
  () => lab.state.user,
  () => {
    if (pendingLaunch.value?.owner !== lab.state.user) pendingLaunch.value = null;
  },
);
let disposed = false;
onBeforeUnmount(() => {
  disposed = true;
});

const highlights = ref<Record<RelationKind, boolean>>({
  prerequisite: true,
  suggest: true,
  alternative: true,
});
const relationOptions: Array<{ kind: RelationKind; label: string }> = [
  { kind: 'prerequisite', label: '硬前置' },
  { kind: 'suggest', label: '软前置' },
  { kind: 'alternative', label: '可替代' },
];

const activeKinds = computed<RelationKind[]>(() =>
  (Object.keys(highlights.value) as RelationKind[]).filter((key) => highlights.value[key]),
);

const cardsById = computed(() => {
  const index = new Map<string, MethodCard>();
  for (const card of library.graph.value?.cards ?? []) index.set(card.id, card);
  return index;
});

watch(
  [() => route.query.card, cardsById],
  ([id]) => {
    const card = typeof id === 'string' ? cardsById.value.get(id) : null;
    if (!card) {
      selected.value = null;
      panelOpen.value = false;
      return;
    }
    const changed = selected.value !== card.id;
    selected.value = card.id;
    showOverview.value = false;
    markOverviewSeen();
    if (changed) panelOpen.value = !narrowDetails.value;
  },
  { immediate: true },
);

const layers = computed<MethodLayer[]>(() => library.graph.value?.layers ?? []);

const whyIndex = computed(() => {
  const index = new Map<string, string>();
  const edges = library.graph.value?.edges;
  if (!edges) return index;
  for (const kind of ['prerequisite', 'suggest', 'alternative'] as RelationKind[]) {
    for (const edge of edges[kind] ?? []) {
      index.set(`${kind}:${edge.from}->${edge.to}`, edge.why ?? '');
    }
  }
  return index;
});

function why(kind: RelationKind, from: string, to: string): string {
  return whyIndex.value.get(`${kind}:${from}->${to}`) ?? '';
}

const selectedCard = computed(() =>
  selected.value ? (cardsById.value.get(selected.value) ?? null) : null,
);
const problems = computed(() => library.graph.value?.problems ?? []);
function toolbarKey(event: KeyboardEvent): void {
  if (event.defaultPrevented) return;
  if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    methodSearch.value?.focus?.();
  }
}

function label(id: string): string {
  return cardsById.value.get(id)?.label ?? id;
}

function pick(id: string): void {
  const card = cardsById.value.get(id);
  if (!card) return;
  selected.value = id;
  showOverview.value = false;
  markOverviewSeen();
  panelOpen.value = !narrowDetails.value;
  void router.replace({ query: { ...route.query, card: id } });
  if (lab.state.user) void library.load();
}

function clearSelection(): void {
  selected.value = null;
  panelOpen.value = false;
  if (route.query.card) {
    const query = { ...route.query };
    delete query.card;
    void router.replace({ query });
  }
}

function pickFromSearch(id: string): void {
  pick(id);
}

function goHome(): void {
  clearSelection();
  showOverview.value = true;
  void nextTick(() => overviewHeading.value?.focus({ preventScroll: true }));
}

function enterGraph(): void {
  markOverviewSeen();
  showOverview.value = false;
  void nextTick(() => methodSearch.value?.focus?.());
}

function toggleKind(kind: RelationKind): void {
  highlights.value = { ...highlights.value, [kind]: !highlights.value[kind] };
}

async function markLearned(card: MethodCard): Promise<void> {
  if (!requireSignIn() || learning.progressBusy.value) return;
  await learning.setDone(card.id, !learned.value.includes(card.id));
  await learning.refresh();
}

async function beginStudy(card: MethodCard): Promise<void> {
  if (!requireSignIn() || launching.value) return;
  if (
    !pendingLaunch.value &&
    !learned.value.includes(card.id) &&
    studying.value.includes(card.id)
  ) {
    const session = lab.state.sessions.find(
      (item) => item.binding?.method_id === card.id && !item.binding.card_missing,
    );
    if (session) {
      launching.value = true;
      try {
        await lab.openSession(session.id);
        if (lab.state.sessionId === session.id) await router.push('/');
      } finally {
        launching.value = false;
      }
      return;
    }
  }
  await learn(card);
}

async function retryMap(): Promise<void> {
  launchError.value = '';
  await library.load(true);
  if (!library.error.value) await learning.load(true);
}

async function learn(card: MethodCard): Promise<void> {
  const owner = lab.state.user;
  launching.value = true;
  launchError.value = '';
  const pending = pendingLaunch.value;
  const reuse = pending?.owner === owner && pending.method === card.id;
  if (reuse && pending.session !== lab.state.sessionId) {
    await lab.openSession(pending.session);
    if (lab.state.sessionId !== pending.session) {
      launchError.value = '暂时无法恢复待绑定会话，请稍后重试。';
      launching.value = false;
      return;
    }
  }
  if (!reuse) lab.newSession();
  let session: string | null = null;
  try {
    session = await lab.ensureSession();
    if (!session || disposed || lab.state.user !== owner || lab.state.sessionId !== session) return;
    pendingLaunch.value = { owner, session, method: card.id };
    await recordLearningSource(lab, card.id);
    if (disposed || lab.state.user !== owner || lab.state.sessionId !== session) return;
    await learning.refresh();
    if (disposed || lab.state.user !== owner || lab.state.sessionId !== session) return;
    lab.setDraft(`带我学习「${card.label}」。`);
    void lab.refreshSessions();
    pendingLaunch.value = null;
    await router.push('/');
  } catch (error) {
    if (disposed || lab.state.user !== owner || lab.state.sessionId !== session) return;
    const message = connectionError(error);
    launchError.value = message.includes('连接中断')
      ? `${message}（当前后端：${ApiBase.get()}）`
      : message;
    lab.setStatus(launchError.value, 'error');
  } finally {
    launching.value = false;
  }
}

function requireSignIn(): boolean {
  if (lab.state.user) return true;
  void router.push({ name: 'signin', query: { next: '/learning' } });
  return false;
}

watch(referenceNavigation.overviewRequest, goHome);

watch(
  () => lab.state.user,
  (owner, previous) => {
    if (!owner || owner === previous) return;
    if (!previous) {
      if (overviewSeen(owner)) {
        showOverview.value = false;
        return;
      }
      showOverview.value = !route.query.card;
      if (showOverview.value) markOverviewSeen(owner);
      return;
    }
    showOverview.value = !route.query.card && !overviewSeen(owner);
    if (showOverview.value) markOverviewSeen(owner);
  },
);

onMounted(() => {
  document.addEventListener('keydown', toolbarKey);
  if (lab.state.user && showOverview.value) markOverviewSeen();
  if (lab.state.user) {
    void library.load();
    void learning.load();
  }
});
onBeforeUnmount(() => {
  document.removeEventListener('keydown', toolbarKey);
});
</script>

<template>
  <main
    ref="workspaceRoot"
    class="learning-view flex h-full min-w-0 flex-col overflow-hidden bg-surface"
    data-view="learning"
  >
    <header class="learning-toolbar" data-role="learning-toolbar">
      <div class="toolbar-heading">
        <button
          v-if="selected"
          type="button"
          class="overview-back"
          data-action="back-to-overview"
          aria-label="返回全部方法"
          title="返回全部方法"
          @click="goHome"
          ><UiIcon name="arrow-left"
        /></button>
        <h1 ref="overviewHeading" tabindex="-1" class="learning-title">参考路线</h1>
        <span v-if="library.graph.value?.counts" class="toolbar-meta"
          >{{ library.graph.value.counts.methods }} 个方法 ·
          {{ library.graph.value.counts.categories }} 类</span
        >
        <button
          v-if="!showOverview"
          type="button"
          class="overview-home"
          data-action="reference-overview"
          @click="goHome"
          >总览</button
        >
      </div>
      <MethodSearch
        ref="methodSearch"
        class="toolbar-search"
        :graph="library.graph.value"
        :selected="selected"
        @pick="pickFromSearch"
      />
      <div v-if="!showOverview" class="relation-toggles" role="group" aria-label="连线显示">
        <button
          v-for="option in relationOptions"
          :key="option.kind"
          type="button"
          class="relation-option"
          :data-toggle="option.kind"
          :aria-pressed="highlights[option.kind]"
          :title="`显示或隐藏${option.label}连线`"
          @click="toggleKind(option.kind)"
        >
          <svg
            class="relation-sample"
            :class="option.kind"
            width="30"
            height="20"
            viewBox="0 0 34 20"
            aria-hidden="true"
          >
            <path
              d="M3 10H30"
              :stroke-dasharray="option.kind === 'prerequisite' ? undefined : '4 3'"
            />
            <path v-if="option.kind !== 'alternative'" d="m25 6 5 4-5 4" />
            <path v-else d="m8 6-5 4 5 4m17-8 5 4-5 4" />
          </svg>
          <span>{{ option.label }}</span>
        </button>
      </div>
    </header>

    <p
      v-if="(launchError || library.error.value) && lab.state.user"
      class="m-0 flex flex-none items-center gap-3 bg-[#fdecec] px-5 py-2 text-[length:var(--dsw-text-sm)] text-[#b42318]"
      data-role="map-error"
    >
      <span class="min-w-0 flex-1">{{ launchError || library.error.value }}</span>
      <button
        type="button"
        class="flex-none cursor-pointer rounded-[6px] border border-[#b42318]/25 bg-white/70 px-2.5 py-0.5 text-[length:var(--dsw-text-sm)] text-[#b42318] hover:bg-white disabled:cursor-wait disabled:opacity-60"
        data-action="retry-map"
        :disabled="library.loading.value"
        @click="retryMap"
        >重试</button
      >
    </p>
    <p
      v-else-if="problems.length"
      class="m-0 flex-none bg-[#fdecec] px-5 py-2 text-[length:var(--dsw-text-sm)] text-[#b42318]"
      data-role="map-problems"
    >
      方法库数据有问题：{{ problems.join('；') }}
    </p>

    <section
      class="panel-layout relative grid min-h-0 flex-1 overflow-hidden"
      :style="{
        gridTemplateColumns: `minmax(0,1fr) min(${panelOpen && !narrowDetails ? detailsWidth.width.value : 0}px, 45%)`,
      }"
      data-panel="workspace"
    >
      <ReferenceOverview
        v-if="showOverview"
        :graph="library.graph.value"
        :learned="learned"
        :studying="studying"
        @enter="enterGraph"
      />
      <MethodGraph
        v-else
        :graph="library.graph.value"
        :layers="layers"
        :selected="selected"
        :details-open="panelOpen"
        :highlight="activeKinds"
        :learned="learned"
        :studying="studying"
        placeholder="方法库为空。"
        @pick="pick"
        @clear="clearSelection"
        @open-detail="panelOpen = true"
      />
      <Transition :css="false" @enter="panelFade.enter" @leave="panelFade.leave">
        <button
          v-if="panelOpen && narrowDetails"
          type="button"
          class="absolute inset-0 z-10 cursor-default border-0 bg-black/15 p-0"
          data-action="detail-backdrop"
          aria-label="收起方法详情"
          tabindex="-1"
          @click="panelOpen = false"
        />
      </Transition>
      <Transition :css="false" @enter="panelFade.enter" @leave="panelFade.leave">
        <div
          v-if="panelOpen && selectedCard"
          class="method-detail-panel relative min-h-0 min-w-0"
          data-panel="method-detail"
          :class="{ 'is-narrow': narrowDetails }"
          :style="{ width: narrowDetails ? `min(${detailsWidth.width.value}px, 100%)` : undefined }"
        >
          <PanelResizeHandle
            v-if="!narrowDetails"
            edge="left"
            label="方法详情栏宽度"
            :width="detailsWidth.width.value"
            :initial="detailsWidth.initial"
            :min="detailsWidth.min"
            :max="detailsWidth.max"
            @resize="detailsWidth.set"
          />
          <div
            class="method-detail-scroll flex h-full min-h-0 min-w-0 flex-col overflow-y-auto overflow-x-hidden border-l border-line p-5"
          >
            <MethodDetail
              :card="selectedCard"
              :label="label"
              :why="why"
              :learned="learned.includes(selectedCard.id)"
              :studying="studying.includes(selectedCard.id) && !learned.includes(selectedCard.id)"
              :launching="launching"
              :progress-busy="learning.progressBusy.value"
              :pending-launch="pendingLaunch?.method === selectedCard.id"
              @pick="pick"
              @learn="beginStudy"
              @mark="markLearned"
              @close="panelOpen = false"
            />
          </div>
        </div>
      </Transition>
    </section>
  </main>
</template>

<style scoped>
.learning-toolbar {
  position: relative;
  z-index: 31;
  display: grid;
  grid-template-columns: auto minmax(120px, 1fr) auto;
  align-items: center;
  gap: 12px;
  flex: 0 0 auto;
  min-height: 64px;
  padding: 10px 24px;
  border-bottom: 1px solid var(--dsw-alias-border-l1);
  background: color-mix(in srgb, var(--dsw-alias-bg-layer-1) 88%, transparent);
  backdrop-filter: blur(14px);
}
.learning-title {
  margin: 0;
  flex: none;
  font-size: var(--dsw-text-lg);
  font-weight: 600;
  letter-spacing: -0.3px;
}
.toolbar-meta {
  flex: none;
  margin-left: 2px;
  padding: 3px 9px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 999px;
  background: color-mix(in srgb, var(--dsw-alias-bg-layer-1) 72%, transparent);
  color: var(--dsw-alias-text-tertiary);
  font-size: 10px;
  letter-spacing: 0.01em;
  line-height: 1.5;
  white-space: nowrap;
}
.toolbar-heading {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.toolbar-search {
  width: 100%;
  min-width: 0;
  max-width: 500px;
  justify-self: center;
}
.overview-back {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: none;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.overview-home {
  flex: none;
  padding: 4px 8px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 7px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.overview-home:hover {
  border-color: var(--dsw-focus-ring);
  color: var(--dsw-alias-text-primary);
}
.relation-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.relation-option {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 6px 9px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  font-size: var(--dsw-text-sm);
  white-space: nowrap;
  cursor: pointer;
}
.relation-option[aria-pressed='true'] {
  border-color: var(--dsw-selection-border);
  background: var(--dsw-selection-surface);
  color: var(--dsw-alias-text-primary);
}
.relation-option:hover,
.overview-back:hover {
  background: var(--dsw-specific-input-major);
  color: var(--dsw-alias-text-primary);
}
.relation-option:focus-visible,
.overview-back:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  outline-offset: 3px;
}
.relation-sample {
  flex: none;
  fill: none;
  stroke: #4f7cff;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.relation-sample.suggest {
  stroke: #94a3b8;
}
.relation-sample.alternative {
  stroke: #d97706;
}
.relation-option[aria-pressed='false'] .relation-sample {
  opacity: 0.45;
}
@media (max-width: 1100px) {
  .learning-toolbar {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px 12px;
    padding: 10px 14px;
  }
  .toolbar-search {
    grid-column: 1 / -1;
    grid-row: 2;
    max-width: none;
  }
  .relation-toggles {
    grid-column: 1 / -1;
    grid-row: 3;
  }
}
@media (max-width: 700px) {
  .toolbar-meta {
    display: none;
  }
}
@media (max-width: 420px) {
  .learning-title {
    font-size: var(--dsw-text-base);
  }
  .relation-option {
    padding-inline: 6px;
  }
  .relation-sample {
    width: 24px;
  }
}
.method-detail-scroll {
  background: radial-gradient(680px 320px at 100% 0%, #f0f6ff 0%, transparent 58%), #fbfcff;
  padding: 20px 20px 28px;
}
.method-detail-panel.is-narrow {
  position: absolute;
  inset: 0 0 0 auto;
  z-index: 20;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: -6px 0 20px rgb(0 0 0 / 0.12);
}
</style>
