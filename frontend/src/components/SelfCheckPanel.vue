<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import MarkdownText from '@/components/MarkdownText.vue';
import ModelAccessAction from '@/components/ModelAccessAction.vue';
import { useLab } from '@/composables/useLab';
import { useLearning } from '@/composables/useLearning';
import { useConsent } from '@/composables/useConsent';
import { createSelfCheckState } from '@/composables/useSelfCheck';
import { vDisclosureMotion } from '@/utils/disclosure-motion';

const props = withDefaults(defineProps<{ active?: boolean }>(), { active: true });
const lab = useLab(),
  learning = useLearning(),
  consent = useConsent(),
  state = createSelfCheckState();
const {
  data,
  attempt,
  operation,
  answers,
  error,
  loading,
  running,
  saving,
  dirty,
  conflict,
  syncFailed,
  reading,
  historyView,
  resendAllowed,
  submitting,
} = state;
const localError = ref(''),
  marking = ref(false);
const binding = computed(() => data.value?.binding);
const bindingReady = computed(
  () =>
    !binding.value ||
    (!binding.value.card_missing && !binding.value.session_missing),
);
const matching = computed(() => {
  const value = attempt.value;
  if (!value?.binding_valid) return false;
  if (!value.method_id) return !binding.value;
  return (
    binding.value?.method_id === value.method_id &&
    binding.value?.card_id === value.card_id
  );
});
const ready = computed(() => attempt.value?.status === 'ready');
const completed = computed(() => attempt.value?.status === 'completed');
const locked = computed(
  () =>
    !ready.value ||
    running.value ||
    historyView.value ||
    !matching.value ||
    lab.state.authExpired ||
    attempt.value?.requires_refresh,
);
const answered = computed(
  () => attempt.value?.questions?.filter((q) => !!answers.value[q.id]?.trim()).length ?? 0,
);
const learned = computed(
  () => !!attempt.value && learning.learned.value.includes(attempt.value.method_id),
);
const historyItems = computed(
  () =>
    data.value?.history.filter((item) =>
      ['ready', 'grading', 'grade_failed', 'completed'].includes(item.status),
    ) ?? [],
);
const backendOutdated = computed(() => !!data.value && data.value.generation_version !== 5);
const failureMessage = computed(() => {
  const failure = attempt.value?.failure;
  if (!failure) return '';
  if (failure.code === 'invalid_grounding')
    return '题目依据尚未匹配，已通过的题目会保留。可点击“恢复本次出题”补齐未完成部分。';
  if (failure.code === 'duplicate_question')
    return '当前学习内容暂时无法形成差异足够的新卷，请补充学习后重新出题。';
  if (
    [
      'invalid_change',
      'invalid_tool_arguments',
      'invalid_model_response',
      'insufficient_learning_sources',
    ].includes(failure.code)
  )
    return attempt.value?.submitted
      ? '点评尚未完成，作答已经保存。可点击“恢复本卷简答评价”继续。'
      : '部分题目尚未通过校验，已通过的题目会保留。可恢复本次出题，继续补齐未完成部分。';
  return failure.error;
});
const canStart = computed(
  () =>
    bindingReady.value &&
    data.value?.can_start &&
    !backendOutdated.value &&
    !lab.state.busy &&
    !lab.state.authExpired &&
    !running.value &&
    !loading.value,
);
const canModel = computed(
  () => lab.modelReady.value && consent.agreed.value && !lab.providerLoading.value,
);
const retakeIssue = computed(() => {
  if (backendOutdated.value) return '出题服务正在更新，更新完成后入口会自动恢复。';
  if (lab.state.authExpired) return '请重新登录后再出题。';
  if (!bindingReady.value) return '当前方法绑定已失效，请先确认绑定。';
  if (loading.value || submitting.value || reading.value) return '正在确认刚才的操作，请稍候。';
  if (running.value) return '当前自测任务尚未结束。';
  if (lab.state.busy) return '请等待当前聊天回答完成。';
  if (!canModel.value)
    return lab.configurationIssue.value || '连接模型并同意数据使用说明后可重新出题。';
  if (syncFailed.value) return '请先重新读取原任务，确认其结果。';
  if (!data.value?.can_start) return '请先补充本会话的数学内容。';
  if (ready.value && dirty.value) return '请先保存本卷作答。';
  return '';
});
const typeNames = { true_false: '判断题', single: '单选题', short: '简答题' };
const levelNames = { met: '符合要点', partial: '部分符合', missing: '尚未体现' };
watch(
  () => [lab.state.user, lab.state.sessionId, lab.state.authExpired] as const,
  () => {
    state.reset();
    localError.value = '';
    if (lab.state.user && lab.state.sessionId && !lab.state.authExpired)
      void state.bind(lab.state.user, lab.state.sessionId);
  },
  { immediate: true },
);
watch(
  () => props.active,
  (active) => {
    if (
      active &&
      lab.state.user &&
      lab.state.sessionId &&
      !lab.state.authExpired &&
      !running.value &&
      !loading.value
    )
      void state.refresh().catch(() => {});
  },
);
watch(
  () => lab.state.busy,
  (busy, previous) => {
    if (!busy && previous && props.active && !running.value && !lab.state.authExpired)
      void state.refresh().catch(() => {});
  },
);
watch(
  () => binding.value?.method_id,
  (id) => {
    if (id && !lab.state.authExpired) void learning.refresh();
  },
);
async function modelAction(action: 'generate' | 'grade' | 'retry', fresh = false) {
  localError.value = '';
  if (
    backendOutdated.value &&
    (action === 'generate' || (action === 'retry' && !attempt.value?.submitted))
  ) {
    localError.value = '出题服务正在更新，请稍候。';
    return;
  }
  if (!canModel.value) {
    localError.value = lab.configurationIssue.value || '连接模型并同意数据使用说明后可开始自测。';
    return;
  }
  if (action === 'generate' && !canStart.value) return;
  await state.dispatch(action, lab.config(), fresh);
}
async function markLearned() {
  const current = attempt.value,
    owner = lab.state.user,
    sid = lab.state.sessionId;
  if (!current?.result?.passed || !matching.value || learned.value || marking.value) return;
  marking.value = true;
  localError.value = '';
  const ok = await learning.setDone(current.method_id, true);
  if (owner === lab.state.user && sid === lab.state.sessionId) {
    marking.value = false;
    if (!ok) localError.value = learning.error.value;
  }
}
const statusNames: Record<string, string> = {
  generating: '准备中',
  ready: '待作答',
  insufficient: '需补学',
  grading: '评价中',
  completed: '已完成',
  generate_failed: '准备未完成',
  grade_failed: '评价未完成',
};
const answerText = (value: string) =>
  value === 'true' ? '正确' : value === 'false' ? '错误' : value;
const date = (timestamp: number) =>
  new Date(timestamp * 1000).toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
const versionTimer = setInterval(() => {
  if (
    backendOutdated.value &&
    props.active &&
    !running.value &&
    !loading.value &&
    !lab.state.authExpired &&
    lab.state.sessionId
  )
    void state.refresh().catch(() => {});
}, 2000);
onBeforeUnmount(() => {
  clearInterval(versionTimer);
  state.reset();
});
</script>

<template>
  <section class="self-check" data-role="self-check">
    <header class="self-check-heading"
      ><UiIcon name="self-check" /><div
        ><h3>学习自测</h3><p>先总结本会话的数学内容，再出五道题检查理解</p></div
      ></header
    >
    <div class="self-check-body">
      <p class="self-check-intro"
        >2 判断 · 2 单选 · 1 短答。结果只代表本次已测范围，学习进度由你确认。</p
      >
      <p v-if="!lab.state.sessionId" class="self-check-note"
        >选择或开始一个会话，再学习当前方法。</p
      >
      <p v-else-if="!loading && !bindingReady" class="self-check-note"
        >先确认当前方法绑定，再开始自测。关联卡片或会话已删除时，原成绩仍保留。</p
      >
      <p v-else-if="bindingReady && data && !data.can_start" class="self-check-note"
        >先总结本会话的数学内容，再据此出题；题目只考数学原理和定义。</p
      >
      <p v-if="loading" class="self-check-note" role="status">正在读取自测记录…</p>
      <p v-if="backendOutdated" class="self-check-note" role="status"
        >出题服务正在更新；当前记录保留，更新后会自动恢复出题入口。</p
      >
      <template v-if="attempt">
        <p
          v-if="attempt.content_notice"
          class="self-check-note"
          data-role="self-check-content-notice"
          >{{ attempt.content_notice }}</p
        >
        <div class="self-check-paper-heading"
          ><strong>{{ attempt.label }}</strong
          ><span>{{ statusNames[attempt.status] }}</span></div
        >
        <section
          v-if="attempt.summary"
          class="self-check-summary"
          data-role="self-check-summary"
          aria-label="本卷会话总结"
          ><h4>本卷总结</h4><MarkdownText :text="attempt.summary" class="self-check-summary-text" /></section
        >
        <p v-if="historyView" class="self-check-note"
          >正在查看历史试卷。<button
            type="button"
            class="self-check-link"
            @click="state.view(data!.attempt!.id)"
            v-if="data?.attempt"
            >返回当前试卷</button
          ></p
        >
        <p v-if="!matching" class="self-check-note"
          >本卷的方法绑定已变化，仅保留查看；不会用于更新当前方法进度。</p
        >
        <template v-if="attempt.status === 'insufficient'">
          <p class="self-check-note">{{ attempt.reason }}</p
          ><ul class="self-check-advice"
            ><li v-for="point in attempt.missing_points" :key="point">{{ point }}</li
            ><li v-for="tip in attempt.advice" :key="tip">{{ tip }}</li></ul
          >
        </template>
        <details
          v-if="attempt.questions?.length"
          v-disclosure-motion
          :open="!completed"
          class="self-check-answer-sheet"
        >
          <summary v-show="completed">查看本卷题目与作答<UiIcon name="chevron-down" /></summary>
          <form class="self-check-form" @submit.prevent="modelAction('grade')">
            <fieldset
              v-for="(question, index) in attempt.questions"
              :key="attempt.id + question.id"
              :data-question="question.id"
              :disabled="locked"
              :class="{ 'is-answered': !!answers[question.id]?.trim() }"
            >
              <legend class="self-check-sr-only"
                >第{{ index + 1 }}题 · {{ typeNames[question.type] }} ·
                {{ question.type === 'short' ? '40' : '15' }}分</legend
              >
              <div class="self-check-question-heading"
                ><span class="self-check-question-number">{{
                  String(index + 1).padStart(2, '0')
                }}</span
                ><span class="self-check-type">{{ typeNames[question.type] }}</span
                ><small class="self-check-question-points"
                  >{{ question.type === 'short' ? '40' : '15' }} 分</small
                ><span v-if="answers[question.id]?.trim()" class="self-check-answer-status"
                  ><UiIcon name="check" />已作答</span
                ></div
              >
              <MarkdownText :text="question.prompt" class="self-check-question" />
              <div
                v-if="question.type === 'true_false'"
                class="self-check-options self-check-boolean"
                ><label
                  v-for="choice in [
                    { id: 'true', text: '正确' },
                    { id: 'false', text: '错误' },
                  ]"
                  :key="choice.id"
                  :class="{ 'is-chosen': answers[question.id] === choice.id }"
                  ><input
                    type="radio"
                    :name="attempt.id + question.id"
                    :value="choice.id"
                    :checked="answers[question.id] === choice.id"
                    @change="state.edit(question.id, choice.id)"
                  /><span class="self-check-choice-text">{{ choice.text }}</span></label
                ></div
              >
              <div
                v-else-if="question.type === 'single'"
                class="self-check-options self-check-single"
                ><label
                  v-for="choice in question.options"
                  :key="choice.id"
                  :class="{ 'is-chosen': answers[question.id] === choice.id }"
                  ><input
                    type="radio"
                    :name="attempt.id + question.id"
                    :value="choice.id"
                    :checked="answers[question.id] === choice.id"
                    @change="state.edit(question.id, choice.id)" /><b
                    class="self-check-choice-key"
                    >{{ choice.id }}</b
                  ><MarkdownText
                    :text="choice.text"
                    :copyable="false"
                    class="self-check-choice-text" /></label
              ></div>
              <template v-else>
                <textarea
                  :value="answers[question.id] ?? ''"
                  maxlength="1500"
                  rows="4"
                  :aria-label="'第' + (index + 1) + '题简答'"
                  placeholder="用 1–3 句解释，或列出简短步骤即可。"
                  @input="state.edit(question.id, ($event.target as HTMLTextAreaElement).value)"
                /><div class="self-check-short-hint"
                  ><span>允许同义表达，不按篇幅评分。</span
                  ><small>{{ answers[question.id]?.length ?? 0 }} / 1500</small></div
                ></template
              >
            </fieldset>
            <div v-if="ready && !historyView" class="self-check-submit"
              ><span
                >{{
                  saving
                    ? '正在保存草稿…'
                    : dirty
                      ? '本机填写已保留，等待同步'
                      : answered
                        ? '草稿已自动保存'
                        : '作答将自动保存'
                }}<small v-if="answered < 5">完成五题后即可提交</small></span
              ><button
                type="submit"
                class="self-check-primary"
                data-action="submit-self-check"
                :disabled="
                  answered !== 5 || running || saving || conflict || !matching || !canModel
                "
                >提交并查看评价<UiIcon name="arrow-right" /></button
            ></div>
          </form>
        </details>
        <section
          v-if="completed && attempt.result"
          class="self-check-result"
          data-role="self-check-result"
        >
          <header
            class="self-check-score"
            :class="attempt.result.passed ? 'is-passed' : 'needs-review'"
            ><div
              ><span class="self-check-score-label">本次自测得分</span
              ><strong>{{ attempt.result.total }}<small> / 100</small></strong></div
            ><span class="self-check-result-status"
              ><UiIcon :name="attempt.result.passed ? 'check-circle' : 'book-open'" />{{
                attempt.result.passed ? '本次自测达标' : '建议继续补学'
              }}</span
            ></header
          >
          <p class="self-check-note"
            >简答 {{ attempt.result.short_points }} / 40；达标需总分至少 80 且简答至少 24。{{
              attempt.result.scope
            }}</p
          >
          <div
            v-for="item in attempt.result.objective"
            :key="item.id"
            class="self-check-review"
            :data-correct="item.correct"
            ><header class="self-check-review-heading"
              ><h5>{{ item.id.replace('q', '第') }}题</h5
              ><span class="self-check-verdict"
                ><UiIcon :name="item.correct ? 'check-circle' : 'warning'" />{{
                  item.correct ? '回答正确' : '需要复习'
                }}</span
              ><strong>{{ item.points }}<small> / 15</small></strong></header
            ><MarkdownText
              :text="attempt.questions?.find((q) => q.id === item.id)?.prompt ?? ''"
              class="self-check-review-question" /><div class="self-check-answer-comparison"
              ><p
                ><span>你的答案</span
                ><strong :class="item.correct ? 'answer-correct' : 'answer-incorrect'">{{
                  answerText(attempt.submitted?.[item.id] ?? '未作答')
                }}</strong></p
              ><p
                ><span>参考答案</span
                ><strong class="answer-reference">{{ answerText(item.answer) }}</strong></p
              ></div
            ><div class="self-check-explanation"
              ><span class="self-check-content-label">解析</span
              ><MarkdownText :text="item.explanation" /></div
          ></div>
          <div class="self-check-review"
            ><header class="self-check-review-heading"
              ><h5>第 5 题 · 简答评价</h5
              ><strong>{{ attempt.result.short_points }}<small> / 40</small></strong></header
            ><MarkdownText :text="attempt.result.short.feedback" class="self-check-feedback" /><div
              v-for="criterion in attempt.result.short.evaluations"
              :key="criterion.id"
              class="self-check-criterion"
              :data-level="criterion.level"
              ><header
                ><strong>{{
                  attempt.review?.[4]?.rubric.find((r) => r.id === criterion.id)?.text
                }}</strong
                ><span>{{ levelNames[criterion.level] }} · {{ criterion.points }}分</span></header
              ><blockquote v-if="criterion.evidence"
                ><span>作答依据</span>{{ criterion.evidence }}</blockquote
              ><p>{{ criterion.reason }}</p></div
            ></div
          >
          <details v-disclosure-motion class="self-check-review-sources"
            ><summary>查看参考解析与已学依据<UiIcon name="chevron-down" /></summary
            ><div v-for="review in attempt.review" :key="review.id"
              ><h5>{{ review.id.replace('q', '第') }}题</h5
              ><MarkdownText :text="review.explanation" /><blockquote
                v-for="ref in review.evidence"
                :key="ref.id"
                >{{ ref.quote }}</blockquote
              ><p class="self-check-note">总结依据：{{ review.lesson_quote }}</p></div
            ></details
          >
          <p v-if="attempt.covered_points?.length" class="self-check-note"
            >本次覆盖：{{ attempt.covered_points.map((p) => p.title).join('、') }}。</p
          >
          <p v-if="attempt.uncovered_points?.length" class="self-check-note"
            >本卷未覆盖：{{ attempt.uncovered_points.join('、') }}。</p
          >
          <div v-if="attempt.result.short.advice.length" class="self-check-next-steps"
            ><h5><UiIcon name="learning-route" />下一步建议</h5
            ><ul class="self-check-advice"
              ><li v-for="tip in attempt.result.short.advice" :key="tip">{{ tip }}</li></ul
            ></div
          >
          <button
            v-if="attempt.method_id && attempt.result.passed && matching"
            type="button"
            class="self-check-primary"
            data-action="self-check-mark-learned"
            :disabled="learned || marking || learning.progressBusy.value || lab.state.authExpired"
            @click="markLearned"
            >{{ learned ? '当前已标记为已学习' : marking ? '正在保存…' : '标记已学习' }}</button
          >
          <p class="self-check-note">本次成绩不会自动更改或撤销原来的已学习状态。</p>
        </section>
      </template>
      <p v-if="running || reading" class="self-check-progress" role="status">{{
        reading ? '正在读取已保存的自测结果…' : operation?.message || '正在准备本次自测…'
      }}</p>
      <p v-if="failureMessage && !running && !reading" class="self-check-error" role="status">{{
        failureMessage
      }}</p>
      <p v-if="error || localError" class="self-check-error" role="alert">{{
        localError || error
      }}</p>
      <div class="self-check-actions">
        <button
          v-if="syncFailed"
          type="button"
          class="self-check-secondary"
          data-action="reread-self-check"
          @click="state.reconnect"
          >重新读取原任务</button
        >
        <button
          v-if="syncFailed && resendAllowed"
          type="button"
          class="self-check-secondary"
          :disabled="submitting || !canModel"
          @click="state.resend"
          >未查到任务，使用原编号重试提交</button
        >
        <button v-if="conflict" type="button" class="self-check-secondary" @click="state.saveLocal"
          >确认保存本机填写</button
        >
        <button
          v-else-if="dirty && !saving"
          type="button"
          class="self-check-secondary"
          @click="state.flush"
          >保存草稿</button
        >
        <button
          v-if="operation?.status === 'running'"
          type="button"
          class="self-check-secondary"
          data-action="cancel-self-check"
          @click="state.cancel"
          >停止本次自测任务</button
        >
        <button
          v-if="!attempt"
          type="button"
          class="self-check-primary"
          data-action="start-self-check"
          :disabled="!canStart || !canModel"
          @click="modelAction('generate')"
          >开始学习自测</button
        >
        <button
          v-else-if="['generate_failed', 'grade_failed'].includes(attempt.status) && !historyView"
          type="button"
          class="self-check-secondary"
          data-action="retry-self-check"
          :disabled="running || !matching || !canModel || (backendOutdated && !attempt.submitted)"
          @click="modelAction('retry')"
          >{{ attempt.submitted ? '恢复本卷简答评价' : '恢复本次出题' }}</button
        >
        <button
          v-if="attempt && !historyView && !['generating', 'grading'].includes(attempt.status)"
          type="button"
          class="self-check-retake"
          data-action="retake-self-check"
          :disabled="!!retakeIssue"
          :title="retakeIssue || '生成不同的新试卷，本卷记录会保留'"
          @click="modelAction('generate', true)"
          ><UiIcon name="regenerate" />重新出题，保留本卷记录</button
        >
        <ModelAccessAction
          v-if="!lab.modelReady.value"
          prefix="self-check"
          class="self-check-secondary"
        />
      </div>
      <p
        v-if="
          attempt &&
          !historyView &&
          !['generating', 'grading'].includes(attempt.status) &&
          retakeIssue
        "
        class="self-check-note"
        data-role="retake-unavailable"
        >{{ retakeIssue }}</p
      >
      <p v-if="!data && !loading && error" class="self-check-note"
        ><button
          type="button"
          class="self-check-link"
          @click="lab.state.sessionId && state.bind(lab.state.user, lab.state.sessionId)"
          >重新读取自测记录</button
        ></p
      >
      <details v-if="historyItems.length" v-disclosure-motion class="self-check-history"
        ><summary
          >自测记录 <small>{{ historyItems.length }}</small
          ><UiIcon name="chevron-down" /></summary
        ><button
          v-for="item in historyItems"
          :key="item.id"
          type="button"
          :disabled="running || loading"
          @click="state.view(item.id)"
          ><span>{{ date(item.created_at) }} · {{ item.label }}</span
          ><small>{{
            item.result
              ? `${item.result.total} 分 · ${item.result.passed ? '达标' : '待巩固'}`
              : statusNames[item.status]
          }}</small></button
        ></details
      >
    </div>
  </section>
</template>

<style scoped src="./SelfCheckPanel.css"></style>
