<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { bindCopyButton, copyContent, type CopyKind } from '@/utils/content-copy';
import '@/styles/content-copy.css';
import UiIcon from '@/components/UiIcon.vue';

const props = withDefaults(defineProps<{ kind?: CopyKind; text?: string; copyable?: boolean }>(), {
  kind: 'code',
  copyable: true,
});
const content = ref<HTMLElement | null>(null);
const button = ref<HTMLButtonElement | null>(null);
let cleanup: (() => void) | undefined;
onMounted(() => {
  if (!props.copyable || !button.value) return;
  cleanup = bindCopyButton(
    button.value,
    () => props.text ?? (content.value ? copyContent(content.value, props.kind) : ''),
    props.kind,
  );
});
onBeforeUnmount(() => cleanup?.());
</script>

<template>
  <div class="copy-region" :data-copy-kind="kind">
    <button
      v-if="copyable"
      ref="button"
      type="button"
      class="content-copy-button"
      data-action="copy-content"
    >
      <UiIcon name="copy" />
    </button>
    <div ref="content" class="copy-content"><slot /></div>
  </div>
</template>
