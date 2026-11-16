<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import { attachmentUrl } from '@/services/attachments';
import type { ChatAttachment } from '@/types';
import '@/styles/attachments.css';

const props = defineProps<{
  file: ChatAttachment;
  message?: string;
  state?: 'queued' | 'preparing' | 'uploading' | 'ready' | 'error';
  error?: string;
  removable?: boolean;
}>();
const emit = defineEmits<{ remove: []; retry: []; preview: [url: string, name: string] }>();
const type = computed(() => props.file.name.split('.').pop()?.toUpperCase().slice(0, 10) || '文件');
const size = computed(() =>
  props.file.size >= 1024 * 1024
    ? `${(props.file.size / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.ceil(props.file.size / 1024))} KB`,
);
const ready = computed(() => !props.state || props.state === 'ready');
const status = computed(
  () =>
    props.error ||
    {
      queued: '等待处理',
      preparing: '正在解码音频',
      uploading: '正在上传和读取',
      error: '上传失败',
      ready: '',
    }[props.state ?? 'ready'] ||
    {
      text: '正文可供模型读取',
      image: '需要模型支持图片输入',
      unreadable: '仅文件 · 正文不可读',
      error: '已上传 · 正文读取失败',
    }[props.file.read_status],
);
const icon = computed(() =>
  props.file.kind === 'table'
    ? 'table'
    : props.file.kind === 'audio'
      ? 'microphone'
      : props.file.kind === 'image'
        ? 'image'
        : 'file-document',
);
const summary = computed(
  () =>
    ({ queued: '等待', preparing: '解码中', uploading: '上传中', error: '上传失败', ready: '' })[
      props.state ?? 'ready'
    ] ||
    { text: '可读取', image: '图片', unreadable: '仅文件', error: '读取失败' }[
      props.file.read_status
    ],
);
const details = ref<HTMLDialogElement | null>(null);
onBeforeUnmount(() => {
  if (details.value?.open) details.value.close();
});
</script>
<template>
  <div
    class="attachment-card"
    :data-kind="file.kind"
    :data-format="type"
    :data-state="state ?? 'ready'"
    data-role="attachment-card"
    :title="`${file.name}\n${status}\n${file.note}`"
  >
    <button
      v-if="ready && file.read_status === 'image'"
      type="button"
      class="attachment-icon attachment-preview"
      :aria-label="`预览 ${file.name}`"
      @click="emit('preview', attachmentUrl(file, 'preview', message), file.name)"
      ><img :src="attachmentUrl(file, 'preview', message)" :alt="file.name"
    /></button>
    <span v-else class="attachment-icon"><UiIcon :name="icon" /></span>
    <div class="attachment-info">
      <a
        v-if="ready"
        class="attachment-name"
        :href="attachmentUrl(file, 'download', message)"
        :download="file.name"
        >{{ file.name }}</a
      >
      <span v-else class="attachment-name">{{ file.name }}</span>
      <button
        type="button"
        class="attachment-caption"
        :aria-label="`查看 ${file.name} 的状态与读取说明`"
        @click="details?.showModal()"
      >
        <span class="attachment-type">{{ type }} · {{ size }}</span
        ><span class="attachment-state" role="status">{{ summary }}</span>
      </button>
    </div>
    <dialog ref="details" class="attachment-details" :aria-label="`附件详情：${file.name}`">
      <strong>{{ file.name }}</strong
      ><p>{{ type }} · {{ size }} · {{ status }}</p
      ><p v-if="file.note">{{ file.note }}</p>
      <button type="button" class="details-close" @click="details?.close()">关闭</button>
    </dialog>
    <div v-if="removable" class="attachment-actions">
      <button
        v-if="state === 'error' || (ready && file.read_status === 'error')"
        type="button"
        :aria-label="`重试 ${file.name}`"
        data-action="retry-attachment"
        @click="emit('retry')"
        ><UiIcon name="regenerate"
      /></button>
      <button
        type="button"
        :aria-label="`移除 ${file.name}`"
        data-action="remove-attachment"
        @click="emit('remove')"
        ><UiIcon name="close"
      /></button>
    </div>
  </div>
</template>
<style scoped>
.attachment-card {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 1 232px;
  min-width: 0;
  max-width: 100%;
  height: 56px;
  padding: 8px 10px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 9px;
  background: var(--dsw-alias-bg-layer-1);
  white-space: normal;
  text-align: left;
}
.attachment-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 30px;
  height: 34px;
  border: 0;
  border-radius: 6px;
  padding: 0;
  background: var(--dsw-alias-bg-layer-2);
  color: var(--dsw-static-deepseek-500);
}
.attachment-icon svg {
  width: 20px;
  height: 20px;
}
[data-kind='table'] > .attachment-icon {
  color: #469467;
}
[data-kind='audio'] > .attachment-icon {
  color: #9470b2;
}
[data-state='error'] {
  border-color: var(--dsw-feedback-error-text);
}
.attachment-preview {
  cursor: zoom-in;
  overflow: hidden;
}
.attachment-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.attachment-info {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.attachment-name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  line-height: 18px;
  color: var(--dsw-alias-text-primary);
  text-decoration: none;
}
.attachment-name[href]:hover {
  text-decoration: underline;
}
.attachment-name[href] {
  /* Grow upward into unused padding; text and the second row keep their geometry. */
  padding-top: 6px;
  margin-top: -6px;
}
.attachment-card :is(button, a):focus-visible {
  outline: 2px solid var(--dsw-focus-ring);
  outline-offset: 2px;
}
.attachment-type {
  font-size: 11px;
  color: var(--dsw-alias-text-secondary);
}
.attachment-state {
  color: var(--dsw-alias-text-secondary);
}
.attachment-actions {
  display: flex;
  flex: none;
  gap: 2px;
}
.attachment-actions button {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 4px;
  padding: 2px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.attachment-actions button:hover {
  background: var(--dsw-alias-bg-layer-2);
  color: var(--dsw-alias-text-primary);
}
.attachment-actions svg {
  width: 13px;
  height: 13px;
}
.attachment-caption {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 5px;
  min-width: 0;
  max-width: 100%;
  height: 14px;
  line-height: 14px;
  white-space: nowrap;
  border: 0;
  padding: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.attachment-caption::after {
  /* 14px visible row, 24px pointer target within the card's bottom padding. */
  content: '';
  position: absolute;
  inset: 0 0 -10px;
}
.attachment-type {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 10px;
}
.attachment-state {
  flex: none;
  font-size: 10px;
  line-height: 14px;
}
.attachment-caption:hover .attachment-state {
  text-decoration: underline;
}
.attachment-details {
  box-sizing: border-box;
  width: min(420px, calc(100vw - 32px));
  padding: 18px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 12px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  font-size: var(--dsw-text-row);
  line-height: 1.65;
  overflow-wrap: anywhere;
  max-height: 80dvh;
  overflow: auto;
}
.attachment-details::backdrop {
  background: #17203350;
}
.attachment-details strong {
  font-size: 14px;
}
.attachment-details p {
  margin: 9px 0;
  color: var(--dsw-alias-text-secondary);
}
.details-close {
  min-height: 32px;
  display: block;
  margin: 14px 0 0 auto;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  padding: 4px 12px;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
[data-format='PDF'] > .attachment-icon {
  color: #c85d50;
}
@media (max-width: 560px) {
  .attachment-card {
    flex-basis: 80%;
    max-width: 80%;
  }
}
</style>
