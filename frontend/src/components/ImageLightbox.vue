<script setup lang="ts">
import { computed, nextTick, onScopeDispose, ref, watch } from 'vue';
import { useLab } from '@/composables/useLab';
import UiIcon from '@/components/UiIcon.vue';
import { zoomAt } from '@/utils/viewport-zoom';

const lab = useLab();
const dialog = ref<HTMLElement>();
const stage = ref<HTMLElement>();
const image = ref<HTMLImageElement>();
const natural = ref({ width: 0, height: 0 });
const viewport = ref({ width: 0, height: 0 });
const zoom = ref(1);
const pan = ref({ x: 0, y: 0 });
const dragging = ref(false);
const failed = ref(false);
let drag: { id: number; x: number; y: number } | null = null;
let observer: ResizeObserver | undefined;
let previousFocus: HTMLElement | null = null;
const fit = computed(() =>
  natural.value.width && natural.value.height
    ? Math.min(
        1,
        Math.max(1, viewport.value.width - 32) / natural.value.width,
        Math.max(1, viewport.value.height - 32) / natural.value.height,
      )
    : 1,
);
const imageStyle = computed(() => ({
  width: `${natural.value.width * fit.value}px`,
  height: `${natural.value.height * fit.value}px`,
  transform: `translate(-50%, -50%) translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value})`,
}));

function reset(): void {
  zoom.value = 1;
  pan.value = { x: 0, y: 0 };
}
function close(): void {
  lab.closeLightbox();
}
function loaded(): void {
  if (!image.value) return;
  natural.value = { width: image.value.naturalWidth, height: image.value.naturalHeight };
  reset();
}
function wheel(event: WheelEvent): void {
  if (!stage.value || !natural.value.width || dragging.value) return;
  const rect = stage.value.getBoundingClientRect();
  const delta =
    event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.height : 1);
  const next = Math.min(12, Math.max(0.2, zoom.value * Math.exp(-delta * 0.0015)));
  pan.value = zoomAt(
    pan.value,
    {
      x: event.clientX - rect.left - rect.width / 2,
      y: event.clientY - rect.top - rect.height / 2,
    },
    zoom.value,
    next,
  );
  zoom.value = next;
}
function startDrag(event: PointerEvent): void {
  if (event.button !== 0 || drag) return;
  if (event.target !== image.value) {
    close();
    return;
  }
  event.preventDefault();
  drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
  dragging.value = true;
  stage.value?.setPointerCapture(event.pointerId);
}
function move(event: PointerEvent): void {
  if (!drag || event.pointerId !== drag.id) return;
  pan.value = { x: pan.value.x + event.clientX - drag.x, y: pan.value.y + event.clientY - drag.y };
  drag.x = event.clientX;
  drag.y = event.clientY;
}
function endDrag(): void {
  if (drag && stage.value?.hasPointerCapture(drag.id)) stage.value.releasePointerCapture(drag.id);
  drag = null;
  dragging.value = false;
}
watch(stage, (element) => {
  observer?.disconnect();
  if (!element) return;
  const measure = () => {
    viewport.value = { width: element.clientWidth, height: element.clientHeight };
  };
  observer = new ResizeObserver(measure);
  observer.observe(element);
  measure();
});
watch(
  () => lab.lightbox.value,
  async (value) => {
    endDrag();
    reset();
    failed.value = false;
    natural.value = { width: 0, height: 0 };
    if (!value) {
      previousFocus?.focus();
      previousFocus = null;
      return;
    }
    if (!previousFocus) previousFocus = document.activeElement as HTMLElement | null;
    await nextTick();
    dialog.value?.focus();
    if (image.value?.complete && image.value.naturalWidth) loaded();
  },
  { immediate: true },
);
onScopeDispose(() => {
  observer?.disconnect();
  endDrag();
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="lab.lightbox.value"
      ref="dialog"
      class="image-lightbox"
      tabindex="-1"
      role="dialog"
      aria-modal="true"
      :aria-label="lab.lightbox.value.name"
      data-role="image-lightbox"
      @pointerdown="startDrag"
      @keydown.esc.stop.prevent="close()"
      @contextmenu.prevent
    >
      <header class="lightbox-toolbar">
        <span class="lightbox-name">{{ lab.lightbox.value.name.replace(/_/g, ' ') }}</span>
        <span class="lightbox-scale">{{ Math.round(fit * zoom * 100) }}%</span>
        <button type="button" @pointerdown.stop @click="reset()">适应窗口</button>
        <button
          type="button"
          aria-label="关闭图片"
          data-action="close-image"
          @pointerdown.stop
          @click="close()"
          ><UiIcon name="close"
        /></button>
      </header>
      <div
        ref="stage"
        class="lightbox-stage"
        :class="{ dragging }"
        data-role="image-stage"
        @wheel.prevent="wheel"
        @pointermove="move"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @lostpointercapture="endDrag"
      >
        <img
          ref="image"
          :key="lab.lightbox.value.url"
          :src="lab.lightbox.value.url"
          :alt="lab.lightbox.value.name"
          :style="imageStyle"
          :class="{ 'is-loaded': natural.width > 0 }"
          draggable="false"
          data-role="lightbox-image"
          @load="loaded"
          @error="failed = true"
          @dragstart.prevent
        />
        <p v-if="failed" class="lightbox-message">图片加载失败，请关闭后重试。</p>
        <p v-else-if="!natural.width" class="lightbox-message">正在加载图片…</p>
      </div>
      <footer class="lightbox-help">滚轮缩放 · 按住左键拖动图片 · 按下空白处或按 Esc 返回</footer>
    </div>
  </Teleport>
</template>

<style scoped>
.image-lightbox {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  background: rgba(12, 16, 23, 0.92);
  color: #edf0f5;
  outline: none;
}
.lightbox-toolbar {
  display: flex;
  align-items: center;
  flex: none;
  gap: 12px;
  padding: 12px 16px;
  min-width: 0;
}
.lightbox-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--dsw-text-row);
}
.lightbox-scale {
  font-size: var(--dsw-text-sm);
  font-variant-numeric: tabular-nums;
}
.lightbox-toolbar button {
  display: grid;
  place-items: center;
  padding: 7px 10px;
  border: 1px solid #ffffff36;
  border-radius: 8px;
  background: #ffffff12;
  color: inherit;
  cursor: pointer;
  white-space: nowrap;
  font-size: var(--dsw-text-sm);
}
.lightbox-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  cursor: zoom-out;
  touch-action: none;
  user-select: none;
}
.lightbox-stage img {
  position: absolute;
  top: 50%;
  left: 50%;
  max-width: none;
  max-height: none;
  object-fit: contain;
  transform-origin: center;
  opacity: 0;
  cursor: grab;
}
.lightbox-stage img.is-loaded {
  opacity: 1;
}
.lightbox-stage.dragging,
.lightbox-stage.dragging img {
  cursor: grabbing;
}
.lightbox-help {
  padding: 10px 16px 14px;
  text-align: center;
  color: #c1c8d4;
  font-size: var(--dsw-text-sm);
}
.lightbox-message {
  position: absolute;
  inset: 40% 16px auto;
  text-align: center;
  pointer-events: none;
}
</style>
