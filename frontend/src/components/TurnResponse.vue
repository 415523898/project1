<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue';
import type { ChatTurn, ToolTrace } from '@/types';
import { activities } from '@/utils/turn-activity';
import { assistantDisplay } from '@/utils/assistant-display';
import CollapseTransition from '@/components/CollapseTransition.vue';
import MarkdownText from '@/components/MarkdownText.vue';
import ToolCallRow from '@/components/ToolCallRow.vue';
import UiIcon from '@/components/UiIcon.vue';
import { visibleTools } from '@/utils/tool-traces';

const props = defineProps<{ turn: ChatTurn }>();
const emit = defineEmits<{ zoom: [url: string, name: string]; viewResult: [trace: ToolTrace] }>();
const bodyId = useId();
const expanded = ref(props.turn.status !== 'complete');
const now = ref(Date.now());
let timer: ReturnType<typeof setInterval> | undefined;
let started = Date.now();

const running = computed(() => props.turn.status === 'pending');
const malformed = computed(() =>
  activities(props.turn).some(
    (item) => item.kind === 'message' && assistantDisplay(item.text).malformed,
  ),
);
const blocks = computed(() =>
  activities(props.turn).map((item) =>
    item.kind === 'message' ? { ...item, text: assistantDisplay(item.text).text } : item,
  ),
);
const final = computed(() => {
  if (props.turn.status === 'complete')
    return blocks.value.filter((item) => item.kind === 'message' && item.phase === 'final');
  const last = blocks.value.at(-1);
  return running.value && last?.kind === 'message' && last.phase !== 'working' ? [last] : [];
});
const process = computed(() => {
  const result: typeof blocks.value = [];
  let hidingAfterFailure = false;
  for (const item of blocks.value) {
    if (final.value.includes(item)) continue;
    if (item.kind === 'tool') {
      const trace = props.turn.tools?.[item.index];
      if (trace?.hidden) {
        hidingAfterFailure = true;
        continue;
      }
      hidingAfterFailure = false;
      result.push(item);
      continue;
    }
    if (hidingAfterFailure) continue;
    result.push(item);
  }
  return result;
});
const hasProcess = computed(() => running.value || process.value.length > 0);
const shownTools = computed(() => visibleTools(props.turn.tools));
const toolCount = computed(() => shownTools.value.length);
const failures = computed(
  () => shownTools.value.filter((tool) => tool.status === 'error').length,
);
const activeTool = computed(() =>
  props.turn.tools
    ?.slice()
    .reverse()
    .find((tool) => tool.status === 'running'),
);
const liveLabel = computed(() => {
  if (activeTool.value) return '正在执行工具';
  const phase = props.turn.model_phase;
  if (phase === 'connecting') return '正在请求模型';
  if (phase === 'thinking') return '模型正在思考';
  if (phase === 'connected') return '等待模型响应';
  if (phase === 'tool_call') return '正在准备工具调用';
  if (phase === 'generating') return '正在生成';
  return !blocks.value.length ? '正在连接模型' : '正在生成';
});
const duration = computed(() => {
  const elapsed = running.value ? Math.max(0, now.value - started) : props.turn.elapsed_ms;
  if (elapsed === undefined) return '';
  const seconds = Math.max(1, Math.round(elapsed / 1000));
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
  return `${Math.floor(seconds / 3600)} 小时 ${Math.floor((seconds % 3600) / 60)} 分`;
});
const savedExperiment = computed(() =>
  props.turn.tools?.some(
    (tool) =>
      tool.status === 'complete' &&
      ['run_ml_suite', 'experiment'].includes(tool.name) &&
      Object.keys(tool.result?.methods ?? {}).length > 0,
  ),
);
const label = computed(() =>
  running.value
    ? liveLabel.value
    : props.turn.status === 'stopped'
      ? '已停止'
      : props.turn.status === 'error'
        ? savedExperiment.value
          ? '回答中断，已有实验结果'
          : '回答未完成'
        : '工作过程',
);

watch(
  [() => props.turn, () => props.turn.status],
  ([, status]) => {
    expanded.value = status !== 'complete';
    if (timer) {
      clearInterval(timer);
      timer = undefined;
    }
    if (status === 'pending') {
      const parsed = Date.parse(props.turn.created_at ?? '');
      started = Number.isFinite(parsed) ? parsed : Date.now();
      now.value = Date.now();
      timer = setInterval(() => {
        now.value = Date.now();
      }, 1000);
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <div class="turn-response" :data-status="turn.status">
    <div v-if="hasProcess" class="turn-work">
      <button
        type="button"
        class="work-toggle"
        :disabled="!process.length"
        :aria-expanded="process.length ? expanded : undefined"
        :aria-controls="process.length ? bodyId : undefined"
        data-action="toggle-work-process"
        @click="expanded = !expanded"
      >
        <UiIcon v-if="running" name="spinner" class="h-3.5 w-3.5" />
        <UiIcon v-else-if="turn.status !== 'complete'" name="warning" class="h-3.5 w-3.5" />
        <span
          ><span :role="running ? 'status' : undefined">{{ label }}</span
          ><span v-if="duration"> · {{ duration }}</span></span
        >
        <span v-if="toolCount" class="work-count">{{ toolCount }} 次工具调用</span>
        <span v-if="failures" class="work-failures">{{ failures }} 次未成功</span>
        <UiIcon
          v-if="process.length"
          name="chevron-right"
          class="work-chevron h-3.5 w-3.5"
          :class="{ 'is-open': expanded }"
        />
      </button>
      <CollapseTransition>
        <div
          v-if="expanded && process.length"
          :id="bodyId"
          class="work-process-window"
          data-role="work-process"
        >
          <div class="work-process">
            <template v-for="(item, index) in process" :key="index">
              <div
                v-if="item.kind === 'message' && item.text"
                class="work-message"
                data-role="work-message"
              >
                <MarkdownText :text="item.text" />
              </div>
              <ToolCallRow
                v-else-if="item.kind === 'tool' && turn.tools?.[item.index]"
                :trace="turn.tools[item.index]!"
                :index="item.index"
                @zoom="(url, name) => emit('zoom', url, name)"
                @view-result="emit('viewResult', $event)"
              />
            </template>
          </div>
        </div>
      </CollapseTransition>
    </div>
    <div
      v-for="(item, index) in final"
      :key="index"
      class="final-answer"
      :class="{ 'is-streaming': running }"
      data-role="final-answer"
      :aria-busy="running"
    >
      <MarkdownText v-if="item.kind === 'message'" :text="item.text" />
    </div>
    <p v-if="malformed && !running" class="text-xs text-ink-3" role="status"
      >此条回复格式异常，请重新生成回复。</p
    >
  </div>
</template>

<style scoped>
.turn-response {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.turn-work {
  min-width: 0;
}
.work-toggle {
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: 100%;
  padding: 5px 0;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: var(--dsw-text-sm);
  line-height: 20px;
  text-align: left;
  flex-wrap: wrap;
}
.work-toggle:hover {
  color: var(--dsw-alias-text-primary);
}
.work-toggle:disabled {
  cursor: default;
}
.work-toggle:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  outline-offset: 4px;
  border-radius: 4px;
}
.work-count {
  font-size: var(--dsw-text-xs);
  opacity: 0.75;
}
.work-failures {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-feedback-error-text);
}
.work-chevron {
  flex: none;
  transition: transform 180ms ease;
}
.work-chevron.is-open {
  transform: rotate(90deg);
}
.work-process-window {
  display: flow-root;
  min-height: 0;
}
.work-process {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 5px 0 6px;
  padding: 11px 13px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  background: var(--dsw-alias-bg-layer-2);
  min-width: 0;
}
.work-process > * {
  flex-shrink: 0;
}
.work-message {
  color: var(--dsw-alias-text-secondary);
  overflow-wrap: anywhere;
}
.final-answer {
  overflow-wrap: anywhere;
  min-width: 0;
}
.final-answer.is-streaming :deep(.markdown-body > :last-child:not(.copy-region))::after,
.final-answer.is-streaming
  :deep(.markdown-body > :last-child > .copy-content > :last-child)::after {
  content: '';
  display: inline-block;
  width: 5px;
  height: 14px;
  margin-left: 4px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.45;
  animation: reply-caret 1s ease-in-out infinite;
}
@keyframes reply-caret {
  50% {
    opacity: 0.12;
  }
}
.final-answer :deep(.markdown-body > :first-child) {
  margin-top: 0;
}
@media (prefers-reduced-motion: reduce) {
  .work-chevron {
    transition: none;
  }
  .final-answer.is-streaming :deep(.markdown-body > :last-child:not(.copy-region))::after,
  .final-answer.is-streaming
    :deep(.markdown-body > :last-child > .copy-content > :last-child)::after {
    animation: none;
  }
}
</style>
