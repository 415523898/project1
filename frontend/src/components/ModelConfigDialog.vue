<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue';
import { useDialogMotion, useDialogViewport } from '@/composables/useDialogMotion';
import { vDisclosureMotion } from '@/utils/disclosure-motion';
import CollapseTransition from '@/components/CollapseTransition.vue';
import UiIcon from '@/components/UiIcon.vue';
import {
  inputTypes,
  normalizeInputTypes,
  modelDefaults,
  mappingError,
  isEffortMapping,
  type ConfiguredModel,
  type InputType,
} from '@/utils/model-config';
import type { Protocol } from '@/utils/model-providers';
import '@/styles/settings-motion.css';
const props = defineProps<{
  model: ConfiguredModel;
  upstream: string;
  protocol: Protocol;
  existing: string[];
  adding?: boolean;
}>();
const emit = defineEmits<{ save: [value: ConfiguredModel]; close: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
useDialogViewport(dialog);
type EditableModel = Omit<ConfiguredModel, 'context_window' | 'max_output_tokens'> & {
  context_window: number | '' | null;
  max_output_tokens: number | '' | null;
};
const draft = reactive<EditableModel>(JSON.parse(JSON.stringify(props.model)));
const mapping = ref(JSON.stringify(draft.effort_mapping, null, 2)),
  levelText = ref(''),
  error = ref('');
const defaults = computed(() => modelDefaults(draft.id, props.upstream, props.protocol));
const invalidField = ref('');
watch([error, invalidField], async ([message, field]) => {
  if (!message || !field) return;
  await nextTick();
  dialog.value?.querySelector<HTMLElement>(`#${field}`)?.focus();
});
const shown = ref(true);
let saved: ConfiguredModel | undefined;
const { onNativeClose } = useDialogMotion(dialog, () => shown.value, {
  requestClose: () => {
    shown.value = false;
  },
  afterClose: () => {
    if (saved) emit('save', saved);
    else emit('close');
  },
});
function addLevel() {
  const level = levelText.value.trim();
  if (/^[a-z][a-z0-9_-]{0,31}$/.test(level) && !draft.efforts.includes(level)) {
    draft.efforts.push(level);
    levelText.value = '';
  } else {
    error.value = '等级请使用小写英文、数字、下划线或短横线。';
    invalidField.value = 'edit-model-level';
  }
}
function toggleInput(type: InputType, enabled: boolean) {
  draft.input_types = normalizeInputTypes(
    enabled ? [...draft.input_types, type] : draft.input_types.filter((value) => value !== type),
  );
}
function reset() {
  Object.assign(draft, JSON.parse(JSON.stringify(defaults.value)));
  mapping.value = '{}';
  levelText.value = '';
  error.value = '';
  invalidField.value = '';
}
function save() {
  if (!shown.value) return;
  error.value = '';
  invalidField.value = '';
  const id = draft.id.trim();
  if (!id || id.length > 200) {
    error.value = '请填写 1–200 字符的模型 ID。';
    invalidField.value = 'edit-model-id';
    return;
  }
  if ((props.adding || id !== props.model.id) && props.existing.includes(id)) {
    error.value = '此上游已经有相同的模型 ID。';
    invalidField.value = 'edit-model-id';
    return;
  }
  for (const key of ['context_window', 'max_output_tokens'] as const) {
    if (draft[key] === '') draft[key] = null;
    const value = draft[key];
    if (
      value !== null &&
      value !== undefined &&
      (!Number.isInteger(value) || value < 1 || value > 1048576)
    ) {
      error.value = '容量需为 1–1048576 的整数，或留空使用默认。';
      invalidField.value = key === 'context_window' ? 'edit-model-context' : 'edit-model-output';
      return;
    }
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(mapping.value || '{}');
  } catch {
    error.value = '推理参数映射不是有效的 JSON。';
    invalidField.value = 'edit-model-mapping';
    return;
  }
  error.value = mappingError(parsed, props.protocol, draft.efforts);
  if (error.value || !isEffortMapping(parsed)) {
    invalidField.value = 'edit-model-mapping';
    return;
  }
  saved = {
    id,
    enabled: draft.enabled,
    context_window: draft.context_window || null,
    max_output_tokens: draft.max_output_tokens || null,
    input_types: normalizeInputTypes(draft.input_types),
    efforts: [...draft.efforts],
    effort_mapping: parsed,
  };
  shown.value = false;
}
</script>
<template>
  <dialog
    ref="dialog"
    class="model-config-dialog"
    aria-labelledby="model-config-title"
    @cancel.prevent="shown = false"
    @close="onNativeClose"
  >
    <form @submit.prevent="save" aria-describedby="model-config-note">
      <header
        ><h2 id="model-config-title">{{ adding ? '添加模型' : '编辑模型配置' }}</h2
        ><button type="button" class="icon" aria-label="关闭模型配置" @click="shown = false"
          ><UiIcon name="close" /></button
      ></header>
      <div class="editor-scroll">
        <p id="model-config-note" class="form-note"
          >所有参数都可以留空；留空即使用服务商默认配置。</p
        >
        <label
          >模型 ID<input
            v-model="draft.id"
            id="edit-model-id"
            :aria-invalid="invalidField === 'edit-model-id' || undefined"
            :aria-describedby="
              invalidField === 'edit-model-id' && error ? 'model-config-error' : undefined
            "
            autocomplete="off"
            spellcheck="false"
            placeholder="填写服务商提供的完整模型 ID"
            :autofocus="adding"
        /></label>
        <div class="capacity-grid"
          ><label
            >上下文窗口<input
              v-model.number="draft.context_window"
              id="edit-model-context"
              :aria-invalid="invalidField === 'edit-model-context' || undefined"
              :aria-describedby="
                invalidField === 'edit-model-context' && error ? 'model-config-error' : undefined
              "
              type="number"
              min="1"
              max="1048576"
              placeholder="服务商默认"
            /><small>仅用于模型列表标注，留空不显示。</small></label
          >
          <label
            >最大输出 Token<input
              v-model.number="draft.max_output_tokens"
              id="edit-model-output"
              :aria-invalid="invalidField === 'edit-model-output' || undefined"
              :aria-describedby="
                invalidField === 'edit-model-output' && error ? 'model-config-error' : undefined
              "
              type="number"
              min="1"
              max="1048576"
              placeholder="服务商默认"
            /><small>留空使用服务商默认输出上限。</small></label
          ></div
        >
        <details v-disclosure-motion open
          ><summary>高级配置</summary>
          <div class="option-section"
            ><span class="field-name">输入类型</span
            ><div class="chips"
              ><label v-for="type in inputTypes" :key="type.value" class="check-chip"
                ><input
                  type="checkbox"
                  :checked="draft.input_types.includes(type.value)"
                  :disabled="type.value === 'text'"
                  @change="
                    toggleInput(type.value, ($event.target as HTMLInputElement).checked)
                  " />{{ type.label
                }}<UiIcon v-if="type.value === 'text'" name="lock" class="tiny" /></label></div
            ><small>按服务商提供的模型能力选择；默认文本和图片。</small></div
          >
          <div class="option-section"
            ><span class="field-name">推理等级（从低到高）</span
            ><div class="chips">
              <span v-for="(level, index) in draft.efforts" :key="level" class="level-chip"
                >{{ level
                }}<button
                  type="button"
                  :aria-label="`删除等级 ${level}`"
                  @click="draft.efforts.splice(index, 1)"
                  >×</button
                ></span
              >
              <span v-if="!draft.efforts.length" class="muted">服务商默认</span> </div
            ><div class="add-level"
              ><input
                v-model="levelText"
                id="edit-model-level"
                :aria-invalid="invalidField === 'edit-model-level' || undefined"
                :aria-describedby="
                  invalidField === 'edit-model-level' && error ? 'model-config-error' : undefined
                "
                aria-label="新的推理等级"
                placeholder="例如 high"
                @keydown.enter.prevent="addLevel"
              /><button type="button" class="secondary" @click="addLevel"
                ><UiIcon name="plus" class="tiny" />添加等级</button
              ></div
            ><small>留空使用服务商默认思考等级。</small></div
          >
          <CollapseTransition
            ><label
              >推理参数映射<textarea
                v-model="mapping"
                id="edit-model-mapping"
                :aria-invalid="invalidField === 'edit-model-mapping' || undefined"
                :aria-describedby="
                  invalidField === 'edit-model-mapping' && error ? 'model-config-error' : undefined
                "
                rows="5"
                spellcheck="false"
                placeholder='{"high":{"reasoning_effort":"high"}}'
              ></textarea
              ><small>JSON：每个等级对应思考参数；不执行脚本。留空不发送额外参数。</small></label
            ></CollapseTransition
          >
        </details>
        <p v-if="error" id="model-config-error" class="error" role="alert">{{ error }}</p>
      </div>
      <footer
        ><button type="button" class="reset" @click="reset">重置表单</button
        ><button type="button" class="secondary" @click="shown = false">取消</button
        ><button type="submit" class="primary" data-action="save-model-config" :disabled="!shown"
          >保存</button
        ></footer
      >
    </form>
  </dialog>
</template>
<style scoped>
.model-config-dialog {
  margin-block: min(7dvh, 56px) auto;
}
.editor-scroll {
  scrollbar-gutter: stable;
  contain: layout style;
}
.model-config-dialog::backdrop {
  transition: background-color 180ms ease-out;
}
.model-config-dialog[data-motion='closing']::backdrop {
  background: transparent;
}
.model-config-dialog[data-motion='closing'] {
  pointer-events: none;
}
@starting-style {
  dialog.model-config-dialog::backdrop {
    background: transparent;
  }
}
@media (prefers-reduced-motion: reduce) {
  .model-config-dialog::backdrop {
    transition: none;
  }
}
.model-config-dialog {
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 16px;
  padding: 0;
  width: min(600px, 92vw);
  max-height: 86vh;
  overflow: hidden;
  color: var(--dsw-alias-text-primary);
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: 0 16px 60px #20305025;
}
.model-config-dialog::backdrop {
  background: #17203350;
}
form {
  display: flex;
  flex-direction: column;
  max-height: calc(86vh - 2px);
  min-height: 0;
  overflow: hidden;
  border-radius: inherit;
}
header,
footer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px var(--settings-inset);
  flex: none;
}
header {
  justify-content: space-between;
}
h2 {
  font-size: var(--dsw-text-lg);
  font-weight: 600;
  margin: 0;
}
.icon {
  border: 0;
  background: none;
  color: var(--dsw-alias-text-tertiary);
  cursor: pointer;
}
.editor-scroll {
  padding: 0 var(--settings-inset) 8px;
  overflow: auto;
  min-height: 0;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.chips,
.add-level {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
}
.form-note {
  margin: 0;
  padding: 9px 11px;
  border-radius: 8px;
  background: var(--dsw-alias-bg-layer-2);
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-sm);
  line-height: 1.6;
}
label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
}
input:not([type='checkbox']),
textarea {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  background: var(--dsw-specific-input-major);
  color: var(--dsw-alias-text-primary);
  padding: 8px 10px;
  font: inherit;
  font-size: var(--dsw-text-row);
  line-height: 1.5;
}
input:disabled {
  opacity: 0.5;
}
textarea {
  resize: vertical;
  font-family: ui-monospace, monospace;
  min-height: 112px;
  max-height: 200px;
}
.capacity-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
small,
.muted {
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
}
.muted {
  margin: 10px 0 0;
}
.field-name {
  display: block;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
  margin-bottom: 9px;
}
summary {
  cursor: pointer;
  font-size: var(--dsw-text-row);
  list-style-position: inside;
  margin-bottom: 12px;
}
.option-section {
  margin-bottom: 14px;
}
.check-chip {
  flex-direction: row;
  align-items: center;
  padding: 8px 11px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  gap: 7px;
}
.tiny {
  width: 14px;
  height: 14px;
}
.level-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 12px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  font:
    12px ui-monospace,
    monospace;
}
.level-chip button {
  border: 0;
  background: none;
  color: var(--dsw-alias-text-tertiary);
  cursor: pointer;
}
.add-level {
  margin-top: 10px;
}
.add-level input {
  max-width: 160px;
}
.reset {
  margin-right: auto;
  border: 0;
  border-bottom: 1px solid currentColor;
  background: none;
  padding: 0;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.error {
  color: var(--dsw-feedback-error-text);
  font-size: var(--dsw-text-sm);
  margin: 0;
}
footer {
  border-top: 1px solid var(--dsw-alias-border-l2);
}
@media (max-width: 560px) {
  .capacity-grid {
    grid-template-columns: 1fr;
  }
}
</style>
