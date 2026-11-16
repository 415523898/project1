<script setup lang="ts">
import { computed, ref } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import CopyRegion from '@/components/CopyRegion.vue';
import ResultExplanation from '@/components/ResultExplanation.vue';
import { vDisclosureMotion } from '@/utils/disclosure-motion';
import type { ExperimentResult } from '@/types';
import { displayLabel, displayValue, entryMetrics } from '@/utils/result-format';
import { experimentRows, resultTables } from '@/utils/result-summary';
import { resultIntegrity } from '@/utils/result-integrity';
import { learnerValue } from '@/utils/learner-text';

const props = defineProps<{
  result: ExperimentResult;
  requested?: string[];
  labels?: Record<string, string>;
  compact?: boolean;
}>();
const rows = computed(() =>
  experimentRows(props.result, props.requested, (id) => props.labels?.[id]),
);
const details = computed(() =>
  rows.value
    .filter((row) => row.entry)
    .map((row) => ({
      ...row,
      metrics: entryMetrics(row.entry!, row.id),
      tables: resultTables(row.entry!),
      integrity: resultIntegrity(row.entry!),
    })),
);
const rawLoaded = ref(false);
const rawJson = computed(() => JSON.stringify(learnerValue(props.result), null, 2));
const context = computed(() => {
  const data = props.result.data;
  const datasets = props.result.datasets ?? [];
  const multiple =
    new Set(datasets.map((item) => item.dataset || item.source || item.label)).size > 1;
  const parts = multiple
    ? [
        datasets
          .map((item) => item.label || item.source || item.dataset)
          .filter(Boolean)
          .join('、'),
      ]
    : [props.result.dataset_label || data?.label || props.result.source || props.result.dataset];
  const count = data?.rows ?? data?.records;
  if (!multiple && typeof count === 'number') parts.push(`${count} 行`);
  if (!multiple && typeof data?.columns === 'number') parts.push(`${data.columns} 列`);
  return parts.filter(Boolean).join(' · ');
});
function prepareRaw(open: boolean) {
  if (open) rawLoaded.value = true;
}
function showRaw(event: Event) {
  prepareRaw((event.target as HTMLDetailsElement).open);
}
</script>

<template>
  <section class="experiment-outcome" data-role="experiment-outcome">
    <p v-if="context" class="outcome-caption" data-role="result-context">{{ context }}</p>
    <table v-if="rows.length" class="result-table outcome-summary" data-role="metric-table">
      <colgroup><col style="width: 30%" /><col /></colgroup>
      <thead
        ><tr><th scope="col">方法</th><th scope="col">结果摘要</th></tr></thead
      >
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.id"
          :data-method-result="row.id"
          :data-result-status="row.status"
        >
          <td
            ><span class="outcome-method"
              >{{ row.label }}
              <span
                v-if="row.status !== 'success'"
                class="outcome-state"
                :class="row.status"
                aria-label="运行状态"
              >
                <UiIcon :name="row.status === 'error' ? 'warning' : 'clock'" class="h-3 w-3" />{{
                  row.status === 'error' ? '未完成' : '无结果'
                }}
              </span>
            </span></td
          >
          <td :class="row.status === 'error' && 'outcome-error'">{{ row.summary }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="!result.results?.length" class="outcome-empty" data-role="result-empty"
      >本次运行未返回方法结果、指标或结果表。</p
    >

    <template v-for="row in details" :key="row.id">
      <section
        v-if="
          row.status === 'success' ||
          (!compact && (row.metrics.length || row.tables.length))
        "
        class="outcome-detail"
        :data-method-detail="row.id"
      >
        <h4 v-if="details.length > 1">{{ row.label }}</h4>
        <p v-if="details.length > 1 && row.entry?.dataset_label" class="outcome-caption">{{
          row.entry.dataset_label
        }}</p>
        <p v-if="row.entry?.split" class="outcome-caption" data-role="method-split">
          划分：{{ (row.entry.split as ExperimentResult['split'])?.kind }}
          <template v-if="(row.entry.split as ExperimentResult['split'])?.train !== undefined">
            · 训练 {{ (row.entry.split as ExperimentResult['split'])?.train }}</template
          >
          <template v-if="(row.entry.split as ExperimentResult['split'])?.test !== undefined">
            · 测试 {{ (row.entry.split as ExperimentResult['split'])?.test }}</template
          >
        </p>
        <p
          v-if="row.entry?.metrics?.evaluation_scope && !row.integrity.length"
          class="outcome-caption"
          data-role="evaluation-scope"
        >
          评价范围：{{ displayValue(row.entry.metrics.evaluation_scope, 'evaluation_scope') }}
          <template v-if="typeof row.entry.metrics.evaluation_rows === 'number'">
            · {{ row.entry.metrics.evaluation_rows }} 条</template
          >
          <template v-else>（拟合/推断统计，未评价保留测试集）</template>
        </p>
        <ResultExplanation
          v-if="row.status === 'success' && row.entry && !row.integrity.length"
          :result="result"
          :method="row.id"
          :entry="row.entry"
          :label="row.label"
        />
        <details
          v-if="!compact && row.metrics.length"
          v-disclosure-motion
          class="outcome-disclosure"
          data-role="method-metrics"
        >
          <summary class="ui-disclosure"
            ><UiIcon name="chevron-right" class="h-3 w-3" /><span
              >指标详情（{{ row.metrics.length }}）</span
            ></summary
          >
          <dl class="outcome-metrics">
            <div v-for="metric in row.metrics" :key="metric.key"
              ><dt :title="metric.key">{{ metric.label }}</dt
              ><dd>{{ metric.value }}</dd></div
            >
          </dl>
        </details>
        <details
          v-for="table in compact ? [] : row.tables"
          :key="table.key"
          v-disclosure-motion
          class="outcome-disclosure"
          :open="rows.length === 1 && row.tables.length === 1"
          data-role="method-table"
        >
          <summary class="ui-disclosure"
            ><UiIcon name="chevron-right" class="h-3 w-3" /><span
              >{{ table.label
              }}<template v-if="!table.raw">（{{ table.total }} 行）</template></span
            ></summary
          >
          <CopyRegion v-if="table.columns.length" kind="table">
            <div class="outcome-table-scroll" tabindex="0" :aria-label="table.label">
              <table class="result-table outcome-data" data-role="result-data-table">
                <thead
                  ><tr
                    ><th
                      v-for="(column, index) in table.columns"
                      :key="index"
                      scope="col"
                      :title="column"
                      >{{ displayLabel(column) }}</th
                    ></tr
                  ></thead
                >
                <tbody
                  ><tr v-for="(cells, index) in table.rows" :key="index">
                    <td v-for="(column, cell) in table.columns" :key="cell">{{
                      displayValue(cells[cell], column)
                    }}</td>
                  </tr></tbody
                >
              </table>
              <p v-if="!table.rows.length" class="outcome-empty">此结果表没有数据行。</p>
            </div>
          </CopyRegion>
          <CopyRegion v-else-if="table.raw" kind="code">
            <pre class="outcome-json">{{ JSON.stringify(learnerValue(table.raw), null, 2) }}</pre>
          </CopyRegion>
          <p v-else class="outcome-empty">此结果表没有数据行。</p>
          <p v-if="table.truncated" class="outcome-caption" data-role="table-truncated"
            >共 {{ table.total }} 行，服务端返回前 {{ table.rows.length }} 行。</p
          >
        </details>
      </section>
    </template>
    <details
      v-if="!compact"
      v-disclosure-motion="prepareRaw"
      class="outcome-disclosure"
      data-role="metric-json"
      @toggle="showRaw"
    >
      <summary class="ui-disclosure"
        ><UiIcon name="chevron-right" class="h-3 w-3" /><span>完整运行结果 JSON</span></summary
      >
      <CopyRegion v-if="rawLoaded" kind="code" :text="rawJson">
        <pre class="outcome-json">{{ rawJson }}</pre>
      </CopyRegion>
    </details>
  </section>
</template>

<style scoped>
.experiment-outcome {
  min-width: 0;
  container-type: inline-size;
  font-size: var(--dsw-text-sm);
  line-height: 1.6;
}
.outcome-summary {
  table-layout: fixed;
  margin: 10px 0;
}
.outcome-summary th,
.outcome-summary td {
  padding: 8px 6px;
  overflow-wrap: anywhere;
}
.outcome-method {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 4px;
}
.outcome-state {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 5px;
  border-radius: 5px;
  background: var(--dsw-alias-bg-skeleton);
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
}
.outcome-state.error {
  color: var(--dsw-feedback-error-text);
  background: var(--dsw-alias-bg-layer-1);
  border: 0.5px solid currentColor;
  white-space: nowrap;
}
.outcome-error {
  color: var(--dsw-feedback-error-text);
}
.outcome-detail {
  margin: 10px 0;
  min-width: 0;
}
.outcome-detail h4 {
  margin: 0 0 6px;
  font-size: inherit;
  font-weight: 600;
}
.outcome-caption {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
  overflow-wrap: anywhere;
}
.outcome-disclosure {
  margin-top: 8px;
  min-width: 0;
}
.outcome-empty {
  margin: 8px 0;
  color: var(--dsw-alias-text-tertiary);
}
.outcome-metrics {
  margin: 8px 0;
}
.outcome-metrics div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
  padding: 4px 6px;
  border-bottom: 0.5px solid var(--dsw-alias-border-l1);
}
.outcome-metrics dt {
  color: var(--dsw-alias-text-secondary);
  overflow-wrap: anywhere;
}
.outcome-metrics dd {
  margin: 0;
  text-align: right;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
.outcome-table-scroll {
  max-height: 240px;
  overflow: auto;
  margin-top: 8px;
  border: 0.5px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
}
.outcome-data {
  width: max-content;
  min-width: 100%;
}
.outcome-data th {
  position: sticky;
  top: 0;
  background: var(--dsw-alias-bg-layer-1);
}
.outcome-data td {
  white-space: nowrap;
}
.outcome-json {
  max-height: 280px;
  overflow: auto;
  padding: 10px;
  border-radius: 6px;
  background: var(--dsw-alias-bg-skeleton);
  font-size: var(--dsw-text-xs);
}
@container (max-width: 220px) {
  .outcome-summary thead,
  .outcome-summary colgroup {
    display: none;
  }
  .outcome-summary,
  .outcome-summary tbody,
  .outcome-summary tr,
  .outcome-summary td {
    display: block;
    width: 100%;
  }
  .outcome-summary td {
    border: 0;
    box-sizing: border-box;
    padding: 4px 0;
  }
  .outcome-summary tr {
    padding: 6px 0;
    border-bottom: 0.5px solid var(--dsw-alias-border-l1);
  }
  .outcome-method {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
}
</style>
