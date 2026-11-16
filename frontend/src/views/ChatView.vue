<script setup lang="ts">
import ModelControls from '@/components/ModelControls.vue';
import type { DetailLevel } from '@/types';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { sessionCardsApi, type SourceLocation } from '@/services/session-cards';

import ExperimentCard from '@/components/ExperimentCard.vue';
import ConversationOutline from '@/components/ConversationOutline.vue';
import LearningReturnBar from '@/components/LearningReturnBar.vue';
import MessageTurn from '@/components/MessageTurn.vue';
import AttachmentCard from '@/components/AttachmentCard.vue';
import TurnResponse from '@/components/TurnResponse.vue';
import ResultsSidebar from '@/components/ResultsSidebar.vue';
import UiIcon from '@/components/UiIcon.vue';
import { usePanelWidth } from '@/composables/usePanelWidth';
import { useElementWidth } from '@/composables/useElementWidth';
import { useLab } from '@/composables/useLab';
import { useThreadNavigation } from '@/composables/useThreadNavigation';
import { useConsent } from '@/composables/useConsent';
import ModelAccessAction from '@/components/ModelAccessAction.vue';
import { useRecorder } from '@/composables/useRecorder';
import { useChatAttachments } from '@/composables/useChatAttachments';
import { transcribe } from '@/services/speech';
import { attachDebug } from '@/utils/debug';
import { finalAnswer } from '@/utils/turn-activity';
import type { ToolTrace } from '@/types';

const lab = useLab();
const consent = useConsent();
const resultsWidth = usePanelWidth('results');
const layout = ref<HTMLElement | null>(null);
const availableWidth = useElementWidth(layout);
const overlayPanel = computed(
  () => availableWidth.value < Math.max(960, resultsWidth.width.value + 560),
);
function panelKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && overlayPanel.value && lab.panelOpen.value) {
    event.preventDefault();
    lab.closePanel();
  }
}
attachDebug(lab);
const draft = lab.draft;
const fileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const sidebarSection = ref<'results' | 'datasets' | 'study' | 'self-check'>('results');
const submitting = ref(false);
const sendError = ref('');
let submissionVersion = 0;
let composerVersion = 0;
const { attachments, preparing, retryAttachment, uploadFiles, messageAttachments } =
  useChatAttachments({
    scope: () => ({
      owner: lab.state.user,
      session: lab.state.sessionId,
      version: composerVersion,
    }),
    ensureSession: lab.ensureSession,
  });
let voiceVersion = 0;
const recorder = useRecorder({
  onRecorded: async (wav, signal) => {
    const version = voiceVersion;
    const text = (await transcribe(wav, signal)).trim();
    if (version !== composerVersion || signal.aborted) return;
    if (!text) throw new Error('没有识别到内容，请靠近麦克风说话后重试。');
    draft.value += (draft.value && !/\s$/.test(draft.value) ? ' ' : '') + text;
  },
  onError: (error) => lab.setStatus(error.message, 'error'),
});
const voiceLabel = computed(() => {
  if (recorder.phase.value === 'requesting') return '正在请求麦克风权限…';
  if (recorder.phase.value === 'recording') return `录音中 ${recorder.seconds.value}s / 60s`;
  return '';
});
onBeforeUnmount(() => {
  composerVersion += 1;
  recorder.cancel();
});

const turns = computed(() => lab.state.turns);
const latestChat = computed(() =>
  turns.value.map((turn) => turn.kind !== 'experiment').lastIndexOf(true),
);
const editing = ref<number | null>(null),
  editedText = ref(''),
  actionNotice = ref(''),
  editError = ref('');
const actionsDisabled = computed(
  () => busy.value || submitting.value || lab.state.messageActionBusy || lab.state.authExpired,
);
function editMessage(index: number) {
  if (actionsDisabled.value || index !== latestChat.value) return;
  const owner = lab.state.user,
    session = lab.state.sessionId;
  pauseFollowing();
  editing.value = index;
  editedText.value = turns.value[index]?.question ?? '';
  editError.value = '';
  actionNotice.value = '';
  void nextTick(() => {
    if (owner !== lab.state.user || session !== lab.state.sessionId || editing.value !== index)
      return;
    const editor = content.value?.querySelector<HTMLElement>('[data-role="message-editor"]');
    editor?.querySelector<HTMLTextAreaElement>('textarea')?.focus({ preventScroll: true });
    editor?.scrollIntoView?.({ block: 'nearest' });
  });
}
async function saveEdit() {
  if (actionsDisabled.value || !editedText.value.trim()) return;
  const accepted = await lab.reviseLatest('edit', editedText.value, () => {
    editing.value = null;
    void followLatest();
  });
  if (!accepted || lab.state.statusTone === 'error')
    editError.value = lab.state.status || '暂时无法修改，请稍后重试。';
}
async function regenerate() {
  actionNotice.value = '';
  const accepted = await lab.reviseLatest('regenerate', undefined, () => void followLatest());
  if (!accepted || lab.state.statusTone === 'error')
    actionNotice.value = lab.state.status || '暂时无法重新生成。';
}
async function branch(index: number) {
  actionNotice.value = '';
  if (!(await lab.forkTurn(index))) actionNotice.value = lab.state.status || '暂时无法分支。';
}
async function viewExperiment(trace: ToolTrace) {
  const result = trace.result,
    owner = lab.state.user,
    session = lab.state.sessionId;
  if (!result) return;
  try {
    if (result.experiment_id && result.experiment_version)
      await lab.revealExperimentVersion(result.experiment_id, result.experiment_version);
    else {
      const block = lab.blocks.value.find(
        (item) =>
          item.tool === trace || (trace.id && item.tool?.id === trace.id) || item.result === result,
      );
      if (!block) throw new Error('暂未找到这项实验，请重新打开会话后查看。');
      lab.selectBlock(block.key);
    }
    if (owner !== lab.state.user || session !== lab.state.sessionId) return;
    sidebarSection.value = 'results';
    lab.openPanel();
  } catch (problem) {
    actionNotice.value = (problem as Error).message;
  }
}
const {
  scroll,
  content,
  active,
  onScroll,
  jumpTo,
  followLatest,
  pauseFollowing,
  onWheel,
  onKeydown: onThreadKeydown,
  onPointerdown,
} = useThreadNavigation(
  computed(() => lab.state.sessionId),
  turns,
);
const route = useRoute();
async function locateSource(location: SourceLocation) {
  const owner = lab.state.user;
  if (lab.state.sessionId !== location.session_id) await lab.openSession(location.session_id);
  if (owner !== lab.state.user || lab.state.sessionId !== location.session_id) return;
  if (location.experiment_id && location.version) {
    try {
      await lab.revealExperimentVersion(location.experiment_id, location.version);
    } catch (problem) {
      lab.setStatus('已定位问答，但实验版本暂不可读取：' + (problem as Error).message, 'error');
    }
    if (owner !== lab.state.user || lab.state.sessionId !== location.session_id) return;
    sidebarSection.value = 'results';
    lab.openPanel();
  }
  await nextTick();
  jumpTo(location.turn_index);
  if (location.superseded) lab.setStatus('这条来源保留的是旧版本，已定位到对应消息的新版本。');
}
watch(
  () => route.query.source,
  async (source) => {
    if (typeof source !== 'string' || !lab.state.user) return;
    const owner = lab.state.user,
      controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const location = await sessionCardsApi.locate(source, owner, controller.signal);
      if (owner === lab.state.user) await locateSource(location);
    } catch (problem) {
      if (owner === lab.state.user) lab.setStatus((problem as Error).message, 'error');
    } finally {
      clearTimeout(timeout);
    }
  },
  { immediate: true },
);
const busy = computed(() => lab.state.busy);
const panelOpen = computed(() => lab.panelOpen.value);
const sendIssue = computed(() => {
  if (!lab.state.user) return '请先登录后再发送。';
  if (lab.configurationIssue.value) return lab.configurationIssue.value;
  if (!consent.agreed.value) return '请先阅读数据使用说明并允许连接模型服务商。';
  const model = lab.state.settings.models.find((model) => model.id === lab.state.settings.model);
  if (
    model &&
    !model.input_types.includes('image') &&
    attachments.value.some((file) => file.read_status === 'image')
  )
    return '当前模型未启用图片输入，请选择支持图片的模型或移除图片。';
  if (recorder.busy.value && !recorder.recording.value) return '语音正在处理，请稍后发送。';
  if (uploading.value || preparing.value) return '附件正在处理，请稍后发送。';
  if (attachments.value.some((item) => item.state === 'error'))
    return '请重试或移除上传失败的附件后发送。';
  if (recorder.recording.value) return '请先结束录音，再发送问题。';
  return '';
});
const sendHint = computed(
  () => sendError.value || (draft.value.trim() || attachments.value.length ? sendIssue.value : ''),
);
const sendDisabled = computed(
  () =>
    busy.value ||
    submitting.value ||
    lab.state.messageActionBusy ||
    Boolean(sendIssue.value) ||
    (!draft.value.trim() && !attachments.value.length),
);

const question = ref<HTMLTextAreaElement | null>(null);
const DETAIL_OPTIONS = [
  { value: 'concise', label: '简洁' },
  { value: 'normal', label: '正常' },
  { value: 'detailed', label: '详细' },
] as const;
const TEXT_MAX = 208;
const SEGMENT_PAD = 2;
const SEGMENT_GAP = 2;

const detailIndex = computed(() =>
  Math.max(
    0,
    DETAIL_OPTIONS.findIndex((option) => option.value === lab.state.settings.detail),
  ),
);

const indicatorStyle = computed(() => ({
  width:
    `calc((100% - ${SEGMENT_PAD * 2}px - ${SEGMENT_GAP}px * ${DETAIL_OPTIONS.length - 1})` +
    ` / ${DETAIL_OPTIONS.length})`,
  height: `calc(100% - ${SEGMENT_PAD * 2}px)`,
  transform: `translateX(calc(${detailIndex.value} * (100% + ${SEGMENT_GAP}px)))`,
}));

function grow(): void {
  const element = question.value;
  if (!element) return;
  element.style.height = 'auto';
  element.style.height = `${Math.min(element.scrollHeight, TEXT_MAX)}px`;
}

onMounted(grow);
watch(draft, () => {
  void nextTick(grow);
});
watch([draft, sendIssue], () => {
  sendError.value = '';
});

watch(panelOpen, (open) => {
  lab.setBodyView(open ? 'results' : 'chat');
});
watch(
  () => [lab.state.user, lab.state.sessionId],
  () => {
    composerVersion += 1;
    submissionVersion += 1;
    attachments.value = [];
    submitting.value = false;
    sendError.value = '';
    recorder.cancel();
    editing.value = null;
    editError.value = '';
    actionNotice.value = '';
    sidebarSection.value = 'results';
  },
  { flush: 'sync' },
);

async function submit(): Promise<void> {
  const text = draft.value.trim()
    ? draft.value
    : attachments.value.length
      ? '请阅读本条消息的附件，并概括其中的内容与读取限制。'
      : '';
  if (!text.trim() || busy.value || submitting.value || lab.state.messageActionBusy) return;
  if (sendIssue.value) {
    sendError.value = sendIssue.value;
    return;
  }
  const files = messageAttachments();
  const sentIds = new Set(files.map((file) => file.id));
  const owner = lab.state.user,
    sourceSession = lab.state.sessionId;
  let version = ++submissionVersion;
  submitting.value = true;
  sendError.value = '';
  try {
    const id = await lab.ensureSession();
    if (
      owner !== lab.state.user ||
      id !== lab.state.sessionId ||
      (sourceSession && version !== submissionVersion)
    )
      return;
    version = ++submissionVersion;
    submitting.value = true;
    const accepted = await lab.ask(
      text,
      [],
      () => {
        if (version !== submissionVersion) return;
        void followLatest();
        submitting.value = false;
        if (draft.value === text) draft.value = '';
        attachments.value = attachments.value.filter((file) => !sentIds.has(file.id));
      },
      undefined,
      files,
    );
    if (!accepted && version === submissionVersion)
      sendError.value = lab.state.status || '暂时无法发送，请稍后重试。';
  } catch (error) {
    if (version === submissionVersion)
      sendError.value = (error as Error).message || '暂时无法发送，请稍后重试。';
  } finally {
    if (version === submissionVersion) submitting.value = false;
  }
}

async function onKeydown(event: KeyboardEvent): Promise<void> {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault();
    await submit();
  }
}

async function onPaste(event: ClipboardEvent): Promise<void> {
  const items = Array.from(event.clipboardData?.items ?? []);
  const attached = items
    .filter((item) => item.kind === 'file')
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file));
  if (!attached.length) return;
  event.preventDefault();
  await uploadFiles(attached);
}

async function pickFiles(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const chosen = Array.from(input.files ?? []);
  input.value = '';
  await uploadFiles(chosen);
}

async function dropFiles(event: DragEvent): Promise<void> {
  await uploadFiles(Array.from(event.dataTransfer?.files ?? []));
}

async function toggleMic(): Promise<void> {
  if (recorder.recording.value) {
    lab.setStatus('');
    await recorder.finish().catch(() => {});
    return;
  }
  if (recorder.busy.value) return;
  const version = composerVersion;
  voiceVersion = version;
  try {
    await recorder.start();
    if (version !== composerVersion) {
      recorder.cancel();
      return;
    }
    lab.setStatus('正在录音，再点一次麦克风结束。', 'busy');
  } catch (error) {
    if (version === composerVersion)
      lab.setStatus(`无法开始录音：${(error as Error).message}`, 'error');
  }
}

function zoom(url: string, name?: string): void {
  lab.openLightbox(url, name ?? url.split('/').pop() ?? url);
}
</script>

<template>
  <div
    ref="layout"
    class="chat-layout panel-layout relative grid h-full min-w-0 overflow-hidden"
    :class="{ 'has-overlay-panel': overlayPanel }"
    :style="{
      gridTemplateColumns: `minmax(0,1fr) min(${panelOpen && !overlayPanel ? resultsWidth.width.value : 44}px, 60%)`,
      '--results-width': `${resultsWidth.width.value}px`,
    }"
    @keydown="panelKey"
  >
    <section
      class="flex h-full min-h-0 min-w-0 flex-col overflow-hidden"
      data-view="chat"
      aria-label="对话"
    >
      <header class="chat-bar flex flex-none items-center gap-[14px]" data-role="chat-bar">
        <div class="chat-heading">
          <p class="chat-eyebrow">EXPERIMENT ASSISTANT</p>
          <h1 class="chat-title">机器学习实验助手</h1>
        </div>
        <LearningReturnBar />
        <span class="chat-local">本地数据 · 可核查结果</span>
      </header>
      <div class="relative min-h-0 flex-1">
        <ConversationOutline
          :key="lab.state.sessionId ?? 'new'"
          :turns="turns"
          :active="active"
          @jump="jumpTo"
        />
        <div
          ref="scroll"
          class="thread-scroll h-full overflow-y-auto pb-2 pl-10 pr-7 pt-[22px] [scrollbar-gutter:stable]"
          data-role="thread"
          role="log"
          aria-live="polite"
          aria-label="对话记录"
          @scroll.passive="onScroll"
          @wheel.passive="onWheel"
          @touchmove.passive="pauseFollowing"
          @keydown="onThreadKeydown"
          @pointerdown="onPointerdown"
        >
          <div ref="content" class="flow-root">
            <div v-if="!turns.length" class="chat-welcome">
              <span class="welcome-mark" aria-hidden="true">知</span>
              <p class="welcome-eyebrow">MODEL LAB · 实验助手</p>
              <h2>把问题交给方法，<br /><em>把结果讲清楚。</em></h2>
              <p class="welcome-lede">
                描述你的数据与目标，agent
                会选择合适的统计或机器学习方法，执行实验，并把每一步的数值依据整理成可核查的回答。
              </p>
              <div class="welcome-chips">
                <span><UiIcon name="sparkles" />116 个方法可用</span>
                <span v-if="lab.activeDataset.value"
                  ><UiIcon name="table" />{{
                    lab.activeDataset.value.name || lab.activeDataset.value.id
                  }}</span
                >
                <span v-else><UiIcon name="table" />AI 自动选择数据</span>
              </div>
              <div class="welcome-grid">
                <button
                  type="button"
                  class="welcome-card"
                  @click="
                    draft = lab.activeDataset.value
                      ? '根据当前选择的数据，推荐并比较两个适用的预测方法，给出测试集表现'
                      : '比较 iris 上 LDA 和随机森林的测试集表现';
                    void submit();
                  "
                >
                  <strong>比较两个分类方法</strong><span>给出准确率、AUC 与混淆矩阵</span>
                </button>
                <button
                  type="button"
                  class="welcome-card"
                  @click="
                    draft = '特征量纲差别很大时要不要先标准化？';
                    void submit();
                  "
                >
                  <strong>要不要标准化</strong><span>解释量纲对模型的影响</span>
                </button>
                <button
                  type="button"
                  class="welcome-card"
                  @click="
                    draft = lab.activeDataset.value
                      ? '在当前选择的数据上运行适用的随机森林预测方法，并给出结果图'
                      : '用随机森林回归在 boston 上做预测，给出残差图';
                    void submit();
                  "
                >
                  <strong>随机森林回归</strong><span>看 R²、RMSE 与残差分布</span>
                </button>
                <button
                  type="button"
                  class="welcome-card"
                  @click="
                    draft = lab.activeDataset.value
                      ? '在当前选择的数据上做模糊聚类，看聚类质量'
                      : '在 iris 上做模糊聚类，看聚类质量';
                    void submit();
                  "
                >
                  <strong>模糊聚类</strong><span>看 FPC 与各簇规模</span>
                </button>
              </div>
              <p class="welcome-foot"
                >Enter 发送 · Shift + Enter 换行 · 结果引用本次实验的真实数值</p
              >
            </div>
            <div
              v-for="(turn, index) in turns"
              :key="index"
              :data-turn-index="index"
              class="flow-root"
            >
              <MessageTurn
                v-if="turn.kind !== 'experiment'"
                :turn-index="index"
                :question="turn.question"
                :attachments="turn.attachments"
                :event-id="turn.event_id"
                :answer="turn.answer"
                :error="turn.error ?? null"
                :model="turn.model"
                :elapsed-ms="turn.elapsed_ms"
                :tools="turn.tools?.filter((tool) => !tool.hidden).length ?? 0"
                actions
                :latest="index === latestChat"
                :completed="turn.status === 'complete'"
                :reply-text="finalAnswer(turn)"
                :actions-disabled="actionsDisabled"
                :editing="editing === index"
                :edit-text="editedText"
                :edit-error="editError"
                @edit="editMessage(index)"
                @regenerate="regenerate"
                @branch="branch(index)"
                @update:edit-text="editedText = $event"
                @cancel-edit="editing = null"
                @save-edit="saveEdit"
                :images="
                  (turn.images ?? []).map((item) => ({ url: item.data_url, name: item.name }))
                "
                :image="turn.images?.length ? null : (turn.image?.data_url ?? null)"
                :image-name="turn.image?.name ?? null"
                @zoom="zoom"
              >
                <template #response
                  ><TurnResponse :turn="turn" @zoom="zoom" @view-result="viewExperiment"
                /></template>
              </MessageTurn>
              <MessageTurn
                v-else
                :turn-index="index"
                :question="turn.question"
                :attachments="turn.attachments"
                :event-id="turn.event_id"
                :answer="' '"
                :model="turn.result?.title"
                :elapsed-ms="turn.result?.elapsed_ms"
              >
                <template #answer>
                  <ExperimentCard v-if="turn.result" :result="turn.result" @zoom="zoom" />
                </template>
              </MessageTurn>
            </div>
            <p
              v-if="actionNotice"
              class="mx-auto max-w-[760px] text-[length:var(--dsw-text-sm)] text-error-ink"
              role="status"
              data-role="message-action-notice"
              >{{ actionNotice }}</p
            >
          </div>
        </div>
      </div>
      <div class="composer-region flex-none px-7 pb-5 pt-2.5" data-role="composer-region">
        <div
          v-if="attachments.length"
          class="composer-files-panel"
          data-role="composer-files"
          role="region"
          aria-label="待发送附件"
          tabindex="0"
          @dragover.prevent
          @drop.prevent="dropFiles"
        >
          <AttachmentCard
            v-for="item in attachments"
            :key="item.id"
            :file="item"
            :state="item.state"
            :error="item.error"
            removable
            @remove="attachments = attachments.filter((file) => file.id !== item.id)"
            @retry="retryAttachment(item)"
            @preview="zoom"
          />
        </div>
        <form
          class="composer-shell mx-auto max-w-[760px] rounded-roomy border-0 bg-field px-3 pb-2 pt-2.5"
          style="box-shadow: var(--dsw-elevation-soft)"
          data-role="composer"
          @submit.prevent="submit()"
          @paste="onPaste"
          @dragover.prevent
          @drop.prevent="dropFiles"
        >
          <input
            ref="fileInput"
            class="hidden"
            type="file"
            multiple
            accept=".csv,.tsv,.txt,.md,.markdown,.xlsx,.xls,.xlsm,.pdf,.docx,image/png,image/jpeg,image/webp,image/gif,audio/*"
            data-role="file-input"
            @change="pickFiles"
          />
          <textarea
            ref="question"
            v-model="draft"
            class="block min-h-[38px] w-full resize-none overflow-y-auto border-0 border-current bg-transparent px-1 py-1.5 text-[length:var(--dsw-text-base)] leading-[1.6] text-ink outline-none"
            :style="{ maxHeight: TEXT_MAX + 'px' }"
            rows="1"
            data-role="question"
            :placeholder="
              lab.activeDataset.value
                ? '围绕当前数据提问，例如：先分析数据特征，再推荐适用的方法'
                : ''
            "
            aria-label="提问"
            @keydown="onKeydown"
          ></textarea>
          <div
            v-if="sendHint"
            id="chat-send-hint"
            class="flex items-center gap-2 px-1 pt-1 text-[length:var(--dsw-text-sm)] leading-5 text-error-ink"
            data-role="send-hint"
            role="alert"
          >
            <span>{{ sendHint }}</span>
            <ModelAccessAction
              v-if="!lab.modelReady.value"
              prefix="chat-model"
              class="flex-none cursor-pointer border-0 bg-transparent p-0 text-link underline"
            />
          </div>
          <div class="composer-toolbar" data-role="composer-toolbar">
            <div class="composer-tools">
              <button
                type="button"
                class="ui-icon-button h-8 w-8 cursor-pointer rounded-card border-0 bg-transparent text-ink-2 hover:bg-skeleton hover:text-ink disabled:cursor-default disabled:opacity-45"
                data-action="attach-file"
                aria-label="添加会话附件"
                title="添加会话附件：文件会显示在对应消息中；实验数据请使用右侧数据集入口"
                :disabled="uploading || preparing"
                @click="fileInput?.click()"
              >
                <UiIcon name="paperclip" />
              </button>
              <button
                type="button"
                class="ui-icon-button h-8 w-8 cursor-pointer rounded-card border-0 bg-transparent hover:bg-skeleton"
                :class="recorder.recording.value ? 'text-error-ink' : 'text-ink-2 hover:text-ink'"
                data-action="voice-input"
                :aria-label="recorder.recording.value ? '结束录音' : '语音输入'"
                :title="recorder.recording.value ? '结束录音' : '语音输入（服务器 SenseVoice）'"
                :disabled="recorder.busy.value && !recorder.recording.value"
                @click="toggleMic"
              >
                <UiIcon name="microphone" />
              </button>
              <div
                class="composer-detail relative inline-grid grid-flow-col auto-cols-fr gap-[2px] rounded-card bg-skeleton p-[2px]"
                role="group"
                aria-label="回复详略"
              >
                <span
                  aria-hidden="true"
                  class="pointer-events-none absolute left-[2px] top-[2px] rounded-xs bg-surface shadow-soft transition-transform duration-150 ease-[ease]"
                  :style="indicatorStyle"
                />
                <button
                  v-for="option in DETAIL_OPTIONS"
                  :key="option.value"
                  type="button"
                  class="relative z-[1] h-6 cursor-pointer rounded-xs border-0 bg-transparent px-2.5 text-[length:var(--dsw-text-xs)] leading-[1.6] transition-colors duration-100 ease-[ease]"
                  :class="
                    lab.state.settings.detail === option.value
                      ? 'text-ink'
                      : 'text-ink-3 hover:text-ink'
                  "
                  :data-detail="option.value"
                  @click="lab.setDetail(option.value)"
                  >{{ option.label }}</button
                >
              </div>
              <select
                class="compact-detail"
                aria-label="回复详略"
                :value="lab.state.settings.detail"
                @change="lab.setDetail(($event.target as HTMLSelectElement).value as DetailLevel)"
                ><option
                  v-for="option in DETAIL_OPTIONS"
                  :key="option.value"
                  :value="option.value"
                  >{{ option.label }}</option
                ></select
              >
            </div>
            <div class="composer-send">
              <ModelControls />
              <button
                type="submit"
                class="send-button panel-button cursor-pointer bg-brand text-brand-ink hover:not-disabled:bg-brand-hover hover:not-disabled:text-brand-ink disabled:cursor-default disabled:bg-transparent disabled:text-ink-2"
                :disabled="sendDisabled"
                :title="
                  sendIssue || (busy || submitting ? '正在处理当前请求，请稍后发送。' : '发送')
                "
                :aria-describedby="sendHint ? 'chat-send-hint' : undefined"
                >发送</button
              >
              <button
                v-if="busy"
                type="button"
                class="panel-button cursor-pointer border-red-400 text-red-500 disabled:cursor-default disabled:opacity-50"
                @click="lab.stop()"
                >停止</button
              >
            </div>
          </div>
          <div
            v-if="voiceLabel"
            class="voice-feedback"
            :data-phase="recorder.phase.value"
            data-role="voice-feedback"
            role="status"
            aria-live="polite"
          >
            <span>{{ voiceLabel }}</span>
            <button
              v-if="recorder.recording.value"
              type="button"
              data-action="finish-recording"
              @click="toggleMic"
              >结束并转文字</button
            >
            <button
              v-if="recorder.busy.value"
              type="button"
              data-action="cancel-recording"
              @click="
                recorder.cancel();
                lab.setStatus('已取消语音输入。');
              "
              >取消</button
            >
            <details v-if="recorder.diagnostic.value.mime"
              ><summary>录音详情</summary
              ><small
                >{{ recorder.diagnostic.value.mime }} · {{ recorder.diagnostic.value.seconds }}s ·
                录音 {{ recorder.diagnostic.value.bytes }} 字节 · WAV
                {{ recorder.diagnostic.value.wavBytes }} 字节</small
              ></details
            >
          </div>
        </form>
      </div>
    </section>
    <button
      v-if="overlayPanel && panelOpen"
      type="button"
      class="results-backdrop"
      aria-label="返回对话"
      data-action="results-backdrop"
      @click="lab.closePanel()"
    />
    <ResultsSidebar v-model:section="sidebarSection" :overlay="overlayPanel" @zoom="zoom" />
  </div>
</template>

<style scoped>
.composer-files-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  box-sizing: border-box;
  width: 100%;
  max-width: 760px;
  max-height: 190px;
  margin: 0 auto 8px;
  padding: 9px 10px;
  overflow: auto;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 12px;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: var(--dsw-elevation-soft);
}
.composer-files-panel :deep(.attachment-card) {
  flex: 0 1 240px;
  min-width: 0;
}
.voice-feedback {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 7px 4px 0;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
  overflow-wrap: anywhere;
}
.voice-feedback[data-phase='error'] {
  color: var(--dsw-feedback-error-text);
}
.voice-feedback button {
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  padding: 4px 7px;
  cursor: pointer;
}
.voice-feedback details {
  flex-basis: 100%;
  font-size: var(--dsw-text-xs);
}
.voice-feedback summary {
  cursor: pointer;
}
.chat-layout {
  container-type: inline-size;
  container-name: chat;
}
.composer-shell {
  container-type: inline-size;
  container-name: composer;
}
.results-backdrop {
  position: absolute;
  inset: 0;
  z-index: 35;
  border: 0;
  background: rgb(0 0 0 / 0.18);
}
.has-overlay-panel :deep(.results-side.open) {
  position: absolute;
  inset: 0 0 0 auto;
  z-index: 36;
  width: min(var(--results-width), calc(100% - 12px));
  box-shadow: -6px 0 24px rgb(0 0 0 / 0.12);
}
.composer-send :deep(.model-controls) {
  flex: 1;
}
.composer-send :deep(.model-picker-anchor) {
  flex: 1;
}
.composer-send :deep(.model-trigger) {
  width: 100%;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
  min-width: 0;
  white-space: nowrap;
}
.composer-tools,
.composer-send {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.composer-tools {
  flex: none;
}
.composer-send {
  justify-content: flex-end;
  flex: 0 1 auto;
}
.composer-send > :deep(.model-controls) {
  margin: 0;
  flex-wrap: nowrap;
  min-width: 0;
}
.composer-send :deep(.model-picker-anchor) {
  min-width: 0;
}
.composer-send :deep(.model-trigger) {
  max-width: 245px;
  min-width: 0;
}
.composer-send :deep(.reasoning-anchor) {
  flex: none;
}
.composer-detail {
  flex: none;
}
.compact-detail {
  display: none;
}
.composer-send > .panel-button {
  flex: none;
}
.composer-tools > [data-role='recording'],
.composer-tools > [data-role='transcribing'] {
  position: absolute;
  bottom: 100%;
  left: 16px;
  padding: 5px 8px;
  background: var(--dsw-alias-bg-layer-1);
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
}
@media (max-width: 1050px) {
  .composer-toolbar {
    gap: 6px;
  }
  .composer-send :deep(.model-trigger) {
    max-width: 185px;
  }
  .composer-detail button {
    padding-left: 7px;
    padding-right: 7px;
  }
}
@media (max-width: 760px) {
  .composer-detail {
    display: none;
  }
  .compact-detail {
    display: block;
    max-width: 64px;
    border: 0;
    background: var(--dsw-specific-input-major);
    border-radius: 6px;
    padding: 5px 3px;
    color: var(--dsw-alias-text-secondary);
    font-size: var(--dsw-text-xs);
  }
  .composer-tools,
  .composer-send {
    gap: 3px;
  }
  .composer-send :deep(.model-trigger) {
    max-width: 145px;
    padding: 6px;
  }
  .composer-send :deep(.model-controls) {
    gap: 2px;
  }
  .composer-send :deep(.reasoning-trigger) {
    gap: 4px;
    padding: 5px;
  }
  .composer-send > .panel-button {
    padding: 5px 8px;
  }
  .composer-tools .ui-icon-button {
    width: 26px;
  }
}
@media (max-width: 420px) {
  .composer-send :deep(.model-trigger) {
    max-width: 95px;
  }
  .composer-send :deep(.reasoning-trigger svg:first-child) {
    display: none;
  }
  .composer-toolbar {
    gap: 3px;
  }
}
@container chat (max-width: 700px) {
  [data-role='chat-bar'] {
    gap: 8px;
    padding: 10px 12px;
    flex-wrap: wrap;
  }
  [data-role='chat-bar'] h1 {
    font-size: var(--dsw-text-base);
  }
  [data-role='thread'] {
    padding: 14px 12px 8px 24px;
  }
  .composer-region {
    padding: 8px 10px 12px;
  }
  [data-role='thread'] .grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@container composer (max-width: 620px) {
  .composer-toolbar {
    flex-wrap: wrap;
    gap: 6px;
  }
  .composer-tools {
    width: 100%;
  }
  .composer-send {
    width: 100%;
    flex: 1 1 100%;
  }
  .composer-send :deep(.model-trigger) {
    max-width: 100%;
  }
  .composer-detail {
    display: none;
  }
  .compact-detail {
    display: block;
    max-width: 72px;
    border: 0;
    border-radius: 6px;
    padding: 5px;
    background: var(--dsw-specific-input-major);
    font-size: var(--dsw-text-xs);
  }
}

/* Page shell */
.chat-layout {
  background: #ffffff;
}
[data-view='chat'] {
  background: transparent;
}
.chat-bar {
  min-height: 70px;
  padding: 11px 28px;
  border-bottom: 1px solid #e9eef8;
  background: color-mix(in srgb, #ffffff 76%, transparent);
  backdrop-filter: blur(16px);
}
.chat-heading {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: none;
}
.chat-eyebrow {
  margin: 0;
  color: #7f8da5;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.2em;
  line-height: 1.4;
}
.chat-title {
  margin: 0;
  color: #13203a;
  font-size: 17px;
  font-weight: 650;
  letter-spacing: -0.015em;
  white-space: nowrap;
}
.chat-local {
  display: inline-flex;
  align-items: center;
  flex: none;
  margin-left: auto;
  padding: 4px 9px;
  border: 1px solid #e4ebf6;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.72);
  color: #7b899f;
  font-size: 10px;
  letter-spacing: 0.01em;
  white-space: nowrap;
}
.thread-scroll {
  padding: 24px 30px 16px 44px;
}
.chat-welcome {
  max-width: 780px;
  margin: clamp(20px, 5.5vh, 58px) auto 0;
}
.welcome-mark {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  border: 1px solid #d7e3fb;
  background: #f7faff;
  color: #315fbd;
  font-size: 17px;
  font-weight: 650;
  box-shadow: 0 8px 18px -16px rgb(20 40 80 / 0.18);
}
.welcome-eyebrow {
  margin: 18px 0 0;
  color: #7f8da5;
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.2em;
  line-height: 1.4;
}
.chat-welcome h2 {
  margin: 9px 0 0;
  color: #111c31;
  font-size: clamp(30px, 2.3vw, 38px);
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.22;
}
.chat-welcome h2 em {
  background: linear-gradient(100deg, #315fbd 0%, #6b8fe6 55%, #3fa7c9 100%);
  background-clip: text;
  color: transparent;
  font-style: normal;
  font-weight: 700;
}
.welcome-lede {
  max-width: 620px;
  margin: 14px 0 0;
  color: #647086;
  font-size: 13px;
  line-height: 1.8;
}
.welcome-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 16px;
}
.welcome-chips span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  border: 1px solid #e2eaf6;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.7);
  color: #74839a;
  font-size: 10.5px;
  line-height: 1.5;
}
.welcome-chips svg {
  width: 12px;
  height: 12px;
  color: #4f7cff;
}
.welcome-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 22px;
  counter-reset: welcome;
}
.welcome-card {
  position: relative;
  display: block;
  min-height: 94px;
  padding: 15px 40px 14px 48px;
  border: 1px solid #e3eaf5;
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
  color: #18233a;
  text-align: left;
  font: inherit;
  cursor: pointer;
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.03),
    0 18px 32px -34px rgb(20 40 80 / 0.35);
  transition:
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 180ms ease,
    box-shadow 180ms ease,
    background 180ms ease;
}
.welcome-card::before {
  counter-increment: welcome;
  content: counter(welcome, decimal-leading-zero);
  position: absolute;
  left: 14px;
  top: 14px;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: #eef3ff;
  color: #3d63c7;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.welcome-card::after {
  content: '↗';
  position: absolute;
  right: 15px;
  top: 13px;
  color: #9aa8bc;
  font-size: 14px;
  line-height: 1;
  transition: color 160ms ease;
}
.welcome-card strong {
  display: block;
  overflow: hidden;
  color: #1a2740;
  font-size: 13.5px;
  font-weight: 650;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.welcome-card > span {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: #7b8799;
  font-size: 11px;
  line-height: 1.55;
}
.welcome-card:hover {
  border-color: #b9cdf6;
  background: #ffffff;
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.03),
    0 18px 32px -26px rgb(20 40 80 / 0.38);
  transform: translateY(-2px);
}
.welcome-card:hover::after {
  color: #4f7cff;
}
.welcome-card:focus-visible {
  outline: 2px solid #4f7cff;
  outline-offset: 2px;
}
.welcome-foot {
  margin: 16px 0 0;
  color: #93a0b3;
  font-size: 10px;
  letter-spacing: 0.02em;
  line-height: 1.6;
}

/* Composer */
.composer-region {
  padding: 10px 32px 22px;
  background: linear-gradient(180deg, rgb(244 247 252 / 0) 0%, #f4f7fc 40%);
}
.composer-shell {
  max-width: 800px;
  padding: 10px 12px 9px;
  border: 1px solid #e2e9f4;
  border-radius: 18px;
  background: #ffffff;
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.04),
    0 28px 60px -40px rgb(15 30 60 / 0.45);
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease;
}
.composer-shell:focus-within {
  border-color: #a9c0ee;
  box-shadow:
    0 0 0 3px rgb(79 124 255 / 0.08),
    0 28px 60px -40px rgb(15 30 60 / 0.45);
}
.composer-shell textarea {
  padding: 5px 6px;
  font-size: 14px;
}
.composer-toolbar {
  margin-top: 3px;
}
.composer-detail {
  background: #f2f5fa;
  border-radius: 9px;
}
.composer-send .send-button {
  min-width: 74px;
  height: 34px;
  padding: 0 16px;
  border-radius: 10px;
  border: 1px solid #d7e3fb;
  background: #eef3ff;
  color: #274a9a;
  font-size: var(--dsw-text-sm);
  font-weight: 600;
  box-shadow: 0 10px 22px -16px rgb(11 25 58 / 0.9);
  transition:
    filter 160ms ease,
    transform 160ms ease,
    opacity 160ms ease;
}
.composer-send .send-button:hover:not(:disabled) {
  border-color: #c3d4f1;
  background: #e1ebff;
  color: #1c3f8a;
  transform: translateY(-1px);
}
.composer-send .send-button:disabled {
  background: #eef2f8;
  color: #9aa7ba;
  box-shadow: none;
  opacity: 1;
}
.composer-files-panel {
  max-width: 800px;
  border-color: #e2e9f4;
  border-radius: 14px;
}

/* Messages */
:deep(.user-turn) {
  margin-bottom: 18px;
}
:deep(.question-bubble) {
  max-width: min(72%, 620px);
  padding: 12px 16px;
  border-radius: 18px 18px 5px 18px;
  border: 1px solid #dbe6fb;
  background: #eef3ff;
  color: #1a2740;
  font-size: 13.5px;
  line-height: 1.7;
  box-shadow: 0 12px 28px -24px rgb(20 40 80 / 0.28);
}
:deep(.question-bubble a) {
  color: #315fbd;
}
:deep(.user-turn + article) {
  position: relative;
  margin-top: 2px;
  margin-bottom: 26px;
  padding-left: 42px;
}
:deep(.user-turn + article)::before {
  content: '知';
  position: absolute;
  left: 0;
  top: 1px;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 10px;
  background: #eef4ff;
  color: #315fbd;
  box-shadow: inset 0 0 0 1px #d8e4fb;
  font-size: 11px;
  font-weight: 650;
}
:deep(.msg-body) {
  color: #243048;
  font-size: 13.5px;
  line-height: 1.8;
}
:deep(.msg-body h3) {
  color: #14213a;
  font-weight: 650;
}

@media (max-width: 1200px) {
  .chat-local {
    display: none;
  }
}
@container chat (max-width: 700px) {
  .chat-bar {
    min-height: 62px;
    padding: 9px 12px;
  }
  .chat-title {
    font-size: 15px;
  }
  .chat-eyebrow {
    display: none;
  }
  .thread-scroll {
    padding: 16px 12px 10px 24px;
  }
  .chat-welcome {
    margin-top: 4px;
  }
  .welcome-mark {
    width: 34px;
    height: 34px;
    border-radius: 11px;
    font-size: 14px;
  }
  .welcome-eyebrow {
    margin-top: 10px;
  }
  .chat-welcome h2 {
    margin-top: 6px;
    font-size: 26px;
  }
  .welcome-lede {
    margin-top: 9px;
    font-size: 12px;
    line-height: 1.65;
  }
  .welcome-chips {
    margin-top: 11px;
  }
  .welcome-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
    margin-top: 15px;
  }
  .welcome-card {
    min-height: 72px;
    padding: 11px 34px 10px 44px;
  }
  .welcome-foot {
    display: none;
  }
  .composer-region {
    padding: 8px 10px 12px;
  }
  .composer-shell {
    border-radius: 15px;
  }
  :deep(.question-bubble) {
    max-width: 86%;
  }
  :deep(.user-turn + article) {
    padding-left: 34px;
  }
  :deep(.user-turn + article)::before {
    width: 25px;
    height: 25px;
    font-size: 10px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .welcome-card,
  .composer-shell,
  .composer-send .send-button {
    transition: none;
  }
}
</style>
