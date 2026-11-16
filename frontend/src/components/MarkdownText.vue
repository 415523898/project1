<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { renderMarkdown } from '@/utils/markdown';
import { learnerText } from '@/utils/learner-text';
import { addMarkdownCopies } from '@/utils/content-copy';
import '@/styles/content-copy.css';

const props = withDefaults(defineProps<{ text: string; copyable?: boolean }>(), { copyable: true });
const host = ref<HTMLElement | null>(null);
let cleanup: (() => void) | undefined;

function paint(): void {
  cleanup?.();
  if (host.value) {
    renderMarkdown(host.value, learnerText(props.text));
    cleanup = props.copyable ? addMarkdownCopies(host.value) : undefined;
  }
}

onMounted(paint);
watch(() => [props.text, props.copyable], paint);
onBeforeUnmount(() => cleanup?.());
</script>

<template>
  <div ref="host" class="markdown-body"></div>
</template>

<style scoped>
.markdown-body p {
  margin: 0 0 8px;
}
.markdown-body {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
}
.markdown-body :deep(hr) {
  margin: 16px 0;
  border: 0;
  border-top: 1px solid var(--dsw-alias-border-l2);
}
.markdown-body :deep(pre),
.markdown-body :deep(.md-table-scroll) {
  max-width: 100%;
  overflow-x: auto;
}
.markdown-body :deep(pre) {
  white-space: pre;
}
.markdown-body :deep(pre code) {
  white-space: pre !important;
  overflow-wrap: normal;
  word-break: normal;
}
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 12px 0 8px;
  font-size: 1.05em;
  font-weight: 600;
}

.markdown-body p:last-child {
  margin-bottom: 0;
}

.markdown-body ol {
  margin: 0 0 8px;
  padding-left: 20px;
}

.markdown-body pre {
  margin: 0 0 8px;
  padding: 8px 10px;
  overflow-x: auto;
  border-radius: var(--dsw-radius-sm);
  background: var(--dsw-specific-input-major);
  font-family: var(--dsw-font-family-code);
  font-size: var(--dsw-text-sm);
}

.markdown-body h4 {
  margin: 10px 0 6px;
  font-size: var(--dsw-text-row);
  font-weight: 500;
}

.markdown-body blockquote {
  margin: 0 0 8px;
  padding-left: 10px;
  border-left: 2px solid var(--dsw-alias-border-l2);
  color: var(--dsw-alias-text-secondary);
}
.markdown-body :deep(.katex-display) {
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 0;
  margin: 10px 0;
}
.markdown-body :deep(.katex) {
  font-size: 1.08em;
}
.markdown-body :deep(.math-source) {
  overflow-wrap: anywhere;
}
</style>
