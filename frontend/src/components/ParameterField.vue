<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import type { ParameterSpec } from '@/types';

const props = defineProps<{
  spec: ParameterSpec;
  modelValue: unknown;
  columns?: string[];
  disabled?: boolean;
}>();

const emit = defineEmits<{ (event: 'update:modelValue', value: unknown): void }>();

const NULL_TOKEN = '__null__';
const CONTROL =
  'w-full rounded-card border-[0.5px] border-line bg-field px-2 py-[3px] text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink outline-none focus:border-line-strong disabled:cursor-default disabled:opacity-50';

function token(value: unknown): string {
  if (value === null || value === undefined) return NULL_TOKEN;
  return `v:${JSON.stringify(value)}`;
}

function parse(value: string): unknown {
  if (value === NULL_TOKEN) return null;
  try {
    return JSON.parse(value.slice(2));
  } catch {
    return value.slice(2);
  }
}

function optionLabel(value: unknown): string {
  if (value === null || value === undefined) return '无';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

const options = computed(() => props.spec.options ?? []);
const booleanValue = computed(() => props.modelValue === true);
const enumToken = computed(() => token(props.modelValue));
const numberValue = computed(() =>
  typeof props.modelValue === 'number' && Number.isFinite(props.modelValue)
    ? String(props.modelValue)
    : '',
);
const textValue = computed(() =>
  props.modelValue === null || props.modelValue === undefined ? '' : String(props.modelValue),
);
const picked = computed(() =>
  Array.isArray(props.modelValue) ? props.modelValue.map((item) => String(item)) : [],
);
const columnNames = computed(() => props.columns ?? []);
const columnsAsText = computed(
  () => props.spec.type === 'columns' && columnNames.value.length === 0,
);
const columnText = ref(picked.value.join(','));

function plainColumns(raw: string): string {
  return raw
    .replace(/，/g, ',')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .join(',');
}

watch(picked, (value) => {
  const incoming = value.join(',');
  if (incoming !== plainColumns(columnText.value)) columnText.value = incoming;
});

function onToggle(): void {
  emit('update:modelValue', !booleanValue.value);
}

function onNumber(event: Event): void {
  const raw = (event.target as HTMLInputElement).value;
  if (!raw.trim()) {
    emit('update:modelValue', null);
    return;
  }
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    emit('update:modelValue', null);
    return;
  }
  emit('update:modelValue', props.spec.type === 'integer' ? Math.round(value) : value);
}

function decimalPlaces(value: number): number {
  const [coefficient = '', exponent = '0'] = String(value).toLowerCase().split('e');
  return Math.max(0, (coefficient.split('.')[1]?.length ?? 0) - Number(exponent));
}

function nextNumber(direction: 1 | -1): number {
  const spec = props.spec;
  const step = Number.isFinite(spec.step) && (spec.step ?? 0) > 0 ? spec.step! : 1;
  // Bounds constrain the result; the default anchors the step grid. Using min as
  // the origin shifts alpha=0.05, min=1e-6, step=0.001 to values like 0.051001.
  const base = typeof spec.default === 'number' && Number.isFinite(spec.default) ? spec.default : 0;
  const current =
    typeof props.modelValue === 'number' && Number.isFinite(props.modelValue)
      ? props.modelValue
      : base;
  const position = (current - base) / step;
  const nearest = Math.round(position);
  const tolerance = Number.EPSILON * Math.max(1, Math.abs(position)) * 4;
  const index =
    Math.abs(position - nearest) <= tolerance
      ? nearest + direction
      : direction > 0
        ? Math.ceil(position)
        : Math.floor(position);
  const precision = Math.min(100, Math.max(decimalPlaces(base), decimalPlaces(step)));
  let value = Number((base + index * step).toFixed(precision));
  if (spec.type === 'integer') value = Math.round(value);
  if (spec.min !== undefined) value = Math.max(spec.min, value);
  if (spec.max !== undefined) value = Math.min(spec.max, value);
  return value;
}

const increasedNumber = computed(() => nextNumber(1));
const decreasedNumber = computed(() => nextNumber(-1));

function onStep(direction: 1 | -1): void {
  if (props.disabled) return;
  emit('update:modelValue', direction > 0 ? increasedNumber.value : decreasedNumber.value);
}

function onEnum(event: Event): void {
  emit('update:modelValue', parse((event.target as HTMLSelectElement).value));
}

function onText(event: Event): void {
  emit('update:modelValue', (event.target as HTMLInputElement).value);
}

function onColumn(event: Event): void {
  const input = event.target as HTMLInputElement;
  const name = input.value;
  const next = input.checked
    ? [...picked.value.filter((item) => item !== name), name]
    : picked.value.filter((item) => item !== name);
  emit('update:modelValue', next);
}

function onColumnText(event: Event): void {
  const raw = (event.target as HTMLInputElement).value;
  columnText.value = raw;
  const parts = raw
    .replace(/，/g, ',')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  emit('update:modelValue', parts);
}
</script>

<template>
  <input
    v-if="props.spec.type === 'boolean'"
    type="checkbox"
    class="h-3.5 w-3.5 flex-none cursor-pointer accent-brand disabled:cursor-default disabled:opacity-50"
    :data-param="props.spec.key"
    :checked="booleanValue"
    :disabled="props.disabled"
    @change="onToggle"
  />
  <div
    v-else-if="props.spec.type === 'integer' || props.spec.type === 'number'"
    class="relative w-full"
  >
    <input
      type="number"
      class="parameter-number pr-7"
      :class="CONTROL"
      :data-param="props.spec.key"
      :aria-label="props.spec.label"
      :value="numberValue"
      :min="props.spec.min"
      :max="props.spec.max"
      step="any"
      :disabled="props.disabled"
      @input="onNumber"
      @keydown.up.prevent="onStep(1)"
      @keydown.down.prevent="onStep(-1)"
    />
    <div class="absolute inset-y-px right-px flex w-5 flex-col overflow-hidden rounded-r-card">
      <button
        type="button"
        class="flex flex-1 items-center justify-center border-0 bg-transparent p-0 text-ink-3 hover:enabled:bg-skeleton disabled:opacity-30"
        :aria-label="'增大' + props.spec.label"
        :disabled="props.disabled || increasedNumber === props.modelValue"
        data-action="step-up"
        @mousedown.prevent
        @click="onStep(1)"
        ><span class="parameter-step-up" aria-hidden="true"></span
      ></button>
      <button
        type="button"
        class="flex flex-1 items-center justify-center border-0 bg-transparent p-0 text-ink-3 hover:enabled:bg-skeleton disabled:opacity-30"
        :aria-label="'减小' + props.spec.label"
        :disabled="props.disabled || decreasedNumber === props.modelValue"
        data-action="step-down"
        @mousedown.prevent
        @click="onStep(-1)"
        ><span class="parameter-step-down" aria-hidden="true"></span
      ></button>
    </div>
  </div>
  <select
    v-else-if="props.spec.type === 'enum'"
    :class="CONTROL"
    :data-param="props.spec.key"
    :value="enumToken"
    :disabled="props.disabled"
    @change="onEnum"
  >
    <option v-for="option in options" :key="token(option)" :value="token(option)">{{
      optionLabel(option)
    }}</option>
  </select>
  <input
    v-else-if="props.spec.type === 'text'"
    type="text"
    :class="CONTROL"
    :data-param="props.spec.key"
    :value="textValue"
    :disabled="props.disabled"
    @input="onText"
  />
  <input
    v-else-if="columnsAsText"
    type="text"
    :class="CONTROL"
    :data-param="props.spec.key"
    :value="columnText"
    :disabled="props.disabled"
    placeholder="列名用逗号分隔，留空表示全部"
    @input="onColumnText"
  />
  <div
    v-else
    class="max-h-[132px] overflow-y-auto rounded-card border-[0.5px] border-line bg-field px-2 py-1"
    :data-param="props.spec.key"
  >
    <label
      v-for="name in columnNames"
      :key="name"
      class="flex cursor-pointer items-center gap-1.5 py-px text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink-2"
    >
      <input
        type="checkbox"
        class="h-3.5 w-3.5 flex-none cursor-pointer accent-brand disabled:cursor-default disabled:opacity-50"
        :value="name"
        :checked="picked.includes(name)"
        :disabled="props.disabled"
        @change="onColumn"
      />
      <span class="truncate">{{ name }}</span>
    </label>
  </div>
</template>

<style scoped>
.parameter-number {
  appearance: textfield;
  -moz-appearance: textfield;
}
.parameter-number::-webkit-inner-spin-button,
.parameter-number::-webkit-outer-spin-button {
  appearance: none;
  margin: 0;
}
.parameter-step-up,
.parameter-step-down {
  width: 0;
  height: 0;
  border-left: 3px solid transparent;
  border-right: 3px solid transparent;
}
.parameter-step-up {
  border-bottom: 4px solid currentColor;
}
.parameter-step-down {
  border-top: 4px solid currentColor;
}
</style>
