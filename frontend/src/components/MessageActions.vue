<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
const props = defineProps<{
  text: string;
  side: 'user' | 'assistant';
  latest?: boolean;
  disabled?: boolean;
  elapsed?: string;
}>();
const emit = defineEmits<{ edit: []; regenerate: []; branch: [] }>();
const copied = ref(false),
  error = ref('');
let timer: ReturnType<typeof setTimeout> | undefined;
async function copy() {
  error.value = '';
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(props.text);
    else {
      const field = document.createElement('textarea');
      field.value = props.text;
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.append(field);
      try {
        field.select();
        if (!document.execCommand('copy')) throw new Error('copy');
      } finally {
        field.remove();
      }
    }
    copied.value = true;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => (copied.value = false), 1800);
  } catch {
    error.value = '复制未成功，请选中文字复制。';
  }
}
onBeforeUnmount(() => {
  if (timer) clearTimeout(timer);
});
</script>
<template>
  <div
    class="message-actions"
    :class="side"
    :data-role="`${side}-actions`"
    :aria-label="side === 'user' ? '用户消息操作' : '回复操作'"
  >
    <button
      type="button"
      class="message-action"
      :aria-label="copied ? '已复制' : side === 'user' ? '复制消息' : '复制回复'"
      :data-tooltip="copied ? '已复制' : '复制'"
      data-action="copy-message"
      :disabled="!text"
      @click="copy"
      ><UiIcon :name="copied ? 'check' : 'copy'"
    /></button>
    <button
      v-if="side === 'user' && latest"
      type="button"
      class="message-action"
      aria-label="编辑消息"
      data-tooltip="编辑"
      data-action="edit-message"
      :disabled="disabled"
      @click="emit('edit')"
      ><UiIcon name="edit"
    /></button>
    <button
      v-if="side === 'assistant' && latest"
      type="button"
      class="message-action"
      aria-label="重新生成回复"
      data-tooltip="重新生成回复"
      data-action="regenerate-reply"
      :disabled="disabled"
      @click="emit('regenerate')"
      ><UiIcon name="regenerate"
    /></button>
    <button
      v-if="side === 'assistant'"
      type="button"
      class="message-action branch-action"
      aria-label="分支到新聊天"
      data-action="branch-reply"
      :disabled="disabled"
      @click="emit('branch')"
      ><UiIcon name="branch" /><span class="branch-tooltip" aria-hidden="true"
        ><UiIcon name="branch" />分支到新聊天</span
      ></button
    >
    <span v-if="elapsed" class="action-time">{{ elapsed }}</span>
    <span class="sr-only" role="status">{{ copied ? '已复制' : error }}</span>
    <span v-if="error" class="copy-error">{{ error }}</span>
  </div>
</template>
<style scoped>
.message-actions {
  display: flex;
  align-items: center;
  gap: 3px;
  min-height: 30px;
  margin-top: 5px;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
  line-height: 18px;
}
.message-actions.user {
  justify-content: flex-end;
  margin-top: 0;
}
.message-action {
  position: relative;
  display: grid;
  place-items: center;
  flex: none;
  width: 29px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
  transition:
    background 140ms,
    color 140ms;
}
.message-action:hover,
.message-action:focus-visible {
  background: var(--dsw-alias-bg-skeleton);
  color: var(--dsw-alias-text-primary);
}
.message-action:disabled {
  opacity: 0.35;
  cursor: default;
}
.message-action::after {
  content: attr(data-tooltip);
  position: absolute;
  z-index: 30;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%) translateY(-2px);
  padding: 5px 9px;
  border-radius: 7px;
  background: #282a2e;
  color: #fff;
  font-size: var(--dsw-text-sm);
  line-height: 18px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition:
    opacity 120ms,
    transform 120ms;
  box-shadow: 0 3px 10px #0002;
}
.message-action:hover::after,
.message-action:focus-visible::after {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.branch-action::after {
  content: none;
}
.branch-tooltip {
  position: absolute;
  z-index: 30;
  top: calc(100% + 6px);
  left: 50%;
  display: flex;
  align-items: center;
  gap: 7px;
  transform: translateX(-50%) translateY(-2px);
  padding: 7px 11px;
  border: 1px solid #ffffff1a;
  border-radius: 9px;
  background: #282a2e;
  color: #fff;
  font-size: var(--dsw-text-sm);
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  box-shadow: 0 3px 10px #0002;
  transition:
    opacity 120ms,
    transform 120ms;
}
.branch-action:hover .branch-tooltip,
.branch-action:focus-visible .branch-tooltip {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.action-time {
  margin-left: 4px;
  font-variant-numeric: tabular-nums;
}
.copy-error {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--dsw-feedback-error-text);
}
@media (prefers-reduced-motion: reduce) {
  .message-action,
  .message-action::after,
  .branch-tooltip {
    transition: none;
  }
}
</style>
