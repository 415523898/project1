<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';

const props = defineProps<{
  width: number;
  initial: number;
  min: number;
  max: number;
  edge: 'left' | 'right';
  label: string;
}>();
const emit = defineEmits<{ (event: 'resize', width: number): void }>();
const active = ref(false);
let pointer: number | null = null;
let startX = 0;
let startWidth = 0;
let oldCursor = '';
let oldSelection = '';

function resize(width: number): void {
  emit('resize', Math.max(props.min, Math.min(props.max, width)));
}

function start(event: PointerEvent): void {
  if (event.button !== 0) return;
  event.preventDefault();
  pointer = event.pointerId;
  startX = event.clientX;
  startWidth =
    (event.currentTarget as HTMLElement).parentElement?.getBoundingClientRect().width ??
    props.width;
  (event.currentTarget as HTMLElement).setPointerCapture(pointer);
  oldCursor = document.body.style.cursor;
  oldSelection = document.body.style.userSelect;
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
  document.body.dataset.panelResizing = 'yes';
  active.value = true;
}

function move(event: PointerEvent): void {
  if (event.pointerId !== pointer) return;
  resize(startWidth + (event.clientX - startX) * (props.edge === 'right' ? 1 : -1));
}

function stop(): void {
  if (!active.value) return;
  pointer = null;
  active.value = false;
  document.body.style.cursor = oldCursor;
  document.body.style.userSelect = oldSelection;
  delete document.body.dataset.panelResizing;
}

function key(event: KeyboardEvent): void {
  const direction = props.edge === 'right' ? 1 : -1;
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    resize(
      props.width + (event.key === 'ArrowRight' ? 1 : -1) * direction * (event.shiftKey ? 40 : 16),
    );
  } else if (event.key === 'Home') {
    event.preventDefault();
    resize(props.initial);
  }
}

onBeforeUnmount(stop);
</script>

<template>
  <div
    class="panel-resize-handle"
    :class="[edge, { active }]"
    role="separator"
    tabindex="0"
    aria-orientation="vertical"
    :aria-label="label"
    :aria-valuenow="Math.round(width)"
    :aria-valuemin="min"
    :aria-valuemax="max"
    data-role="panel-resize"
    :data-edge="edge"
    title="拖动调宽；双击恢复默认；方向键微调"
    @pointerdown.stop="start"
    @pointermove.stop="move"
    @pointerup="stop"
    @pointercancel="stop"
    @lostpointercapture="stop"
    @keydown="key"
    @dblclick.stop="resize(initial)"
  />
</template>

<style scoped>
.panel-resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 10px;
  z-index: 30;
  cursor: col-resize;
  touch-action: none;
  outline: none;
}
.left {
  left: -5px;
}
.right {
  right: -5px;
}
.panel-resize-handle::after {
  content: '';
  position: absolute;
  left: 4px;
  top: calc(50% - 18px);
  width: 2px;
  height: 36px;
  border-radius: 2px;
  background: var(--dsw-alias-text-tertiary);
  opacity: 0.35;
  transition:
    background 120ms,
    opacity 120ms;
}
.panel-resize-handle:hover,
.panel-resize-handle.active,
.panel-resize-handle:focus-visible {
  background: color-mix(in srgb, var(--dsw-alias-brand-primary) 10%, transparent);
}
.panel-resize-handle:hover::after,
.panel-resize-handle.active::after,
.panel-resize-handle:focus-visible::after {
  background: var(--dsw-alias-brand-primary);
  opacity: 1;
}
</style>
