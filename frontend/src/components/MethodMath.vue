<script setup lang="ts">
import { computed } from 'vue';
import MarkdownText from '@/components/MarkdownText.vue';
import UiIcon from '@/components/UiIcon.vue';
import { vDisclosureMotion } from '@/utils/disclosure-motion';
import type { MethodMath } from '@/types';

const props = defineProps<{ lesson: MethodMath }>();
const text = computed(() =>
  [
    `**当前变体**\u3000${props.lesson.variant}`,
    props.lesson.formula
      ? `$$\n${props.lesson.formula}\n$$`
      : '**计算规则**\u3000此方法没有单一标准公式。',
    `**公式意义**\u3000${props.lesson.meaning}`,
    `**符号含义**\u3000${props.lesson.symbols}`,
    `**计算思想与步骤**\u3000${props.lesson.steps}`,
    `**适用条件**\u3000${props.lesson.conditions}`,
    props.lesson.example,
  ].join('\n\n'),
);
</script>

<template>
  <details v-disclosure-motion class="method-math" data-role="method-math">
    <summary>主要公式与计算过程<UiIcon name="chevron-down" /></summary>
    <div class="method-math-content">
      <MarkdownText :text="text" />
      <ul class="math-sources" aria-label="公式来源">
        <li v-for="source in lesson.sources" :key="source.url + source.section">
          <a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }}</a>
          <span> · {{ source.section }}</span>
        </li>
      </ul>
    </div>
  </details>
</template>

<style scoped>
.method-math {
  min-width: 0;
  max-width: 100%;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  font-size: var(--dsw-text-sm);
}
summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  cursor: pointer;
  font-weight: 600;
  list-style: none;
}
summary::-webkit-details-marker {
  display: none;
}
summary > svg {
  width: 14px;
  height: 14px;
  flex: none;
  color: var(--dsw-alias-text-secondary);
  transition: transform 200ms ease;
}
.method-math:is([open], [data-disclosure-expanded='true']) > summary > svg {
  transform: rotate(180deg);
}
.method-math[data-disclosure-expanded='false'] > summary > svg {
  transform: none;
}
summary:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 2px;
}
.method-math-content {
  min-width: 0;
  padding: 0 10px 10px;
  overflow-wrap: anywhere;
}
.math-sources {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
}
.math-sources {
  padding-left: 16px;
  margin-bottom: 0;
}
.math-sources li {
  margin-top: 6px;
}
.method-math-content :deep(.katex-display) {
  text-align: left;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}
@media (prefers-reduced-motion: reduce) {
  summary > svg {
    transition: none;
  }
}
</style>
