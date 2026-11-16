<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import CollapseTransition from '@/components/CollapseTransition.vue';
import MethodMath from '@/components/MethodMath.vue';

import type { MethodCard, RelationKind } from '@/types';

const props = defineProps<{
  card: MethodCard | null;
  label: (id: string) => string;
  why: (kind: RelationKind, from: string, to: string) => string;
  learned?: boolean;
  studying?: boolean;
  pendingLaunch?: boolean;
  progressBusy?: boolean;
  launching?: boolean;
}>();

const emit = defineEmits<{
  (event: 'pick', id: string): void;
  (event: 'learn', card: MethodCard): void;
  (event: 'mark', card: MethodCard): void;
  (event: 'close'): void;
}>();

const before = computed(() => props.card?.before ?? []);
const suggests = computed(() => props.card?.suggests ?? []);
const after = computed(() => props.card?.after ?? []);
const more = computed(() => props.card?.more ?? []);
const similar = computed(() => props.card?.similar ?? []);

const alternativeWhys = computed(() => props.card?.similar_why ?? {});

function prerequisiteWhy(id: string): string {
  if (!props.card) return '';
  return props.why('prerequisite', id, props.card.id);
}

function suggestWhy(id: string): string {
  if (!props.card) return '';
  return props.why('suggest', id, props.card.id);
}

function downstreamWhy(id: string): string {
  if (!props.card) return '';
  return props.why('prerequisite', props.card.id, id);
}

const expandedRelations = ref<string[]>([]);
watch(
  () => props.card?.id,
  () => {
    expandedRelations.value = [];
  },
);
const relations = computed(() =>
  [
    {
      key: 'before',
      title: '硬前置',
      ids: before.value,
      icon: 'arrow-left' as const,
      reason: prerequisiteWhy,
      tone: 'solid',
    },
    {
      key: 'suggests',
      title: '软前置',
      ids: suggests.value,
      icon: 'arrow-left-dashed' as const,
      reason: suggestWhy,
      tone: 'soft',
    },
    {
      key: 'after',
      title: '学完能接',
      ids: after.value,
      icon: 'arrow-right' as const,
      reason: downstreamWhy,
      tone: 'solid',
    },
    {
      key: 'more',
      title: '之后会更顺',
      ids: more.value,
      icon: 'arrow-right-dashed' as const,
      reason: (id: string) => (props.card ? props.why('suggest', props.card.id, id) : ''),
      tone: 'soft',
    },
    {
      key: 'similar',
      title: '同一任务可以换用',
      ids: similar.value,
      icon: 'arrows-horizontal' as const,
      reason: (id: string) => alternativeWhys.value[id] ?? '',
      tone: 'alternative',
    },
  ].filter((relation) => relation.ids.length),
);

function toggleRelation(key: string): void {
  expandedRelations.value = expandedRelations.value.includes(key)
    ? expandedRelations.value.filter((value) => value !== key)
    : [...expandedRelations.value, key];
}
</script>

<template>
  <aside class="flex flex-col gap-3" data-role="method-side">
    <p v-if="!card" class="text-[length:var(--dsw-text-sm)] text-ink-2" data-role="side-empty">
      在左边选一个方法，或者点中间的卡片，这里会显示它什么时候用、要先会什么、学完能接什么。
    </p>
    <template v-else>
      <header class="flex items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <h2
            class="m-0 text-[length:var(--dsw-text-title)] font-semibold"
            data-role="side-title"
            >{{ card.label }}</h2
          >
          <p class="mt-1 mb-0 text-[length:var(--dsw-text-xs)] text-ink-2"
            >{{ card.category_name }} · {{ card.group }}</p
          >
        </div>
        <button
          type="button"
          class="ui-icon-button h-7 w-7 flex-none cursor-pointer rounded-card border-0 bg-transparent text-ink-2 hover:bg-field hover:text-ink"
          data-action="toggle-panel"
          aria-label="收起方法详情"
          title="收起方法详情"
          @click="emit('close')"
          ><UiIcon name="close" class="h-4 w-4"
        /></button>
      </header>

      <div class="flex flex-wrap items-center gap-[5px]">
        <span
          class="rounded-[999px] bg-accent-faint px-2 py-px text-[length:var(--dsw-text-xs)] font-semibold text-accent-deep"
          data-role="side-kind"
          >{{ card.kind }}</span
        >
      </div>

      <p
        class="m-0 text-[length:var(--dsw-text-row)] leading-normal text-ink"
        data-role="side-when"
      >
        <span class="text-ink-2">{{ '什么时候用\u3000' }}</span
        >{{ card.when }}
      </p>
      <p
        class="m-0 text-[length:var(--dsw-text-sm)] leading-normal text-ink-2"
        data-role="side-note"
        >{{ card.note }}</p
      >

      <dl class="m-0 flex flex-col gap-[7px]">
        <div class="grid grid-cols-[62px_minmax(0,1fr)] gap-2">
          <dt class="text-[length:var(--dsw-text-sm)] text-ink-2">输入</dt>
          <dd class="m-0 break-words text-[length:var(--dsw-text-sm)]">{{
            card.inputs.join('、') || '—'
          }}</dd>
        </div>
        <div class="grid grid-cols-[62px_minmax(0,1fr)] gap-2">
          <dt class="text-[length:var(--dsw-text-sm)] text-ink-2">输出</dt>
          <dd class="m-0 break-words text-[length:var(--dsw-text-sm)]">{{
            card.outputs.join('、') || '—'
          }}</dd>
        </div>
        <div class="grid grid-cols-[62px_minmax(0,1fr)] gap-2">
          <dt class="text-[length:var(--dsw-text-sm)] text-ink-2">适用任务</dt>
          <dd class="m-0 break-words text-[length:var(--dsw-text-sm)]">{{
            card.tasks.join('、') || '—'
          }}</dd>
        </div>
      </dl>

      <MethodMath v-if="card.math" :key="card.id" :lesson="card.math" />

      <p
        v-if="card.missing.length"
        class="m-0 flex items-start gap-1.5 rounded-[7px] bg-warn-bg px-[9px] py-[7px] text-[length:var(--dsw-text-sm)] text-warn-ink"
        data-role="side-missing"
      >
        <UiIcon name="warning" class="mt-0.5 h-[14px] w-[14px]" /><span
          >缺少依赖：{{ card.missing.join('、') }}，当前环境无法运行。</span
        >
      </p>

      <section
        v-for="relation in relations"
        :key="relation.key"
        class="flex flex-col gap-1.5"
        :data-role="`side-${relation.key}`"
      >
        <h3 class="m-0 flex items-baseline gap-1.5 text-[length:var(--dsw-text-sm)] font-semibold">
          {{ relation.title
          }}<span
            data-role="side-count"
            class="text-[10.5px] font-normal tabular-nums text-ink-3"
            >{{ relation.ids.length }}</span
          >
        </h3>
        <div class="flex flex-wrap gap-1">
          <button
            v-for="id in relation.ids.slice(0, 4)"
            :key="id"
            type="button"
            data-role="chip"
            class="relation-chip"
            :class="relation.tone"
            :title="relation.reason(id) || label(id)"
            @click="emit('pick', id)"
          >
            <UiIcon :name="relation.icon" class="h-3 w-3" /><span class="min-w-0 truncate">{{
              label(id)
            }}</span>
          </button>
        </div>
        <CollapseTransition>
          <div
            v-if="expandedRelations.includes(relation.key)"
            class="flex flex-wrap gap-1"
            data-role="relation-extra"
          >
            <button
              v-for="id in relation.ids.slice(4)"
              :key="id"
              type="button"
              data-role="chip"
              class="relation-chip"
              :class="relation.tone"
              :title="relation.reason(id) || label(id)"
              @click="emit('pick', id)"
            >
              <UiIcon :name="relation.icon" class="h-3 w-3" /><span class="min-w-0 truncate">{{
                label(id)
              }}</span>
            </button>
          </div>
        </CollapseTransition>
        <div v-if="relation.ids.length > 4">
          <button
            type="button"
            class="relation-more"
            data-action="relation-expand"
            :aria-expanded="expandedRelations.includes(relation.key)"
            @click="toggleRelation(relation.key)"
          >
            {{
              expandedRelations.includes(relation.key)
                ? '收起'
                : `展开其余 ${relation.ids.length - 4} 个`
            }}
          </button>
        </div>
      </section>

      <div class="mt-0.5 flex w-full flex-col gap-2">
        <button
          type="button"
          class="ui-button w-full"
          :class="
            props.studying
              ? 'border border-[#f59e0b] bg-[#fffaeb] text-[#b45309]'
              : 'ui-button-primary'
          "
          data-action="side-learn"
          :disabled="props.launching"
          :aria-busy="props.launching || undefined"
          :data-studying="props.studying ? 'true' : 'false'"
          @click="emit('learn', card)"
        >
          <span
            v-if="props.studying"
            class="mr-1.5 grid h-[13px] w-[13px] flex-none place-items-center rounded-full bg-[#f59e0b] text-brand-ink"
            aria-hidden="true"
            ><UiIcon name="clock" class="h-[10px] w-[10px]"
          /></span>
          {{
            props.launching
              ? '正在绑定会话…'
              : props.pendingLaunch
                ? '重试绑定并进入会话'
                : props.learned
                  ? '再次探索'
                  : props.studying
                    ? '继续学习'
                    : '开始学习'
          }}
        </button>
        <button
          type="button"
          class="ui-button ui-button-ghost w-full"
          :class="props.learned && 'border-accent-edge text-accent'"
          data-action="side-learned"
          :data-learned="props.learned ? 'true' : 'false'"
          :aria-pressed="props.learned ? 'true' : 'false'"
          :disabled="props.progressBusy"
          @click="emit('mark', card)"
          ><UiIcon v-if="props.learned" name="check" class="mr-1.5 h-[14px] w-[14px]" /><span
            >已学习</span
          ></button
        >
      </div>
    </template>
  </aside>
</template>

<style scoped>
.relation-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  min-height: 24px;
  padding: 2px 7px;
  border: 0.5px solid var(--dsw-alias-border-l2);
  border-radius: 6px;
  background: transparent;
  color: var(--dsw-alias-text-primary);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.relation-chip.soft {
  border-style: dashed;
  color: var(--dsw-alias-text-secondary);
}
.relation-chip.alternative {
  border-color: var(--dsw-static-orange-200, #fed7aa);
}
.relation-chip:hover {
  background: var(--dsw-selection-surface);
  border-color: var(--dsw-alias-brand-primary);
}
.relation-more {
  padding: 2px 4px;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-link);
  font: inherit;
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.relation-chip:focus-visible,
.relation-more:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 2px;
}
</style>
