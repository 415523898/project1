<script setup lang="ts">
import { frontendConfig } from '@/config';
import { computed } from 'vue';
import AssociationWarning from '@/components/AssociationWarning.vue';
import UiIcon from '@/components/UiIcon.vue';
import { useLearning } from '@/composables/useLearning';
import { learningCardStyle, type LearningCardStatus } from '@/utils/learning-card';
import type { StudyCardModel, StudyNode } from '@/services/study';
import { learnerText } from '@/utils/learner-text';
const props = defineProps<{
  card: StudyCardModel;
  node: StudyNode;
  selected: boolean;
  position: { x: number; y: number };
  sourceLabel: string;
  pendingReason?: string;
}>();
const learning = useLearning();
const methods = computed(() =>
  props.card.binding?.method_id ? [props.card.binding.method_id] : (props.card.method_ids ?? []),
);
const linkedToReference = computed(() => methods.value.length > 0);
const status = computed<LearningCardStatus>(() => {
  if (methods.value.some((id) => learning.learned.value.includes(id))) return 'learned';
  return (learning.curriculum.value?.nodes ?? []).some(
    (node) => node.studying && methods.value.includes(String(node.id)),
  )
    ? 'studying'
    : 'unlearned';
});
defineEmits<{
  pointer: [event: PointerEvent];
  select: [];
  source: [];
  learn: [];
  delete: [];
  level: [value: string];
}>();
</script>

<template>
  <article
    class="study-card route-card"
    :class="{ selected, locked: node.position_locked }"
    :style="{
      left: `${position.x}px`,
      top: `${position.y}px`,
      width: frontendConfig.canvas.study.cardWidth + 'px',
      height: frontendConfig.canvas.study.cardHeight + 'px',
      ...learningCardStyle(status, selected, linkedToReference),
    }"
    data-role="study-card"
    :data-card="card.card_id"
    :data-learning-status="status"
    :aria-label="`${learnerText(card.title)}${selected ? '，已选中' : ''}`"
    tabindex="0"
    @pointerdown.stop="$emit('pointer', $event)"
    @keydown.enter.stop="$emit('select')"
  >
    <header>
      <AssociationWarning
        v-if="card.binding?.session_missing"
        message="关联会话已删除；卡片与采用事实仍保留。"
      />
      <input
        class="card-number"
        type="text"
        inputmode="numeric"
        maxlength="3"
        :value="node.level_pin ?? node.level"
        :aria-label="`${card.title}的编号，留空自动计算`"
        data-role="study-card-number"
        @pointerdown.stop
        @change="$emit('level', ($event.target as HTMLInputElement).value)"
      />
      <span v-if="node.position_locked" class="lock-label" title="位置已固定">固定</span>
      <span v-if="pendingReason" class="lock-label" :title="pendingReason" data-role="study-pending"
        >待补充</span
      >
      <span
        v-if="status !== 'unlearned'"
        class="card-status"
        :class="status"
        :title="status === 'learned' ? '已学习' : '学习中'"
      >
        <UiIcon :name="status === 'learned' ? 'check' : 'clock'" class="h-[10px] w-[10px]" />
      </span>
      <button
        v-if="!sourceLabel || card.binding?.session_missing"
        type="button"
        class="source-action"
        data-action="study-learn"
        @pointerdown.stop
        @click.stop="$emit('learn')"
        >去学习<UiIcon name="arrow-up-right" class="h-3 w-3"
      /></button>
      <button
        v-if="sourceLabel"
        type="button"
        class="source-action"
        data-action="study-source"
        @pointerdown.stop
        @click.stop="$emit('source')"
        >{{ sourceLabel }}<UiIcon name="arrow-up-right" class="h-3 w-3"
      /></button>
      <button
        type="button"
        class="ui-icon-button delete-action"
        :aria-label="`删除卡片「${card.title}」`"
        title="删除卡片"
        data-action="study-delete"
        @pointerdown.stop
        @click.stop="$emit('delete')"
        ><UiIcon name="trash" class="h-3.5 w-3.5"
      /></button>
    </header>
    <span class="card-title" :title="learnerText(card.title)">{{ learnerText(card.title) }}</span>
    <span
      class="card-summary"
      :class="{ empty: !card.summary }"
      :title="card.summary || '点击卡片填写小结'"
      >{{ learnerText(card.summary || '点击卡片填写小结') }}</span
    >
  </article>
</template>

<style scoped>
.study-card {
  position: absolute;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  overflow: hidden;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  background: var(--dsw-alias-bg-layer-1);
  cursor: grab;
  touch-action: none;
  user-select: none;
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.06);
}
.study-card.selected {
  border-color: var(--dsw-focus-ring);
  box-shadow: 0 0 0 2px var(--dsw-selection-border);
  z-index: 2;
}
.study-card.locked {
  cursor: default;
}
header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
  height: 19px;
}
.card-number {
  box-sizing: border-box;
  width: 34px;
  height: 19px;
  border: 0;
  border-radius: 999px;
  padding: 0 6px;
  background: var(--dsw-alias-text-primary);
  color: var(--dsw-alias-text-inverted);
  font-size: var(--dsw-text-xs);
  font-weight: 600;
  text-align: center;
}
.source-action {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.delete-action {
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  margin-left: auto;
}
.source-action + .delete-action {
  margin-left: 0;
}
.lock-label {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
}
.card-status {
  display: grid;
  place-items: center;
  width: 15px;
  height: 15px;
  flex: none;
  border-radius: 50%;
  color: var(--dsw-static-neutral-bluish-1000);
}
.card-status.studying {
  background: #f59e0b;
}
.card-status.learned {
  background: #22a06b;
}
.card-title,
.card-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
  flex: none;
}
.card-title {
  height: 36px;
  font-size: var(--dsw-text-row);
  font-weight: 500;
  line-height: 18px;
}
.card-summary {
  height: 32px;
  font-size: var(--dsw-text-sm);
  line-height: 16px;
  color: var(--dsw-alias-text-secondary);
}
.empty {
  color: var(--dsw-alias-text-tertiary);
}

/* Refined study card */
.study-card {
  padding: 11px 12px 10px;
  gap: 3px;
}
header {
  height: 21px;
  gap: 6px;
}
.card-number {
  width: 36px;
  height: 20px;
  padding: 0 7px;
  border-radius: 7px;
  background: #eef3ff;
  color: #1c3f8a;
  box-shadow: inset 0 0 0 1px #d7e3fb;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.card-number:focus {
  outline: 2px solid #7fa0ff;
  outline-offset: 1px;
}
.source-action {
  gap: 3px;
  padding: 2px 4px;
  border-radius: 5px;
  color: #7b879c;
  font-size: 9.5px;
  line-height: 1.4;
  transition:
    color 150ms ease,
    background 150ms ease;
}
.source-action:hover {
  background: #eef3fb;
  color: #315fbd;
}
.source-action svg {
  width: 11px;
  height: 11px;
}
.delete-action {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  color: #9aa7ba;
}
.delete-action:hover {
  background: #fdecec;
  color: #b63d30;
}
.lock-label {
  padding: 1px 5px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f8faff;
  color: #8a96ab;
  font-size: 8px;
  line-height: 1.5;
}
.card-status {
  width: 15px;
  height: 15px;
  box-shadow: 0 3px 8px -4px rgb(20 40 80 / 0.45);
}
.card-status.studying {
  background: #f59e0b;
}
.card-status.learned {
  background: #22a06b;
}
.card-title {
  margin-top: 3px;
  height: 36px;
  color: #14213a;
  font-size: 13px;
  font-weight: 650;
  line-height: 18px;
  letter-spacing: -0.005em;
}
.card-summary {
  height: 32px;
  color: #7b879c;
  font-size: 10.5px;
  line-height: 16px;
}
.empty {
  color: #9aa7ba;
}
</style>
