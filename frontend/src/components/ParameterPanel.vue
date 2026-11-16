<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';

import ParameterField from '@/components/ParameterField.vue';
import { useLab } from '@/composables/useLab';
import { appliedParams, methodGroups, methodParams, runExperiment } from '@/services/experiments';
import type { ExperimentResult, MethodSpec, ParameterSpec } from '@/types';

const props = defineProps<{
  method: MethodSpec;
  result?: ExperimentResult | null;
  source?: string | null;
  sourceLabel?: string;
  session?: string | null;
  columns?: string[];
  target?: string | null;
  group?: string | null;
  time?: string | null;
}>();

const emit = defineEmits<{ (event: 'ran', result: ExperimentResult): void }>();

const lab = useLab();
const values = reactive<Record<string, unknown>>({});
const running = ref(false);
const error = ref('');

const specs = computed(() => methodParams(props.method));
const groups = computed(() =>
  methodGroups(props.method)
    .map((group) => ({
      name: group.name,
      params: group.params.filter((spec) => spec.key !== 'figures'),
    }))
    .filter((group) => group.params.length),
);
const figuresSpec = computed(() => specs.value.find((spec) => spec.key === 'figures') ?? null);
const figuresOn = computed(() => values.figures !== false);
const missing = computed(() => props.method.missing ?? []);
const blocked = computed(() => props.method.runnable === false || missing.value.length > 0);
const sourceName = computed(() => props.sourceLabel || props.source || 'iris');

function seed(spec: ParameterSpec): unknown {
  if (spec.type === 'columns') return [];
  return spec.default === undefined ? null : spec.default;
}

function reset(): void {
  for (const key of Object.keys(values)) delete values[key];
  for (const spec of specs.value) values[spec.key] = seed(spec);
  for (const [key, value] of Object.entries(appliedParams(props.result ?? null))) {
    const spec = specs.value.find((item) => item.key === key);
    if (!spec) continue;
    if (spec.type === 'columns') {
      values[key] = Array.isArray(value) ? value.map((item) => String(item)) : [];
      continue;
    }
    values[key] = value;
  }
}

watch(() => [props.method.id, props.result] as const, reset, { immediate: true });

function hidden(spec: ParameterSpec): boolean {
  const need = spec.hidden_when;
  if (!need || typeof need !== 'object') return false;
  return Object.entries(need).some(([key, expected]) => {
    const current = values[key];
    const blockedValues = Array.isArray(expected) ? expected : [expected];
    if (Array.isArray(current))
      return current.some((item) => blockedValues.some((option) => option === item));
    return blockedValues.some((option) => option === current);
  });
}

function dependency(spec: ParameterSpec): ParameterSpec | null {
  if (!spec.depends_on) return null;
  return specs.value.find((item) => item.key === spec.depends_on) ?? null;
}

function locked(spec: ParameterSpec): boolean {
  const item = dependency(spec);
  if (!item) return false;
  const value = values[item.key];
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'boolean') return !value;
  if (typeof value === 'number') return value === 0;
  if (item.type === 'enum')
    return value === null || value === undefined || value === '' || value === item.default;
  return value === null || value === undefined || value === '';
}

function lockHint(spec: ParameterSpec): string {
  const item = dependency(spec);
  return item ? `先开启「${item.label}」` : '';
}

function buildParams(): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const spec of specs.value) {
    const value = values[spec.key];
    if (spec.type === 'columns') {
      const list = Array.isArray(value)
        ? value.map((item) => String(item)).filter((item) => item.trim())
        : [];
      params[spec.key] = list.length ? list : null;
      continue;
    }
    if (spec.type === 'integer' || spec.type === 'number') {
      params[spec.key] = typeof value === 'number' && Number.isFinite(value) ? value : null;
      continue;
    }
    params[spec.key] = value === undefined ? null : value;
  }
  return params;
}

async function run(): Promise<void> {
  if (running.value || blocked.value) return;
  const owner = lab.state.user;
  running.value = true;
  error.value = '';
  try {
    const session = props.session ?? (await lab.ensureSession());
    const result = await runExperiment({
      kind: props.method.engine === 'sklearn' ? 'sklearn' : 'library',
      reason: `用右侧栏参数重跑「${props.method.title}」`,
      methods: [props.method.id],
      params: buildParams(),
      source: props.source || 'iris',
      session,
      experiment_id: props.result?.experiment_id,
      experiment_version: props.result?.experiment_version,
      target: props.target ?? null,
      group: props.group ?? null,
      time: props.time ?? null,
      figures: figuresOn.value,
    });
    // Keep a completed rerun with its originating account and conversation.
    if (result.experiment_id) {
      lab.acceptExperimentResult(result, session, owner);
      if (lab.state.user !== owner || lab.state.sessionId !== session) return;
    }
    const failures = result.failures ?? [];
    if (failures.length) error.value = failures[0]?.error ?? '';
    emit('ran', result);
  } catch (problem) {
    error.value = (problem as Error).message;
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <section
    class="parameter-panel mb-2 rounded-panel border-[0.5px] border-line bg-surface p-2.5"
    data-role="parameter-panel"
    :data-method="props.method.id"
  >
    <header class="mb-2 flex items-center justify-between gap-2">
      <h4 class="m-0 flex-none text-[length:var(--dsw-text-sm)] font-medium text-ink">参数</h4>
      <span
        class="min-w-0 truncate text-[length:var(--dsw-text-xs)] text-ink-3"
        data-role="param-source"
        :title="sourceName"
        >数据来源：{{ sourceName }}</span
      >
    </header>
    <div
      v-if="figuresSpec"
      class="mb-2 flex items-center justify-between gap-2 rounded-card bg-field px-2.5 py-1.5"
      data-role="figures-row"
    >
      <span class="min-w-0 text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink">输出图形</span>
      <button
        type="button"
        role="switch"
        aria-label="输出图形"
        :aria-checked="figuresOn ? 'true' : 'false'"
        data-param="figures"
        data-role="figures-switch"
        class="relative h-5 w-9 flex-none cursor-pointer rounded-[999px] border-0 p-0 transition-colors duration-200"
        :class="figuresOn ? 'bg-brand' : 'bg-skeleton'"
        @click="values.figures = !figuresOn"
      >
        <span
          class="absolute top-[2px] h-4 w-4 rounded-[999px] bg-surface transition-[left] duration-200"
          :class="figuresOn ? 'left-[18px]' : 'left-[2px]'"
        ></span>
      </button>
    </div>
    <section
      v-for="group in groups"
      :key="group.name"
      class="mb-2"
      data-role="param-group"
      :data-group="group.name"
    >
      <p class="mb-1 mt-0 text-[length:var(--dsw-text-xs)] font-medium text-ink-3">{{
        group.name
      }}</p>
      <div class="flex flex-col gap-1.5">
        <template v-for="spec in group.params" :key="spec.key">
          <div
            v-if="!hidden(spec)"
            class="flex gap-2"
            :class="spec.type === 'columns' ? 'flex-col' : 'items-center justify-between'"
            :data-field="spec.key"
            :data-type="spec.type"
          >
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink-2">{{
                spec.label
              }}</span>
              <span
                v-if="locked(spec)"
                class="text-[length:var(--dsw-text-xs)] leading-[1.6] text-ink-3"
                data-role="param-locked"
                >{{ lockHint(spec) }}</span
              >
            </span>
            <div :class="spec.type === 'columns' ? 'w-full' : 'w-[132px] flex-none'">
              <ParameterField
                :spec="spec"
                :model-value="values[spec.key]"
                :columns="props.columns"
                :disabled="locked(spec)"
                @update:model-value="(value) => (values[spec.key] = value)"
              />
            </div>
          </div>
        </template>
      </div>
    </section>
    <p
      v-if="blocked"
      class="mb-1.5 mt-0 text-[length:var(--dsw-text-sm)] leading-[1.6] text-error-ink"
      data-role="param-blocked"
    >
      需要 {{ missing.join('、') }}，当前环境未安装，无法运行。
    </p>
    <footer class="flex items-center gap-2">
      <button
        type="button"
        class="panel-button cursor-pointer bg-brand text-brand-ink hover:not-disabled:bg-brand-hover hover:not-disabled:text-brand-ink disabled:cursor-default disabled:bg-transparent disabled:text-ink-2"
        data-action="run-method"
        :disabled="running || blocked"
        @click="run"
        >{{ running ? '运行中…' : '运行' }}</button
      >
      <span
        v-if="running"
        class="text-[length:var(--dsw-text-xs)] leading-[1.6] text-ink-3"
        data-role="param-running"
        >正在服务端重跑，指标与图会就地刷新…</span
      >
    </footer>
    <p
      v-if="error"
      class="mb-0 mt-1.5 text-[length:var(--dsw-text-sm)] leading-[1.6] text-error-ink"
      data-role="param-error"
      >{{ error }}</p
    >
  </section>
</template>

<style scoped>
.parameter-panel {
  container-type: inline-size;
}
@container (max-width: 250px) {
  [data-field] {
    flex-direction: column;
    align-items: stretch;
  }
  [data-field] > div {
    width: 100%;
  }
}
</style>
