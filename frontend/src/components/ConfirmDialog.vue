<script setup lang="ts">
import { useDialogViewport } from '@/composables/useDialogMotion';
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue';
const props = defineProps<{
  open: boolean;
  title: string;
  message: string;
  confirm: string;
  busy?: boolean;
  secondary?: string;
}>();
const emit = defineEmits<{
  (event: 'confirm'): void;
  (event: 'cancel'): void;
  (event: 'secondary'): void;
}>();
const dialog = ref<HTMLDialogElement | null>(null);
useDialogViewport(dialog);
const id = useId();
watch(
  () => props.open,
  async () => {
    await nextTick();
    if (props.open && !dialog.value?.open) dialog.value?.showModal();
    if (!props.open && dialog.value?.open) dialog.value?.close();
  },
  { immediate: true },
);
function cancel() {
  if (!props.busy) emit('cancel');
}
function backdrop(event: MouseEvent) {
  if (event.target !== dialog.value) return;
  const box = dialog.value!.getBoundingClientRect();
  if (
    event.clientX < box.left ||
    event.clientX > box.right ||
    event.clientY < box.top ||
    event.clientY > box.bottom
  )
    cancel();
}
onBeforeUnmount(() => dialog.value?.close());
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="confirm-dialog"
      :aria-labelledby="id"
      :aria-describedby="`${id}-message`"
      data-role="delete-confirmation"
      @cancel.prevent="cancel"
      @click="backdrop"
    >
      <h2 :id="id">{{ title }}</h2>
      <p :id="`${id}-message`">{{ message }}</p>
      <div class="confirm-actions">
        <button
          type="button"
          class="ui-button ui-button-ghost"
          data-action="cancel-delete"
          autofocus
          :disabled="busy"
          @click="cancel"
          >取消</button
        >
        <button
          v-if="secondary"
          type="button"
          class="ui-button ui-button-ghost"
          data-action="delete-only-current"
          :disabled="busy"
          @click="emit('secondary')"
          >{{ secondary }}</button
        >
        <button
          type="button"
          class="ui-button confirm-danger"
          data-action="confirm-delete"
          :disabled="busy"
          @click="emit('confirm')"
          >{{ busy ? '删除中…' : confirm }}</button
        >
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.confirm-dialog {
  width: min(380px, calc(100vw - 32px));
  padding: 22px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 14px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  box-shadow: var(--dsw-elevation-panel);
}
.confirm-dialog::backdrop {
  background: rgb(0 0 0 / 0.25);
}
.confirm-dialog h2 {
  margin: 0 0 10px;
  font-size: var(--dsw-text-lg);
}
.confirm-dialog p {
  margin: 0;
  font-size: var(--dsw-text-row);
  line-height: 1.7;
  overflow-wrap: anywhere;
  color: var(--dsw-alias-text-secondary);
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
.confirm-danger {
  border: 0;
  background: #b92f34;
  color: #ffffff;
}
.confirm-danger:hover {
  background: #b92f34;
}
.confirm-actions button:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>
