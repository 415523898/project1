<script setup lang="ts">
import { learnerText } from '@/utils/learner-text';
import type { CardDraft } from '@/composables/useStudy';
import type { StudyCardModel } from '@/services/study';
defineProps<{
  card: StudyCardModel | null;
  draft: CardDraft | null;
  selectedCount: number;
  paused: boolean;
  saving: boolean;
}>();
defineEmits<{
  edit: [field: 'title' | 'summary' | 'body' | 'levelPin', value: string];
  save: [];
  close: [];
  remove: [];
  delete: [];
}>();
</script>

<template>
  <aside class="study-inspector" data-role="study-inspector">
    <header
      ><h2>{{ selectedCount > 1 ? `已选 ${selectedCount} 张卡片` : '卡片详情' }}</h2
      ><button
        type="button"
        class="ui-button ui-button-ghost"
        aria-label="关闭卡片详情"
        @click="$emit('close')"
        >关闭</button
      ></header
    >
    <template v-if="card && draft && selectedCount === 1">
      <p class="draft-state">{{ draft.dirty ? '未保存的文字草稿' : '已保存的卡片内容' }}</p>
      <form @submit.prevent="$emit('save')">
        <label
          >标题<input
            :value="learnerText(draft.title)"
            maxlength="60"
            data-role="study-title"
            @input="$emit('edit', 'title', ($event.target as HTMLInputElement).value)"
        /></label>
        <label
          >小结<textarea
            :value="learnerText(draft.summary)"
            rows="10"
            maxlength="200"
            data-role="study-summary"
            @input="$emit('edit', 'summary', ($event.target as HTMLTextAreaElement).value)"
          />
        </label>
        <label
          >编号<input
            :value="draft.levelPin"
            inputmode="numeric"
            maxlength="3"
            placeholder="留空自动计算"
            data-role="study-level"
            @input="$emit('edit', 'levelPin', ($event.target as HTMLInputElement).value)"
        /></label>
        <button
          type="submit"
          class="ui-button ui-button-primary"
          data-action="study-save-card"
          :disabled="paused || !draft.dirty || saving"
          >保存卡片</button
        >
      </form>
    </template>
    <p v-else class="muted">{{
      selectedCount > 1 ? '可同时移出路线或删除选中卡片。' : '选择卡片以编辑内容。'
    }}</p>
    <div v-if="selectedCount" class="danger-actions"
      ><button
        type="button"
        class="ui-button ui-button-ghost"
        data-action="study-remove"
        :disabled="paused"
        @click="$emit('remove')"
        >从路线移出</button
      >
      <button
        type="button"
        class="ui-button ui-button-ghost"
        data-action="study-delete-selection"
        :disabled="paused"
        @click="$emit('delete')"
        >删除卡片</button
      ></div
    >
  </aside>
</template>

<style scoped>
.study-inspector {
  box-sizing: border-box;
  min-width: 0;
  overflow: auto;
  padding: 14px;
  border-left: 1px solid var(--dsw-alias-border-l2);
  background: var(--dsw-alias-bg-layer-1);
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
h2 {
  margin: 0;
  font-size: var(--dsw-text-row);
  font-weight: 600;
}
form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
}
input,
textarea {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  padding: 7px 9px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  font: inherit;
  line-height: 1.5;
  user-select: text;
}
textarea {
  min-height: 220px;
  resize: vertical;
}
.draft-state,
.muted {
  font-size: var(--dsw-text-sm);
  line-height: 1.6;
  color: var(--dsw-alias-text-secondary);
}
.draft-state {
  margin: 8px 0 12px;
}
.danger-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}

/* Inspector */
.study-inspector {
  padding: 18px 18px 22px;
  border-left: 1px solid #e9eef8;
  background: #fbfcff;
}
header {
  margin-bottom: 2px;
}
h2 {
  color: #13203a;
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.015em;
}
header .ui-button {
  height: 28px;
  padding: 0 9px;
  border: 1px solid #e5ebf5;
  border-radius: 8px;
  background: #ffffff;
  color: #647086;
  font-size: 10px;
}
header .ui-button:hover {
  border-color: #c9d9f8;
  background: #f4f8ff;
  color: #14213a;
}
.draft-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin: 10px 0 14px;
  padding: 3px 8px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f8faff;
  color: #8a96ab;
  font-size: 9.5px;
  line-height: 1.5;
}
.draft-state::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #22a06b;
}
form {
  gap: 13px;
}
label {
  gap: 6px;
  color: #5f6b80;
  font-size: 10.5px;
  font-weight: 500;
}
input,
textarea {
  border-color: #e2e9f4;
  border-radius: 10px;
  padding: 9px 11px;
  background: #ffffff;
  color: #14213a;
  font-size: 11.5px;
}
input {
  height: 40px;
}
input:focus,
textarea:focus {
  border-color: #9db5ee;
  box-shadow: 0 0 0 3px rgb(79 124 255 / 0.09);
  outline: none;
}
textarea {
  min-height: 190px;
  line-height: 1.7;
  resize: vertical;
}
form > .ui-button-primary {
  height: 38px;
  border-radius: 10px;
  border: 1px solid #d7e3fb;
  background: #eef3ff;
  color: #274a9a;
  font-size: 11.5px;
  font-weight: 600;
  box-shadow: 0 10px 22px -18px rgb(11 25 58 / 0.9);
}
form > .ui-button-primary:hover:not(:disabled) {
  background: #e1ebff;
}
.muted {
  margin: 12px 0 0;
  color: #8a96ab;
  font-size: 11px;
}
.danger-actions {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid #edf1f8;
}
.danger-actions .ui-button {
  height: 32px;
  padding: 0 10px;
  border: 1px solid #e5ebf5;
  border-radius: 8px;
  background: #ffffff;
  color: #647086;
  font-size: 10px;
}
.danger-actions .ui-button[data-action='study-delete-selection'] {
  border-color: #f0d4d2;
  background: #fffafa;
  color: #b63d30;
}
.danger-actions .ui-button[data-action='study-delete-selection']:hover:not(:disabled) {
  background: #fdecec;
}
.danger-actions .ui-button:hover:not(:disabled) {
  border-color: #c9d9f8;
  background: #f4f8ff;
  color: #14213a;
}
</style>
