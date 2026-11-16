<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import AssociationWarning from '@/components/AssociationWarning.vue';
import UiIcon from '@/components/UiIcon.vue';
import ModelAccessAction from '@/components/ModelAccessAction.vue';
import { RouterLink } from 'vue-router';
import { useLab } from '@/composables/useLab';
import { useLearning } from '@/composables/useLearning';
import { useStudy } from '@/composables/useStudy';
import { useConsent } from '@/composables/useConsent';
import { createSessionCardsState } from '@/composables/useSessionCards';
import { createSessionCard } from '@/services/learning-exploration';
import { learnerText } from '@/utils/learner-text';

const lab = useLab(),
  study = useStudy(),
  consent = useConsent(),
  state = createSessionCardsState();
const learning = useLearning();
const { data, job, running, loading, starting, error } = state;
const localError = ref('');
const matching = ref(false);
let matchingRequest: AbortController | null = null;
const cards = computed(() => data.value?.cards ?? []);
const cardLink = computed(() => ({
  path: '/route',
  query: { card: data.value?.binding?.card_id ?? cards.value[0]?.card_id },
}));
const progress = computed(() => job.value?.progress);
const status = computed(() =>
  starting.value
    ? '正在提交更新，准备本轮学习内容…'
    : state.readingResult.value
      ? '卡片已提交，正在读取已保存结果…'
      : job.value?.reused
        ? '学习内容未变化，已复用已有结果。'
        : progress.value?.message || '',
);
const issue = computed(() => localError.value || error.value || job.value?.failure?.error || '');
const methodId = computed(() => data.value?.binding?.method_id);
const learned = computed(() => !!methodId.value && learning.learned.value.includes(methodId.value));
watch(methodId, (id) => {
  if (id) void learning.refresh();
});
async function markLearned() {
  const id = methodId.value,
    owner = lab.state.user,
    session = lab.state.sessionId;
  if (!id || learning.progressBusy.value || lab.state.authExpired) return;
  const ok = await learning.setDone(id, !learned.value);
  if (owner === lab.state.user && session === lab.state.sessionId)
    localError.value = ok ? '' : learning.error.value;
}
async function retry() {
  if (
    matching.value ||
    loading.value ||
    running.value ||
    lab.state.busy ||
    lab.state.authExpired ||
    data.value?.binding?.card_missing
  )
    return;
  localError.value = '';
  if (!consent.agreed.value) {
    localError.value = '请先在接口设置中同意数据使用说明。';
    return;
  }
  if (lab.configurationIssue.value) {
    localError.value = lab.configurationIssue.value;
    return;
  }
  await state.start('', lab.config());
}
async function maintainCard() {
  if (state.syncFailed.value) {
    try {
      await state.refresh();
    } catch {
      localError.value = '仍无法读取结果，请恢复连接后重试。';
    }
    return;
  }
  if (data.value?.binding) await retry();
  else await matchCard();
}
async function matchCard() {
  if (matching.value || lab.state.busy || !lab.state.sessionId || !lab.state.user) return;
  localError.value = '';
  if (!consent.agreed.value) {
    localError.value = '请先在接口设置中同意数据使用说明。';
    return;
  }
  if (lab.configurationIssue.value) {
    localError.value = lab.configurationIssue.value;
    return;
  }
  const owner = lab.state.user,
    session = lab.state.sessionId,
    controller = new AbortController();
  matchingRequest = controller;
  matching.value = true;
  const timeout = setTimeout(() => controller.abort(), 100000);
  try {
    const result = await createSessionCard(session, lab.config(), controller.signal);
    if (owner !== lab.state.user || session !== lab.state.sessionId) return;
    if (!result.created) throw new Error('没有生成学习卡片，请重试。');
    await state.refresh();
    if (owner !== lab.state.user || session !== lab.state.sessionId) return;
    await Promise.all([lab.refreshSessions(), study.open(owner, true), learning.refresh()]);
  } catch (problem) {
    if (owner === lab.state.user && session === lab.state.sessionId)
      localError.value = (problem as Error).message;
  } finally {
    clearTimeout(timeout);
    if (matchingRequest === controller) {
      matching.value = false;
      matchingRequest = null;
    }
  }
}
watch(
  () => [lab.state.user, lab.state.sessionId] as const,
  async ([owner, session]) => {
    matchingRequest?.abort();
    matchingRequest = null;
    matching.value = false;
    localError.value = '';
    await state.bind(owner || '', session || '');
  },
  { immediate: true },
);
const ensuring = ref(false);
const ensured = new Set<string>();
async function ensureCard() {
  const owner = lab.state.user,
    session = lab.state.sessionId,
    key = owner && session ? owner + '/' + session : '';
  if (
    !owner ||
    !session ||
    !key ||
    ensuring.value ||
    matching.value ||
    running.value ||
    loading.value ||
    starting.value ||
    lab.state.busy ||
    lab.state.authExpired ||
    !data.value ||
    data.value.binding ||
    cards.value.length ||
    ensured.has(key) ||
    lab.providerLoading.value ||
    !consent.agreed.value ||
    lab.configurationIssue.value
  )
    return;
  ensured.add(key);
  ensuring.value = true;
  try {
    const result = await createSessionCard(session, lab.config());
    if (owner === lab.state.user && session === lab.state.sessionId && result.created)
      await state.refresh();
  } catch {
    // Automatic generation is best effort; the button stays available.
  } finally {
    ensuring.value = false;
  }
}
watch(
  () =>
    [
      lab.state.user,
      lab.state.sessionId,
      data.value?.stamp,
      cards.value.length,
      data.value?.binding,
      lab.providerLoading.value,
      consent.agreed.value,
    ] as const,
  () => void ensureCard(),
  { immediate: true },
);
const timer = setInterval(() => {
  if (
    lab.state.user &&
    lab.state.sessionId &&
    !lab.state.authExpired &&
    !loading.value &&
    !running.value &&
    !state.syncFailed.value
  )
    void state.refresh().catch(() => {});
}, 2500);
watch(
  () =>
    [
      data.value?.graph_revision,
      data.value?.layout_revision,
      data.value?.job?.operation_id,
    ] as const,
  async () => {
    const current = data.value?.job;
    if (current?.status === 'succeeded' && current.result && lab.state.user)
      await study.acceptExternal(lab.state.user, current.result);
  },
);
const seconds = (value?: number) => `${((value ?? 0) / 1000).toFixed(2)} 秒`;
onBeforeUnmount(() => {
  matchingRequest?.abort();
  clearInterval(timer);
  state.reset();
});
</script>

<template>
  <section class="session-cards" data-role="session-cards-panel" aria-label="会话学习卡片">
    <header class="session-card-intro"
      ><div class="session-card-heading"
        ><h3>会话学习卡片</h3
        ><RouterLink
          v-if="cards.length"
          :to="cardLink"
          class="view-learning-card"
          data-action="view-learning-card"
          ><UiIcon name="book-open" /><span>查看学习卡片</span
          ><UiIcon name="arrow-up-right" /></RouterLink></div
      ><p>每个会话的第一轮回答完成后会自动生成一张复习卡片；绑定方法后，可以手动让 AI 更新方法卡片。</p></header
    >
    <template v-if="lab.state.sessionId">
      <p v-if="!data?.binding" class="session-card-note"
        >{{
          cards.length
            ? '尚未绑定方法；已按本会话生成一张复习卡片。'
            : '尚未绑定方法；第一轮回答完成后会自动生成一张复习卡片。'
        }}</p
      >
      <p v-else-if="data.binding.card_missing" class="session-card-note"
        ><AssociationWarning message="关联卡片已删除；会话仍可继续。" />
        关联卡片已删除，会话仍可继续。</p
      >
      <div class="session-card-actions" role="group" aria-label="学习卡片操作">
        <button
          class="match-session-card"
          type="button"
          data-action="match-session-card"
          :disabled="
            ensuring ||
            matching ||
            loading ||
            running ||
            lab.state.busy ||
            lab.state.authExpired ||
            lab.providerLoading.value ||
            !!data?.binding?.card_missing
          "
          @click="maintainCard"
          ><UiIcon :name="matching || running || ensuring ? 'spinner' : 'sparkles'" /><span>{{
            ensuring
              ? '正在生成会话卡片…'
              : matching
                ? cards.length
                  ? '正在更新会话卡片…'
                  : '正在生成会话卡片…'
                : running
                  ? '正在更新学习卡片…'
                  : state.syncFailed.value
                    ? '重新读取更新结果'
                    : data?.binding || cards.length
                      ? '让AI更新学习卡片'
                      : '从会话生成学习卡片'
          }}</span></button
        >
        <button
          v-if="methodId"
          type="button"
          class="session-mark-learned"
          data-action="session-mark-learned"
          :aria-pressed="learned"
          :disabled="learning.progressBusy.value || lab.state.authExpired"
          @click="markLearned"
        >
          <UiIcon :name="learned ? 'check-circle' : 'check'" />{{
            learned ? '取消已学习' : '标记已学习'
          }}
        </button>
        <ModelAccessAction
          v-if="!lab.modelReady.value"
          prefix="session-card"
          class="ui-button ui-button-ghost"
        />
        <button
          v-if="job?.status === 'running'"
          class="ui-button ui-button-ghost"
          type="button"
          data-action="cancel-session-cards"
          :disabled="starting"
          @click="state.cancel"
          >停止更新</button
        >
      </div>
      <p v-if="loading" class="session-card-note">正在读取已有卡片…</p>
      <p v-if="ensuring" class="session-card-note">正在根据本会话自动生成学习卡片…</p>
      <div
        v-if="job?.snapshot || (status && !issue)"
        class="session-card-progress"
        role="status"
        aria-live="polite"
        data-role="session-card-progress"
      >
        <p v-if="job?.snapshot" data-role="session-source-count"
          >会话 {{ job.snapshot.turns }} 轮 ·
          {{ job.snapshot.unit_count }} 段内容（问答、工具与实验结果）</p
        >
        <p v-if="status && !issue">{{ status }}</p>
        <p v-if="progress?.total_chunks"
          >已读取 {{ progress.completed_chunks ?? 0 }}/{{ progress.total_chunks }} 批<span
            v-if="progress.cached_chunks"
            >（复用 {{ progress.cached_chunks }} 批）</span
          ><span v-if="progress.total_cards">
            · 卡片 {{ progress.completed_cards ?? 0 }}/{{ progress.total_cards }}</span
          >
          · {{ job?.reused ? '本次无需请求模型' : '已请求 ' + (progress.calls ?? 0) + ' 次'
          }}<span v-if="job?.elapsed_ms && !job.reused">
            · {{ Math.floor(job.elapsed_ms / 1000) }} 秒</span
          ></p
        >
        <p v-if="running" class="session-card-note"
          >按内容长度合并处理，一批可含多轮；过长的一轮会拆批。已完成的批次可复用，随后合并当前方法的事实并更新同一张卡片。</p
        >
      </div>
      <details
        v-if="job?.timings && !job.reused"
        class="session-card-progress"
        data-role="session-card-timings"
        ><summary>查看耗时分段</summary>
        <p
          >准备 {{ seconds(job.timings.preparation_ms) }} · 排队
          {{ seconds(job.timings.queued_ms) }} · 模型请求 {{ seconds(job.timings.model_ms) }}</p
        >
        <p
          >校验与保存 {{ seconds(job.timings.commit_ms)
          }}<span v-if="job.timings.route_wait_ms">
            · 等待路线保存 {{ seconds(job.timings.route_wait_ms) }}</span
          >
          · 界面回读 {{ seconds(state.clientTimings.value.readback_ms) }}</p
        >
        <p class="session-card-note"
          >模型请求耗时包含网络连接、生成和响应传输；已完成分块会复用。</p
        >
      </details>
      <p v-if="issue" class="session-card-error" role="alert">{{ issue }}</p>
      <p v-if="!cards.length && !running && !loading" class="session-card-empty"
        >第一轮完整回答完成后，这里会自动出现一张会话卡片。</p
      >
      <article
        v-for="card in cards"
        :key="card.card_id"
        class="session-card"
        :data-card-id="card.card_id"
      >
        <header
          ><h4>{{ learnerText(card.title) }}</h4></header
        >
        <p class="session-card-note">{{ learnerText(card.summary) }}</p>
      </article>
    </template>
    <p v-else class="session-card-empty">开始会话、确认方法后，学习卡片将在这里自动维护。</p>
  </section>
</template>

<style scoped>
.session-cards {
  padding: 14px;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-primary);
}
.match-session-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--dsw-specific-input-major);
  border-radius: 9px;
  background: var(--dsw-specific-input-major);
  color: var(--dsw-feedback-info-text);
  font: inherit;
  cursor: pointer;
  transition: background-color 150ms ease-out;
}
.match-session-card svg {
  width: 15px;
  height: 15px;
  flex: none;
}
.match-session-card:disabled {
  opacity: 0.55;
  cursor: default;
}
.session-card-intro h3 {
  margin: 0 0 6px;
  font-size: var(--dsw-text-base);
}
.session-card-intro p,
.session-card-note,
.session-card-empty {
  color: var(--dsw-alias-text-secondary);
  line-height: 1.65;
}
.session-card-prompt {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin: 16px 0 12px;
}
.session-card-prompt textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  padding: 9px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  background: var(--dsw-alias-bg-layer-1);
  color: inherit;
  font: inherit;
  line-height: 1.5;
}
.session-card-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.session-card-progress,
.session-card-summary {
  margin: 14px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--dsw-alias-bg-skeleton);
  line-height: 1.6;
}
.session-card-progress p,
.session-card-summary p {
  margin: 3px 0;
}
.session-card-error {
  color: var(--dsw-feedback-error-text);
  line-height: 1.6;
}
.session-card {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  background: var(--dsw-alias-bg-layer-1);
}
.session-card header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: baseline;
}
.session-card h4 {
  margin: 0;
  font-size: var(--dsw-text-row);
}
.session-card-link {
  color: var(--dsw-feedback-info-text);
}
.session-card-body {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
}
.session-card details summary {
  cursor: pointer;
}
.history-actions {
  margin: 12px 0;
}
.session-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.session-card-heading h3 {
  margin: 0;
}
.session-card-intro > p {
  margin: 8px 0 0;
}
.view-learning-card {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  background: var(--dsw-specific-input-major);
  color: var(--dsw-feedback-info-text);
  text-decoration: none;
  font-size: var(--dsw-text-xs);
  font-weight: 500;
  transition:
    background-color 150ms ease-out,
    border-color 150ms ease-out;
}
.view-learning-card:hover {
  background: var(--dsw-alias-bg-layer-2);
  border-color: var(--dsw-focus-ring);
}
.view-learning-card svg {
  width: 13px;
  height: 13px;
}
.view-learning-card svg:last-child {
  width: 12px;
  height: 12px;
}
.session-card-intro {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--dsw-alias-border-l2);
}
.session-card-intro > p {
  margin: 10px 0 0;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-sm);
  line-height: 1.85;
}
.session-card-actions {
  display: flex;
  align-items: stretch;
  flex-wrap: wrap;
  gap: 9px;
  margin: 16px 0;
}
.session-card-actions .match-session-card {
  width: auto;
  max-width: 100%;
  flex: 0 1 auto;
  min-width: 0;
  justify-content: flex-start;
  padding: 11px 13px;
  border: 1px solid #b9ccef;
  background: var(--dsw-selection-surface);
  color: var(--dsw-feedback-info-text);
  text-align: left;
  font-size: var(--dsw-text-sm);
  line-height: 1.7;
}
.match-session-card > span {
  min-width: 0;
  overflow-wrap: anywhere;
}
.session-mark-learned {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 0 0 auto;
  padding: 10px 12px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 9px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.session-mark-learned > svg {
  width: 14px;
  height: 14px;
  flex: none;
}
.session-mark-learned[aria-pressed='true'] {
  color: var(--dsw-feedback-success-text);
  border-color: var(--dsw-feedback-success-border);
  background: var(--dsw-feedback-success-surface);
}
.session-mark-learned:disabled {
  opacity: 0.45;
  cursor: default;
}
.session-card-actions button:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 3px;
}
@container (max-width:360px) {
  .session-card-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .session-card-actions .match-session-card {
    justify-content: center;
  }
}
</style>
