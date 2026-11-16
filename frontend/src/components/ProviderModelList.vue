<script setup lang="ts">
import UiIcon from '@/components/UiIcon.vue';
import SettingsSwitch from '@/components/SettingsSwitch.vue';
import type { ConfiguredModel } from '@/utils/model-config';
defineProps<{
  models: ConfiguredModel[];
  selected: string;
  disabled?: boolean;
  loading?: boolean;
}>();
defineEmits<{
  add: [];
  edit: [model: ConfiguredModel];
  toggle: [id: string, value: boolean];
  select: [id: string];
  test: [model: ConfiguredModel];
  fetch: [];
}>();
const capacity = (size: number) =>
  size >= 1000000 ? `${+(size / 1000000).toFixed(1)}M` : `${+(size / 1000).toFixed(1)}K`;
</script>
<template>
  <section class="provider-models" aria-label="模型列表">
    <div class="section-heading"
      ><h3>模型列表</h3
      ><button
        type="button"
        class="text-action"
        :disabled="disabled || loading"
        @click="$emit('fetch')"
        >{{ loading ? '获取中…' : '获取可用模型' }}</button
      ><button
        type="button"
        class="add-model"
        :disabled="disabled"
        data-action="add-provider-model"
        @click="$emit('add')"
        ><UiIcon name="plus" />添加模型</button
      ></div
    >
    <TransitionGroup v-if="models.length" name="settings-list" tag="div" class="model-list">
      <div
        v-for="model in models"
        :key="model.id"
        class="model-row"
        :class="{ inactive: !model.enabled }"
        :data-model-row="model.id"
      >
        <button
          type="button"
          class="model-identity"
          :disabled="disabled || !model.enabled"
          :title="`使用 ${model.id}`"
          @click="$emit('select', model.id)"
          ><span class="model-id">{{ model.id }}</span
          ><span v-if="selected === model.id" class="model-badge selected">当前</span
          ><span v-if="model.context_window" class="model-badge">{{
            capacity(model.context_window)
          }}</span></button
        >
        <button
          type="button"
          class="icon-action"
          :disabled="disabled || !model.enabled"
          :aria-label="`测试模型 ${model.id}`"
          title="测试连接"
          @click="$emit('test', model)"
          ><UiIcon name="play-circle"
        /></button>
        <button
          type="button"
          class="icon-action"
          :disabled="disabled"
          :aria-label="`编辑模型 ${model.id}`"
          title="编辑模型配置"
          @click="$emit('edit', model)"
          ><UiIcon name="edit"
        /></button>
        <SettingsSwitch
          :model-value="model.enabled"
          :label="`启用模型 ${model.id}`"
          :disabled="disabled"
          @update:model-value="$emit('toggle', model.id, $event)"
        />
      </div>
    </TransitionGroup>
    <div v-else class="empty-models"
      ><UiIcon name="grid" /><p>暂未添加模型</p
      ><span>可获取上游模型目录，或填写模型 ID。</span></div
    >
  </section>
</template>
<style scoped>
.model-list {
  position: relative;
}
.model-row {
  box-sizing: border-box;
  transition: background-color 150ms ease-out;
}
.model-identity {
  transition: opacity 150ms ease-out;
}
.icon-action {
  transition:
    background-color 150ms ease-out,
    color 150ms ease-out;
}
.model-row.settings-list-enter-active,
.model-row.settings-list-leave-active {
  transition:
    opacity 160ms ease-out,
    transform 160ms ease-out;
}
.model-row.settings-list-move {
  transition: none;
}
@media (prefers-reduced-motion: reduce) {
  .model-row,
  .model-row.settings-list-enter-active,
  .model-row.settings-list-leave-active,
  .model-row.settings-list-move,
  .model-identity,
  .icon-action {
    transition: none;
  }
}
.section-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 9px;
}
.section-heading h3 {
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
  font-weight: 500;
  margin: 0 auto 0 0;
}
.text-action {
  min-height: 32px;
  border: 0;
  background: none;
  color: var(--settings-action-text);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.add-model {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  border: 1px solid var(--dsw-alias-border-l2);
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  border-radius: 7px;
  padding: 5px 8px;
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.add-model svg {
  width: 13px;
  height: 13px;
}
.model-list {
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  overflow: hidden;
}
.model-row {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 40px;
  padding: 0 12px;
}
.model-row + .model-row {
  border-top: 1px solid var(--dsw-alias-border-l2);
}
.model-row:hover {
  background: var(--dsw-specific-input-major);
}
.model-identity {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 1;
  min-width: 0;
  text-align: left;
  border: 0;
  background: none;
  padding: 9px 0;
  cursor: pointer;
  color: var(--dsw-alias-text-primary);
}
.model-id {
  font:
    12px ui-monospace,
    monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-badge {
  font-size: var(--dsw-text-xs);
  flex: none;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 5px;
  padding: 1px 4px;
  color: var(--dsw-alias-text-secondary);
}
.selected {
  color: var(--settings-action-text);
  border-color: var(--dsw-alias-border-l2);
  background: var(--dsw-selection-surface);
}
.icon-action {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: none;
  border: 0;
  border-radius: 5px;
  background: none;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.icon-action:hover {
  color: var(--dsw-alias-text-primary);
  background: var(--dsw-alias-bg-layer-2);
}
.icon-action svg {
  width: 14px;
  height: 14px;
}
.inactive .model-identity {
  opacity: 0.45;
}
.empty-models {
  padding: 28px 12px;
  text-align: center;
  border: 1px dashed var(--dsw-alias-border-l2);
  border-radius: 10px;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
}
.empty-models svg {
  width: 21px;
  height: 21px;
}
.empty-models p {
  margin: 8px 0 6px;
  font-size: var(--dsw-text-sm);
}
:disabled {
  cursor: default;
  opacity: 0.45;
}
</style>
