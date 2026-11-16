<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useLab } from '@/composables/useLab';
import { currentDatasetInfo, type CurrentDatasetInfo } from '@/services/files';
import UiIcon from '@/components/UiIcon.vue';
import DatasetPreview from '@/components/DatasetPreview.vue';
import { vDisclosureMotion } from '@/utils/disclosure-motion';
const lab = useLab(),
  info = ref<CurrentDatasetInfo | null>(null),
  error = ref(''),
  loading = ref(false);
const retry = ref(0);
let version = 0,
  abort: AbortController | undefined;
const tasks: Record<string, string> = {
  classification: '分类',
  regression: '回归',
  clustering: '聚类／无目标分析',
};
const data = computed(() => info.value?.dataset);
const resultKey = computed(
  () =>
    lab.blocks?.value
      ?.map((item) =>
        [item.result.dataset, item.result.experiment_id, item.result.experiment_version].join(':'),
      )
      .join('|') ?? '',
);
watch(
  () =>
    [
      lab.state.user,
      lab.state.sessionId,
      lab.state.authExpired,
      lab.activeDataset.value?.dataset,
      resultKey.value,
      lab.state.busy,
      retry.value,
    ] as const,
  async ([owner, session, expired], previous) => {
    const ticket = ++version;
    abort?.abort();
    error.value = '';
    if (!previous || previous[0] !== owner || previous[1] !== session) info.value = null;
    if (!owner || !session || expired) {
      loading.value = false;
      return;
    }
    const request = new AbortController();
    abort = request;
    loading.value = true;
    const timeout = setTimeout(
      () =>
        request.abort(new DOMException('读取当前数据集超过 15 秒，请重新读取。', 'TimeoutError')),
      15000,
    );
    try {
      const value = await currentDatasetInfo(session, request.signal);
      if (ticket === version) info.value = value;
    } catch (problem) {
      if (
        ticket === version &&
        (request.signal.reason?.name === 'TimeoutError' || (problem as Error).name !== 'AbortError')
      )
        error.value = (request.signal.reason ?? (problem as Error)).message;
    } finally {
      clearTimeout(timeout);
      if (ticket === version) loading.value = false;
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  version++;
  abort?.abort();
});
</script>
<template>
  <section class="current-dataset" data-role="current-dataset" aria-label="当前数据集">
    <Transition name="current-data" mode="out-in">
      <div v-if="data" :key="data.dataset" class="current-content">
        <div class="current-heading"
          ><span>当前数据集</span
          ><span class="dataset-mode" :class="{ 'is-manual': info?.selection_mode === 'manual' }">{{
            info?.selection_mode === 'manual' ? '手动指定' : 'AI 自动选择'
          }}</span></div
        >
        <header
          ><UiIcon name="table" /><h3>{{ data.name || data.label || data.dataset }}</h3></header
        >
        <p class="dataset-description">{{ data.description }}</p>
        <dl class="current-dataset-facts"
          ><div
            ><dt>分析概况</dt
            ><dd
              >{{ data.rows?.toLocaleString() ?? '—' }} 行 · {{ data.columns ?? '—' }} 列</dd
            ></div
          ><div
            ><dt>任务</dt><dd>{{ tasks[data.task] || data.task }}</dd></div
          ><div
            ><dt>目标列</dt><dd>{{ data.target || '未指定' }}</dd></div
          ></dl
        >
        <DatasetPreview :dataset="data" :copyable="false" />
        <p class="current-scope-note">预览包含完整源表，具体实验的有效行列以结果为准。</p>
        <details v-disclosure-motion class="current-metadata"
          ><summary>字段与选择依据<UiIcon name="chevron-down" /></summary>
          <div class="current-metadata-body">
            <p v-if="info?.reason" class="dataset-note">{{ info.reason }}</p>
            <p class="dataset-note">{{
              data.kind === 'upload' ? '当前账号上传的数据' : `内置数据 · ${data.dataset}`
            }}</p>
            <p v-if="data.time" class="dataset-note">时间列：{{ data.time }}</p
            ><p v-if="data.group" class="dataset-note">分组列：{{ data.group }}</p>
            <div v-if="data.column_names?.length" class="current-fields" aria-label="数据字段"
              ><code v-for="column in data.column_names" :key="column">{{ column }}</code></div
            >
            <p v-for="note in info?.notes" :key="note" class="dataset-note">{{ note }}</p>
          </div>
        </details>
      </div>
      <div v-else class="current-empty"
        ><span class="current-empty-icon"><UiIcon name="table" /></span
        ><h3>{{
          loading ? '正在读取当前数据集' : error ? '暂时无法读取数据集' : '尚未选定数据集'
        }}</h3
        ><p>{{
          loading
            ? '读取已确认的数据来源…'
            : error
              ? '已保存的数据来源会保留，重新读取后可继续查看。'
              : '手动指定数据集，或保持 AI 自动选择；开始实验后这里会显示当前使用的数据。'
        }}</p></div
      >
    </Transition>
    <p v-if="error" class="dataset-load-error" role="status"
      >{{ error }} <button type="button" @click="retry++">重新读取</button></p
    >
  </section>
</template>
<style scoped>
.current-dataset {
  min-width: 0;
  padding: 18px 20px;
  background: var(--dsw-alias-bg-layer-1);
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 12px;
  color: var(--dsw-alias-text-primary);
  font-size: var(--dsw-text-sm);
  line-height: 1.65;
  overflow: hidden;
}
.current-content {
  min-width: 0;
}
.current-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
}
.dataset-mode {
  flex: none;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--dsw-selection-surface);
  color: var(--dsw-alias-link);
  font-size: var(--dsw-text-xs);
}
.dataset-mode.is-manual {
  background: var(--dsw-specific-sidebar-fill);
  color: var(--dsw-alias-text-secondary);
}
.current-dataset header {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}
.current-dataset header > svg {
  width: 18px;
  height: 18px;
  flex: none;
  margin-top: 3px;
  color: var(--dsw-alias-link);
}
h3 {
  margin: 0;
  font-size: var(--dsw-text-title);
  font-weight: 600;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.dataset-description {
  margin: 10px 0 16px;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
  overflow-wrap: anywhere;
}
.current-dataset-facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(105px, 1fr));
  gap: 10px;
  margin: 0 0 18px;
  padding: 12px 0;
  border-block: 1px solid var(--dsw-alias-border-l1);
}
.current-dataset-facts > div {
  min-width: 0;
}
.current-dataset-facts dt {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
  margin-bottom: 4px;
}
.current-dataset-facts dd {
  margin: 0;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
.current-scope-note {
  margin: 8px 0 14px;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
  line-height: 1.6;
}
.current-metadata {
  padding-top: 12px;
  border-top: 1px solid var(--dsw-alias-border-l1);
}
.current-metadata summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  list-style: none;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.current-metadata summary::-webkit-details-marker {
  display: none;
}
.current-metadata summary > svg {
  width: 14px;
  height: 14px;
  flex: none;
  transition: transform 200ms ease;
}
.current-metadata:is([open], [data-disclosure-expanded='true']) summary > svg {
  transform: rotate(180deg);
}
.current-metadata[data-disclosure-expanded='false'] summary > svg {
  transform: none;
}
.current-metadata-body {
  padding-top: 8px;
}
.current-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 10px 0;
  max-height: 160px;
  overflow: auto;
}
.current-fields code {
  max-width: 100%;
  overflow-wrap: anywhere;
  font-size: var(--dsw-text-xs);
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--dsw-specific-sidebar-fill);
  color: var(--dsw-alias-text-secondary);
}
.dataset-note {
  margin: 6px 0 0;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
  overflow-wrap: anywhere;
}
.dataset-load-error {
  margin: 10px 0 0;
  color: var(--dsw-feedback-error-text);
  font-size: var(--dsw-text-xs);
  overflow-wrap: anywhere;
}
.dataset-load-error button {
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}
.current-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  text-align: center;
  padding: 18px;
  color: var(--dsw-alias-text-secondary);
}
.current-empty h3 {
  font-size: var(--dsw-text-base);
}
.current-empty p {
  margin: 9px 0 0;
  font-size: var(--dsw-text-sm);
  line-height: 1.8;
  color: var(--dsw-alias-text-tertiary);
  max-width: 300px;
}
.current-empty-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  margin-bottom: 14px;
  border-radius: 11px;
  background: var(--dsw-selection-surface);
  color: var(--dsw-alias-link);
}
.current-empty-icon svg {
  width: 21px;
  height: 21px;
}
.current-data-enter-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}
.current-data-leave-active {
  transition: opacity 120ms ease;
}
.current-data-enter-from {
  opacity: 0;
  transform: translateY(5px);
}
.current-data-leave-to {
  opacity: 0;
}
:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  outline-offset: 3px;
}
@media (max-width: 600px) {
  .current-dataset {
    padding: 16px;
  }
  .current-empty {
    min-height: 280px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .current-data-enter-active,
  .current-data-leave-active,
  .current-metadata summary > svg {
    transition: none;
  }
}
</style>
