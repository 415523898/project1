<script setup lang="ts">
import { computed, ref } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import CopyRegion from '@/components/CopyRegion.vue';
import ExperimentOutcome from '@/components/ExperimentOutcome.vue';
import CollapseTransition from '@/components/CollapseTransition.vue';
import { experimentRows } from '@/utils/result-summary';

import type { ToolTrace } from '@/types';
import { figureSrc } from '@/utils/figure-url';
import { learnerText, learnerValue, learnerToolName } from '@/utils/learner-text';

const props = defineProps<{
  trace: ToolTrace;
  index: number;
}>();

const emit = defineEmits<{ zoom: [url: string, name: string]; viewResult: [trace: ToolTrace] }>();

const open = ref(false);

const TITLES: Record<string, string> = {
  search_ml_methods: '检索方法库',
  inspect_datasets: '查看数据集',
  run_ml_suite: '运行实验',
  view_experiment_image: '查看实验图像',
  read_experiment_figure_data: '读取实验图数据',
};

const title = computed(() => TITLES[props.trace.name] ?? learnerToolName(props.trace.name));

const requested = computed(() =>
  Array.isArray(props.trace.arguments?.methods)
    ? props.trace.arguments.methods.filter((id): id is string => typeof id === 'string')
    : [],
);
const outcomes = computed(() =>
  props.trace.result ? experimentRows(props.trace.result, requested.value) : [],
);
const state = computed(() =>
  props.trace.status === 'running'
    ? 'running'
    : props.trace.status === 'error' ||
        props.trace.result?.error ||
        (outcomes.value.length && outcomes.value.every((row) => row.status === 'error'))
      ? 'error'
      : 'done',
);

const summary = computed(() => {
  const result = props.trace.result;
  if (state.value === 'running') return '进行中…';
  if (state.value === 'error') {
    const failures = result?.failures ?? [];
    return (
      result?.error ||
      failures[0]?.error ||
      outcomes.value.find((row) => row.status === 'error')?.summary ||
      '执行失败'
    );
  }
  if (result) {
    if (props.trace.name === 'inspect_datasets') {
      const inspected = result as Record<string, unknown>;
      return typeof inspected.total === 'number'
        ? `已读取 ${inspected.total} 份可用数据的目录`
        : `${inspected.label || inspected.id || '数据'} · ${inspected.rows ?? '—'} 行 · ${inspected.columns ?? '—'} 列`;
    }
    if (props.trace.name === 'view_experiment_image')
      return '已查看真实图像 · ' + String((result as Record<string, unknown>).figure_name ?? '');
    const parts: string[] = [];
    if (result.dataset_label || result.source)
      parts.push(result.dataset_label ?? result.source ?? '');
    const completed = outcomes.value.filter((row) => row.status === 'success').length;
    const failed = outcomes.value.filter((row) => row.status === 'error').length;
    if (completed) parts.push(`${completed} 个方法完成`);
    if (failed) parts.push(`${failed} 个方法未完成`);
    if (outcomes.value.some((row) => row.status === 'empty')) parts.push('有方法未返回结果');
    if (result.data?.records) parts.push(`${result.data.records} 行`);
    if (result.elapsed_ms) parts.push(`${(result.elapsed_ms / 1000).toFixed(1)}s`);
    if (parts.length) return parts.join(' · ');
  }
  return props.trace.reason || '完成';
});

const payload = computed(() => {
  const args = props.trace.arguments;
  if (!args) return '';
  try {
    return JSON.stringify(learnerValue(args), null, 2);
  } catch {
    return '';
  }
});

const figures = computed(() =>
  (props.trace.result?.figures ?? [])
    .filter((figure) => Boolean(figure.url))
    .map((figure) => ({ name: figure.name, url: figureSrc(figure.name, figure.url) })),
);

// Non-experiment tools return catalogues, search hits or metadata instead of methods/figures.
const resultPayload = computed(() => {
  if (!open.value || outcomes.value.length || figures.value.length || props.trace.result == null)
    return '';
  try {
    return JSON.stringify(learnerValue(props.trace.result), null, 2);
  } catch {
    return '工具结果无法格式化。';
  }
});
</script>

<template>
  <div class="flex flex-col" :data-tool="trace.name" :data-state="state" data-role="tool-row">
    <button
      type="button"
      class="flex h-6 w-full cursor-pointer items-center gap-1.5 rounded-sm border-0 bg-transparent p-0 text-left"
      :aria-expanded="open ? 'true' : 'false'"
      :data-action="open ? 'tool-collapse' : 'tool-expand'"
      @click="open = !open"
    >
      <span
        class="grid h-4 w-4 flex-none place-items-center"
        :class="
          state === 'error'
            ? 'text-[var(--dsw-feedback-error-text)]'
            : state === 'running'
              ? 'text-[var(--dsw-alias-text-tertiary)]'
              : 'text-[var(--dsw-alias-text-secondary)]'
        "
        aria-hidden="true"
      >
        <UiIcon
          :name="state === 'running' ? 'spinner' : state === 'error' ? 'warning' : 'check-circle'"
          class="h-[14px] w-[14px]"
        />
      </span>
      <span
        class="flex-none text-[length:var(--dsw-text-row)] leading-6 text-[var(--dsw-alias-text-primary)]"
        >{{ title }}</span
      >
      <UiIcon name="dot" class="mx-2 h-1 w-1 text-[var(--dsw-alias-text-tertiary)]" />
      <span
        class="min-w-0 flex-1 truncate text-[length:var(--dsw-text-row)] leading-6"
        :class="
          state === 'error'
            ? 'text-[var(--dsw-feedback-error-text)]'
            : 'text-[var(--dsw-alias-text-tertiary)]'
        "
        data-role="tool-summary"
        >{{ learnerText(summary) }}</span
      >
    </button>

    <CollapseTransition>
      <div v-if="open" class="tool-disclosure-window" data-role="tool-body">
        <div class="mb-1 ml-1 flex flex-col">
          <div
            v-if="payload"
            class="my-1 flex flex-col rounded-lg bg-[var(--dsw-specific-tip)]"
            style="border: 0.5px solid var(--dsw-alias-border-l1)"
            data-role="tool-input"
          >
            <div
              class="grid max-h-[150px] grid-cols-[max-content_1fr] items-baseline gap-x-3.5 overflow-y-auto px-4 py-3"
            >
              <span
                class="sticky top-0 self-start text-[length:var(--dsw-text-sm)] leading-[18px] text-[var(--dsw-alias-text-tertiary)]"
                >设置</span
              >
              <span
                class="min-w-0 whitespace-pre-wrap break-words font-mono text-[length:var(--dsw-text-sm)] leading-[18px] text-[var(--dsw-alias-text-secondary)]"
                >{{ payload }}</span
              >
            </div>
          </div>

          <template v-if="trace.name === 'run_ml_suite'">
            <button
              type="button"
              class="view-experiment-result"
              data-action="view-experiment-result"
              :disabled="state === 'running' || !trace.result"
              @click="emit('viewResult', trace)"
              >点击查看详细实验结果<UiIcon name="panel-right"
            /></button>
            <p v-if="state === 'error'" class="tool-result-error" data-role="tool-error">{{
              learnerText(summary)
            }}</p>
          </template>
          <div
            v-else-if="outcomes.length || figures.length || resultPayload"
            class="my-1 flex flex-col rounded-lg bg-[var(--dsw-specific-tip)]"
            style="border: 0.5px solid var(--dsw-alias-border-l1)"
            data-role="tool-output"
          >
            <div
              v-if="resultPayload"
              class="grid max-h-[360px] grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-3.5 overflow-y-auto px-4 py-3"
            >
              <span
                class="sticky top-0 self-start text-[length:var(--dsw-text-sm)] leading-[18px] text-[var(--dsw-alias-text-tertiary)]"
                >结果</span
              >
              <CopyRegion kind="code" :text="resultPayload">
                <pre
                  class="m-0 min-w-0 whitespace-pre-wrap break-words font-mono text-[length:var(--dsw-text-sm)] leading-[18px] text-[var(--dsw-alias-text-secondary)]"
                  data-role="tool-result-json"
                  >{{ resultPayload }}</pre>
              </CopyRegion>
            </div>
            <ExperimentOutcome
              v-if="trace.result && outcomes.length"
              class="px-4 py-3"
              :result="trace.result"
              :requested="requested"
              compact
            />
            <div
              v-if="figures.length"
              class="experiment-figures px-4 py-3"
              :style="outcomes.length ? 'border-top: 0.5px solid var(--dsw-alias-border-l2)' : ''"
              data-role="tool-figures"
            >
              <figure v-for="figure in figures" :key="figure.name" class="cursor-zoom-in">
                <img
                  class="rounded-card"
                  style="border: 0.5px solid var(--dsw-alias-border-l1)"
                  :src="figure.url"
                  :alt="figure.name"
                  loading="lazy"
                  @click="emit('zoom', figure.url, figure.name)"
                />
                <figcaption
                  class="mt-0.5 text-[length:var(--dsw-text-xs)] leading-[16px] text-[var(--dsw-alias-text-tertiary)]"
                >
                  {{ figure.name.replace(/_/g, ' ') }}
                </figcaption>
              </figure>
            </div>
          </div>

          <p
            v-else-if="state === 'error'"
            class="m-0 px-1 py-1 text-[length:var(--dsw-text-sm)] leading-[18px] text-[var(--dsw-feedback-error-text)]"
            data-role="tool-error"
            >{{ summary }}</p
          >

          <p
            v-else
            class="m-0 px-1 py-1 text-[length:var(--dsw-text-sm)] leading-[18px] text-[var(--dsw-alias-text-tertiary)]"
            data-role="tool-empty"
            >{{ state === 'running' ? '正在执行，等待工具返回结果…' : '工具未返回结果。' }}</p
          >
        </div>
      </div>
    </CollapseTransition>
  </div>
</template>

<style scoped>
.tool-disclosure-window {
  display: flow-root;
  min-height: 0;
}
.tool-disclosure-window > div > * {
  flex-shrink: 0;
}
.view-experiment-result {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  gap: 7px;
  margin: 5px 0 2px;
  padding: 6px 9px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 7px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-link);
  font: inherit;
  font-size: var(--dsw-text-sm);
  cursor: pointer;
}
.view-experiment-result:hover {
  background: var(--dsw-alias-bg-skeleton);
}
.view-experiment-result:disabled {
  opacity: 0.45;
  cursor: default;
}
[data-role='tool-error'] {
  min-width: 0;
  overflow-wrap: anywhere;
}
.tool-result-error {
  margin: 4px 0;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-feedback-error-text);
}
</style>
