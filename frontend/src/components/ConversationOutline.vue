<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import type { ChatTurn } from '@/types';
import { previewAnswer } from '@/utils/turn-activity';

const props = defineProps<{ turns: ChatTurn[]; active: number }>();
const emit = defineEmits<{ jump: [index: number] }>();
const root = ref<HTMLElement | null>(null);
const list = ref<HTMLElement | null>(null);
const preview = ref<number | null>(null);
const position = ref({ top: '0px', width: '300px' });

function plain(text: string, length: number): string {
  const value = text
    .replace(/```[\s\S]*?```/g, ' [代码] ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '[图片]')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]*>/g, '')
    .replace(/[#*`>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return value.length > length ? `${value.slice(0, length)}…` : value;
}
const selected = computed(() => (preview.value === null ? null : props.turns[preview.value]));
const answer = computed(() => {
  const turn = selected.value;
  if (!turn) return '';
  return plain(
    previewAnswer(turn) ||
      turn.error ||
      turn.result?.title ||
      (turn.status === 'pending' ? '正在生成回答…' : '查看这一轮的实验与工具结果'),
    180,
  );
});

function show(index: number, event: Event): void {
  const host = root.value;
  if (!host) return;
  const button = event.currentTarget as HTMLElement;
  const rect = button.getBoundingClientRect();
  const bounds = host.getBoundingClientRect();
  const width = Math.max(100, Math.min(340, (host.parentElement?.clientWidth ?? 400) - 52));
  position.value = {
    top: `${Math.max(0, Math.min(rect.top - bounds.top - 25, bounds.height - 154))}px`,
    width: `${width}px`,
  };
  preview.value = index;
}

function leave(event: FocusEvent): void {
  if (!root.value?.contains(event.relatedTarget as Node | null)) preview.value = null;
}

function keydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    preview.value = null;
    return;
  }
  const buttons = Array.from(list.value?.querySelectorAll<HTMLButtonElement>('button') ?? []);
  const index = buttons.indexOf(event.target as HTMLButtonElement);
  if (index < 0) return;
  const target =
    event.key === 'ArrowDown'
      ? Math.min(index + 1, buttons.length - 1)
      : event.key === 'ArrowUp'
        ? Math.max(0, index - 1)
        : event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? buttons.length - 1
            : -1;
  if (target < 0) return;
  event.preventDefault();
  buttons[target]?.focus({ preventScroll: true });
  reveal(target);
}

function reveal(index: number): void {
  const host = list.value;
  const button = host?.querySelectorAll<HTMLButtonElement>('button')[index];
  if (!host || !button) return;
  const rect = button.getBoundingClientRect();
  const bounds = host.getBoundingClientRect();
  if (rect.top < bounds.top) host.scrollTop -= bounds.top - rect.top;
  else if (rect.bottom > bounds.bottom) host.scrollTop += rect.bottom - bounds.bottom;
}
watch(
  () => props.active,
  async (index) => {
    await nextTick();
    reveal(index);
  },
  { immediate: true },
);
</script>

<template>
  <nav
    v-if="turns.length"
    ref="root"
    class="conversation-outline"
    aria-label="会话消息导航"
    @mouseleave="preview = null"
    @focusout="leave"
    @keydown="keydown"
  >
    <div ref="list" class="outline-ticks" @scroll="preview = null">
      <button
        v-for="(turn, index) in turns"
        :key="index"
        type="button"
        class="outline-tick"
        :class="{ 'is-active': index === active }"
        :aria-current="index === active ? 'step' : undefined"
        :aria-label="`第 ${index + 1} 轮：${plain(turn.question, 100) || '实验结果'}`"
        data-role="message-jump"
        :data-index="index"
        @mouseenter="show(index, $event)"
        @focus="show(index, $event)"
        @click="
          emit('jump', index);
          preview = null;
        "
      >
        <span aria-hidden="true" />
      </button>
    </div>
    <Transition name="outline-preview">
      <div
        v-if="selected && preview !== null"
        class="outline-card"
        :style="position"
        data-role="message-preview"
      >
        <span class="outline-count">第 {{ preview + 1 }} / {{ turns.length }} 轮</span>
        <strong>{{ plain(selected.question, 150) || '实验结果' }}</strong>
        <p>{{ answer }}</p>
      </div>
    </Transition>
  </nav>
</template>

<style scoped>
.conversation-outline {
  position: absolute;
  z-index: 20;
  inset: 12px auto 12px 3px;
  width: 28px;
  display: flex;
  align-items: center;
  pointer-events: none;
}
.outline-ticks {
  width: 100%;
  max-height: 100%;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: none;
  pointer-events: auto;
}
.outline-ticks::-webkit-scrollbar {
  display: none;
}
.outline-tick {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 22px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  border-radius: 4px;
}
.outline-tick span {
  width: 10px;
  height: 2px;
  border-radius: 2px;
  background: var(--dsw-alias-text-secondary);
  opacity: 0.35;
  transition:
    width 160ms ease,
    opacity 160ms ease,
    background 160ms ease;
}
.outline-tick:hover span,
.outline-tick:focus-visible span {
  width: 18px;
  opacity: 0.8;
}
.outline-tick.is-active span {
  width: 24px;
  opacity: 1;
  background: var(--dsw-alias-link);
}
.outline-tick:focus-visible {
  outline: 2px solid var(--dsw-alias-link);
  outline-offset: -2px;
}
.outline-card {
  position: absolute;
  left: 34px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--dsw-alias-border-l2);
  background: var(--dsw-alias-bg-base);
  color: var(--dsw-alias-text-primary);
  box-shadow: 0 6px 24px #0000001a;
  font-size: var(--dsw-text-row);
  line-height: 1.55;
  pointer-events: auto;
}
.outline-count {
  display: block;
  margin-bottom: 4px;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
}
.outline-card strong,
.outline-card p {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.outline-card strong {
  -webkit-line-clamp: 2;
  font-weight: 600;
}
.outline-card p {
  margin: 5px 0 0;
  -webkit-line-clamp: 3;
  color: var(--dsw-alias-text-secondary);
}
.outline-preview-enter-active,
.outline-preview-leave-active {
  transition:
    opacity 140ms ease,
    transform 140ms ease;
}
.outline-preview-enter-from,
.outline-preview-leave-to {
  opacity: 0;
  transform: translateX(-4px);
}
@media (prefers-reduced-motion: reduce) {
  .outline-tick span,
  .outline-preview-enter-active,
  .outline-preview-leave-active {
    transition: none;
  }
}
</style>
