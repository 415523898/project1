<script setup lang="ts">
import { computed } from 'vue';
import { learnerText } from '@/utils/learner-text';
import UiIcon from '@/components/UiIcon.vue';
import MessageActions from '@/components/MessageActions.vue';
import AttachmentCard from '@/components/AttachmentCard.vue';
import type { ChatAttachment } from '@/types';

const props = defineProps<{
  turnIndex: number;
  question: string;
  answer: string;
  loading?: boolean;
  loadingText?: string;
  error?: string | null;
  model?: string;
  elapsedMs?: number;
  tools?: number;
  image?: string | null;
  imageName?: string | null;
  images?: Array<{ url: string; name: string }>;
  attachments?: ChatAttachment[];
  eventId?: string;
  actions?: boolean;
  latest?: boolean;
  completed?: boolean;
  replyText?: string;
  actionsDisabled?: boolean;
  editing?: boolean;
  editText?: string;
  editError?: string;
}>();

const emit = defineEmits<{
  zoom: [url: string, name: string];
  edit: [];
  regenerate: [];
  branch: [];
  cancelEdit: [];
  saveEdit: [];
  'update:editText': [text: string];
}>();

const formattedElapsed = computed(() => {
  if (typeof props.elapsedMs !== 'number') return '';
  return props.elapsedMs >= 1000
    ? `${(props.elapsedMs / 1000).toFixed(1)} 秒`
    : `${props.elapsedMs} 毫秒`;
});
</script>

<template>
  <article class="user-turn mx-auto mb-4 flex max-w-[760px] flex-col items-end gap-1.5">
    <div
      v-if="attachments?.length"
      class="message-attachments attachment-region"
      data-role="message-attachments"
      role="region"
      aria-label="此消息的附件"
      tabindex="0"
    >
      <AttachmentCard
        v-for="file in attachments"
        :key="file.id"
        :file="file"
        :message="eventId"
        @preview="(url, name) => emit('zoom', url, name)"
      />
    </div>
    <div
      class="question-bubble whitespace-pre-wrap break-words rounded-[var(--dsw-radius-xl)] bg-bubble px-4 py-2.5 text-[length:var(--dsw-text-base)] leading-[22px] text-ink"
      :class="{ 'is-editing': editing }"
      data-role="turn-question"
    >
      <div v-if="props.images?.length" class="mb-2 flex flex-wrap justify-end gap-2">
        <img
          v-for="item in props.images"
          :key="item.url.length + item.name"
          :src="item.url"
          :alt="item.name"
          class="block max-h-[320px] max-w-full cursor-zoom-in rounded-card"
          style="border: 0.5px solid var(--dsw-alias-border-l1)"
          data-role="turn-image"
          @click="emit('zoom', item.url, item.name)"
        />
      </div>
      <img
        v-else-if="props.image"
        :src="props.image"
        :alt="props.imageName ?? '上传的图片'"
        class="mb-2 block max-h-[320px] max-w-full cursor-zoom-in rounded-card"
        style="border: 0.5px solid var(--dsw-alias-border-l1)"
        data-role="turn-image"
        @click="emit('zoom', props.image, props.imageName ?? '上传的图片')"
      />
      <template v-if="!editing">{{ learnerText(props.question) }}</template>
      <div v-else class="message-editor" data-role="message-editor">
        <textarea
          :value="editText"
          aria-label="编辑最新消息"
          rows="4"
          maxlength="4000"
          :disabled="actionsDisabled"
          @input="emit('update:editText', ($event.target as HTMLTextAreaElement).value)"
          @keydown.esc="emit('cancelEdit')"
        />
        <p v-if="editError" class="edit-error" role="status">{{ editError }}</p>
        <div class="editor-actions"
          ><button
            type="button"
            :disabled="actionsDisabled"
            data-action="cancel-edit"
            @click="emit('cancelEdit')"
            >取消</button
          ><button
            type="button"
            :disabled="actionsDisabled || !editText?.trim()"
            class="save-edit"
            data-action="save-edit"
            @click="emit('saveEdit')"
            >保存并发送</button
          ></div
        >
      </div>
    </div>
    <span
      v-if="formattedElapsed && !actions"
      class="text-[length:var(--dsw-text-sm)] leading-[18px] text-ink-3"
      data-role="question-meta"
      >{{ formattedElapsed }}</span
    >
    <MessageActions
      v-if="actions && !editing"
      :text="learnerText(question)"
      side="user"
      :latest="latest"
      :disabled="actionsDisabled"
      @edit="emit('edit')"
    />
  </article>
  <article class="mx-auto mb-4 max-w-[760px]">
    <div
      v-if="$slots.response"
      class="msg-body text-[length:var(--dsw-text-base)] leading-6 text-ink"
      ><slot name="response"
    /></div>
    <template v-else>
      <div
        v-if="props.answer"
        class="msg-body flex flex-col gap-4 text-[length:var(--dsw-text-base)] leading-6 text-ink"
        data-role="turn-answer"
      >
        <slot name="answer" />
      </div>
      <div v-if="props.loading" class="stream-progress" data-role="stream-progress" role="status">
        <UiIcon name="spinner" class="h-3.5 w-3.5" /><span>{{
          props.loadingText || (props.answer ? '正在继续生成…' : '模型正在分析并组织回答…')
        }}</span>
      </div>
      <div v-if="$slots.foot" class="mt-4 flex flex-col gap-1.5">
        <slot name="foot" />
      </div>
    </template>
    <footer
      v-if="props.model || (props.tools && !$slots.response) || props.error"
      class="mt-2 flex flex-wrap items-center gap-2 text-[length:var(--dsw-text-sm)] leading-[18px] text-ink-3"
      data-role="turn-tail"
    >
      <span v-if="props.model">{{ props.model }}</span>
      <span v-if="props.tools && !$slots.response">{{ props.tools }} 次工具调用</span>
      <span v-if="props.error" class="text-[var(--dsw-feedback-error-text)]">{{
        props.error
      }}</span>
    </footer>
    <MessageActions
      v-if="actions && completed && replyText"
      :text="learnerText(replyText)"
      side="assistant"
      :latest="latest"
      :disabled="actionsDisabled"
      :elapsed="formattedElapsed"
      @regenerate="emit('regenerate')"
      @branch="emit('branch')"
    />
  </article>
</template>

<style scoped>
.user-turn {
  width: 100%;
  min-width: 0;
}
.message-attachments {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  margin-bottom: 2px;
}
.message-attachments :deep(.attachment-card) {
  flex: 0 1 260px;
  min-width: 0;
}
.question-bubble {
  box-sizing: border-box;
  max-width: 70%;
  min-width: 0;
  overflow-wrap: anywhere;
}
.question-bubble.is-editing {
  width: 100%;
  max-width: 100%;
}
.message-editor {
  width: 100%;
  min-width: 0;
  white-space: normal;
}
.message-editor textarea {
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  min-height: 95px;
  max-height: 260px;
  resize: vertical;
  padding: 3px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: 1.6;
  outline: none;
}
.editor-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 9px;
}
.editor-actions button {
  border: 0;
  border-radius: 7px;
  padding: 5px 12px;
  background: var(--dsw-alias-bg-layer-1);
  color: inherit;
  font: inherit;
  font-size: var(--dsw-text-sm);
  cursor: pointer;
}
.editor-actions .save-edit {
  background: var(--dsw-action-fill);
  color: var(--dsw-action-ink);
}
.editor-actions button:disabled {
  opacity: 0.4;
  cursor: default;
}
[data-role='turn-tail'] > span,
.edit-error {
  min-width: 0;
  overflow-wrap: anywhere;
}
.edit-error {
  color: var(--dsw-feedback-error-text);
  font-size: var(--dsw-text-sm);
  margin: 5px 0;
  overflow-wrap: anywhere;
}
.stream-progress {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 8px 0 0;
  color: var(--dsw-alias-text-tertiary, #919aa7);
  font-size: var(--dsw-text-sm);
  line-height: 20px;
}
.msg-body :deep(p) {
  margin: 0;
}

.msg-body :deep(.md-table-scroll) {
  overflow-x: auto;
}

.msg-body :deep(table) {
  width: 100%;
  max-width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: var(--dsw-text-row);
  line-height: 20px;
}

.msg-body :deep(th),
.msg-body :deep(td) {
  padding: 6px 10px;
  border-bottom: 0.5px solid var(--dsw-alias-border-l2);
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.msg-body :deep(th) {
  color: var(--dsw-alias-text-secondary);
  font-weight: 500;
}

.msg-body :deep(h3) {
  margin: 0;
  font-size: var(--dsw-text-base);
  font-weight: 500;
}

.msg-body :deep(ol),
.msg-body :deep(ul) {
  margin: 0;
  padding-left: 20px;
}

.msg-body :deep(code) {
  padding: 1px 4px;
  border-radius: var(--dsw-radius-xs);
  background: var(--dsw-alias-bg-skeleton);
  font-family: var(--dsw-font-family-code);
  font-size: var(--dsw-text-row);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.msg-body :deep(pre) {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--dsw-radius-sm);
  background: var(--dsw-alias-bg-skeleton);
  overflow-x: auto;
}

.msg-body :deep(pre code) {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}
</style>
