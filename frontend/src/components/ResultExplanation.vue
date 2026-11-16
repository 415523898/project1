<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue';
import MarkdownText from '@/components/MarkdownText.vue';
import ModelAccessAction from '@/components/ModelAccessAction.vue';
import { useLab } from '@/composables/useLab';
import {
  explanationInput,
  explanationState,
  generateExplanation,
  loadExplanation,
  type ExplanationState,
} from '@/services/result-explanation';
import type { ExperimentResult, MetricEntry } from '@/types';

const props = defineProps<{
  result: ExperimentResult;
  method: string;
  entry: MetricEntry;
  label: string;
}>();
const lab = useLab();
const session = computed(() => props.result.session || lab.state.sessionId || '');
const input = computed(() =>
  explanationInput(props.result, props.method, props.entry, session.value, props.label),
);
const state = shallowRef<ExplanationState>({
  text: '',
  busy: false,
  error: '',
  model: '',
  usage: null,
});
const available = computed(() => Boolean(session.value && lab.modelReady.value));

function generate(force = false): void {
  if (!available.value) return;
  try {
    void generateExplanation(state.value, input.value, lab.config(), force);
  } catch (error) {
    state.value.error = (error as Error).message;
  }
}
watch(
  () => [
    JSON.stringify(input.value),
    lab.state.backend,
    lab.state.user,
    lab.state.authExpired,
    lab.state.settings.base_url,
    lab.state.settings.model,
    lab.state.apiKey,
    lab.modelReady.value,
  ],
  async () => {
    state.value = explanationState(
      lab.state.user,
      input.value,
      lab.state.settings.base_url,
      lab.state.settings.model,
    );
    const current = state.value;
    const saved = props.result.result_explanations?.[props.method];
    if (saved?.text && !current.text) Object.assign(current, saved, { loaded: true });
    if (session.value && lab.state.user && !lab.state.authExpired)
      await loadExplanation(current, input.value);
    if (state.value !== current || current.text || current.error) return;
    generate();
  },
  { immediate: true },
);
</script>

<template>
  <section
    class="result-explanation"
    data-role="method-notes"
    :data-explanation-method="method"
    aria-live="polite"
  >
    <header>
      <span>结果说明</span>
      <span v-if="state.usage?.total_tokens" class="explanation-usage"
        >{{ state.usage.total_tokens }} token</span
      >
      <button
        v-if="available"
        type="button"
        :disabled="state.busy || state.loading"
        data-action="explain-result"
        @click="generate(true)"
      >
        {{ state.busy ? '解读中…' : state.text || state.error ? '重新解读' : '生成解读' }}
      </button>
      <ModelAccessAction v-else prefix="explanation" />
    </header>
    <MarkdownText v-if="state.text" :text="state.text" data-role="generated-explanation" />
    <p v-else-if="state.loading" class="explanation-placeholder">正在读取已保存的解读…</p>
    <p v-else-if="state.busy" class="explanation-placeholder">正在根据本次指标与结果表生成解读…</p>
    <p v-else-if="lab.state.authExpired" class="explanation-placeholder"
      >重新登录后可继续解读，已有实验指标和图表仍保留。</p
    >
    <p v-else-if="!session" class="explanation-placeholder">打开对应会话后，可解读本次实验结果。</p>
    <p v-else-if="!available" class="explanation-placeholder">{{
      lab.modelAccess.value.message
    }}</p>
    <p
      v-if="state.error && !lab.state.authExpired"
      class="explanation-error"
      data-role="explanation-error"
      >{{ state.error }}</p
    >
  </section>
</template>

<style scoped>
.result-explanation {
  margin: 8px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--dsw-alias-bg-skeleton);
  overflow-wrap: anywhere;
  font-size: var(--dsw-text-sm);
  line-height: 1.6;
}
.result-explanation header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 7px;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
}
.result-explanation button,
.result-explanation header a {
  margin-left: auto;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-link);
  font: inherit;
  cursor: pointer;
}
.result-explanation button:disabled {
  color: var(--dsw-alias-text-tertiary);
  cursor: wait;
}
.explanation-placeholder {
  margin: 0;
  color: var(--dsw-alias-text-secondary);
}
.explanation-error {
  margin: 6px 0 0;
  color: var(--dsw-feedback-error-text);
}
.explanation-usage {
  font-variant-numeric: tabular-nums;
}
</style>
