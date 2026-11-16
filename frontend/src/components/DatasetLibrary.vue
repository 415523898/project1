<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import ConfirmDialog from '@/components/ConfirmDialog.vue';
import DatasetPreview from '@/components/DatasetPreview.vue';
import ModelAccessAction from '@/components/ModelAccessAction.vue';
import { useLab } from '@/composables/useLab';
import {
  configureDataset,
  datasetLibrary,
  deleteTable,
  suggestDataset,
  uploadTable,
  type DatasetSuggestion,
} from '@/services/files';
import type { DatasetChoice } from '@/types';
import { vDisclosureMotion } from '@/utils/disclosure-motion';

const props = defineProps<{
  incoming?: File[];
  source?: 'all' | 'upload';
  applyToSession?: boolean;
}>();
const emit = defineEmits<{ close: [] }>();
const lab = useLab();
const input = ref<HTMLInputElement | null>(null);
const query = ref('');
const tab = ref<'all' | 'builtin' | 'upload'>('all');
const filter = ref('all');
const builtins = ref<DatasetChoice[]>([]);
const mine = ref<DatasetChoice[]>([]);
const picked = ref<DatasetChoice | null>(null);
const target = ref('');
const task = ref('clustering');
const timeColumn = ref('');
const groupColumn = ref('');
const loading = ref(true);
const saving = ref(false);
const dragging = ref(false);
const error = ref('');
const savedNotice = ref('');
const suggestion = ref<DatasetSuggestion | null>(null);
const filling = ref(false);
const aiError = ref('');
const deleteTarget = ref<DatasetChoice | null>(null);
const deleting = ref(false);
let aiRequest: AbortController | null = null;
let alive = true;
let libraryVersion = 0;
const taskNames: Record<string, string> = {
  classification: '分类',
  regression: '回归',
  clustering: '无目标分析',
};
const visible = computed(() =>
  [...mine.value, ...builtins.value].filter((item) => {
    const needle = query.value.trim().toLowerCase();
    return (
      (tab.value === 'all' || item.kind === tab.value) &&
      (!needle || `${item.dataset} ${item.label}`.toLowerCase().includes(needle)) &&
      (filter.value === 'all' ||
        (filter.value === 'series' ? Boolean(item.time) : item.task === filter.value))
    );
  }),
);
const columns = computed(() => picked.value?.column_names ?? []);
const aiAvailable = computed(() => lab.modelReady.value);
const roleValues = () => ({
  target: target.value || null,
  task: task.value,
  time: timeColumn.value || null,
  group: groupColumn.value || null,
});
const needsConfirmation = computed(
  () =>
    picked.value?.kind === 'upload' &&
    (!picked.value.configured ||
      ['target', 'task', 'time', 'group'].some(
        (key) =>
          (picked.value?.[key as keyof DatasetChoice] || null) !==
          roleValues()[key as keyof ReturnType<typeof roleValues>],
      )),
);
const validation = computed(() => {
  if (picked.value?.kind !== 'upload') return '';
  if (task.value !== 'clustering' && !target.value)
    return '请为分类或回归选择目标列，即希望预测的那一列。';
  if (task.value === 'regression' && target.value && picked.value.dtypes?.[target.value] === 'text')
    return '回归需要数值目标列；类别标签请选择分类。';
  const roles = [target.value, timeColumn.value, groupColumn.value].filter(Boolean);
  if (new Set(roles).size !== roles.length) return '目标列、时间列和分组列不能重复。';
  return '';
});

function cancelAutofill(): void {
  aiRequest?.abort();
  aiRequest = null;
  filling.value = false;
}

function edited(): void {
  cancelAutofill();
  savedNotice.value = '';
  suggestion.value = null;
  aiError.value = '';
}

function pick(item: DatasetChoice): void {
  edited();
  picked.value = item;
  target.value = item.target ?? '';
  task.value = item.task;
  timeColumn.value = item.time ?? '';
  groupColumn.value = item.group ?? '';
  error.value = '';
}

async function load(): Promise<void> {
  const version = ++libraryVersion,
    owner = lab.state.user;
  loading.value = true;
  error.value = '';
  try {
    const library = await datasetLibrary();
    if (!alive || version !== libraryVersion || owner !== lab.state.user) return;
    builtins.value = library.builtins;
    mine.value = library.files;
    const active = lab.activeDataset.value;
    if (active) {
      const found = [...mine.value, ...builtins.value].find(
        (item) => item.dataset === active.dataset,
      );
      if (found) pick(found);
    }
  } catch (issue) {
    if (alive && version === libraryVersion) error.value = (issue as Error).message;
  } finally {
    if (alive && version === libraryVersion) loading.value = false;
  }
}

function switchSource(source: 'all' | 'builtin' | 'upload'): void {
  edited();
  tab.value = source;
  filter.value = 'all';
  error.value = '';
}

async function clearSelection(): Promise<void> {
  edited();
  saving.value = true;
  error.value = '';
  try {
    await lab.chooseDataset(null);
    picked.value = null;
  } catch (issue) {
    error.value = (issue as Error).message;
  } finally {
    saving.value = false;
  }
}

function askDelete(item: DatasetChoice): void {
  if (deleting.value) return;
  error.value = '';
  deleteTarget.value = item;
}

async function confirmDelete(): Promise<void> {
  const item = deleteTarget.value;
  if (!item || deleting.value) return;
  deleting.value = true;
  error.value = '';
  try {
    await deleteTable(item.id);
    deleteTarget.value = null;
    mine.value = mine.value.filter((record) => record.id !== item.id);
    if (picked.value?.id === item.id) picked.value = null;
    if (lab.activeDataset.value?.dataset === item.dataset && lab.state.sessionId)
      await lab.chooseDataset(null).catch(() => {});
    await load();
  } catch (issue) {
    deleteTarget.value = null;
    error.value = (issue as Error).message;
  } finally {
    deleting.value = false;
  }
}

async function upload(files: File[]): Promise<void> {
  if (!files.length || saving.value) return;
  edited();
  const owner = lab.state.user;
  saving.value = true;
  error.value = '';
  tab.value = 'upload';
  query.value = '';
  filter.value = 'all';
  const failures: string[] = [];
  try {
    for (const file of files) {
      if (lab.state.user !== owner) break;
      try {
        if (!file.size) throw new Error('文件为空。');
        const saved = await uploadTable('', file);
        if (!alive || lab.state.user !== owner) break;
        const choice: DatasetChoice = { ...saved, kind: 'upload', label: saved.name };
        mine.value.unshift(choice);
        pick(choice);
      } catch (issue) {
        failures.push(`${file.name}：${(issue as Error).message}`);
      }
    }
    error.value = failures.join('；');
  } finally {
    saving.value = false;
  }
}

function changeTarget(): void {
  edited();
  // Preserve a task chosen first. Selecting a target from no-target mode gives
  // a tentative type-based default that the user can still change.
  if (target.value && task.value === 'clustering') {
    task.value = picked.value?.dtypes?.[target.value] === 'text' ? 'classification' : 'regression';
  }
}

function changeTask(): void {
  edited();
  if (task.value === 'clustering') target.value = '';
}

async function autofill(): Promise<void> {
  const item = picked.value;
  if (!item || item.kind !== 'upload' || saving.value || filling.value || !aiAvailable.value)
    return;
  const request = new AbortController();
  const owner = lab.state.user,
    session = lab.state.sessionId;
  aiRequest = request;
  filling.value = true;
  aiError.value = '';
  savedNotice.value = '';
  const current = () =>
    alive &&
    aiRequest === request &&
    !request.signal.aborted &&
    picked.value?.id === item.id &&
    lab.state.user === owner &&
    lab.state.sessionId === session;
  try {
    const value = await suggestDataset(item.id, lab.config(), request.signal);
    if (!current()) return;
    if (value.id !== item.id) throw new Error('数据集已变化，请重新点击 AI 帮填。');
    task.value = value.task;
    target.value = value.target ?? '';
    timeColumn.value = value.time ?? '';
    groupColumn.value = value.group ?? '';
    suggestion.value = value;
  } catch (issue) {
    if (current()) aiError.value = (issue as Error).message;
  } finally {
    if (aiRequest === request) {
      aiRequest = null;
      filling.value = false;
    }
  }
}

async function saveConfiguration(applyToChat = false): Promise<void> {
  const item = picked.value;
  if (!item || saving.value || filling.value || validation.value) return;
  const owner = lab.state.user,
    session = lab.state.sessionId;
  const values = roleValues();
  saving.value = true;
  error.value = '';
  savedNotice.value = '';
  try {
    if (item.kind === 'upload' && needsConfirmation.value) {
      const saved = await configureDataset(item.id, values);
      if (!alive || lab.state.user !== owner || lab.state.sessionId !== session) return;
      mine.value = mine.value.map((record) => (record.id === saved.id ? saved : record));
      picked.value = saved;
      savedNotice.value = '配置已保存到当前账号，重新登录无需重复确认。';
    }
    if (applyToChat && alive && lab.state.user === owner && lab.state.sessionId === session) {
      await lab.chooseDataset(item.dataset);
      if (alive && lab.state.user === owner && lab.state.sessionId === session) emit('close');
    }
  } catch (issue) {
    if (alive && lab.state.user === owner && lab.state.sessionId === session)
      error.value = (issue as Error).message;
  } finally {
    saving.value = false;
  }
}

watch(
  () => lab.state.user,
  () => {
    builtins.value = [];
    mine.value = [];
    picked.value = null;
    void load();
  },
);
watch(
  () => [
    lab.state.user,
    lab.state.sessionId,
    lab.state.apiKey,
    lab.state.settings?.base_url,
    lab.state.settings?.provider_id,
    lab.state.settings?.protocol,
    lab.state.settings?.model,
    lab.modelReady.value,
  ],
  () => edited(),
);
onBeforeUnmount(() => {
  alive = false;
  libraryVersion++;
  cancelAutofill();
});
let incomingQueue = Promise.resolve();
function receive(files: File[]): void {
  if (!files.length) return;
  const owner = lab.state.user;
  incomingQueue = incomingQueue.then(async () => {
    if (saving.value)
      await new Promise<void>((resolve) => {
        const stop = watch(saving, (busy) => {
          if (!busy) {
            stop();
            resolve();
          }
        });
      });
    if (lab.state.user === owner) await upload(files);
  });
}
watch(
  () => props.incoming,
  (files) => {
    if (files?.length) receive(files);
  },
);
watch(
  () => props.source,
  (source) => {
    if (source) switchSource(source);
  },
  { immediate: true },
);
defineExpose({ cancelAutofill });
onMounted(() => {
  incomingQueue = load();
  receive(props.incoming ?? []);
});
</script>

<template>
  <section class="dataset-library" data-role="dataset-library" aria-label="浏览其他数据集">
    <div class="dataset-workspace">
      <section class="dataset-browser" aria-label="数据列表">
        <div class="dataset-section-heading"
          ><h3 id="dataset-list-heading">数据目录</h3
          ><span>{{ mine.length + builtins.length }} 份</span></div
        >
        <div
          class="dataset-source-tabs"
          :style="{ '--source-index': tab === 'all' ? 0 : tab === 'builtin' ? 1 : 2 }"
          role="group"
          aria-label="数据来源"
        >
          <button
            v-for="source in [
              { id: 'all' as const, label: '全部', count: mine.length + builtins.length },
              { id: 'builtin' as const, label: '内置', count: builtins.length },
              { id: 'upload' as const, label: '我的', count: mine.length },
            ]"
            :key="source.id"
            type="button"
            :aria-pressed="tab === source.id"
            @click="switchSource(source.id)"
            >{{ source.label }} <span>{{ source.count }}</span></button
          >
        </div>
        <label class="dataset-search"
          ><UiIcon name="search" /><input
            v-model="query"
            aria-label="搜索数据集"
            placeholder="搜索 ID 或说明"
        /></label>
        <details v-disclosure-motion class="dataset-filter-disclosure"
          ><summary
            >按任务筛选<span v-if="filter !== 'all'"> · 已筛选</span
            ><UiIcon name="chevron-down" /></summary
          ><div class="dataset-filters" aria-label="任务筛选">
            <button
              v-for="option in [
                { id: 'all', name: '全部' },
                { id: 'classification', name: '分类' },
                { id: 'regression', name: '回归' },
                { id: 'series', name: '时间 / 面板' },
              ]"
              :key="option.id"
              type="button"
              :aria-pressed="filter === option.id"
              @click="filter = option.id"
              >{{ option.name }}</button
            >
          </div>
        </details>
        <div
          v-if="tab !== 'builtin'"
          class="dataset-upload"
          data-role="dataset-upload"
          :class="{ 'is-dragging': dragging }"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="
            dragging = false;
            void upload(Array.from($event.dataTransfer?.files ?? []));
          "
        >
          <button
            type="button"
            data-action="upload-dataset"
            :disabled="saving"
            @click="input?.click()"
            ><UiIcon :name="saving ? 'spinner' : 'plus'" />{{
              saving ? '正在处理…' : '上传数据集'
            }}</button
          >
          <small>拖入 CSV / Excel 文件</small>
          <input
            ref="input"
            type="file"
            class="hidden"
            accept=".csv,.tsv,.txt,.xlsx,.xls,.xlsm"
            aria-label="上传数据文件"
            @change="
              void upload(Array.from(($event.target as HTMLInputElement).files ?? []));
              ($event.target as HTMLInputElement).value = '';
            "
          />
        </div>
        <Transition name="dataset-content" mode="out-in"
          ><div
            :key="tab + '|' + filter"
            class="dataset-list"
            role="region"
            aria-labelledby="dataset-list-heading"
            :aria-busy="loading"
          >
            <p v-if="loading" class="dataset-empty">正在读取服务器数据…</p>
            <button
              v-for="item in visible"
              :key="item.dataset"
              type="button"
              class="dataset-item"
              :class="{ 'is-selected': picked?.dataset === item.dataset }"
              :aria-pressed="picked?.dataset === item.dataset"
              :data-source="item.dataset"
              :disabled="saving"
              @click="pick(item)"
            >
              <span class="dataset-item-icon" aria-hidden="true"><UiIcon name="table" /></span>
              <span class="dataset-item-body"
                ><span class="dataset-item-title"
                  ><strong>{{ item.kind === 'builtin' ? item.id : item.name }}</strong
                  ><em v-if="item.task">{{ taskNames[item.task] || item.task }}</em></span
                ><small>{{
                  item.kind === 'builtin'
                    ? item.label
                    : `${item.rows} 行 × ${item.columns} 列 · ${item.configured ? '配置已保存' : '配置待确认'}`
                }}</small></span
              >
              <span
                v-if="picked?.dataset === item.dataset"
                class="dataset-item-check"
                aria-hidden="true"
                ><UiIcon name="check"
              /></span>
            </button>
            <p v-if="!loading && !visible.length" class="dataset-empty">{{
              query
                ? '没有匹配的数据'
                : tab === 'upload'
                  ? '还没有上传数据，可以从上方添加'
                  : '没有符合筛选条件的数据'
            }}</p>
          </div></Transition
        >
      </section>
      <section class="dataset-detail" aria-label="数据详情">
        <Transition name="dataset-content" mode="out-in"
          ><div v-if="picked" :key="picked.dataset" class="dataset-detail-content">
            <div class="dataset-detail-head">
              <div class="dataset-detail-title">
                <span class="dataset-kind">{{
                  picked.kind === 'builtin' ? '服务器内置' : '我的数据'
                }}</span>
                <h3>{{ picked.name || picked.id }}</h3>
              </div>
              <button
                v-if="picked.kind === 'upload'"
                type="button"
                class="dataset-delete"
                data-action="delete-dataset"
                :disabled="deleting || saving"
                @click="askDelete(picked)"
                ><UiIcon name="trash" />删除数据集</button
              >
            </div>
            <p v-if="picked.kind === 'builtin'" class="dataset-description">{{ picked.label }}</p>
            <div class="dataset-stats" v-if="picked.rows || picked.columns">
              <span
                ><b>{{ picked.rows ?? '—' }}</b
                >行</span
              >
              <span
                ><b>{{ picked.columns ?? '—' }}</b
                >列</span
              >
              <span
                ><b>{{ taskNames[picked.task] || picked.task || '—' }}</b
                >默认任务</span
              >
            </div>
            <DatasetPreview :dataset="picked" />
            <details
              v-disclosure-motion
              v-if="picked.kind === 'upload'"
              class="dataset-config"
              :open="needsConfirmation"
            >
              <summary
                >分析配置 <span>{{ needsConfirmation ? '待确认' : '已保存' }}</span
                ><UiIcon name="chevron-down"
              /></summary>
              <div class="dataset-config-heading">
                <p class="dataset-muted">默认任务与字段角色</p>
                <button
                  type="button"
                  class="dataset-ai"
                  data-action="autofill-dataset"
                  :disabled="saving || filling || !aiAvailable"
                  @click="autofill"
                >
                  <UiIcon :name="filling ? 'spinner' : 'sparkles'" />{{
                    filling ? 'AI 分析中…' : 'AI 帮填'
                  }}
                </button>
              </div>
              <p class="dataset-muted dataset-ai-hint"
                >{{
                  aiAvailable
                    ? '使用当前模型分析字段、全表统计与前 5 行样本，会消耗 token；填写后请确认保存。'
                    : lab.modelAccess.value.message
                }}
                <ModelAccessAction
                  v-if="!aiAvailable"
                  prefix="dataset"
                  class="dataset-secondary-action"
              /></p>
              <p v-if="filling" class="dataset-muted" role="status"
                >正在分析这份数据；修改任一字段将取消本次填写。</p
              >
              <div class="dataset-fields">
                <label
                  >任务<select
                    aria-label="任务"
                    v-model="task"
                    :disabled="saving"
                    @change="changeTask"
                    ><option value="clustering">无目标分析</option
                    ><option value="classification">分类</option
                    ><option value="regression">回归</option></select
                  ></label
                >
                <label
                  >{{ task === 'clustering' ? '目标列（可不选）' : '目标列（必选）'
                  }}<select
                    aria-label="目标列"
                    v-model="target"
                    :disabled="saving"
                    :aria-invalid="task !== 'clustering' && !target"
                    @change="changeTarget"
                    ><option value="">{{
                      task === 'clustering' ? '无目标列' : '请选择希望预测的列'
                    }}</option
                    ><option v-for="column in columns" :key="column" :value="column">{{
                      column
                    }}</option></select
                  ></label
                >
                <label
                  >时间列（可选）<select
                    aria-label="时间列"
                    v-model="timeColumn"
                    :disabled="saving"
                    @change="edited"
                    ><option value="">不指定</option
                    ><option v-for="column in columns" :key="column" :value="column">{{
                      column
                    }}</option></select
                  ></label
                >
                <label
                  >分组列（可选）<select
                    aria-label="分组列"
                    v-model="groupColumn"
                    :disabled="saving"
                    @change="edited"
                    ><option value="">不指定</option
                    ><option v-for="column in columns" :key="column" :value="column">{{
                      column
                    }}</option></select
                  ></label
                >
              </div>
              <p
                v-if="validation"
                class="dataset-error"
                role="alert"
                data-role="dataset-validation"
                >{{ validation }}</p
              >
              <p v-if="aiError" class="dataset-error" role="alert">{{ aiError }}</p>
              <div
                v-if="suggestion"
                class="dataset-ai-reason"
                data-role="dataset-ai-suggestion"
                role="status"
              >
                <strong>AI 填写依据</strong><p>{{ suggestion.reason }}</p>
                <small
                  >{{ suggestion.model
                  }}<template v-if="suggestion.usage?.total_tokens">
                    · {{ suggestion.usage.total_tokens }} token</template
                  >
                  · {{ needsConfirmation ? '请检查后确认保存' : '已确认保存' }}</small
                >
              </div>
              <p class="dataset-muted">{{
                applyToSession
                  ? '文件已保存在服务器，可供 AI 自动选择。这里保存默认分析配置，不会强制指定当前会话的数据来源。'
                  : '文件已保存在服务器。这里保存默认分析配置，供 AI 和实验使用。'
              }}</p>
              <div class="dataset-save-row">
                <span v-if="savedNotice" class="dataset-saved" role="status">{{
                  savedNotice
                }}</span>
                <button
                  type="button"
                  class="dataset-save"
                  data-action="save-dataset-config"
                  :disabled="saving || filling || !needsConfirmation || Boolean(validation)"
                  @click="saveConfiguration()"
                  >{{
                    saving ? '正在保存…' : needsConfirmation ? '确认并保存配置' : '配置已保存'
                  }}</button
                >
              </div>
            </details>
            <details v-disclosure-motion v-else class="dataset-config"
              ><summary>默认分析配置<UiIcon name="chevron-down" /></summary
              ><dl class="dataset-metadata"
                ><dt>任务</dt><dd>{{ taskNames[picked.task] || picked.task }}</dd
                ><dt>目标列</dt><dd>{{ picked.target || '未指定' }}</dd>
                <template v-if="picked.time"
                  ><dt>时间列</dt><dd>{{ picked.time }}</dd></template
                ><template v-if="picked.group"
                  ><dt>分组列</dt><dd>{{ picked.group }}</dd></template
                ></dl
              ></details
            >
          </div>
          <div v-else class="dataset-placeholder">
            <span class="dataset-placeholder-icon" aria-hidden="true"><UiIcon name="table" /></span>
            <h3>{{ applyToSession ? '选择数据查看预览' : '选择一份数据开始预览' }}</h3>
            <p>{{
              applyToSession
                ? '浏览内置示例或上传自己的表格；浏览不会切换当前会话的数据来源。'
                : '从左侧选择内置示例或上传自己的表格，查看字段、样例行和默认分析配置。'
            }}</p>
            <div class="dataset-placeholder-chips">
              <span>字段预览</span><span>默认配置</span><span>不切换当前会话</span>
            </div>
          </div></Transition
        >
      </section>
    </div>
    <footer v-if="applyToSession" class="dataset-footer">
      <div
        ><p v-if="error" role="alert" class="dataset-error"
          >{{ error }}
          <button v-if="!builtins.length && !saving" type="button" @click="load">重试</button></p
        >
        <p v-else class="dataset-current" data-role="dataset-current"
          >{{
            lab.activeDataset.value
              ? `手动指定：${lab.activeDataset.value.name || lab.activeDataset.value.id}`
              : '当前由 AI 按问题和方法自动选择数据'
          }}
          <button
            v-if="lab.activeDataset.value"
            type="button"
            class="dataset-secondary-action"
            data-action="clear-dataset-selection"
            :disabled="saving"
            @click="clearSelection"
            >恢复自动选择</button
          ></p
        >
        <p class="dataset-browse-note">浏览数据不会切换来源；点击“用于当前会话”才会应用。</p>
      </div>
      <button
        type="button"
        class="dataset-confirm"
        :disabled="lab.state.busy || !picked || saving || filling || loading || Boolean(validation)"
        :title="
          lab.state.busy ? '回答进行中，可以浏览数据；结束后可切换当前会话的数据集。' : undefined
        "
        @click="saveConfiguration(true)"
        >{{ needsConfirmation ? '保存并用于当前会话' : '用于当前会话' }}</button
      >
    </footer>
    <ConfirmDialog
      :open="!!deleteTarget"
      title="删除数据集"
      :message="
        deleteTarget
          ? `确定删除「${deleteTarget.name || deleteTarget.label || deleteTarget.id}」吗？删除后无法恢复；使用过它的会话会恢复为 AI 自动选择。`
          : ''
      "
      confirm="删除"
      :busy="deleting"
      @cancel="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </section>
</template>

<style scoped>
.dataset-library {
  container-type: inline-size;
  container-name: dataset-library;
  min-width: 0;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
}
.dataset-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
}
.dataset-browser,
.dataset-detail {
  min-width: 0;
  margin: 0;
  padding: 0;
  background: transparent;
}
.dataset-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.dataset-section-heading h3 {
  margin: 0;
  font-size: var(--dsw-text-row);
  font-weight: 500;
}
.dataset-section-heading > span {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
}
.dataset-source-tabs {
  position: relative;
  isolation: isolate;
  display: flex;
  margin-top: 12px;
  padding: 3px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 9px;
  background: var(--dsw-alias-bg-layer-1);
}
.dataset-source-tabs::before {
  content: '';
  position: absolute;
  z-index: -1;
  left: 3px;
  top: 3px;
  bottom: 3px;
  width: calc((100% - 6px) / 3);
  transform: translateX(calc(var(--source-index, 0) * 100%));
  background: var(--dsw-selection-surface);
  border-radius: 6px;
  transition: transform 200ms cubic-bezier(0.22, 1, 0.36, 1);
}
.dataset-source-tabs button {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  padding: 7px 3px;
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
  transition: color 160ms;
}
.dataset-source-tabs button[aria-pressed='true'] {
  color: var(--dsw-alias-link);
}
.dataset-source-tabs button span {
  font-size: var(--dsw-text-xs);
  opacity: 0.7;
  margin-left: 3px;
}
.dataset-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0 10px;
  padding: 9px 10px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  color: var(--dsw-alias-text-tertiary);
}
.dataset-search svg {
  width: 15px;
  height: 15px;
  flex: none;
}
.dataset-search input {
  width: 100%;
  min-width: 0;
  outline: 0;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-primary);
}
.dataset-filter-disclosure {
  margin-bottom: 12px;
}
.dataset-filter-disclosure > summary,
.dataset-config > summary {
  display: flex;
  align-items: center;
  gap: 6px;
  list-style: none;
  cursor: pointer;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
}
summary::-webkit-details-marker {
  display: none;
}
summary > svg {
  width: 14px;
  height: 14px;
  margin-left: auto;
  flex: none;
  transition: transform 200ms ease;
}
details:is([open], [data-disclosure-expanded='true']) > summary > svg {
  transform: rotate(180deg);
}
details[data-disclosure-expanded='false'] > summary > svg {
  transform: none;
}
.dataset-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  padding-top: 9px;
}
.dataset-filters button {
  border: 0;
  border-radius: 6px;
  padding: 5px 7px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
  transition:
    background-color 160ms,
    color 160ms;
}
.dataset-filters button[aria-pressed='true'] {
  background: var(--dsw-selection-surface);
  color: var(--dsw-alias-link);
}
.dataset-upload {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  padding: 9px 10px;
  margin-bottom: 10px;
  border: 1px dashed var(--dsw-alias-border-l2);
  border-radius: 8px;
  transition:
    background-color 160ms,
    border-color 160ms;
}
.dataset-upload.is-dragging {
  background: var(--dsw-selection-surface);
  border-color: var(--dsw-alias-link);
}
.dataset-upload button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--dsw-alias-link);
  padding: 4px 0;
  font: inherit;
  font-size: var(--dsw-text-xs);
  white-space: nowrap;
  cursor: pointer;
}
.dataset-upload svg {
  width: 14px;
  height: 14px;
}
.dataset-upload small {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
}
.dataset-list {
  max-height: 260px;
  min-height: 80px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
.dataset-item {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  min-width: 0;
  margin-bottom: 4px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  text-align: left;
  font: inherit;
  cursor: pointer;
  transition:
    background-color 160ms,
    border-color 160ms,
    color 160ms;
}
.dataset-item > svg {
  width: 15px;
  height: 15px;
  flex: none;
}
.dataset-item > span {
  min-width: 0;
  flex: 1;
}
.dataset-item strong {
  display: block;
  font-size: var(--dsw-text-sm);
  font-weight: 500;
  overflow-wrap: anywhere;
}
.dataset-item small {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-top: 3px;
  font-size: var(--dsw-text-xs);
  line-height: 1.6;
  color: var(--dsw-alias-text-tertiary);
}
.dataset-item:hover {
  background: var(--dsw-specific-sidebar-fill);
}
.dataset-item.is-selected {
  background: var(--dsw-selection-surface);
  border-color: var(--dsw-selection-border);
}
.dataset-detail {
  padding-top: 18px;
  border-top: 1px solid var(--dsw-alias-border-l2);
}
.dataset-detail-content {
  min-width: 0;
}
.dataset-kind {
  display: inline-block;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
}
.dataset-delete {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin: 0 0 10px;
  padding: 5px 9px;
  border: 1px solid var(--dsw-feedback-error-border, var(--dsw-alias-border-l2));
  border-radius: 7px;
  background: transparent;
  color: var(--dsw-feedback-error-text);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.dataset-delete:hover {
  background: var(--dsw-feedback-error-surface);
}
.dataset-delete:disabled {
  opacity: 0.45;
  cursor: default;
}
.dataset-delete svg {
  width: 13px;
  height: 13px;
  flex: none;
}
.dataset-detail h3 {
  margin: 7px 0;
  font-size: var(--dsw-text-title);
  font-weight: 600;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.dataset-description {
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
  color: var(--dsw-alias-text-tertiary);
  margin: 0 0 12px;
  overflow-wrap: anywhere;
}
.dataset-config {
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 9px;
  padding: 12px;
}
.dataset-config > summary {
  font-size: var(--dsw-text-sm);
}
.dataset-config > summary > span {
  margin-left: auto;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
}
.dataset-config > summary > span + svg {
  margin-left: 6px;
}
.dataset-config-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
}
.dataset-config-heading p {
  margin: 0;
}
.dataset-ai {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 8px;
  border: 1px solid var(--dsw-selection-border);
  border-radius: 7px;
  background: var(--dsw-selection-surface);
  color: var(--dsw-alias-link);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.dataset-ai svg {
  width: 14px;
  height: 14px;
}
.dataset-muted {
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
  color: var(--dsw-alias-text-tertiary);
  overflow-wrap: anywhere;
}
.dataset-ai-hint {
  margin: 9px 0 0;
}
.dataset-ai-hint button {
  margin-left: 5px;
}
.dataset-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}
.dataset-fields label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
}
.dataset-fields select {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 7px;
  padding: 7px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  font: inherit;
  font-size: var(--dsw-text-sm);
}
.dataset-fields select[aria-invalid='true'] {
  border-color: var(--dsw-feedback-error-text);
}
.dataset-metadata {
  display: grid;
  grid-template-columns: 65px minmax(0, 1fr);
  gap: 8px;
  margin: 14px 0 0;
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
}
.dataset-metadata dt {
  color: var(--dsw-alias-text-tertiary);
}
.dataset-metadata dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.dataset-ai-reason {
  margin: 12px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--dsw-specific-sidebar-fill);
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.dataset-ai-reason strong {
  font-weight: 500;
}
.dataset-ai-reason p {
  margin: 5px 0;
  white-space: pre-line;
}
.dataset-ai-reason small {
  color: var(--dsw-alias-text-tertiary);
}
.dataset-save-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.dataset-saved {
  flex: 1;
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
  color: var(--dsw-alias-text-secondary);
}
.dataset-save {
  padding: 8px 10px;
  border: 0;
  border-radius: 7px;
  background: var(--dsw-action-fill);
  color: var(--dsw-action-ink);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.dataset-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin: 18px 0 0;
  padding: 16px 0 0;
  border-top: 1px solid var(--dsw-alias-border-l2);
  background: transparent;
}
.dataset-footer > div {
  flex: 1 1 220px;
  min-width: 0;
}
.dataset-current {
  margin: 0;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.dataset-browse-note {
  margin: 5px 0 0;
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
  color: var(--dsw-alias-text-tertiary);
  overflow-wrap: anywhere;
}
.dataset-secondary-action {
  border: 0;
  background: transparent;
  color: var(--dsw-alias-link);
  padding: 0;
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.dataset-current .dataset-secondary-action {
  margin-left: 6px;
}
.dataset-confirm {
  flex: none;
  margin-left: auto;
  padding: 9px 12px;
  border: 0;
  border-radius: 8px;
  background: var(--dsw-action-fill);
  color: var(--dsw-action-ink);
  font: inherit;
  font-size: var(--dsw-text-sm);
  cursor: pointer;
  transition:
    background-color 160ms,
    transform 160ms;
}
.dataset-confirm:active {
  transform: scale(0.98);
}
.dataset-error {
  margin: 0 0 6px;
  color: var(--dsw-feedback-error-text);
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.dataset-empty {
  margin: 0;
  padding: 24px 10px;
  text-align: center;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-tertiary);
}
.dataset-placeholder {
  display: grid;
  place-content: center;
  min-height: 200px;
  padding: 18px;
  text-align: center;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-sm);
  line-height: 1.8;
}
.dataset-placeholder > svg {
  width: 24px;
  height: 24px;
  margin: auto;
}
.dataset-content-enter-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}
.dataset-content-leave-active {
  transition: opacity 120ms ease;
}
.dataset-content-enter-from {
  opacity: 0;
  transform: translateY(5px);
}
.dataset-content-leave-to {
  opacity: 0;
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  outline-offset: 3px;
}
@container dataset-library (min-width:700px) {
  .dataset-workspace {
    grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
    gap: 26px;
  }
  .dataset-detail {
    border-top: 0;
    border-left: 1px solid #edf1f8;
    padding-top: 0;
    padding-left: 26px;
  }
  .dataset-list {
    max-height: 520px;
  }
}
@container dataset-library (max-width:330px) {
  .dataset-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (prefers-reduced-motion: reduce) {
  .dataset-content-enter-active,
  .dataset-content-leave-active,
  .dataset-source-tabs::before,
  .dataset-source-tabs button,
  .dataset-filters button,
  .dataset-upload,
  .dataset-item,
  .dataset-confirm,
  summary > svg {
    transition: none;
  }
}

/* Editorial dataset workspace */
.dataset-library {
  padding: 20px 22px 22px;
  border: 1px solid #e6ecf6;
  border-radius: 22px;
  background: rgb(255 255 255 / 0.92);
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.03),
    0 30px 64px -56px rgb(20 40 80 / 0.4);
  backdrop-filter: blur(10px);
}
.dataset-section-heading {
  align-items: flex-start;
  gap: 12px;
}
.dataset-section-heading h3 {
  color: #14213a;
  font-size: 16px;
  font-weight: 650;
  letter-spacing: -0.015em;
  line-height: 1.3;
}
.dataset-section-heading h3::before {
  content: 'LIBRARY';
  display: block;
  margin-bottom: 3px;
  color: #8895aa;
  font-size: 8.5px;
  font-weight: 600;
  letter-spacing: 0.18em;
  line-height: 1.3;
}
.dataset-section-heading > span {
  margin-top: 2px;
  padding: 3px 8px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f7f9fd;
  color: #7b879c;
  font-size: 10px;
}
.dataset-source-tabs {
  height: 38px;
  margin-top: 15px;
  padding: 3px;
  border: 1px solid #e6ecf6;
  border-radius: 11px;
  background: #f3f6fb;
}
.dataset-source-tabs::before {
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgb(20 40 80 / 0.08);
}
.dataset-source-tabs button {
  border-radius: 8px;
  color: #74839a;
  font-size: 11.5px;
  font-weight: 500;
  transition: color 160ms ease;
}
.dataset-source-tabs button[aria-pressed='true'] {
  color: #1a2740;
  font-weight: 600;
}
.dataset-source-tabs button span {
  color: #93a0b3;
  font-size: 10px;
}
.dataset-search {
  margin: 11px 0 9px;
  padding: 10px 12px;
  border: 1px solid #e5ebf5;
  border-radius: 11px;
  background: #ffffff;
  color: #8a96ab;
  box-shadow: 0 1px 2px rgb(20 40 80 / 0.03);
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}
.dataset-search:focus-within {
  border-color: #9db5ee;
  box-shadow: 0 0 0 3px rgb(79 124 255 / 0.09);
}
.dataset-search input {
  font-size: 12px;
}
.dataset-filter-disclosure {
  margin-bottom: 10px;
}
.dataset-filter-disclosure > summary {
  padding: 1px 2px;
  color: #7b879c;
  font-size: 10.5px;
}
.dataset-filters button {
  padding: 5px 9px;
  border: 1px solid transparent;
  border-radius: 7px;
  font-size: 10.5px;
}
.dataset-filters button[aria-pressed='true'] {
  border-color: #dbe6fb;
  background: #edf3ff;
  color: #315fbd;
}
.dataset-upload {
  margin-bottom: 11px;
  padding: 11px 13px;
  border: 1px dashed #c8d8f0;
  border-radius: 12px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
  transition:
    background 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}
.dataset-upload:hover {
  border-color: #9db5ee;
  background: linear-gradient(135deg, #f4f9ff 0%, #e8f1ff 100%);
}
.dataset-upload.is-dragging {
  border-color: #4f7cff;
  background: #edf3ff;
  box-shadow: 0 0 0 3px rgb(79 124 255 / 0.08);
}
.dataset-upload button {
  gap: 6px;
  color: #315fbd;
  font-size: 11.5px;
  font-weight: 600;
}
.dataset-upload button svg {
  width: 14px;
  height: 14px;
}
.dataset-upload small {
  color: #8a96ab;
  font-size: 10px;
}
.dataset-list {
  max-height: 430px;
  padding-right: 3px;
  scrollbar-gutter: stable;
}
.dataset-item {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: #4f5d73;
  transition:
    background 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease,
    color 160ms ease;
}
.dataset-item:hover {
  border-color: #e7eefb;
  background: #f8faff;
  color: #1a2740;
}
.dataset-item.is-selected {
  border-color: #c9d9f8;
  background: #f7faff;
  color: #14213a;
  box-shadow: 0 8px 20px -22px rgb(20 40 80 / 0.45);
}
.dataset-item-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: linear-gradient(140deg, #eef4ff 0%, #dfe9ff 100%);
  color: #3d63c7;
  box-shadow: inset 0 0 0 1px rgb(79 124 255 / 0.1);
}
.dataset-item-icon svg {
  width: 15px;
  height: 15px;
}
.dataset-item-body {
  min-width: 0;
  flex: 1;
}
.dataset-item-title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.dataset-item strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  color: #1a2740;
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dataset-item-title em {
  flex: none;
  padding: 1px 6px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f7f9fd;
  color: #7b879c;
  font-size: 8.5px;
  font-style: normal;
  line-height: 1.5;
  white-space: nowrap;
}
.dataset-item small {
  margin-top: 2px;
  color: #8a96ab;
  font-size: 10px;
  line-height: 1.5;
}
.dataset-item-check {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  flex: none;
  border-radius: 50%;
  background: #edf3ff;
  color: #3d63c7;
}
.dataset-item-check svg {
  width: 13px;
  height: 13px;
}
.dataset-detail {
  min-width: 0;
}
.dataset-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}
.dataset-detail-title {
  min-width: 0;
}
.dataset-kind {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border: 1px solid #e1eaf9;
  border-radius: 999px;
  background: #eef4ff;
  color: #3d63c7;
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
  line-height: 1.5;
}
.dataset-detail h3 {
  margin: 8px 0 0;
  color: #13203a;
  font-size: 24px;
  font-weight: 650;
  letter-spacing: -0.025em;
  line-height: 1.25;
}
.dataset-description {
  max-width: 760px;
  margin: 9px 0 0;
  color: #647086;
  font-size: 12px;
  line-height: 1.7;
}
.dataset-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 14px 0 4px;
}
.dataset-stats span {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 5px 9px;
  border: 1px solid #e6ecf6;
  border-radius: 9px;
  background: #f8faff;
  color: #7b879c;
  font-size: 9.5px;
  line-height: 1.5;
}
.dataset-stats b {
  color: #1a2740;
  font-size: 11.5px;
  font-weight: 650;
}
.dataset-delete {
  flex: none;
  margin: 3px 0 0;
  padding: 5px 9px;
  border: 1px solid #f0d4d2;
  border-radius: 8px;
  background: #fffafa;
  color: #b63d30;
  font-size: 10px;
}
.dataset-delete:hover {
  background: #fdecec;
}
.dataset-config {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid #e6ecf6;
  border-radius: 13px;
  background: #fbfcff;
}
.dataset-config > summary {
  color: #4f5d73;
  font-size: 12px;
}
.dataset-config-heading {
  margin-top: 13px;
}
.dataset-ai {
  padding: 6px 9px;
  border-color: #dbe6fb;
  border-radius: 8px;
  background: #edf3ff;
  color: #315fbd;
}
.dataset-fields select {
  border-color: #e5ebf5;
  border-radius: 8px;
  background: #ffffff;
}
.dataset-ai-reason {
  border: 1px solid #e6ecf6;
  border-radius: 10px;
  background: #f8faff;
}
.dataset-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 24px;
  text-align: center;
}
.dataset-placeholder-icon {
  display: grid;
  place-items: center;
  width: 66px;
  height: 66px;
  border-radius: 21px;
  background: linear-gradient(145deg, #eef4ff 0%, #dfe9ff 100%);
  color: #3d63c7;
  box-shadow:
    inset 0 0 0 1px rgb(79 124 255 / 0.12),
    0 18px 34px -26px rgb(30 60 120 / 0.5);
}
.dataset-placeholder-icon svg {
  width: 27px;
  height: 27px;
}
.dataset-placeholder h3 {
  margin: 16px 0 0;
  color: #1a2740;
  font-size: 19px;
  font-weight: 650;
  letter-spacing: -0.02em;
  line-height: 1.3;
}
.dataset-placeholder p {
  max-width: 420px;
  margin: 7px 0 0;
  color: #7b879c;
  font-size: 11.5px;
  line-height: 1.7;
}
.dataset-placeholder-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 14px;
}
.dataset-placeholder-chips span {
  padding: 4px 9px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f8faff;
  color: #8a96ab;
  font-size: 9.5px;
  line-height: 1.5;
}
.dataset-footer {
  margin-top: 16px;
  padding-top: 14px;
  border-top-color: #edf1f8;
}
.dataset-confirm {
  border-radius: 10px;
  border: 1px solid #d7e3fb;
  background: #eef3ff;
  color: #274a9a;
  box-shadow: none;
}
@media (max-width: 720px) {
  .dataset-library {
    padding: 15px 14px 16px;
    border-radius: 18px;
  }
  .dataset-placeholder {
    min-height: 320px;
  }
  .dataset-detail h3 {
    font-size: 21px;
  }
}
</style>
