<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import { useMethodSearch } from '@/composables/useMethodSearch';
import type { MethodGraph } from '@/types';

const props = defineProps<{
  graph: MethodGraph | null;
  selected: string | null;
}>();

const emit = defineEmits<{
  (event: 'pick', id: string): void;
  (event: 'open'): void;
}>();

const { failure, query, submittedQuery, hits, running, guidance, run, clear } = useMethodSearch();
const anchor = ref<HTMLElement | null>(null);
const form = ref<HTMLFormElement | null>(null);
const popup = ref<HTMLElement | null>(null);
const results = ref<HTMLElement | null>(null);
const expanded = ref(false);
const availableHeight = ref(180);
const popupId = `method-search-${useId()}`;
const visible = computed(
  () =>
    expanded.value && Boolean(query.value.trim()) && query.value.trim() === submittedQuery.value,
);

function position(): void {
  if (!anchor.value) return;
  const bottom = Math.min(
    window.innerHeight,
    anchor.value.closest('main')?.getBoundingClientRect().bottom ?? window.innerHeight,
  );
  availableHeight.value = Math.max(0, bottom - anchor.value.getBoundingClientRect().bottom - 24);
}

function close(): void {
  expanded.value = false;
}
function focus(): void {
  form.value?.querySelector<HTMLInputElement>('input')?.focus({ preventScroll: true });
}
function reopen(): void {
  if (query.value.trim() && query.value.trim() === submittedQuery.value) {
    position();
    expanded.value = true;
    emit('open');
  }
}

async function submit(): Promise<void> {
  if (!query.value.trim() || !props.graph) return;
  position();
  expanded.value = true;
  emit('open');
  const text = query.value.trim(),
    changed = text !== submittedQuery.value;
  const pending = run(props.graph);
  await nextTick();
  // A late semantic append or repeated submit must not move the row under the user.
  if (results.value && changed && submittedQuery.value === text) results.value.scrollTop = 0;
  await pending;
}

function pick(id: string): void {
  close();
  emit('pick', id);
}

function navigate(event: KeyboardEvent): void {
  if (!visible.value || !results.value) return;
  const buttons = [...results.value.querySelectorAll<HTMLButtonElement>('[data-hit]')];
  const current = buttons.indexOf(event.target as HTMLButtonElement);
  if (current < 0 && !['ArrowDown', 'ArrowUp'].includes(event.key)) return;
  let next: number;
  if (event.key === 'ArrowDown') next = Math.min(current + 1, buttons.length - 1);
  else if (event.key === 'ArrowUp')
    next = current < 0 ? buttons.length - 1 : Math.max(0, current - 1);
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = buttons.length - 1;
  else return;
  event.preventDefault();
  buttons[next]?.focus();
}

function outside(event: Event): void {
  const target = event.target;
  if (target instanceof Node && !form.value?.contains(target) && !popup.value?.contains(target))
    close();
}

watch(query, (value) => {
  if (value.trim() !== submittedQuery.value) close();
  if (!value) clear();
});
onMounted(() => {
  document.addEventListener('pointerdown', outside, true);
  document.addEventListener('focusin', outside);
  window.addEventListener('resize', position);
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', outside, true);
  document.removeEventListener('focusin', outside);
  window.removeEventListener('resize', position);
});
defineExpose({ close, focus });
</script>

<template>
  <section
    class="method-search"
    data-role="method-search"
    @keydown.esc.stop.prevent="close()"
    @keydown="navigate"
  >
    <div ref="anchor" class="search-anchor">
      <form ref="form" class="search-form" @submit.prevent="submit()">
        <input
          v-model="query"
          type="search"
          data-role="search-input"
          class="search-input"
          placeholder="描述问题，查找方法"
          aria-label="按卡片描述检索方法"
          :aria-expanded="visible"
          :aria-controls="visible ? popupId : undefined"
          @focus="reopen()"
          @click="reopen()"
        />
        <button
          type="submit"
          data-action="search-run"
          aria-label="检索"
          :aria-busy="running"
          class="search-submit"
          :disabled="!query.trim() || !props.graph"
        >
          <UiIcon :name="running ? 'spinner' : 'search'" class="h-4 w-4" />
        </button>
      </form>

      <div
        v-if="visible"
        :id="popupId"
        ref="popup"
        class="search-popup"
        data-role="search-popup"
        role="region"
        aria-label="匹配方法"
        :aria-busy="running"
        :style="{ '--search-available-height': `${availableHeight}px` }"
      >
        <p v-if="running" class="search-message text-ink-3" role="status" data-role="search-loading"
          >正在匹配…</p
        >
        <p
          v-if="failure"
          class="search-message text-error-ink"
          role="status"
          data-role="search-error"
          >{{ failure }}</p
        >
        <p v-if="guidance" class="search-guidance text-ink-3" data-role="search-guidance">{{
          guidance
        }}</p>
        <ul v-if="hits.length" ref="results" class="search-hits" data-role="search-hits">
          <li v-for="hit in hits" :key="hit.id">
            <button
              type="button"
              class="search-hit rounded-card border-0 bg-transparent text-left text-inherit hover:bg-nav-active focus-visible:bg-nav-active"
              :class="hit.id === props.selected && 'bg-nav-active'"
              :data-hit="hit.id"
              @click="pick(hit.id)"
            >
              <span class="min-w-0 flex-1 text-[length:var(--dsw-text-sm)] text-ink"
                ><span class="block truncate" :title="hit.label">{{ hit.label }}</span
                ><small v-if="hit.reason" class="block truncate text-ink-3" :title="hit.reason">{{
                  hit.reason
                }}</small></span
              >
              <span
                class="search-group text-[length:var(--dsw-text-xs)] text-ink-3"
                :title="hit.group"
                >{{ hit.group }}</span
              >
            </button>
          </li>
        </ul>
        <p
          v-else-if="!running && !failure"
          class="search-message text-ink-3"
          role="status"
          data-role="search-empty"
          >没有找到相近的方法。</p
        >
      </div>
    </div>
  </section>
</template>

<style scoped>
.method-search {
  position: relative;
  z-index: 30;
  min-width: 0;
}
.search-form {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 6px 0 15px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 11px;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: 0 1px 2px rgb(20 40 80 / 0.04);
}
.search-form:hover {
  border-color: var(--dsw-alias-border-l3);
}
.search-form:focus-within {
  border-color: var(--dsw-alias-link);
  background: var(--dsw-alias-bg-layer-1);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--dsw-alias-link) 12%, transparent),
    0 1px 2px rgb(20 40 80 / 0.04);
}
.search-input {
  width: 100%;
  min-width: 0;
  flex: 1;
  padding: 0;
  outline: none;
  border: 0;
  background: transparent;
  color: var(--dsw-alias-text-primary);
  font: inherit;
  font-size: var(--dsw-text-sm);
}
.search-input::placeholder {
  color: var(--dsw-alias-text-secondary);
  opacity: 1;
}
.search-submit {
  display: grid;
  place-items: center;
  flex: none;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--dsw-alias-link);
  cursor: pointer;
}
.search-submit:hover:not(:disabled) {
  background: color-mix(in srgb, var(--dsw-alias-link) 10%, transparent);
}
.search-submit:disabled {
  color: var(--dsw-alias-text-tertiary);
  cursor: default;
}
.search-submit:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  border-radius: 4px;
}
.search-anchor {
  position: relative;
}
.search-popup {
  position: absolute;
  inset-inline: 0;
  top: calc(100% + 6px);
  padding: 4px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: var(--dsw-radius-md);
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: var(--dsw-elevation-panel, 0 8px 24px rgb(0 0 0 / 12%));
  display: flex;
  flex-direction: column;
  max-height: var(--search-available-height);
  overflow: hidden;
}
.search-hits {
  --search-row-height: 52px;
  max-height: min(calc(5 * var(--search-row-height)), var(--search-available-height));
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  scrollbar-gutter: stable;
  min-height: 0;
  flex: 0 1 auto;
}
.search-hit {
  display: flex;
  width: 100%;
  height: var(--search-row-height);
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  cursor: pointer;
}
.search-group {
  flex: none;
  max-width: 30%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-message {
  max-height: var(--search-available-height);
  margin: 0;
  padding: 10px 8px;
  overflow-y: auto;
  font-size: var(--dsw-text-sm);
}
.search-guidance {
  margin: 0;
  padding: 6px 8px;
  font-size: var(--dsw-text-xs);
  overflow-y: auto;
  min-height: 0;
}
</style>
