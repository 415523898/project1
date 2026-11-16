<script setup lang="ts">
import { RouterLink } from 'vue-router';
import { useLab } from '@/composables/useLab';
import { useLearningExploration } from '@/composables/useLearningExploration';
import { useMethodGraph } from '@/composables/useMethodGraph';
import AssociationWarning from '@/components/AssociationWarning.vue';
const lab = useLab(),
  library = useMethodGraph(),
  assist = useLearningExploration(lab),
  state = assist.state;
</script>
<template>
  <div class="learning-return-bar" data-role="learning-return-bar">
    <RouterLink
      v-if="state.binding"
      class="learning-match"
      :to="{ path: '/learning', query: { card: state.binding.method_id } }"
      data-action="return-learning"
      >已绑定：{{ library.label(state.binding.method_id) }}</RouterLink
    >
    <span
      v-if="lab.state?.authExpired"
      class="learning-suggestion drift"
      role="status"
      data-role="auth-expired-notice"
      >登录已失效，已完成的实验结果仍保留。<RouterLink
        class="learning-match"
        :to="{ path: '/signin', query: { next: '/' } }"
        >重新登录</RouterLink
      ></span
    >
    <AssociationWarning
      v-if="state.binding?.card_missing"
      message="关联卡片已删除，会话仍可继续。"
    />
    <span
      v-if="!lab.state?.authExpired && state.drift_id"
      class="learning-suggestion drift"
      role="status"
      data-role="method-drift-notice"
    >
      建议使用新会话进行学习新方法，以获得更好的效果
      <button
        type="button"
        class="learning-match"
        data-action="continue-new-method"
        :disabled="lab.state?.busy || assist.forking?.value"
        title="继承截至最近完整回复的上下文，单独学习新方法"
        @click="assist.newChat(library.label(state.drift_id))"
        >新会话</button
      >
      <button
        type="button"
        class="dismiss"
        data-action="dismiss-method-drift"
        aria-label="关闭新方法学习提示"
        @click="assist.dismissDrift"
        >×</button
      >
    </span>
    <span
      v-if="
        !lab.state?.authExpired &&
        (assist.error.value || state.last_error || state.maintenance_error)
      "
      class="learning-note"
      role="status"
      >{{ assist.error.value || state.last_error || state.maintenance_error }}</span
    >
  </div>
</template>
<style scoped>
.learning-return-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  font-size: var(--dsw-text-sm);
}
.learning-match {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border: 1px solid #dbe4ff;
  border-radius: 7px;
  background: var(--dsw-selection-surface);
  color: #3355cc;
  text-decoration: none;
  font: inherit;
  cursor: pointer;
}
.learning-suggestion {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  color: var(--dsw-alias-text-secondary);
}
.drift {
  padding: 4px 8px;
  border-radius: 7px;
  background: var(--dsw-feedback-warning-surface);
  color: var(--dsw-feedback-warning-text);
}
.dismiss {
  border: 0;
  background: transparent;
  color: inherit;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
}
.learning-note {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
}
</style>
