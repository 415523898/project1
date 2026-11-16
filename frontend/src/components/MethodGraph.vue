<script setup lang="ts">
import { frontendConfig } from '@/config';
import { computed, onUnmounted, ref, shallowRef, watch } from 'vue';
import UiIcon from '@/components/UiIcon.vue';

import type { MethodGraph, MethodLayer, RelationKind } from '@/types';
import { useGraphMotion } from '@/composables/useGraphMotion';
import { focusGroupOf, indexGraphEdges, relationMarks, routeEdges } from '@/utils/graph-edges';
import { createEdgeBatchCache } from '@/utils/graph-edge-batches';
import {
  createCanvasSpatialIndex,
  rectsOverlap,
  type CanvasRect,
} from '@/utils/canvas-spatial-index';
import { canvasWindow, pathBounds } from '@/utils/canvas-visibility';
import { opacityTransition } from '@/utils/opacity-transition';
import { learningCardStyle } from '@/utils/learning-card';
import { PAD, buildLayers } from '@/utils/graph-layout';
import { focusPoses, followPath, type CardPose } from '@/utils/graph-focus';
import { clampZoom as clampZoomTo, snapZoom as snapZoomTo } from '@/utils/viewport-zoom';
import { useCanvasZoom, CANVAS_ZOOM_LIMITS, canvasPan } from '@/composables/useCanvasZoom';

const props = withDefaults(
  defineProps<{
    graph: MethodGraph | null;
    layers: MethodLayer[];
    selected: string | null;
    detailsOpen?: boolean;
    highlight: RelationKind[];
    placeholder: string;
    learned?: string[];
    studying?: string[];
  }>(),
  { detailsOpen: true },
);

const learnedIds = computed(() => new Set(props.learned ?? []));
const studyingIds = computed(() => new Set(props.studying ?? []));

const emit = defineEmits<{
  (event: 'pick', id: string): void;
  (event: 'clear'): void;
  (event: 'open-detail'): void;
}>();

const CARD_WIDTH = frontendConfig.canvas.reference.cardWidth;
const CARD_HEIGHT = frontendConfig.canvas.reference.cardHeight;
const OPEN_ZOOM = frontendConfig.canvas.reference.openZoom;
const FIT_PAD = frontendConfig.canvas.reference.fitPadding;
const wrapping = ref<HTMLElement | null>(null);
const cardSize = { width: CARD_WIDTH, height: CARD_HEIGHT };
const motion = useGraphMotion(cardSize);
const { poses, zoom, pan } = motion;
const { zoomBy, wheel: onWheel } = useCanvasZoom(wrapping, motion);
const viewport = ref({ width: 640, height: 460 });
const journey = ref<string[]>([]);
const edgeSelection = ref(props.selected);
const targetPoses = shallowRef(new Map<string, CardPose>());
const panning = ref(false);
const edgeFade = opacityTransition(
  frontendConfig.canvas.edgeEnterMs,
  frontendConfig.canvas.edgeLeaveMs,
);
let removeDrag: (() => void) | null = null;

const total = computed(() => props.graph?.cards.length ?? 0);
const levelCount = computed(() => props.layers.length);
const cards = computed(() => props.graph?.cards ?? []);
const layout = computed(() => buildLayers(props.layers, cardSize));
const focused = computed(() => Boolean(focusGroupOf(props.selected, props.graph)));
const bounds = computed(() => {
  const points = [...targetPoses.value.values()];
  const left = focused.value ? Math.min(0, ...points.map((point) => point.x)) - PAD : 0;
  const top = focused.value ? Math.min(0, ...points.map((point) => point.y)) - PAD : 0;
  const right = Math.max(0, ...points.map((point) => point.x + CARD_WIDTH)) + PAD;
  const bottom = Math.max(0, ...points.map((point) => point.y + CARD_HEIGHT)) + PAD;
  return {
    left,
    top,
    width: Math.max(right - left, 640),
    height: Math.max(bottom - top, 460),
  };
});

const edgeIndex = computed(() => indexGraphEdges(props.graph));
const edges = computed(() =>
  routeEdges({
    graph: props.graph,
    index: edgeIndex.value,
    selected: edgeSelection.value,
    highlight: props.highlight,
    spots: new Map(
      [...poses.value].filter(([id, pose]) => pose.role !== 'leaving' && targetPoses.value.has(id)),
    ),
    anchorSpots: targetPoses.value,
    horizontalColumns: !edgeSelection.value,
    card: { width: CARD_WIDTH, height: CARD_HEIGHT },
  }).filter(
    (edge) =>
      edge.kind === 'alternative' ||
      (targetPoses.value.get(edge.from)?.role !== 'alternative' &&
        targetPoses.value.get(edge.to)?.role !== 'alternative'),
  ),
);

const viewWindow = computed<CanvasRect>((previous) =>
  canvasWindow(pan.value, zoom.value, viewport.value, previous),
);
const edgeIndexByPosition = computed(() => {
  const index = createCanvasSpatialIndex();
  for (const edge of edges.value) index.set(edge.key, pathBounds(edge.path));
  return index;
});
const renderedEdges = computed(() => {
  const ids = new Set(edgeIndexByPosition.value.search(viewWindow.value));
  return edges.value.filter((edge) => ids.has(edge.key));
});
const edgeBatchCache = createEdgeBatchCache();
const edgeBatches = computed(() => edgeBatchCache.build(renderedEdges.value));
const edgeLayers = computed(() =>
  (['prerequisite', 'suggest', 'alternative'] as RelationKind[]).map((kind) => ({
    key: `${edgeSelection.value ?? 'all'}:${kind}`,
    kind,
    enabled: props.highlight.includes(kind),
    batches: edgeBatches.value.filter((batch) => batch.kind === kind),
  })),
);

const visibleCards = computed(() =>
  cards.value.filter((card) => {
    const pose = poses.value.get(card.id);
    return (
      pose &&
      pose.opacity > 0.001 &&
      (card.id === props.selected ||
        rectsOverlap(
          {
            x: pose.x,
            y: pose.y,
            width: CARD_WIDTH * pose.scale,
            height: CARD_HEIGHT * pose.scale,
          },
          viewWindow.value,
        ))
    );
  }),
);
const marks = computed(() => {
  const value = relationMarks(props.selected, props.graph);
  for (const id of value.keys()) if (!targetPoses.value.has(id)) value.delete(id);
  const card = props.graph?.cards.find((item) => item.id === props.selected);
  for (const [id, pose] of targetPoses.value) {
    if (pose.role === 'alternative')
      value.set(id, { text: '可换用', kind: 'alternative', why: card?.similar_why?.[id] || '' });
  }
  const previous = journey.value.at(-2);
  if (previous && targetPoses.value.get(previous)?.role === 'previous') {
    const known = value.get(previous);
    value.set(previous, {
      text: '上一步',
      kind: known?.kind ?? 'suggest',
      why: known?.why || '上一张选择的学习卡片',
    });
  }
  return value;
});

function markClass(kind: RelationKind): string {
  if (kind === 'prerequisite') return 'border-[#4f7cff] bg-[#eef2ff] text-[#3355cc]';
  if (kind === 'suggest') return 'border-line bg-field text-ink-2';
  return 'border-warn-edge bg-warn-bg text-warn-ink';
}

const ZOOM_LIMITS = CANVAS_ZOOM_LIMITS;

function clampZoom(value: number): number {
  return clampZoomTo(value, ZOOM_LIMITS);
}

function snapZoom(value: number): number {
  return snapZoomTo(value, ZOOM_LIMITS);
}

function alignPan(value: number): number {
  return canvasPan(value);
}

function position(id: string): CardPose {
  return poses.value.get(id) ?? { x: 0, y: 0, opacity: 0, scale: 1, role: 'leaving' };
}

function destination(id: string): { x: number; y: number } | null {
  return targetPoses.value.get(id) ?? null;
}

function focusView(): void {
  if (props.selected) {
    centreOn(props.selected);
    return;
  }
  const element = wrapping.value;
  if (!element || !targetPoses.value.size) return;
  const box = bounds.value;
  const scale = motion.getView().zoom;
  motion.moveView({
    zoom: scale,
    pan: {
      x: (element.clientWidth - box.width * scale) / 2 - box.left * scale,
      y: (element.clientHeight - box.height * scale) / 2 - box.top * scale,
    },
  });
}

function overviewView() {
  const first = layout.value.bands[0];
  const scale = snapZoom(OPEN_ZOOM);
  return {
    zoom: scale,
    pan: { x: alignPan(14 - (first?.x ?? 0) * scale), y: alignPan(14 - PAD * scale) },
  };
}

function focusPanY(
  height: number,
  scale: number,
  spots: Map<string, CardPose>,
  anchorY = 0,
): number {
  const top = Math.min(0, ...[...spots.values()].map((spot) => spot.y));
  return alignPan(
    Math.max(height / 3 - (anchorY + CARD_HEIGHT / 2) * scale, FIT_PAD - top * scale),
  );
}

function fitView(): void {
  const element = wrapping.value;
  if (!element || !targetPoses.value.size) return;
  let box = bounds.value;
  const availableWidth = element.clientWidth - FIT_PAD * 2;
  const availableHeight = element.clientHeight - FIT_PAD * 2 - 48;
  if (availableWidth <= 0 || availableHeight <= 0) return;
  const raw = Math.min(1, availableWidth / box.width, availableHeight / box.height);
  const spot = props.selected ? destination(props.selected) : null;
  if (raw < 0.85 && spot)
    box = {
      left: spot.x - FIT_PAD,
      top: spot.y - FIT_PAD,
      width: CARD_WIDTH + FIT_PAD * 2,
      height: CARD_HEIGHT + FIT_PAD * 2,
    };
  const scale = snapZoom(
    Math.max(0.85, Math.min(1, availableWidth / box.width, availableHeight / box.height)),
  );
  motion.moveView({
    zoom: scale,
    pan: {
      x: alignPan((element.clientWidth - box.width * scale) / 2 - box.left * scale),
      y: alignPan((element.clientHeight - 48 - box.height * scale) / 2 - box.top * scale),
    },
  });
}

function centreOn(id: string): void {
  const element = wrapping.value;
  if (!element) return;
  const spot = destination(id);
  if (!spot) return;
  motion.moveView({
    zoom: zoom.value,
    pan: {
      x: alignPan(element.clientWidth / 2 - (spot.x + CARD_WIDTH / 2) * zoom.value),
      y: alignPan((element.clientHeight - 48) / 2 - (spot.y + CARD_HEIGHT / 2) * zoom.value),
    },
  });
}

function isBackground(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    !target.closest('[data-method]') &&
    !target.closest('[data-role="zoom-bar"]')
  );
}

function onBackgroundPointerDown(event: PointerEvent): void {
  if (event.button !== 0 || !isBackground(event.target)) return;
  removeDrag?.();
  motion.stopView();
  const origin = { ...pan.value };
  const startX = event.clientX;
  const startY = event.clientY;
  let travelled = false;
  panning.value = true;
  const move = (moveEvent: PointerEvent) => {
    if (Math.abs(moveEvent.clientX - startX) > 3 || Math.abs(moveEvent.clientY - startY) > 3) {
      travelled = true;
    }
    motion.setView({
      zoom: zoom.value,
      pan: {
        x: alignPan(origin.x + moveEvent.clientX - startX),
        y: alignPan(origin.y + moveEvent.clientY - startY),
      },
    });
  };
  const stop = () => {
    removeDrag?.();
    panning.value = false;
    if (!travelled && props.selected) emit('clear');
  };
  removeDrag = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', stop);
    window.removeEventListener('pointercancel', stop);
    removeDrag = null;
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', stop);
  window.addEventListener('pointercancel', stop);
}

function pickCard(id: string): void {
  if (id === props.selected) {
    emit('clear');
    return;
  }
  emit('pick', id);
}

let activeId: string | null = null;
let signature = '';
let activeViewport = viewport.value;
let activeGraph = props.graph;
let activeLayers = props.layers;
watch(
  [() => props.selected, () => props.graph, () => props.layers, () => viewport.value],
  () => {
    const changed = activeId !== props.selected;
    const oldId = activeId;
    const resized = activeViewport !== viewport.value;
    const resizeOnly =
      resized && !changed && activeGraph === props.graph && activeLayers === props.layers;
    journey.value = followPath(journey.value, props.selected, props.graph);
    const group = focusGroupOf(props.selected, props.graph);
    const scale = group
      ? clampZoom(
          Math.min(
            oldId ? motion.getView().zoom : OPEN_ZOOM,
            (viewport.value.width - 24) / CARD_WIDTH,
          ),
        )
      : zoom.value;
    const next = group
      ? focusPoses(
          group,
          journey.value,
          cardSize,
          (viewport.value.width - 32) / scale,
          viewport.value.height / scale,
        )
      : new Map(
          [...layout.value.spots].map(([id, point]) => [
            id,
            { ...point, scale: 1, opacity: 1, role: 'overview' } as CardPose,
          ]),
        );
    const nextSignature = JSON.stringify([...next]);
    const oldSpot = oldId ? layout.value.spots.get(oldId) : null;
    const view = panning.value
      ? { zoom: zoom.value, pan: { ...pan.value } }
      : group
        ? {
            zoom: scale,
            pan: {
              x: viewport.value.width / 2 - (CARD_WIDTH * scale) / 2,
              y: focusPanY(viewport.value.height, scale, next),
            },
          }
        : changed && oldSpot
          ? {
              zoom: scale,
              pan: {
                x: viewport.value.width / 2 - (oldSpot.x + CARD_WIDTH / 2) * scale,
                y: viewport.value.height / 2 - (oldSpot.y + CARD_HEIGHT / 2) * scale,
              },
            }
          : overviewView();
    if (nextSignature !== signature) targetPoses.value = next;
    if (resizeOnly) {
      if (nextSignature === signature) {
        motion.shiftView({
          x: (viewport.value.width - activeViewport.width) / 2,
          y: (viewport.value.height - activeViewport.height) / 2,
        });
      } else motion.reflow(next, view, viewport.value);
    } else if (changed || nextSignature !== signature) {
      motion.move(
        next,
        view,
        viewport.value,
        true,
        undefined,
        changed ? (props.selected ?? oldId ?? undefined) : undefined,
      );
    } else if (resized && group) {
      motion.setView(view);
    }
    // Return cards with the small focused topology before fading in the full graph at rest.
    if (props.selected || !motion.moving.value) edgeSelection.value = props.selected;
    activeId = props.selected;
    activeViewport = viewport.value;
    activeGraph = props.graph;
    activeLayers = props.layers;
    signature = nextSignature;
  },
  { flush: 'post', immediate: true },
);
watch(
  motion.moving,
  (moving) => {
    if (!moving) edgeSelection.value = props.selected;
  },
  { flush: 'post' },
);

let resize: ResizeObserver | null = null;
watch(
  wrapping,
  (element, previous) => {
    if (previous) previous.removeEventListener('wheel', onWheel);
    resize?.disconnect();
    if (element) {
      element.addEventListener('wheel', onWheel, { passive: false });
      const measure = () => {
        if (
          element.clientWidth &&
          element.clientHeight &&
          (viewport.value.width !== element.clientWidth ||
            viewport.value.height !== element.clientHeight)
        ) {
          viewport.value = { width: element.clientWidth, height: element.clientHeight };
        }
      };
      measure();
      resize = new ResizeObserver(measure);
      resize.observe(element);
    }
  },
  { flush: 'post' },
);

onUnmounted(() => {
  const element = wrapping.value;
  if (element) element.removeEventListener('wheel', onWheel);
  resize?.disconnect();
  removeDrag?.();
});

defineExpose({ focusView, fitView, centreOn });
</script>

<template>
  <section class="relative min-h-0 flex-1">
    <section
      v-if="cards.length"
      ref="wrapping"
      class="relative h-full cursor-grab touch-none select-none overflow-clip"
      :class="panning && 'cursor-grabbing'"
      :style="{
        backgroundImage: 'radial-gradient(circle, var(--dsw-alias-border-l1) 1px, transparent 1px)',
        backgroundSize: `${32 * zoom}px ${32 * zoom}px`,
        backgroundPosition: `${pan.x}px ${pan.y}px`,
      }"
      data-role="method-graph"
      :data-total="total"
      :data-visible-count="total"
      :data-level-count="levelCount"
      :data-moving="motion.moving.value"
      :data-scope="focused ? 'focus' : 'all'"
      tabindex="0"
      @pointerdown="onBackgroundPointerDown"
    >
      <div
        class="relative origin-top-left"
        data-role="graph-stage"
        :style="{
          width: bounds.width + 'px',
          height: bounds.height + 'px',
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
        }"
      >
        <svg
          class="pointer-events-none absolute left-0 top-0 overflow-visible text-[#4f7cff]"
          :width="bounds.width"
          :height="bounds.height"
          aria-hidden="true"
        >
          <g v-for="layer in edgeLayers" :key="layer.kind">
            <Transition :css="false" appear @enter="edgeFade.enter" @leave="edgeFade.leave">
              <g
                v-if="layer.enabled"
                :key="layer.key"
                :data-edge-layer="layer.kind"
                :data-edge-view="layer.key"
              >
                <g
                  v-for="batch in layer.batches"
                  :key="batch.key"
                  :opacity="batch.opacity"
                  :data-edge-batch="batch.kind"
                >
                  <path
                    class="fill-none"
                    :d="batch.path"
                    stroke="var(--dsw-alias-bg-layer-1)"
                    stroke-width="4.5"
                    stroke-linecap="round"
                    vector-effect="non-scaling-stroke"
                    aria-hidden="true"
                  />
                  <path
                    class="fill-none"
                    :stroke="
                      batch.kind === 'prerequisite'
                        ? '#4f7cff'
                        : batch.kind === 'suggest'
                          ? '#94a3b8'
                          : '#d97706'
                    "
                    :stroke-dasharray="batch.kind === 'prerequisite' ? undefined : '7 5'"
                    :d="batch.path"
                    stroke-width="1.7"
                    vector-effect="non-scaling-stroke"
                  />
                  <path
                    v-if="batch.arrows"
                    :d="batch.arrows"
                    :fill="batch.kind === 'suggest' ? '#94a3b8' : '#4f7cff'"
                    data-role="edge-arrowheads"
                  />
                </g>
              </g>
            </Transition>
          </g>
          <template v-if="!motion.moving.value && !panning">
            <path
              v-for="edge in renderedEdges"
              :key="edge.key"
              :d="edge.path"
              fill="none"
              stroke="transparent"
              stroke-width="7"
              vector-effect="non-scaling-stroke"
              style="pointer-events: stroke"
              :data-edge="edge.kind"
              :data-why="edge.why"
            >
              <title>{{ edge.why }}</title>
            </path>
          </template>
        </svg>

        <div
          v-for="band in layout.bands"
          :key="'band-' + band.level"
          class="absolute z-[1] flex flex-col items-start gap-1 transition-opacity ease-[ease] motion-reduce:transition-none"
          :class="focused && 'pointer-events-none opacity-0'"
          :style="{
            left: band.x + 'px',
            top: band.y + 'px',
            transitionDuration: frontendConfig.canvas.categoryFadeMs + 'ms',
          }"
          :data-layer="band.level"
        >
          <span class="flex items-baseline gap-2 whitespace-nowrap">
            <span class="text-[12.5px] font-semibold text-ink">{{ band.name }}</span>
            <span class="text-[10px] text-ink-3">{{ band.count }} 个方法</span>
          </span>
        </div>

        <div
          v-for="column in layout.columns"
          :key="'lane-' + column.x"
          class="absolute box-border rounded-[16px] border border-[#e1eaf8] transition-opacity ease-[ease] motion-reduce:transition-none"
          data-role="method-category-background"
          :class="focused && 'pointer-events-none opacity-0'"
          :style="{
            left: Math.round(column.x - 20) + 'px',
            top: PAD - 24 + 'px',
            width: Math.round(column.width + 40) + 'px',
            height: layout.height + 48 + 'px',
            transitionDuration: frontendConfig.canvas.categoryFadeMs + 'ms',
            backgroundColor: `rgba(246, 249, 255, ${1 - frontendConfig.canvas.categoryTransparencyPercent / 100})`,
          }"
        />

        <article
          v-for="card in visibleCards"
          :key="card.id"
          v-memo="[
            card,
            position(card.id),
            card.id === props.selected,
            marks.get(card.id),
            learnedIds.has(card.id),
            studyingIds.has(card.id),
          ]"
          class="absolute box-border flex cursor-pointer flex-col justify-center gap-0.5 rounded-[9px] border border-l-[5px] bg-surface px-[11px] py-2 transition-shadow duration-[220ms] ease-[ease] select-none touch-none motion-reduce:transition-none"
          :style="{
            left: '0px',
            top: '0px',
            transformOrigin: 'top left',
            transform: `translate(${position(card.id).x}px, ${position(card.id).y}px) scale(${position(card.id).scale})`,
            opacity: position(card.id).opacity,
            pointerEvents:
              position(card.id).role === 'leaving' || position(card.id).opacity < 0.1
                ? 'none'
                : 'auto',
            zIndex: card.id === props.selected ? 3 : position(card.id).role === 'leaving' ? 0 : 2,
            width: CARD_WIDTH + 'px',
            height: CARD_HEIGHT + 'px',
            ...learningCardStyle(
              learnedIds.has(card.id)
                ? 'learned'
                : studyingIds.has(card.id)
                  ? 'studying'
                  : 'unlearned',
              card.id === props.selected,
            ),
          }"
          :data-selected="card.id === props.selected ? 'true' : 'false'"
          :data-method="card.id"
          :data-kind="card.kind"
          :data-learning-status="
            learnedIds.has(card.id)
              ? 'learned'
              : studyingIds.has(card.id)
                ? 'studying'
                : 'unlearned'
          "
          :data-flow-role="position(card.id).role"
          data-role="method-node"
          role="button"
          :tabindex="position(card.id).role === 'leaving' ? -1 : 0"
          :aria-label="card.label"
          :aria-hidden="position(card.id).role === 'leaving'"
          @click="pickCard(card.id)"
          @keydown.enter.stop.prevent="pickCard(card.id)"
          @keydown.space.stop.prevent="pickCard(card.id)"
        >
          <span class="truncate text-[10px] text-ink-2">{{ card.group }}</span>
          <span
            class="line-clamp-2 overflow-hidden text-[12.5px] font-medium leading-[1.25] text-ink"
            >{{ card.label }}</span
          >
          <span
            v-if="marks.get(card.id)"
            class="absolute -top-[9px] left-2 rounded-[999px] border px-1.5 text-[10px] font-medium leading-[16px]"
            :class="markClass(marks.get(card.id)!.kind)"
            :data-mark="card.id"
            :title="marks.get(card.id)!.why"
            >{{ marks.get(card.id)!.text }}</span
          >
          <span
            v-if="studyingIds.has(card.id) && !learnedIds.has(card.id)"
            class="absolute right-2 top-[26px] grid h-[15px] w-[15px] place-items-center rounded-full bg-[#f59e0b] text-white"
            data-studying="true"
            title="学习中"
            ><UiIcon name="clock" class="h-[11px] w-[11px]"
          /></span>
          <span
            v-if="learnedIds.has(card.id)"
            class="absolute right-2 bottom-1.5 grid h-[15px] w-[15px] place-items-center rounded-full bg-[#22a06b] text-[10px] font-bold leading-none text-white"
            data-learned="true"
            title="已学习，已放进你的学习路线"
            ><UiIcon name="check" class="h-[11px] w-[11px]"
          /></span>
          <span
            v-if="card.missing.length"
            class="ui-icon-slot absolute right-2 top-1.5 h-4 w-4 text-[#d97706]"
            :title="`缺少依赖：${card.missing.join('、')}`"
            ><UiIcon name="warning" class="h-[14px] w-[14px]"
          /></span>
        </article>
      </div>

      <div class="graph-zoom" data-role="zoom-bar" @pointerdown.stop @wheel.stop>
        <button
          type="button"
          class="ui-icon-button"
          data-action="zoom-out"
          aria-label="缩小"
          @click="zoomBy(1 / 1.2)"
          ><UiIcon name="minus"
        /></button>
        <output data-role="zoom-value">{{ Math.round(zoom * 100) }}%</output>
        <button
          type="button"
          class="ui-icon-button"
          data-action="zoom-in"
          aria-label="放大"
          @click="zoomBy(1.2)"
          ><UiIcon name="plus"
        /></button>
        <button type="button" data-action="graph-fit" @click="fitView">适应</button>
        <button
          type="button"
          data-action="graph-center"
          title="保持缩放，定位选中方法或内容中心"
          @click="focusView"
          >居中</button
        >
      </div>
    </section>
    <p
      v-else
      class="m-0 px-5 py-7 text-[length:var(--dsw-text-sm)] text-ink-2"
      data-role="graph-empty"
      >{{ props.placeholder }}</p
    >
  </section>
</template>

<style scoped>
.graph-zoom {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: flex;
  align-items: center;
  gap: 3px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 999px;
  padding: 4px;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.1);
  cursor: default;
}
.graph-zoom button {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 26px;
  padding: 0 6px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
}
.graph-zoom button:hover {
  background: var(--dsw-alias-bg-layer-2);
}
.graph-zoom output {
  min-width: 44px;
  text-align: center;
  font-size: var(--dsw-text-sm);
  font-variant-numeric: tabular-nums;
}

[data-role='method-graph']::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(820px 480px at 8% -10%, rgb(235 243 255 / 0.85) 0%, transparent 64%),
    radial-gradient(640px 400px at 98% 2%, rgb(237 249 244 / 0.7) 0%, transparent 60%);
}
.graph-zoom {
  border-color: #e2e9f4;
  background: rgb(255 255 255 / 0.92);
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.05),
    0 12px 28px -22px rgb(20 40 80 / 0.4);
  backdrop-filter: blur(10px);
}
.graph-zoom button {
  height: 28px;
  border-radius: 8px;
  color: #4f5d73;
  font-size: 11px;
}
.graph-zoom button:hover {
  background: #eef3fb;
  color: #13203a;
}
.graph-zoom output {
  color: #4f5d73;
  font-size: 11px;
  font-weight: 600;
}
</style>
