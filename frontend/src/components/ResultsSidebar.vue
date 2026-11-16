<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import ParameterPanel from '@/components/ParameterPanel.vue';
import DatasetPicker from '@/components/DatasetPicker.vue';
import ExperimentOutcome from '@/components/ExperimentOutcome.vue';
import PanelResizeHandle from '@/components/PanelResizeHandle.vue';
import UiIcon from '@/components/UiIcon.vue';
import CopyRegion from '@/components/CopyRegion.vue';
import SessionCardsPanel from '@/components/SessionCardsPanel.vue';
import SelfCheckPanel from '@/components/SelfCheckPanel.vue';
import { vDisclosureMotion } from '@/utils/disclosure-motion';
import { usePanelWidth } from '@/composables/usePanelWidth';
import { useLab } from '@/composables/useLab';
import type { ResultBlock } from '@/composables/lab/experiments';
import {
  fetchCatalog,
  methodSpec,
  methodContext,
  resultSource,
  sourceColumns,
  sourceLabel as sourceName,
} from '@/services/experiments';
import { figureSrc } from '@/utils/figure-url';
import {
  experimentName,
  experimentRows,
  mergeExperiment,
  requestedMethods,
} from '@/utils/result-summary';
import type { Catalog, ExperimentResult } from '@/types';

const lab = useLab();
type SidebarSection = 'results' | 'datasets' | 'study' | 'self-check';
const props = withDefaults(defineProps<{ section?: SidebarSection; overlay?: boolean }>(), {
  section: 'results',
});
const resultsWidth = usePanelWidth('results');
const emit = defineEmits<{
  (event: 'zoom', url: string, name: string): void;
  (event: 'update:section', section: SidebarSection): void;
}>();

const catalog = ref<Catalog | null>(null);
const catalogError = ref('');

const blocks = computed(() => lab.blocks.value);
const open = computed(() => lab.panelOpen.value);
const body = ref<HTMLElement | null>(null);
let sectionAnimation: Animation | undefined,
  sectionSequence = 0;
onBeforeUnmount(() => {
  sectionSequence++;
  sectionAnimation?.cancel();
});
const datasetReady = ref(props.section === 'datasets');
const studyReady = ref(props.section === 'study');
const selfCheckReady = ref(props.section === 'self-check');
const scrollPositions = { results: 0, datasets: 0, study: 0, 'self-check': 0 };
const scope = computed(() => JSON.stringify([lab.state.user, lab.state.sessionId]));
function activate(section: SidebarSection): void {
  emit('update:section', section);
  lab.openPanel();
}
watch(
  () => props.section,
  async (section, previous) => {
    const ticket = ++sectionSequence;
    sectionAnimation?.cancel();
    if (section === 'datasets') datasetReady.value = true;
    if (section === 'study') studyReady.value = true;
    if (section === 'self-check') selfCheckReady.value = true;
    if (body.value) scrollPositions[previous] = body.value.scrollTop;
    await nextTick();
    if (ticket !== sectionSequence) return;
    if (body.value) body.value.scrollTop = scrollPositions[section];
    const pane = body.value?.querySelector<HTMLElement>(`#sidebar-${section}-pane`);
    if (pane?.animate && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      sectionAnimation = pane.animate(
        [
          { opacity: 0.3, transform: 'translateY(5px)' },
          { opacity: 1, transform: 'none' },
        ],
        { duration: 180, easing: 'cubic-bezier(.22,1,.36,1)' },
      );
      void sectionAnimation.finished.catch(() => {});
    }
  },
);
watch(scope, () => {
  sectionSequence++;
  sectionAnimation?.cancel();
  datasetReady.value = props.section === 'datasets';
  studyReady.value = props.section === 'study';
  selfCheckReady.value = props.section === 'self-check';
  scrollPositions.results = 0;
  scrollPositions.datasets = 0;
  scrollPositions.study = 0;
  scrollPositions['self-check'] = 0;
  if (body.value) body.value.scrollTop = 0;
});

const selected = computed(() => {
  const key = lab.selectedKey.value;
  return blocks.value.find((item) => item.key === key) ?? blocks.value.at(-1) ?? null;
});

const labels = computed(() =>
  Object.fromEntries(
    [...(catalog.value?.library ?? []), ...(catalog.value?.methods ?? [])].map((method) => [
      method.id,
      method.title,
    ]),
  ),
);
const requested = computed(() => requestedMethods(selected.value?.tool?.arguments));
const outcomes = computed(() =>
  selected.value
    ? experimentRows(selected.value.result, requested.value, (id) => labels.value[id])
    : [],
);
const adjustable = computed(() =>
  outcomes.value.filter((row) => methodSpec(catalog.value, row.id)),
);
const chosenMethod = ref('');
watch(
  () => [selected.value?.key, adjustable.value.map((row) => row.id).join('|')] as const,
  ([key], previous) => {
    if (key !== previous?.[0] || !adjustable.value.some((row) => row.id === chosenMethod.value))
      chosenMethod.value = adjustable.value[0]?.id ?? '';
  },
  { immediate: true },
);
const resultNote = computed(() => (selected.value ? blockName(selected.value) : '实验结果'));

function blockName(block: ResultBlock): string {
  return experimentName(
    block.result,
    requestedMethods(block.tool?.arguments),
    (id) => labels.value[id],
  );
}

function blockTitle(block: ResultBlock): string {
  return `${block.panel} ${blockName(block)}`;
}

const selectedMethodId = computed(() => {
  return chosenMethod.value || null;
});

const selectedMethod = computed(() => methodSpec(catalog.value, selectedMethodId.value));
const selectedResult = computed(() =>
  selected.value ? methodContext(selected.value.result, selectedMethodId.value) : null,
);
const selectedSource = computed(() => resultSource(selectedResult.value));
const selectedTarget = computed(() => columnName(selectedResult.value?.data?.target));
const selectedGroup = computed(() => columnName(selectedResult.value?.data?.group));
const selectedTime = computed(() => columnName(selectedResult.value?.data?.time));
const selectedSourceSpec = computed(
  () => (catalog.value?.sources ?? []).find((item) => item.id === selectedSource.value) ?? null,
);
const selectedColumns = computed(() =>
  sourceColumns(selectedResult.value, selectedSourceSpec.value),
);

onMounted(async () => {
  try {
    catalog.value = await fetchCatalog();
  } catch (error) {
    catalogError.value = (error as Error).message;
  }
});

function columnName(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function figureList(block: ResultBlock): Array<{ name: string; url: string }> {
  return (block.result.figures ?? [])
    .filter((figure) => Boolean(figure.url))
    .map((figure) => ({ name: figure.name, url: figureSrc(figure.name, figure.url) }));
}

function applyResult(block: ResultBlock, result: ExperimentResult): void {
  if (result.experiment_id) {
    lab.acceptExperimentResult(result);
    lab.setStatus(`已保存重跑结果：版本 ${result.experiment_version}。`);
    return;
  }
  const merged = mergeExperiment(block.result, result, selectedMethodId.value ?? undefined);
  if (block.kind === 'experiment') block.turn.result = merged;
  else if (block.tool) block.tool.result = merged;
  lab.indexBlocks();
  void lab.persist();
  lab.setStatus(
    result.failures?.length
      ? '本次方法未完成，请查看结果摘要中的原因。'
      : `已用面板参数重跑：${selectedMethod.value?.title ?? result.title ?? resultNote.value}。`,
  );
}

function onRan(result: ExperimentResult): void {
  const block = selected.value;
  if (!block) return;
  applyResult(block, result);
}
</script>

<template>
  <aside
    class="results-side relative"
    :class="{ open }"
    data-panel="results"
    :data-section="props.section"
    aria-label="会话右侧栏"
  >
    <Transition name="panel-content">
      <PanelResizeHandle
        v-if="open && !props.overlay"
        edge="left"
        label="右侧栏宽度"
        :width="resultsWidth.width.value"
        :initial="resultsWidth.initial"
        :min="resultsWidth.min"
        :max="resultsWidth.max"
        @resize="resultsWidth.set"
      />
    </Transition>
    <Transition name="panel-content">
      <button
        v-if="!open"
        type="button"
        class="results-entry"
        data-action="expand-results"
        :aria-label="`展开实验结果（${blocks.length} 条）`"
        :title="blocks.length ? `查看本会话的 ${blocks.length} 项实验结果` : '展开实验结果'"
        :aria-expanded="false"
        @click="activate('results')"
      >
        <span class="results-entry-icon" aria-hidden="true">
          <UiIcon name="chart-results" class="h-5 w-5" />
          <span v-if="blocks.length" class="results-entry-count" data-role="results-count">{{
            blocks.length > 99 ? '99+' : blocks.length
          }}</span>
        </span>
        <span class="results-entry-label">结果</span>
      </button>
    </Transition>
    <Transition name="panel-content">
      <button
        v-if="!open"
        type="button"
        class="results-entry dataset-entry"
        data-action="open-datasets"
        aria-label="数据集"
        title="上传和管理数据集"
        @click="activate('datasets')"
      >
        <span class="results-entry-icon"><UiIcon name="table" class="h-5 w-5" /></span>
        <span class="results-entry-label">数据集</span>
      </button>
    </Transition>
    <Transition name="panel-content">
      <button
        v-if="!open"
        type="button"
        class="results-entry study-entry"
        data-action="open-session-cards"
        aria-label="学习卡片"
        title="按会话内容整理学习卡片"
        @click="activate('study')"
      >
        <span class="results-entry-icon"><UiIcon name="book-open" class="h-5 w-5" /></span
        ><span class="results-entry-label">学习卡片</span>
      </button>
    </Transition>
    <Transition name="panel-content">
      <button
        v-if="!open"
        type="button"
        class="results-entry self-check-entry"
        data-action="open-self-check"
        aria-label="学习自测"
        title="检查当前会话已学内容"
        @click="activate('self-check')"
      >
        <span class="results-entry-icon"><UiIcon name="self-check" class="h-5 w-5" /></span
        ><span class="results-entry-label">学习自测</span>
      </button>
    </Transition>
    <Transition name="panel-content">
      <header v-show="open" class="panel-head">
        <nav class="sidebar-tabs" role="tablist" aria-label="右侧栏栏目">
          <button
            id="sidebar-results-tab"
            type="button"
            class="sidebar-tab"
            role="tab"
            aria-controls="sidebar-results-pane"
            :aria-selected="props.section === 'results'"
            data-action="select-results"
            @click="activate('results')"
          >
            <UiIcon name="chart-results" /><span>实验结果</span
            ><span v-if="blocks.length" class="sidebar-tab-count">{{ blocks.length }}</span>
          </button>
          <button
            id="sidebar-datasets-tab"
            type="button"
            class="sidebar-tab"
            role="tab"
            aria-controls="sidebar-datasets-pane"
            :aria-selected="props.section === 'datasets'"
            data-action="open-datasets"
            @click="activate('datasets')"
          >
            <UiIcon name="table" /><span>数据集</span>
          </button>
          <button
            id="sidebar-study-tab"
            type="button"
            class="sidebar-tab"
            role="tab"
            aria-controls="sidebar-study-pane"
            :aria-selected="props.section === 'study'"
            data-action="open-session-cards"
            @click="activate('study')"
          >
            <UiIcon name="book-open" /><span>学习卡片</span>
          </button>
          <button
            id="sidebar-self-check-tab"
            type="button"
            class="sidebar-tab"
            role="tab"
            aria-controls="sidebar-self-check-pane"
            :aria-selected="props.section === 'self-check'"
            data-action="open-self-check"
            @click="activate('self-check')"
          >
            <UiIcon name="self-check" /><span>学习自测</span>
          </button>
        </nav>
        <button
          type="button"
          class="ui-icon-button h-7 w-7 rounded-card hover:bg-field"
          data-action="collapse-results"
          aria-label="收起右侧栏"
          title="收起右侧栏"
          @click="lab.closePanel()"
          ><UiIcon name="chevron-right"
        /></button>
      </header>
    </Transition>
    <Transition name="panel-content">
      <div v-show="open" ref="body" class="panel-body" data-role="results-body">
        <div
          v-show="props.section === 'self-check'"
          id="sidebar-self-check-pane"
          role="tabpanel"
          aria-labelledby="sidebar-self-check-tab"
        >
          <SelfCheckPanel v-if="selfCheckReady" :active="open && props.section === 'self-check'" />
        </div>
        <div
          v-show="props.section === 'study'"
          id="sidebar-study-pane"
          role="tabpanel"
          aria-labelledby="sidebar-study-tab"
        >
          <SessionCardsPanel v-if="studyReady" />
        </div>
        <div
          v-show="props.section === 'results'"
          id="sidebar-results-pane"
          role="tabpanel"
          aria-labelledby="sidebar-results-tab"
        >
          <p v-if="!blocks.length" class="panel-empty" data-role="results-empty">
            还没有实验结果。在左侧提问后，agent 会在服务端运行对应算法，指标与图会展示在这里。
          </p>
          <template v-else>
            <nav
              v-if="blocks.length > 1"
              class="panel-list"
              data-role="block-list"
              aria-label="选择实验结果"
            >
              <div
                v-for="block in blocks"
                :key="block.key"
                class="panel-tab-item"
                :data-panel-entry="block.key"
              >
                <button
                  type="button"
                  class="panel-tab"
                  data-role="panel-choice"
                  :class="{ active: block.key === (selected?.key ?? '') }"
                  :aria-pressed="block.key === selected?.key"
                  :title="blockTitle(block)"
                  :data-block="block.key"
                  @click="lab.selectBlock(block.key)"
                  ><span class="panel-number">{{ block.panel }}</span
                  ><span class="panel-method">{{ blockName(block) }}</span></button
                >
                <button
                  type="button"
                  class="delete-result tab-delete"
                  data-action="delete-result"
                  :aria-label="`删除 ${blockTitle(block)}`"
                  :title="`删除 ${blockTitle(block)}`"
                  @click.stop="lab.removeBlock(block.key)"
                  ><UiIcon name="trash" class="h-3.5 w-3.5"
                /></button>
              </div>
            </nav>
            <article
              v-if="selected"
              class="result-block"
              :data-kind="selected.kind"
              :data-block="selected.key"
            >
              <header class="result-head">
                <h3 data-role="block-title">{{ blockTitle(selected) }}</h3>
                <button
                  type="button"
                  class="delete-result block-delete"
                  data-action="delete-result"
                  :aria-label="`删除 ${blockTitle(selected)}`"
                  :title="`删除 ${blockTitle(selected)}`"
                  @click="lab.removeBlock(selected.key)"
                  ><UiIcon name="trash"
                /></button>
              </header>
              <div
                v-if="selected.experiment"
                class="experiment-version-bar"
                data-role="experiment-version"
              >
                <span class="experiment-id" :title="selected.experiment.id"
                  >ID {{ selected.experiment.id }}</span
                >
                <div class="version-navigation" aria-label="切换实验结果版本">
                  <button
                    type="button"
                    aria-label="上一个实验版本"
                    data-action="previous-version"
                    :disabled="lab.sidebarSaving?.value || selected.experiment.active_version <= 1"
                    @click="lab.switchExperimentVersion(selected.key, -1)"
                    ><UiIcon name="chevron-left"
                  /></button>
                  <span
                    >版本 {{ selected.experiment.active_version }} /
                    {{ selected.experiment.versions.length }}</span
                  >
                  <button
                    type="button"
                    aria-label="下一个实验版本"
                    data-action="next-version"
                    :disabled="
                      lab.sidebarSaving?.value ||
                      selected.experiment.active_version >= selected.experiment.versions.length
                    "
                    @click="lab.switchExperimentVersion(selected.key, 1)"
                    ><UiIcon name="chevron-right"
                  /></button>
                </div>
              </div>
              <ExperimentOutcome
                :result="selected.result"
                :requested="requested"
                :labels="labels"
              />
              <details
                v-if="selectedMethod"
                v-disclosure-motion
                class="parameters-disclosure"
                :open="outcomes.some((row) => row.status === 'error')"
                data-role="parameter-editor"
              >
                <summary class="ui-disclosure"
                  ><UiIcon name="chevron-right" class="h-3 w-3" /><span
                    >调整参数并重跑</span
                  ></summary
                >
                <label v-if="adjustable.length > 1" class="method-picker"
                  >调整方法
                  <select
                    v-model="chosenMethod"
                    data-role="parameter-method"
                    aria-label="选择要调整参数的方法"
                  >
                    <option v-for="row in adjustable" :key="row.id" :value="row.id">{{
                      row.label
                    }}</option>
                  </select>
                </label>
                <ParameterPanel
                  v-if="selectedMethod"
                  :key="`${selected.key}-${selected.result.experiment_version ?? 1}-${selectedMethodId}`"
                  :method="selectedMethod"
                  :result="selectedResult"
                  :source="selectedSource"
                  :source-label="sourceName(catalog, selectedSource)"
                  :session="lab.state.sessionId"
                  :columns="selectedColumns"
                  :target="selectedTarget"
                  :group="selectedGroup"
                  :time="selectedTime"
                  @ran="onRan"
                />
              </details>
              <p v-else-if="catalogError" class="panel-empty" data-role="param-note"
                >参数面板加载失败：{{ catalogError }}</p
              >
              <p v-else-if="catalog" class="panel-empty" data-role="param-note"
                >此结果没有可调整的参数。</p
              >
              <CopyRegion v-if="selected.result.results?.length" kind="table">
                <table class="result-table" data-role="search-table">
                  <thead
                    ><tr><th>方法</th><th>适用条件</th></tr></thead
                  >
                  <tbody>
                    <tr v-for="entry in selected.result.results" :key="entry.id">
                      <td>{{ entry.title }}（{{ entry.id }}）</td>
                      <td>{{ entry.when }}</td>
                    </tr>
                  </tbody>
                </table>
              </CopyRegion>
              <div
                v-if="selected.result.figures?.length"
                class="experiment-figures tool-figures result-figures"
                data-role="block-figures"
              >
                <figure
                  v-for="figure in figureList(selected)"
                  :key="figure.name"
                  class="result-figure"
                >
                  <img
                    :src="figure.url"
                    :alt="figure.name"
                    loading="lazy"
                    data-role="block-figure"
                    @click="emit('zoom', figure.url, figure.name)"
                  />
                  <figcaption>{{ figure.name.replace(/_/g, ' ') }}</figcaption>
                </figure>
              </div>
            </article>
          </template>
        </div>
        <div
          v-show="props.section === 'datasets'"
          id="sidebar-datasets-pane"
          role="tabpanel"
          aria-labelledby="sidebar-datasets-tab"
        >
          <DatasetPicker v-if="datasetReady" :key="scope" />
        </div>
      </div>
    </Transition>
  </aside>
</template>

<style scoped>
.experiment-version-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 12px;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
}
.experiment-id {
  overflow-wrap: anywhere;
  font-family: var(--dsw-font-family-code);
}
.version-navigation {
  display: flex;
  align-items: center;
  gap: 7px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.version-navigation button {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 1px solid var(--dsw-alias-border-l1);
  border-radius: 7px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.version-navigation button:disabled {
  opacity: 0.35;
  cursor: default;
}
.panel-body {
  scrollbar-gutter: stable;
}
.panel-tab-item {
  position: relative;
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
}
.panel-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  min-width: 0;
  max-width: 100%;
  padding: 5px 34px 5px 10px;
  border: 0.5px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  font-size: var(--dsw-text-sm);
  cursor: pointer;
}
.panel-tab:hover {
  background: var(--dsw-alias-bg-skeleton);
  color: var(--dsw-alias-text-primary);
}
.panel-tab.active {
  background: var(--dsw-selection-surface);
  border-color: var(--dsw-alias-brand-primary);
  color: var(--dsw-alias-brand-primary);
}
.panel-tab:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 2px;
}
.panel-number {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.panel-method {
  min-width: 0;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-block {
  position: relative;
}
.result-head {
  padding-right: 34px;
}
.result-head h3 {
  min-width: 0;
  overflow-wrap: anywhere;
}
.delete-result {
  position: absolute;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-tertiary);
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 120ms ease,
    color 120ms ease;
}
.tab-delete {
  top: 4px;
  right: 4px;
}
.block-delete {
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
}
.panel-tab-item:hover > .delete-result,
.panel-tab-item:focus-within > .delete-result,
.result-block:hover > .result-head > .delete-result,
.result-block:focus-within > .result-head > .delete-result {
  opacity: 1;
  pointer-events: auto;
}
.delete-result:hover {
  color: var(--dsw-feedback-error-text);
  background: var(--dsw-alias-bg-skeleton);
}
.delete-result:focus-visible {
  opacity: 1;
  pointer-events: auto;
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 1px;
}
@media (hover: none) {
  .delete-result {
    opacity: 1;
    pointer-events: auto;
  }
}
@media (prefers-reduced-motion: reduce) {
  .delete-result {
    transition: none;
  }
}
.method-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 8px 0;
  font-size: var(--dsw-text-sm);
}
.method-picker select {
  min-width: 0;
  max-width: 70%;
  padding: 5px 8px;
  border: 0.5px solid var(--dsw-alias-border-l2);
  border-radius: 7px;
  background: var(--dsw-alias-bg-layer-1);
  color: inherit;
  font: inherit;
}
.parameters-disclosure {
  margin: 12px 0;
  padding-top: 10px;
  border-top: 0.5px solid var(--dsw-alias-border-l2);
}
.parameters-disclosure[open] > summary {
  margin-bottom: 8px;
}
.results-entry {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  width: 36px;
  max-width: calc(100% - 8px);
  flex-shrink: 0;
  margin: 10px 4px;
  padding: 9px 2px 7px;
  border: 0.5px solid var(--dsw-alias-border-l2);
  border-radius: 9px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
  font: inherit;
}
.results-entry:hover {
  background: var(--dsw-alias-bg-skeleton);
  border-color: var(--dsw-alias-brand-primary);
  color: var(--dsw-alias-brand-primary);
}
.results-entry:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 1px;
}
.results-entry-icon {
  position: relative;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
}
.results-entry-count {
  position: absolute;
  top: -5px;
  right: -4px;
  display: grid;
  place-items: center;
  min-width: 15px;
  height: 15px;
  padding: 0 3px;
  border: 1.5px solid var(--dsw-alias-bg-layer-1);
  border-radius: 9px;
  background: var(--dsw-alias-brand-primary);
  color: var(--dsw-alias-text-inverted);
  font-size: var(--dsw-text-xs);
  line-height: 1;
}
.results-entry-label {
  font-size: var(--dsw-text-xs);
  line-height: 1.2;
}
.dataset-entry {
  top: 76px;
}
.study-entry {
  top: 158px;
}
.self-check-entry {
  top: 240px;
}
.results-side {
  container-type: inline-size;
}
.panel-head {
  gap: 8px;
  padding: 12px 14px;
}
.sidebar-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.panel-head .sidebar-tabs {
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
}
.panel-head > [data-action='collapse-results'] {
  flex: none;
}
.panel-head .sidebar-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-height: 32px;
  padding: 5px 8px;
  border-radius: 7px;
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  font-size: var(--dsw-text-sm);
  white-space: nowrap;
}
.panel-head .sidebar-tab:hover {
  background: var(--dsw-alias-bg-skeleton);
}
.panel-head .sidebar-tab[aria-selected='true'] {
  background: var(--dsw-selection-surface);
  color: var(--dsw-feedback-info-text);
}
.sidebar-tab-count {
  display: grid;
  place-items: center;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-radius: 6px;
  background: var(--dsw-alias-bg-layer-1);
  font-size: var(--dsw-text-xs);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.sidebar-tab:disabled,
.dataset-entry:disabled {
  opacity: 0.45;
  cursor: default;
}
.sidebar-tab:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 1px;
}
@container (max-width:440px) {
  .panel-head {
    gap: 4px;
    padding: 10px 8px;
  }
  .panel-head .sidebar-tabs {
    gap: 2px;
  }
  .panel-head .sidebar-tab {
    gap: 4px;
    padding: 5px 4px;
    font-size: var(--dsw-text-xs);
  }
  .sidebar-tab > svg {
    width: 14px;
    height: 14px;
    flex: none;
  }
  .sidebar-tab-count {
    min-width: 15px;
    height: 15px;
    padding: 0 3px;
    font-size: var(--dsw-text-xs);
  }
}
@container (max-width:340px) {
  .panel-head .sidebar-tabs {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .panel-head .sidebar-tab {
    position: relative;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    min-height: 48px;
    padding: 4px 2px;
  }
  .sidebar-tab-count {
    position: absolute;
    right: 1px;
    top: 1px;
  }
}

/* Right rail chrome */
.results-side {
  border-left: 1px solid #e9eef8;
  background:
    radial-gradient(300px 220px at 50% -10%, #eef4ff 0%, transparent 70%),
    linear-gradient(180deg, #fbfcff 0%, #f6f8fd 100%);
}
.results-entry {
  width: 38px;
  margin: 8px 3px;
  padding: 9px 2px 7px;
  border: 1px solid #e5ebf5;
  border-radius: 11px;
  background: #ffffff;
  color: #647086;
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.04),
    0 10px 22px -24px rgb(20 40 80 / 0.45);
  transition:
    border-color 160ms ease,
    background 160ms ease,
    color 160ms ease,
    box-shadow 160ms ease;
}
.results-entry:hover {
  border-color: #c9d9f8;
  background: #f8fbff;
  color: #315fbd;
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.04),
    0 14px 26px -22px rgb(20 40 80 / 0.42);
}
.results-entry-icon {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: #eef4ff;
  color: #3d63c7;
}
.results-entry-icon svg {
  width: 16px;
  height: 16px;
}
.dataset-entry .results-entry-icon {
  background: #e8f8f1;
  color: #1c7a58;
}
.study-entry .results-entry-icon {
  background: #f3edff;
  color: #6b46c1;
}
.self-check-entry .results-entry-icon {
  background: #fff5e8;
  color: #a35d12;
}
.results-entry-label {
  color: #7b879c;
  font-size: 9px;
  letter-spacing: 0.02em;
}
.results-entry:hover .results-entry-label {
  color: #315fbd;
}
.results-entry-count {
  border-color: #ffffff;
  background: #315fbd;
  font-size: 8px;
}
.dataset-entry {
  top: 78px;
}
.study-entry {
  top: 160px;
}
.self-check-entry {
  top: 242px;
}
.panel-head {
  border-bottom: 1px solid #edf1f8;
  background: rgb(255 255 255 / 0.7);
}
.panel-head .sidebar-tab {
  border-radius: 8px;
  color: #647086;
  font-size: 11px;
}
.panel-head .sidebar-tab[aria-selected='true'] {
  background: #eef4ff;
  color: #315fbd;
}
.sidebar-tab-count {
  border: 1px solid #e2e9f4;
  background: #ffffff;
}
</style>
