<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import StudyCanvas from '@/components/StudyCanvas.vue';
import StudyInspector from '@/components/StudyInspector.vue';
import ConfirmDialog from '@/components/ConfirmDialog.vue';
import UiIcon from '@/components/UiIcon.vue';
import ModelAccessAction from '@/components/ModelAccessAction.vue';
import { useStudy, type StudyIntent } from '@/composables/useStudy';
import { useLab } from '@/composables/useLab';
import { useElementWidth } from '@/composables/useElementWidth';
import { opacityTransition } from '@/utils/opacity-transition';
import type { StudyEdge, StudySide } from '@/services/study';

const study = useStudy(),
  lab = useLab(),
  router = useRouter();
const workspaceRoot = ref<HTMLElement | null>(null),
  toolsOpen = ref(false);
const availableWidth = useElementWidth(workspaceRoot);
const narrowInspector = computed(() => availableWidth.value < 900);
const compactTools = computed(() => availableWidth.value < 1100);
function inspectSelection() {
  if (!narrowInspector.value) inspectorOpen.value = true;
}
function closeTools(event: MouseEvent) {
  if (compactTools.value && event.target instanceof Element && event.target.closest('button'))
    toolsOpen.value = false;
}
const canvas = ref<InstanceType<typeof StudyCanvas> | null>(null);
const selected = ref<string[]>([]),
  inspectorOpen = ref(false),
  search = ref('');
const inspectorPresent = ref(false),
  inspectorFade = opacityTransition(180, 120),
  contentFade = opacityTransition(120, 80);
watch(inspectorOpen, (open) => {
  if (open) inspectorPresent.value = true;
});
function inspectorLeft() {
  if (!inspectorOpen.value) inspectorPresent.value = false;
}
const route = useRoute();
watch(
  [() => route.query.card, () => study.graph.value?.graph_revision],
  async ([id]) => {
    if (typeof id !== 'string' || !study.graph.value?.cards.some((card) => card.card_id === id))
      return;
    await nextTick();
    canvas.value?.select([id]);
    inspectorOpen.value = true;
  },
  { immediate: true },
);
const notice = ref(''),
  adding = ref(false);
const newTitle = computed({
  get: () => study.newCardDraft.value.title,
  set: (value) => {
    study.newCardDraft.value.title = value;
  },
});
const newSummary = computed({
  get: () => study.newCardDraft.value.summary,
  set: (value) => {
    study.newCardDraft.value.summary = value;
  },
});
const pendingDelete = ref<string[] | null>(null);
const value = computed(() => study.view.value!);
const visibleNodes = computed(() => {
  const query = search.value.trim().toLocaleLowerCase();
  return value.value.nodes.filter((node) => {
    const card = value.value.cards.find((card) => card.card_id === node.card_id);
    return (
      card &&
      (!query || `${card.title} ${card.summary} ${card.body}`.toLocaleLowerCase().includes(query))
    );
  });
});
const selectedCard = computed(() =>
  selected.value.length === 1
    ? (value.value.cards.find((card) => card.card_id === selected.value[0]) ?? null)
    : null,
);
const selectedDraft = computed(() =>
  selectedCard.value ? study.draft(selectedCard.value.card_id) : null,
);
const library = computed(() =>
  value.value.cards.filter(
    (card) => !value.value.nodes.some((node) => node.card_id === card.card_id),
  ),
);
const head = computed(() => study.queue.value[0]);
const workspaceNotice = computed(() => notice.value || study.error.value || study.feedback.value);
const graphNotice = computed(() =>
  [...new Set(value.value.warnings?.map((warning) => warning.message) ?? [])].join(' '),
);
const historyBusy = computed(
  () =>
    study.queue.value.length > 0 ||
    Object.values(study.drafts.value).some((draft) => draft.dirty) ||
    !!newTitle.value ||
    !!newSummary.value,
);
function submit(intent: StudyIntent) {
  notice.value = '';
  return study.submit(intent);
}
function history(direction: 'undo' | 'redo') {
  const entry = value.value.history?.[direction];
  if (!entry || historyBusy.value) return;
  canvas.value?.cancel();
  void submit({ kind: 'history', direction, revisionId: entry.revision_id });
}
function shortcut(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    if (narrowInspector.value) inspectorOpen.value = false;
    toolsOpen.value = false;
  }
  if (
    !(event.ctrlKey || event.metaKey) ||
    event.altKey ||
    !(event.target instanceof Element) ||
    event.target.closest('input,textarea,select,[contenteditable="true"]') ||
    !event.target.closest('.study-canvas')
  )
    return;
  const key = event.key.toLowerCase();
  if (key === 'z' || key === 'y') {
    event.preventDefault();
    history(key === 'y' || event.shiftKey ? 'redo' : 'undo');
  }
}
function connect(fromId: string, toId: string, sourceSide: StudySide, targetSide: StudySide) {
  const samePair = (a: string, b: string) => a === fromId && b === toId;
  if (
    value.value.edges.some(
      (edge) => edge.type === 'suggested_next' && samePair(edge.from_id, edge.to_id),
    ) ||
    study.queue.value.some(
      (entry) =>
        entry.intent.kind === 'create-edge' && samePair(entry.intent.fromId, entry.intent.toId),
    )
  ) {
    notice.value = '这条方向相同的连线已存在。';
    return;
  }
  void submit({ kind: 'create-edge', fromId, toId, sourceSide, targetSide });
}
function deleteEdge(edge: StudyEdge) {
  if (study.paused.value) return;
  const { revision, from_id, to_id, type, why } = edge;
  void submit({
    kind: 'delete-edge',
    edgeId: edge.edge_id,
    basis: { revision, from_id, to_id, type, why },
  });
}
function move(
  positions: Record<string, { x: number; y: number }>,
  basis: Record<string, { x: number; y: number }>,
) {
  void submit({ kind: 'move', positions, basis });
}
async function createCard() {
  if (!newTitle.value.trim()) {
    notice.value = '请填写新卡片标题。';
    return;
  }
  const center = canvas.value?.world(
    (canvas.value.container?.getBoundingClientRect().left ?? 0) +
      (canvas.value.container?.clientWidth ?? 800) / 2,
    (canvas.value.container?.getBoundingClientRect().top ?? 0) +
      (canvas.value.container?.clientHeight ?? 600) / 2,
  ) ?? { x: 40, y: 40 };
  const operation = submit({
    kind: 'create',
    title: newTitle.value.trim(),
    summary: newSummary.value,
    x: Math.max(-20000, Math.min(20000, center.x - 120)),
    y: Math.max(-20000, Math.min(20000, center.y - 64)),
  });
  adding.value = false;
  newTitle.value = '';
  newSummary.value = '';
  const result = await operation;
  if (result?.id_map.new_card) {
    await nextTick();
    canvas.value?.select([result.id_map.new_card]);
  }
}
function edit(field: 'title' | 'summary' | 'body' | 'levelPin', text: string) {
  if (selectedCard.value) study.editDraft(selectedCard.value.card_id, field, text);
}
function saveLevel(cardId: string, text: string) {
  study.editDraft(cardId, 'levelPin', text);
  void study.saveDraft(cardId);
}
function deleteCards(ids = selected.value) {
  if (!study.paused.value && ids.length) pendingDelete.value = [...ids];
}
const hasBoundDelete = computed(() =>
  (pendingDelete.value ?? []).some((id) => {
    const binding = value.value.cards.find((c) => c.card_id === id)?.binding;
    return binding && !binding.session_missing;
  }),
);
async function confirmDelete(syncSessions = false) {
  const ids = pendingDelete.value;
  pendingDelete.value = null;
  if (ids?.length) {
    await submit({ kind: 'delete', cardIds: ids, syncSessions });
    await lab.refreshSessions();
  }
}
async function openSession(id: string) {
  await lab.openSession(id);
  void router.push('/');
}
function source(cardId: string) {
  const binding = value.value.cards.find((card) => card.card_id === cardId)?.binding;
  if (binding && !binding.session_missing) {
    void openSession(binding.session_id);
    return;
  }
  const sources = value.value.sources.filter((source) => source.card_id === cardId);
  if (sources.length === 1 && sources[0]?.session_id && sources[0].availability === 'available') {
    if (sources[0].event_refs.length)
      void router.push({ path: '/', query: { source: sources[0].source_id } });
    else void openSession(sources[0].session_id);
  } else canvas.value?.select([cardId]);
}
function learn(cardId: string) {
  const card = value.value.cards.find((card) => card.card_id === cardId);
  if (!card) return;
  if (card.binding && !card.binding.session_missing) {
    void openSession(card.binding.session_id);
    return;
  }
  lab.newSession();
  lab.setDraft(
    `请带我学「${card.title}」，先说明适用前提，再使用合适的数据运行实验。${card.summary ? `参考学习目标：${card.summary}` : ''}`,
  );
  void router.push('/');
}
</script>

<template>
  <main
    ref="workspaceRoot"
    class="study-workspace"
    :class="{ 'compact-tools': compactTools, 'narrow-inspector': narrowInspector }"
    data-view="route"
    data-role="study-workspace"
    @keydown="shortcut"
  >
    <header class="workspace-bar">
      <h1>学习路线</h1
      ><span class="counts">卡片 {{ value.nodes.length }} · 关系 {{ value.edges.length }}</span>
      <button
        type="button"
        class="ui-button ui-button-primary"
        data-action="study-add-card"
        :disabled="study.paused.value"
        @click="adding = !adding"
        >添加卡片</button
      >
      <div class="workspace-more" :class="{ 'is-open': toolsOpen }">
        <button
          type="button"
          class="ui-button ui-button-ghost more-trigger"
          data-action="study-more"
          :aria-expanded="toolsOpen"
          aria-controls="study-secondary-tools"
          aria-label="更多路线操作"
          @click="toolsOpen = !toolsOpen"
          ><UiIcon name="more" /><span>更多</span></button
        >
        <div id="study-secondary-tools" class="workspace-secondary" @click="closeTools">
          <ModelAccessAction
            v-if="lab.providerLoading.value || lab.providerLoadError.value"
            prefix="study-model"
            class="ui-button ui-button-ghost"
          />
          <span v-if="value.capabilities.history" class="history-pill">
            <button
              type="button"
              data-action="study-undo"
              aria-label="向后撤回"
              :disabled="historyBusy || !value.history?.undo"
              :title="
                value.history?.undo
                  ? `向后撤回：${value.history.undo.label}（Ctrl / ⌘ Z）`
                  : '向后撤回：暂无可撤回动作'
              "
              @click="history('undo')"
              ><UiIcon name="undo"
            /></button>
            <button
              type="button"
              data-action="study-redo"
              aria-label="向前撤回"
              :disabled="historyBusy || !value.history?.redo"
              :title="
                value.history?.redo
                  ? `向前撤回：${value.history.redo.label}（Ctrl / ⌘ Shift Z）`
                  : '向前撤回：暂无可重做动作'
              "
              @click="history('redo')"
              ><UiIcon name="redo"
            /></button>
          </span>
          <details v-if="library.length" class="bar-menu"
            ><summary class="ui-button ui-button-ghost">卡片库 · {{ library.length }}</summary
            ><div class="bar-menu-options">
              <button
                v-for="card in library"
                :key="card.card_id"
                type="button"
                :disabled="study.paused.value"
                @click="submit({ kind: 'add', cardIds: [card.card_id] })"
                >重新加入：{{ card.title }}</button
              >
            </div></details
          >
          <span class="bar-search"
            ><input
              v-model="search"
              type="search"
              placeholder="搜索卡片"
              aria-label="搜索学习卡片"
              data-role="study-search"
          /></span> </div
      ></div>
      <span v-if="selected.length" class="muted">已选 {{ selected.length }} 张</span>
      <output
        class="save-status"
        :class="{ 'is-saved': study.status.value === '已保存' }"
        data-role="study-save-status"
        :title="head?.progress?.last_action || study.feedback.value"
        aria-live="polite"
        >{{ study.status.value }}</output
      >
      <span class="bar-divider"></span>
      <button
        type="button"
        class="ui-button ui-button-ghost bar-icon-button"
        :aria-expanded="inspectorOpen"
        aria-label="展开或收起右栏"
        :title="inspectorOpen ? '收起右栏' : '展开右栏'"
        data-action="study-toggle-inspector"
        @click="inspectorOpen = !inspectorOpen"
        ><UiIcon name="panel-right"
      /></button>
    </header>

    <form v-if="adding" class="new-card-form" @submit.prevent="createCard">
      <input
        v-model="newTitle"
        maxlength="60"
        placeholder="卡片标题"
        aria-label="新卡片标题"
        data-role="study-new-title"
      />
      <input
        v-model="newSummary"
        maxlength="200"
        placeholder="小结（可选）"
        aria-label="新卡片小结"
      />
      <button type="submit" class="ui-button ui-button-primary" data-action="study-create-card"
        >创建</button
      >
      <button type="button" class="ui-button ui-button-ghost" @click="adding = false">取消</button>
    </form>
    <div v-if="workspaceNotice || graphNotice" class="workspace-notice" role="status">{{
      [workspaceNotice, graphNotice].filter(Boolean).join(' ')
    }}</div>
    <section
      v-if="head && study.paused.value"
      class="save-recovery"
      data-role="study-recovery"
      aria-live="polite"
    >
      <p>{{ head.error || study.status.value }}</p>
      <div class="recovery-actions">
        <button
          v-if="
            head.status !== 'conflict' &&
            (head.status !== 'committed' || (head.readAttempts ?? 0) >= 4)
          "
          type="button"
          class="ui-button ui-button-primary"
          data-action="study-retry"
          @click="study.retry()"
          >{{
            head.status === 'unknown'
              ? '确认保存结果'
              : head.status === 'committed'
                ? '重新同步'
                : '重试保存'
          }}</button
        >
      </div>
    </section>
    <section v-if="study.syncError.value && !head" class="save-recovery" aria-live="polite"
      ><p>{{ study.syncError.value }}</p
      ><button
        type="button"
        class="ui-button ui-button-ghost"
        :disabled="study.syncing.value"
        @click="study.retry()"
        >重新同步</button
      ></section
    >
    <section
      class="workspace-body"
      :class="{ 'has-inspector': inspectorPresent && !narrowInspector }"
    >
      <StudyCanvas
        ref="canvas"
        :cards="value.cards"
        :nodes="visibleNodes"
        :sources="value.sources"
        :edges="value.edges"
        :routes="value.edge_routes"
        :paused="study.paused.value"
        @move="move"
        @connect="connect"
        @delete-edge="deleteEdge"
        @selection="selected = $event"
        @inspect="inspectSelection"
        @source="source"
        @learn="learn"
        @delete="deleteCards([$event])"
        @level="saveLevel"
        @notice="notice = $event"
      />
      <button
        v-if="narrowInspector && inspectorOpen"
        type="button"
        class="inspector-backdrop"
        aria-label="返回学习路线画布"
        @click="inspectorOpen = false"
      />
      <Transition
        :css="false"
        @enter="inspectorFade.enter"
        @leave="inspectorFade.leave"
        @after-leave="inspectorLeft"
      >
        <div v-if="inspectorOpen" class="study-inspector-panel" data-role="study-inspector-panel">
          <Transition
            :css="false"
            mode="out-in"
            @enter="contentFade.enter"
            @leave="contentFade.leave"
          >
            <StudyInspector
              :key="selectedCard?.card_id ?? `selection-${selected.length}`"
              :card="selectedCard"
              :draft="selectedDraft"
              :selected-count="selected.length"
              :paused="study.paused.value"
              :saving="study.saving.value"
              @edit="edit"
              @save="selectedCard && study.saveDraft(selectedCard.card_id)"
              @close="inspectorOpen = false"
              @remove="submit({ kind: 'remove', cardIds: selected })"
              @delete="deleteCards()"
            />
          </Transition>
        </div>
      </Transition>
    </section>
    <ConfirmDialog
      :open="!!pendingDelete"
      title="删除学习卡片"
      :message="
        hasBoundDelete
          ? '是否同步删除对应的会话？仅删除卡片时会保留会话，并标记关联已缺失。'
          : `删除选中的 ${pendingDelete?.length ?? 0} 张卡片及其关系？`
      "
      :confirm="hasBoundDelete ? '同步删除' : '删除卡片'"
      :secondary="hasBoundDelete ? '仅删除卡片' : undefined"
      @confirm="confirmDelete(hasBoundDelete)"
      @secondary="confirmDelete(false)"
      @cancel="pendingDelete = null"
    />
  </main>
</template>

<style scoped>
.workspace-more {
  display: contents;
}
.workspace-more > .more-trigger {
  display: none;
}
.workspace-secondary {
  display: contents;
}
.workspace-body {
  position: relative;
}
.compact-tools .workspace-bar {
  position: relative;
  flex-wrap: nowrap;
  padding: 8px 12px;
  gap: 6px;
}
.compact-tools .counts,
.compact-tools .workspace-bar > .bar-divider,
.compact-tools .workspace-bar > .muted {
  display: none;
}
.compact-tools .workspace-bar > h1 {
  margin-right: auto;
}
.compact-tools .workspace-more {
  position: static;
  display: block;
}
.compact-tools .workspace-more > .more-trigger {
  display: flex;
  gap: 4px;
}
.compact-tools .workspace-more > .more-trigger .ui-icon {
  width: 16px;
  height: 16px;
}
.compact-tools .workspace-secondary {
  position: absolute;
  right: 12px;
  top: calc(100% + 4px);
  z-index: 25;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  box-sizing: border-box;
  width: min(320px, calc(100% - 24px));
  padding: 12px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: var(--dsw-elevation-panel);
}
.compact-tools .workspace-more:not(.is-open) > .workspace-secondary {
  display: none;
}
.compact-tools .bar-search,
.compact-tools .bar-search input {
  width: 100%;
  max-width: none;
}
.compact-tools .save-status {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.narrow-inspector .study-inspector-panel {
  position: absolute;
  inset: 0 0 0 auto;
  width: min(360px, 100%);
  z-index: 20;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: -6px 0 24px rgb(0 0 0 / 0.12);
}
.inspector-backdrop {
  position: absolute;
  inset: 0;
  z-index: 19;
  border: 0;
  background: rgb(0 0 0 / 0.15);
}
@media (max-width: 480px) {
  .compact-tools .workspace-bar {
    flex-wrap: wrap;
  }
  .compact-tools .workspace-bar > .save-status {
    order: 5;
    flex-basis: 100%;
    max-width: 100%;
    height: 16px;
    font-size: var(--dsw-text-xs);
  }
  .compact-tools .workspace-bar > .ui-button,
  .compact-tools .workspace-more > .more-trigger {
    padding-inline: 7px;
  }
}
.study-workspace {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  background: var(--dsw-alias-bg-layer-1);
}
.workspace-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 11px 20px;
  border-bottom: 1px solid var(--dsw-alias-border-l2);
}
h1 {
  margin: 0;
  font-size: var(--dsw-text-title);
  font-weight: 600;
  white-space: nowrap;
}
.counts,
.muted {
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
  white-space: nowrap;
}
.bar-divider {
  flex: none;
  width: 1px;
  height: 20px;
  margin: 0 4px;
  background: var(--dsw-alias-border-l2);
}
.bar-search {
  display: flex;
  margin-left: auto;
}
.bar-search input {
  box-sizing: border-box;
  width: 200px;
  max-width: 34vw;
  padding: 6px 9px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  color: var(--dsw-alias-text-primary);
  background: var(--dsw-alias-bg-layer-1);
  font: inherit;
  font-size: var(--dsw-text-sm);
}
.new-card-form input {
  box-sizing: border-box;
  padding: 6px 9px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  color: var(--dsw-alias-text-primary);
  background: var(--dsw-alias-bg-layer-1);
  font: inherit;
  font-size: var(--dsw-text-sm);
}
.history-pill {
  display: inline-flex;
  align-items: center;
  overflow: hidden;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: var(--dsw-radius-md, 8px);
}
.history-pill > button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 30px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-text-primary);
  cursor: pointer;
}
.history-pill > button + button {
  border-left: 1px solid var(--dsw-alias-border-l2);
}
.history-pill > button:hover:not(:disabled) {
  background: var(--dsw-specific-input-major);
}
.history-pill > button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.history-pill :deep(.ui-icon) {
  width: 18px;
  height: 18px;
}
.bar-icon-button {
  width: 34px;
  padding: 0;
}
.save-status {
  display: inline-flex;
  align-items: center;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
  white-space: nowrap;
}
.save-status::before {
  content: '';
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.45;
}
.save-status.is-saved::before {
  background: rgb(52, 168, 110);
  opacity: 1;
}
.bar-menu {
  position: relative;
}
.bar-menu summary {
  list-style: none;
  cursor: pointer;
}
.bar-menu summary::-webkit-details-marker {
  display: none;
}
.bar-menu-options {
  position: absolute;
  top: calc(100% + 5px);
  left: 0;
  display: flex;
  flex-direction: column;
  min-width: 170px;
  max-height: 360px;
  overflow: auto;
  padding: 6px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: 0 8px 20px rgb(0 0 0 / 0.1);
  z-index: 20;
}
.bar-menu-options button {
  border: 0;
  background: transparent;
  padding: 7px 9px;
  text-align: left;
  font: inherit;
  font-size: var(--dsw-text-sm);
  cursor: pointer;
  color: var(--dsw-alias-text-primary);
}
.bar-menu-options button:hover {
  background: var(--dsw-alias-bg-layer-2);
}
.bar-menu-options button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.workspace-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  min-width: 0;
}
.workspace-body.has-inspector {
  grid-template-columns: minmax(0, 1fr) min(320px, 44%);
}
.study-inspector-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.study-inspector-panel :deep(.study-inspector) {
  flex: 1;
  min-height: 0;
}
.new-card-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--dsw-alias-border-l2);
}
.new-card-form input {
  flex: 1;
  min-width: 140px;
}
.workspace-notice,
.save-recovery {
  padding: 8px 20px;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
  border-bottom: 1px solid var(--dsw-alias-border-l2);
}
.save-recovery {
  background: var(--dsw-alias-bg-layer-2);
}
.save-recovery p {
  margin: 0 0 8px;
}
.recovery-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
@media (max-width: 720px) {
  .workspace-header {
    padding: 12px;
  }
  .workspace-toolbar {
    padding: 8px 12px;
  }
  .search {
    order: 1;
    max-width: none;
  }
  .workspace-body.has-inspector {
    grid-template-columns: minmax(0, 1fr) min(290px, 58%);
  }
}

/* Editorial study workspace */
.study-workspace {
  background: #ffffff;
}
.workspace-bar {
  min-height: 66px;
  padding: 10px 24px;
  gap: 10px;
  border-bottom: 1px solid #e9eef8;
  background: color-mix(in srgb, #ffffff 80%, transparent);
  backdrop-filter: blur(16px);
}
.workspace-bar h1 {
  color: #13203a;
  font-size: 17px;
  font-weight: 650;
  letter-spacing: -0.02em;
  line-height: 1.25;
}
.workspace-bar h1::before {
  content: 'STUDY ROUTE';
  display: block;
  margin-bottom: 2px;
  color: #7f8da5;
  font-size: 8.5px;
  font-weight: 600;
  letter-spacing: 0.18em;
  line-height: 1.3;
}
.counts {
  padding: 4px 9px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f8faff;
  color: #7b879c;
  font-size: 10px;
  line-height: 1.5;
}
.workspace-bar > .ui-button-primary {
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid #d7e3fb;
  background: #eef3ff;
  color: #274a9a;
  font-size: 11.5px;
  font-weight: 600;
  box-shadow: none;
}
.workspace-bar > .ui-button-primary:hover {
  background: #e1ebff;
}
.workspace-bar .ui-button-ghost {
  height: 34px;
  border: 1px solid #e5ebf5;
  border-radius: 9px;
  background: #ffffff;
  color: #4f5d73;
  font-size: 11px;
}
.workspace-bar .ui-button-ghost:hover {
  border-color: #c9d9f8;
  background: #f7faff;
  color: #14213a;
}
.history-pill {
  height: 34px;
  border-color: #e5ebf5;
  border-radius: 9px;
  background: #ffffff;
}
.history-pill > button {
  width: 32px;
  height: 32px;
  color: #4f5d73;
}
.history-pill > button + button {
  border-left-color: #edf1f8;
}
.history-pill > button:hover:not(:disabled) {
  background: #eef3fb;
}
.bar-search {
  margin-left: auto;
}
.bar-search input {
  width: 230px;
  max-width: 32vw;
  padding: 8px 11px;
  border: 1px solid #e5ebf5;
  border-radius: 9px;
  background: #ffffff;
  color: #14213a;
  font-size: 11.5px;
  box-shadow: 0 1px 2px rgb(20 40 80 / 0.03);
}
.bar-search input:focus {
  border-color: #9db5ee;
  box-shadow: 0 0 0 3px rgb(79 124 255 / 0.09);
  outline: none;
}
.save-status {
  padding: 4px 9px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f8faff;
  color: #7b879c;
  font-size: 10px;
  line-height: 1.5;
}
.save-status::before {
  width: 5px;
  height: 5px;
  margin-right: 5px;
  opacity: 0.5;
}
.save-status.is-saved {
  border-color: #d5eee4;
  background: #f2fbf7;
  color: #247653;
}
.save-status.is-saved::before {
  background: #22a06b;
}
.bar-divider {
  background: #e9eef8;
}
.bar-icon-button {
  height: 34px;
  border: 1px solid #e5ebf5;
  border-radius: 9px;
  background: #ffffff;
  color: #4f5d73;
}
.bar-icon-button:hover {
  border-color: #c9d9f8;
  background: #f7faff;
}
.new-card-form {
  padding: 12px 24px;
  border-bottom: 1px solid #e9eef8;
  background: #fbfcff;
}
.new-card-form input {
  padding: 8px 11px;
  border: 1px solid #e5ebf5;
  border-radius: 8px;
  background: #ffffff;
  font-size: 11.5px;
}
.workspace-notice,
.save-recovery {
  border-bottom-color: #e9eef8;
  background: #fbfcff;
  color: #647086;
  font-size: 11.5px;
}
@media (max-width: 1100px) {
  .workspace-bar h1::before {
    display: none;
  }
  .workspace-bar {
    min-height: 58px;
    padding: 9px 12px;
  }
}

@media (max-width: 480px) {
  .study-workspace.compact-tools .workspace-bar > .save-status {
    order: 5;
    flex: 0 0 8px;
    width: 8px;
    min-width: 8px;
    max-width: 8px;
    height: 8px;
    margin-left: auto;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: currentColor;
    font-size: 0;
    line-height: 0;
    overflow: hidden;
  }
  .study-workspace.compact-tools .workspace-bar > .save-status::before {
    display: none;
  }
}
</style>
