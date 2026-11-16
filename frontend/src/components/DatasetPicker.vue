<script setup lang="ts">
import { computed, ref } from 'vue';
import CurrentDataset from '@/components/CurrentDataset.vue';
import DatasetLibrary from '@/components/DatasetLibrary.vue';
import UiIcon from '@/components/UiIcon.vue';
import { useLab } from '@/composables/useLab';

const lab = useLab();
const restoring = ref(false);
const chooser = ref<HTMLDialogElement | null>(null);
const error = ref('');
const manual = computed(() => Boolean(lab.activeDataset.value));

async function chooseAutomatic(): Promise<void> {
  if (restoring.value || lab.state.busy) return;
  if (!lab.activeDataset.value) return;
  restoring.value = true;
  error.value = '';
  try {
    await lab.chooseDataset(null);
  } catch (problem) {
    error.value = (problem as Error).message;
  } finally {
    restoring.value = false;
  }
}

function browse(): void {
  if (lab.state.busy) return;
  error.value = '';
  if (!chooser.value?.open) chooser.value?.showModal();
}

function closeChooser(): void {
  chooser.value?.close();
}
</script>

<template>
  <section class="dataset-panel" data-role="dataset-panel" aria-label="数据集">
    <div class="source-choice" role="group" aria-label="数据来源">
      <button
        type="button"
        class="source-option"
        data-action="automatic-dataset"
        :aria-pressed="!manual"
        :disabled="restoring || lab.state.busy"
        @click="chooseAutomatic"
        ><UiIcon name="sparkles" />AI 自动选择</button
      >
      <button
        type="button"
        class="source-option"
        data-action="manual-dataset"
        :aria-pressed="manual"
        :disabled="lab.state.busy"
        @click="browse"
        ><UiIcon name="table" />手动指定</button
      >
    </div>
    <CurrentDataset class="dataset-primary" />
    <p v-if="error" class="dataset-error" role="alert">{{ error }}</p>
    <dialog
      ref="chooser"
      class="dataset-library-dialog"
      aria-label="选择当前会话的数据集"
      @cancel.prevent="closeChooser"
    >
      <header class="library-dialog-head"
        ><div
          ><h2>选择当前会话的数据</h2
          ><p>浏览数据不会切换来源；点击“用于当前会话”才会应用。</p></div
        ><button
          type="button"
          class="library-dialog-close"
          aria-label="关闭"
          @click="closeChooser"
          ><UiIcon name="close" /></button
        ></header
      >
      <div class="library-dialog-body">
        <DatasetLibrary apply-to-session @close="closeChooser" />
      </div>
    </dialog>
  </section>
</template>

<style scoped>
.dataset-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  color: var(--dsw-alias-text-primary);
}
.source-choice {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  background: var(--dsw-specific-sidebar-fill);
}
.source-option {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 0;
  padding: 7px 6px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.source-option[aria-pressed='true'] {
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-link);
  box-shadow: 0 1px 3px #1d2d4814;
}
.source-option svg {
  width: 14px;
  height: 14px;
  flex: none;
}
.dataset-primary {
  min-width: 0;
  background: var(--dsw-alias-bg-layer-1);
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 12px;
}
.dataset-error {
  margin: 0;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-feedback-error-text);
}
.dataset-library-dialog {
  width: min(980px, calc(100vw - 32px));
  max-height: min(86dvh, 860px);
  padding: 0;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 14px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  overflow: hidden;
}
.dataset-library-dialog::backdrop {
  background: #1d2d4833;
}
.library-dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--dsw-alias-border-l2);
}
.library-dialog-head h2 {
  margin: 0;
  font-size: var(--dsw-text-base);
}
.library-dialog-head p {
  margin: 5px 0 0;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
  line-height: 1.6;
}
.library-dialog-close {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: none;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.library-dialog-close:hover {
  background: var(--dsw-specific-sidebar-fill);
}
.library-dialog-close svg {
  width: 16px;
  height: 16px;
}
.library-dialog-body {
  max-height: min(72dvh, 760px);
  padding: 16px 20px 20px;
  overflow: auto;
  overscroll-behavior: contain;
}
.library-dialog-body :deep(.dataset-list) {
  height: 420px;
}
.library-dialog-body :deep(.dataset-footer) {
  position: sticky;
  bottom: 0;
  z-index: 2;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: 0 -1px 0 var(--dsw-alias-border-l2);
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  outline-offset: 3px;
}
@media (max-width: 520px) {
  .library-dialog-head,
  .library-dialog-body {
    padding-inline: 14px;
  }
}
</style>
