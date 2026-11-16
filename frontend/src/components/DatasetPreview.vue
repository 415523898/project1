<script setup lang="ts">
import { useDialogViewport } from '@/composables/useDialogMotion';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import CopyRegion from '@/components/CopyRegion.vue';
import { useLab } from '@/composables/useLab';
import { previewDataset, type DatasetPage } from '@/services/files';
import type { DatasetChoice } from '@/types';

const props = withDefaults(defineProps<{ dataset: DatasetChoice; copyable?: boolean }>(), {
  copyable: true,
});
const lab = useLab(),
  sample = ref<DatasetPage | null>(null),
  page = ref<DatasetPage | null>(null);
const loading = ref(false),
  error = ref(''),
  expanded = ref(false),
  dialog = ref<HTMLDialogElement | null>(null);
useDialogViewport(dialog);
const opener = ref<HTMLButtonElement | null>(null),
  pageSize = ref(50),
  pageNumber = ref(1),
  fieldQuery = ref('');
let sequence = 0,
  request: AbortController | undefined,
  requestedOffset = 0;
const columns = computed(() => sample.value?.column_names ?? []);
const pageCount = computed(() =>
  Math.max(
    1,
    Math.ceil((page.value?.total_rows ?? sample.value?.total_rows ?? 0) / pageSize.value),
  ),
);
const shownColumns = computed(() =>
  (page.value?.column_names ?? [])
    .map((name, index) => ({ name, index }))
    .filter((column) => column.name.toLowerCase().includes(fieldQuery.value.trim().toLowerCase())),
);
const display = (value: unknown) =>
  value === null || value === undefined || value === '' ? '—' : String(value);

async function load(offset = 0, full = false) {
  request?.abort();
  const controller = new AbortController();
  request = controller;
  const ticket = ++sequence,
    owner = lab.state.user,
    source = props.dataset.dataset;
  requestedOffset = offset;
  loading.value = true;
  error.value = '';
  const timeout = setTimeout(
    () => controller.abort(new DOMException('读取超过 15 秒，请重试。', 'TimeoutError')),
    15000,
  );
  try {
    const result = await previewDataset(
      source,
      offset,
      full ? pageSize.value : 5,
      controller.signal,
    );
    if (ticket !== sequence || owner !== lab.state.user || source !== props.dataset.dataset) return;
    if (full) {
      page.value = result;
      pageNumber.value = Math.floor(result.offset / pageSize.value) + 1;
    } else sample.value = result;
  } catch (problem) {
    if (ticket === sequence)
      error.value =
        (controller.signal.reason ?? (problem as Error)).message || '数据读取失败，请重试。';
  } finally {
    clearTimeout(timeout);
    if (ticket === sequence) loading.value = false;
  }
}
async function open() {
  expanded.value = true;
  fieldQuery.value = '';
  await nextTick();
  if (dialog.value?.showModal) dialog.value.showModal();
  else dialog.value?.setAttribute('open', '');
  await load(0, true);
}
function close() {
  sequence++;
  request?.abort();
  loading.value = false;
  error.value = '';
  expanded.value = false;
  if (dialog.value?.close) dialog.value.close();
  else dialog.value?.removeAttribute('open');
  opener.value?.focus({ preventScroll: true });
}
function jump(number: number) {
  const next = Math.min(pageCount.value, Math.max(1, Math.trunc(number) || 1));
  void load((next - 1) * pageSize.value, true);
}
watch(
  () => [props.dataset.dataset, lab.state.user, lab.state.authExpired] as const,
  () => {
    if (expanded.value) close();
    sequence++;
    request?.abort();
    sample.value = null;
    page.value = null;
    error.value = '';
    if (lab.state.user && !lab.state.authExpired) void load();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  sequence++;
  request?.abort();
  dialog.value?.close?.();
});
</script>

<template>
  <section class="data-preview" data-role="dataset-preview">
    <div class="preview-heading"
      ><div
        ><h4>数据预览</h4
        ><span v-if="sample"
          >源表 {{ sample.total_rows.toLocaleString() }} 行 · {{ columns.length }} 列</span
        ></div
      ><button
        ref="opener"
        type="button"
        class="expand-data"
        data-action="expand-full-data"
        :disabled="!sample || loading"
        @click="open"
        ><UiIcon name="fit" />查看完整数据</button
      ></div
    >
    <p v-if="loading && !expanded" class="preview-note" role="status">正在读取数据…</p>
    <CopyRegion v-if="sample" kind="table" :copyable="copyable">
      <div class="sample-scroll" tabindex="0" aria-label="前 5 行数据预览">
        <table
          ><thead
            ><tr
              ><th class="row-number">行</th
              ><th v-for="column in columns.slice(0, 6)" :key="column" :title="column">{{
                column
              }}</th></tr
            ></thead
          >
          <tbody
            ><tr v-for="(row, index) in sample.rows" :key="index"
              ><th class="row-number">{{ index + 1 }}</th
              ><td
                v-for="(column, i) in columns.slice(0, 6)"
                :key="column"
                :title="display(row[i])"
                >{{ display(row[i]) }}</td
              ></tr
            ></tbody
          ></table
        >
      </div>
    </CopyRegion>
    <div class="preview-bottom"
      ><span class="preview-note"
        >前 {{ sample?.rows.length ?? 5 }} 行<span v-if="columns.length > 6"> · 前 6 列</span></span
      ></div
    >
    <p v-if="error && !expanded" class="preview-error" role="alert"
      >{{ error }} <button type="button" @click="load()">重试</button></p
    >
    <Teleport to="body">
      <dialog
        v-if="expanded"
        ref="dialog"
        class="full-data-dialog"
        aria-labelledby="full-data-title"
        data-role="full-data-dialog"
        @cancel.prevent="close"
      >
        <header class="full-data-head"
          ><div
            ><h2 id="full-data-title">{{ dataset.name || dataset.id }}</h2
            ><p
              >完整数据 · {{ (page?.total_rows ?? sample?.total_rows ?? 0).toLocaleString() }} 行 ·
              {{ columns.length }} 列</p
            ></div
          >
          <button type="button" class="close-data" aria-label="关闭完整数据" @click="close"
            ><UiIcon name="close" /></button
        ></header>
        <div class="full-data-toolbar"
          ><p>数据表内容，实验结果可能采用清洗后的行列。</p
          ><label
            ><UiIcon name="search" /><input
              v-model="fieldQuery"
              aria-label="筛选数据字段"
              placeholder="筛选字段" /></label
        ></div>
        <CopyRegion kind="table" class="full-data-copy" :copyable="copyable">
          <div class="full-data-scroll" tabindex="0" aria-label="完整数据表格" :aria-busy="loading">
            <table v-if="page"
              ><thead
                ><tr
                  ><th class="row-number">行</th
                  ><th v-for="column in shownColumns" :key="column.name">{{ column.name }}</th></tr
                ></thead
              >
              <tbody
                ><tr v-for="(row, index) in page.rows" :key="page.offset + index"
                  ><th class="row-number">{{ page.offset + index + 1 }}</th
                  ><td v-for="column in shownColumns" :key="column.name">{{
                    display(row[column.index])
                  }}</td></tr
                ></tbody
              ></table
            >
            <p v-if="loading" class="full-data-status" role="status">正在读取数据…</p>
            <p v-else-if="page && !shownColumns.length" class="full-data-status"
              >没有匹配的字段。</p
            >
            <p v-else-if="page && !page.rows.length" class="full-data-status">当前页没有数据。</p>
          </div>
        </CopyRegion>
        <p v-if="error" class="full-data-error" role="alert"
          >{{ error }}
          <button type="button" @click="load(requestedOffset, true)">重新读取</button></p
        >
        <footer class="full-data-footer"
          ><span
            >{{ page ? `${page.offset + 1}–${page.offset + page.rows.length}` : '—' }} /
            {{ (page?.total_rows ?? sample?.total_rows ?? 0).toLocaleString() }} 行</span
          >
          <label
            >每页<select
              v-model="pageSize"
              aria-label="每页行数"
              :disabled="loading"
              @change="jump(1)"
              ><option :value="25">25 行</option
              ><option :value="50">50 行</option
              ><option :value="100">100 行</option></select
            ></label
          >
          <div class="page-actions"
            ><button
              type="button"
              aria-label="上一页数据"
              :disabled="loading || !page || page.offset === 0"
              @click="jump(pageNumber - 1)"
              ><UiIcon name="chevron-left"
            /></button>
            <label
              >第<input
                v-model.number="pageNumber"
                type="number"
                min="1"
                :max="pageCount"
                aria-label="数据页码"
                :disabled="loading"
                @change="jump(pageNumber)"
                @keydown.enter.prevent="jump(pageNumber)"
              />
              / {{ pageCount }} 页</label
            >
            <button
              type="button"
              aria-label="下一页数据"
              :disabled="loading || !page || page.offset + page.rows.length >= page.total_rows"
              @click="jump(pageNumber + 1)"
              ><UiIcon name="chevron-right" /></button></div
        ></footer>
      </dialog>
    </Teleport>
  </section>
</template>

<style scoped>
.data-preview {
  min-width: 0;
  margin: 16px 0;
}
.preview-heading,
.preview-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.preview-heading {
  margin-bottom: 8px;
}
.preview-heading h4 {
  margin: 0 0 3px;
  font-size: var(--dsw-text-sm);
  font-weight: 600;
}
.preview-heading > div > span,
.preview-note {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
}
.sample-scroll {
  max-height: 240px;
  overflow: auto;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 9px;
}
.data-preview table,
.full-data-dialog table {
  border-collapse: separate;
  border-spacing: 0;
  min-width: 100%;
  font-size: var(--dsw-text-sm);
  text-align: left;
}
.data-preview th,
.data-preview td,
.full-data-dialog th,
.full-data-dialog td {
  padding: 8px 11px;
  border-bottom: 1px solid var(--dsw-alias-border-l1);
  white-space: nowrap;
}
.data-preview thead th,
.full-data-dialog thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--dsw-specific-sidebar-fill);
  font-weight: 500;
  color: var(--dsw-alias-text-secondary);
}
.sample-scroll td,
.sample-scroll th {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: var(--dsw-text-xs);
}
.row-number {
  position: sticky;
  left: 0;
  z-index: 1;
  min-width: 42px;
  text-align: right;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-tertiary);
  font-weight: 400;
}
.data-preview thead .row-number,
.full-data-dialog thead .row-number {
  z-index: 3;
}
.preview-bottom {
  margin-top: 9px;
}
.expand-data {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-link);
  font: inherit;
  font-size: var(--dsw-text-sm);
  cursor: pointer;
  padding: 5px 0;
}
.expand-data svg {
  width: 14px;
  height: 14px;
}
.preview-error,
.full-data-error {
  color: var(--dsw-feedback-error-text);
  font-size: var(--dsw-text-sm);
  line-height: 1.6;
}
.preview-error button,
.full-data-error button {
  color: inherit;
  text-decoration: underline;
}
.full-data-dialog {
  width: min(1440px, 94vw);
  height: min(850px, 90dvh);
  max-width: none;
  max-height: none;
  padding: 0;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 16px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  overflow: hidden;
  box-shadow: 0 24px 80px #17294133;
}
.full-data-dialog[open] {
  display: flex;
  flex-direction: column;
}
.full-data-dialog::backdrop {
  background: #15243c66;
}
.full-data-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px 12px;
  flex: none;
}
.full-data-head > div {
  min-width: 0;
}
.full-data-head h2 {
  margin: 0;
  font-size: var(--dsw-text-lg);
  overflow-wrap: anywhere;
}
.full-data-head p {
  margin: 5px 0 0;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-sm);
}
.close-data {
  display: grid;
  place-items: center;
  flex: none;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 7px;
  background: var(--dsw-specific-sidebar-fill);
  cursor: pointer;
}
.close-data svg {
  width: 17px;
  height: 17px;
}
.full-data-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 0 22px 12px;
  flex: none;
}
.full-data-toolbar p {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-tertiary);
  margin: 0;
}
.full-data-toolbar label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 9px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 7px;
  max-width: 100%;
}
.full-data-toolbar svg {
  width: 14px;
  height: 14px;
  color: var(--dsw-alias-text-tertiary);
}
.full-data-toolbar input {
  border: 0;
  background: transparent;
  outline: 0;
  font-size: var(--dsw-text-sm);
  width: 150px;
  min-width: 0;
}
.full-data-copy {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.full-data-copy :deep(.copy-content) {
  display: flex;
  flex: 1;
  min-height: 0;
}
.full-data-scroll {
  overflow: auto;
  min-height: 0;
  flex: 1;
  border-block: 1px solid var(--dsw-alias-border-l2);
  overscroll-behavior: contain;
}
.full-data-scroll td {
  max-width: 460px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  min-width: 100px;
  vertical-align: top;
  line-height: 1.6;
}
.full-data-scroll tbody tr:hover td {
  background: var(--dsw-specific-sidebar-fill);
}
.full-data-status {
  padding: 22px;
  text-align: center;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-tertiary);
}
.full-data-error {
  margin: 9px 20px;
}
.full-data-footer {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  flex: none;
  padding: 12px 20px;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
}
.full-data-footer > span {
  margin-right: auto;
}
.full-data-footer label,
.page-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.full-data-footer input,
.full-data-footer select {
  padding: 5px 7px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  background: var(--dsw-alias-bg-layer-1);
  font: inherit;
  min-width: 0;
}
.full-data-footer input {
  width: 62px;
}
.page-actions button {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  cursor: pointer;
}
.page-actions svg {
  width: 14px;
  height: 14px;
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  outline-offset: 2px;
}
@media (max-width: 600px) {
  .full-data-dialog {
    width: 96vw;
    height: 94dvh;
    border-radius: 12px;
  }
  .full-data-head {
    padding: 15px;
  }
  .full-data-toolbar {
    padding: 0 15px 12px;
  }
  .full-data-toolbar p {
    flex-basis: 100%;
  }
  .full-data-footer {
    padding: 10px 12px;
    gap: 10px;
  }
  .page-actions {
    flex-basis: 100%;
    justify-content: center;
  }
  .full-data-footer > label {
    margin-left: auto;
  }
}

/* Editorial preview surface */
.data-preview {
  margin: 16px 0 4px;
}
.preview-heading {
  align-items: flex-end;
  margin-bottom: 10px;
}
.preview-heading h4 {
  margin: 0;
  color: #1a2740;
  font-size: 13px;
  font-weight: 650;
  letter-spacing: -0.01em;
}
.preview-heading > div {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.preview-heading > div > span {
  padding: 2px 7px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f8faff;
  color: #8a96ab;
  font-size: 9.5px;
  line-height: 1.5;
}
.expand-data {
  padding: 6px 10px;
  border: 1px solid #dfe9f8;
  border-radius: 8px;
  background: #f7faff;
  color: #315fbd;
  font-size: 10.5px;
  font-weight: 600;
  transition:
    background 160ms ease,
    border-color 160ms ease;
}
.expand-data:hover:not(:disabled) {
  border-color: #b9cdf6;
  background: #edf3ff;
}
.sample-scroll {
  max-height: 300px;
  border: 1px solid #e6ecf6;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 8px 24px -30px rgb(20 40 80 / 0.4);
}
.data-preview table {
  font-size: 11.5px;
}
.data-preview th,
.data-preview td {
  padding: 8px 11px;
  border-bottom: 1px solid #edf1f8;
}
.data-preview thead th {
  background: #f7f9fd;
  color: #647086;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.data-preview tbody tr:hover td {
  background: #fbfcff;
}
.row-number {
  background: #fbfcff;
  color: #9aa7ba;
}
.preview-bottom {
  margin-top: 8px;
}
.preview-note {
  color: #8a96ab;
  font-size: 9.5px;
}
.full-data-dialog {
  border: 1px solid #e2e9f4;
  border-radius: 20px;
  box-shadow: 0 30px 90px -30px rgb(15 30 60 / 0.5);
}
.full-data-dialog::backdrop {
  background: rgb(11 21 48 / 0.5);
  backdrop-filter: blur(4px);
}
.full-data-head {
  padding: 20px 24px 14px;
  border-bottom: 1px solid #edf1f8;
}
.full-data-head h2 {
  color: #13203a;
  font-size: 18px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.full-data-head p {
  color: #7b879c;
  font-size: 11px;
}
.close-data {
  border: 1px solid #e6ecf6;
  background: #f8faff;
  color: #4f5d73;
}
.full-data-toolbar {
  padding-top: 12px;
  border-bottom: 1px solid #edf1f8;
}
.full-data-toolbar label {
  border-color: #e5ebf5;
  border-radius: 8px;
  background: #ffffff;
}
.full-data-scroll {
  border-block-color: #edf1f8;
}
.full-data-dialog thead th {
  background: #f7f9fd;
  color: #647086;
  font-size: 10px;
}
.full-data-footer {
  border-top: 1px solid #edf1f8;
  color: #647086;
}
.full-data-footer input,
.full-data-footer select {
  border-color: #e5ebf5;
  border-radius: 7px;
}
.page-actions button {
  border-color: #e5ebf5;
  border-radius: 7px;
  background: #ffffff;
}
</style>
