<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, toRef, watch } from 'vue';
import StudyCard from '@/components/StudyCard.vue';
import StudyArrowLayer from '@/components/StudyArrowLayer.vue';
import UiIcon from '@/components/UiIcon.vue';
import { useStudyCanvas, STUDY_CARD_WIDTH, STUDY_CARD_HEIGHT } from '@/composables/useStudyCanvas';
import type {
  StudyCardModel,
  StudyEdge,
  StudyEdgeRoute,
  StudyNode,
  StudySide,
  StudySource,
} from '@/services/study';
import {
  arrowsNear,
  STUDY_SIDES,
  studyAnchor,
  studyArrow,
  targetSideFor,
} from '@/utils/study-arrows';
import { createStudyArrowCache } from '@/utils/study-arrow-cache';
import { createCanvasSpatialIndex, type CanvasRect } from '@/utils/canvas-spatial-index';
import { canvasWindow } from '@/utils/canvas-visibility';

const props = withDefaults(
  defineProps<{
    cards: StudyCardModel[];
    nodes: StudyNode[];
    sources: StudySource[];
    edges?: StudyEdge[];
    routes?: StudyEdgeRoute[];
    paused?: boolean;
    pending?: Array<{ card_id: string; reason: string; suggestion?: string }>;
  }>(),
  { edges: () => [], routes: () => [], paused: false },
);
const emit = defineEmits<{
  move: [
    positions: Record<string, { x: number; y: number }>,
    basis: Record<string, { x: number; y: number }>,
  ];
  selection: [ids: string[]];
  inspect: [];
  source: [cardId: string];
  learn: [cardId: string];
  delete: [cardId: string];
  level: [cardId: string, value: string];
  notice: [message: string];
  connect: [fromId: string, toId: string, sourceSide: StudySide, targetSide: StudySide];
  deleteEdge: [edge: StudyEdge];
}>();
const container = ref<HTMLElement | null>(null);
const canvas = useStudyCanvas(
  container,
  toRef(props, 'nodes'),
  (positions, basis) => emit('move', positions, basis),
  (message) => emit('notice', message),
);
const cardMap = computed(() => new Map(props.cards.map((card) => [card.card_id, card])));
const pendingReasons = computed(
  () =>
    new Map(
      (props.pending ?? []).map((item) => [
        item.card_id,
        [item.reason, item.suggestion ? `建议：${item.suggestion}` : ''].filter(Boolean).join('；'),
      ]),
    ),
);
const allNodes = computed(() => props.nodes.filter((node) => cardMap.value.has(node.card_id)));
const arrowNodes = computed(() =>
  allNodes.value.map((node) => ({ card_id: node.card_id, ...canvas.position(node) })),
);
const focusedCard = ref<string | null>(null);
const viewWindow = computed<CanvasRect>((previous) =>
  canvasWindow(canvas.pan.value, canvas.zoom.value, canvas.viewport.value, previous),
);
const nodeIndex = computed(() => {
  const index = createCanvasSpatialIndex();
  for (const node of arrowNodes.value)
    index.set(node.card_id, {
      x: node.x,
      y: node.y,
      width: STUDY_CARD_WIDTH,
      height: STUDY_CARD_HEIGHT,
    });
  return index;
});
const visible = computed(() => {
  const ids = new Set(nodeIndex.value.search(viewWindow.value));
  const dragging =
    canvas.gestureKind.value === 'drag' ? new Set(canvas.selected.value) : new Set<string>();
  const selected = canvas.selected.value.length === 1 ? canvas.selected.value[0] : null;
  return allNodes.value.filter(
    (node) =>
      ids.has(node.card_id) ||
      dragging.has(node.card_id) ||
      node.card_id === focusedCard.value ||
      node.card_id === selected,
  );
});
const arrowCache = createStudyArrowCache();
const arrows = computed(() =>
  arrowCache.build(props.edges, arrowNodes.value, props.routes, canvas.zoom.value),
);
const arrowIndex = computed(() => {
  const index = createCanvasSpatialIndex();
  for (const arrow of arrows.value) index.set(arrow.edge.edge_id, arrow.bounds);
  return index;
});
const visibleArrows = computed(() => {
  const ids = new Set(arrowIndex.value.search(viewWindow.value));
  return arrows.value.filter((arrow) => ids.has(arrow.edge.edge_id));
});
function trackFocus(event: FocusEvent) {
  const target = event.type === 'focusout' ? event.relatedTarget : event.target;
  focusedCard.value =
    target instanceof Element && container.value?.contains(target)
      ? (target.closest<HTMLElement>('[data-card]')?.dataset.card ?? null)
      : null;
}
const hoveredCard = ref<string | null>(null);
const connection = ref<{
  fromId: string;
  side: StudySide;
  point: { x: number; y: number };
  target: { id: string; side: StudySide } | null;
} | null>(null);
const menu = ref<{ ids: string[]; selected: string; x: number; y: number } | null>(null);
const menuEdges = computed(() =>
  props.edges.filter((edge) => menu.value?.ids.includes(edge.edge_id)),
);
const selectedEdge = computed(() =>
  menuEdges.value.find((edge) => edge.edge_id === menu.value?.selected),
);
const sideLabels: Record<StudySide, string> = { top: '上', right: '右', bottom: '下', left: '左' };
// Screen pixels: the hit area stays usable when the canvas is zoomed out.
const portHitSize = 32;
const preview = computed(() => {
  const gesture = connection.value;
  if (!gesture) return '';
  const from = arrowNodes.value.find((node) => node.card_id === gesture.fromId);
  if (!from) return '';
  const target = arrowNodes.value.find((node) => node.card_id === gesture.target?.id);
  if (target && gesture.target)
    return studyArrow({ from_id: from.card_id, to_id: target.card_id } as StudyEdge, from, target, {
      edge_id: '',
      waypoints: [],
      source_side: gesture.side,
      target_side: gesture.target.side,
    }).path;
  const start = studyAnchor(from, gesture.side),
    end = gesture.point;
  const forward =
    gesture.side === 'right'
      ? end.x - start.x
      : gesture.side === 'left'
        ? start.x - end.x
        : gesture.side === 'bottom'
          ? end.y - start.y
          : start.y - end.y;
  const length = Math.max(0, forward / 2);
  const dx = gesture.side === 'right' ? length : gesture.side === 'left' ? -length : 0;
  const dy = gesture.side === 'bottom' ? length : gesture.side === 'top' ? -length : 0;
  return `M ${start.x} ${start.y} C ${start.x + dx} ${start.y + dy}, ${end.x} ${end.y}, ${end.x} ${end.y}`;
});
function closeMenu() {
  menu.value = null;
}
function edgeTitle(edge: StudyEdge) {
  return `${cardMap.value.get(edge.from_id)?.title ?? edge.from_id} ${['alternative', 'related'].includes(edge.type) ? '—' : '→'} ${cardMap.value.get(edge.to_id)?.title ?? edge.to_id}`;
}
function showMenu(event: PointerEvent, ids: string[], selected = ids[0]) {
  if (!selected || event.button !== 0) return;
  canvas.cancel();
  const rect = container.value?.getBoundingClientRect();
  menu.value = {
    ids,
    selected,
    x: Math.max(
      8,
      Math.min(event.clientX - (rect?.left ?? 0) + 8, (container.value?.clientWidth || 800) - 290),
    ),
    y: Math.max(
      8,
      Math.min(
        event.clientY - (rect?.top ?? 0) + 8,
        (container.value?.clientHeight || 600) - Math.min(280, 90 + ids.length * 38),
      ),
    ),
  };
}
function selectArrow(event: PointerEvent, edgeId: string) {
  const candidates = arrowsNear(
    arrows.value,
    canvas.world(event.clientX, event.clientY),
    9 / canvas.zoom.value,
  ).map((arrow) => arrow.edge.edge_id);
  showMenu(event, [...new Set([edgeId, ...candidates])], edgeId);
}
function deleteArrow() {
  if (selectedEdge.value && !props.paused) emit('deleteEdge', selectedEdge.value);
  closeMenu();
}
function targetAt(event: PointerEvent, fromId: string) {
  const point = canvas.world(event.clientX, event.clientY);
  const element = document.elementFromPoint?.(event.clientX, event.clientY);
  const port = element?.closest<HTMLElement>('[data-role="study-port"]');
  if (
    port &&
    container.value?.contains(port) &&
    arrowNodes.value.some((node) => node.card_id === port.dataset.card)
  )
    return { id: port.dataset.card!, side: port.dataset.side as StudySide };
  const candidates = [...arrowNodes.value].reverse();
  for (const node of candidates)
    for (const side of STUDY_SIDES) {
      const anchor = studyAnchor(node, side);
      if (Math.hypot(point.x - anchor.x, point.y - anchor.y) <= portHitSize / 2 / canvas.zoom.value)
        return { id: node.card_id, side };
    }
  const node = candidates.find(
    (node) =>
      point.x >= node.x &&
      point.x <= node.x + STUDY_CARD_WIDTH &&
      point.y >= node.y &&
      point.y <= node.y + STUDY_CARD_HEIGHT,
  );
  return node
    ? {
        id: node.card_id,
        side: targetSideFor(
          studyAnchor(
            arrowNodes.value.find((item) => item.card_id === fromId)!,
            connection.value!.side,
          ),
          node,
        ),
      }
    : null;
}
function startConnection(event: PointerEvent, fromId: string, side: StudySide) {
  if (props.paused || event.button !== 0) return;
  closeMenu();
  canvas.cancel();
  connection.value = {
    fromId,
    side,
    point: canvas.world(event.clientX, event.clientY),
    target: null,
  };
  canvas.connect(
    event,
    (next) => {
      if (connection.value) {
        connection.value.point = canvas.world(next.clientX, next.clientY);
        connection.value.target = targetAt(next, fromId);
      }
    },
    (next, dragged) => {
      const target = targetAt(next, fromId);
      connection.value = null;
      if (dragged) {
        if (target) emit('connect', fromId, target.id, side, target.side);
        return;
      }
      const ids = arrows.value
        .filter(
          (arrow) =>
            (arrow.edge.from_id === fromId && arrow.sourceSide === side) ||
            (arrow.edge.to_id === fromId && arrow.targetSide === side),
        )
        .map((arrow) => arrow.edge.edge_id);
      showMenu(next, ids);
    },
    () => {
      connection.value = null;
    },
  );
}
function hover(event: PointerEvent) {
  hoveredCard.value =
    event.target instanceof Element
      ? (event.target.closest<HTMLElement>('[data-card]')?.dataset.card ?? null)
      : null;
}
function outside(event: PointerEvent) {
  if (!(event.target instanceof Element && event.target.closest('[data-role="study-arrow-menu"]')))
    closeMenu();
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') closeMenu();
}
const sourceLabels = computed(() => {
  const sources = new Map<string, StudySource[]>();
  for (const source of props.sources) {
    const group = sources.get(source.card_id) ?? [];
    group.push(source);
    sources.set(source.card_id, group);
  }
  return new Map(
    props.cards.map((card) => {
      const items = sources.get(card.card_id) ?? [];
      const label =
        (card.binding && !card.binding.session_missing) ||
        (items.length === 1 && items[0]?.availability === 'available')
          ? '打开对话'
          : items.length
            ? `${items.length} 个来源`
            : '';
      return [card.card_id, label];
    }),
  );
});
function select(ids: string[]) {
  canvas.select(ids);
  emit('inspect');
}
function pointer(event: PointerEvent, cardId?: string) {
  closeMenu();
  canvas.pointerDown(event, cardId);
  if (cardId && canvas.gestureKind.value !== 'pan') emit('inspect');
}
watch(canvas.selected, (ids) => emit('selection', ids));
watch(
  () => props.paused,
  (paused) => {
    if (paused) canvas.cancel();
  },
);
watch(menuEdges, (edges) => {
  if (menu.value && !edges.length) closeMenu();
});
onMounted(async () => {
  document.addEventListener('pointerdown', outside, true);
  window.addEventListener('keydown', keydown);
  await nextTick();
  canvas.fit();
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', outside, true);
  window.removeEventListener('keydown', keydown);
});
defineExpose({
  select,
  fit: canvas.fit,
  cancel: canvas.cancel,
  world: canvas.world,
  boxes: canvas.boxes,
  container,
  zoom: canvas.zoom,
});
</script>

<template>
  <div
    ref="container"
    class="study-canvas"
    data-role="study-canvas"
    tabindex="0"
    aria-label="学习路线画布，Shift 拖动框选，空格拖动平移"
    :class="{
      'is-panning': canvas.gestureKind.value === 'pan',
      'is-dragging': canvas.gestureKind.value === 'drag',
    }"
    :style="{
      backgroundSize: `${32 * canvas.zoom.value}px ${32 * canvas.zoom.value}px`,
      backgroundPosition: `${canvas.pan.value.x}px ${canvas.pan.value.y}px`,
    }"
    @pointerdown="pointer($event)"
    @pointermove="hover"
    @pointerleave="hoveredCard = null"
    @focusin="trackFocus"
    @focusout="trackFocus"
    @wheel="
      closeMenu();
      canvas.wheel($event);
    "
  >
    <div
      class="study-stage"
      data-role="study-stage"
      :style="{
        transform: `translate(${canvas.pan.value.x}px, ${canvas.pan.value.y}px) scale(${canvas.zoom.value})`,
      }"
    >
      <StudyArrowLayer
        :arrows="visibleArrows"
        :viewport="viewWindow"
        :zoom="canvas.zoom.value"
        :selected="menu?.selected ?? null"
        :preview="preview"
        @select="selectArrow"
      />
      <svg class="study-guides" aria-hidden="true">
        <template v-for="guide in canvas.guides.value" :key="`${guide.axis}:${guide.kind}`">
          <line
            v-if="guide.kind !== 'gap'"
            :x1="guide.axis === 'x' ? guide.value : guide.start"
            :x2="guide.axis === 'x' ? guide.value : guide.end"
            :y1="guide.axis === 'y' ? guide.value : guide.start"
            :y2="guide.axis === 'y' ? guide.value : guide.end"
            class="alignment-guide"
            vector-effect="non-scaling-stroke"
            data-role="study-snap-guide"
          />
          <g v-for="(gap, index) in guide.gaps ?? []" :key="index" data-role="study-gap-guide">
            <line
              :x1="guide.axis === 'x' ? gap.start : gap.at"
              :x2="guide.axis === 'x' ? gap.end : gap.at"
              :y1="guide.axis === 'y' ? gap.start : gap.at"
              :y2="guide.axis === 'y' ? gap.end : gap.at"
              class="gap-guide"
              vector-effect="non-scaling-stroke"
            />
            <line
              v-for="end in [gap.start, gap.end]"
              :key="end"
              :x1="guide.axis === 'x' ? end : gap.at - 4 / canvas.zoom.value"
              :x2="guide.axis === 'x' ? end : gap.at + 4 / canvas.zoom.value"
              :y1="guide.axis === 'y' ? end : gap.at - 4 / canvas.zoom.value"
              :y2="guide.axis === 'y' ? end : gap.at + 4 / canvas.zoom.value"
              class="gap-guide"
              vector-effect="non-scaling-stroke"
            />
            <text
              :x="guide.axis === 'x' ? (gap.start + gap.end) / 2 : gap.at + 6 / canvas.zoom.value"
              :y="guide.axis === 'y' ? (gap.start + gap.end) / 2 : gap.at - 5 / canvas.zoom.value"
              :font-size="11 / canvas.zoom.value"
              text-anchor="middle"
              class="gap-label"
            >
              {{ Number((gap.end - gap.start).toFixed(1)) }}
            </text>
          </g>
        </template>
      </svg>
      <StudyCard
        v-for="node in visible"
        :key="node.card_id"
        :card="cardMap.get(node.card_id)!"
        :node="node"
        :position="canvas.position(node)"
        :selected="canvas.selected.value.includes(node.card_id)"
        :source-label="sourceLabels.get(node.card_id) ?? ''"
        :pending-reason="pendingReasons.get(node.card_id)"
        @pointer="pointer($event, node.card_id)"
        @select="select([node.card_id])"
        @source="emit('source', node.card_id)"
        @learn="emit('learn', node.card_id)"
        @delete="emit('delete', node.card_id)"
        @level="emit('level', node.card_id, $event)"
      />
      <div
        v-for="node in visible"
        :key="`ports-${node.card_id}`"
        class="study-ports"
        :class="{
          'ports-visible':
            hoveredCard === node.card_id ||
            canvas.selected.value.includes(node.card_id) ||
            connection,
        }"
        :style="{
          left: `${canvas.position(node).x}px`,
          top: `${canvas.position(node).y}px`,
          width: `${STUDY_CARD_WIDTH}px`,
          height: `${STUDY_CARD_HEIGHT}px`,
        }"
        :data-card="node.card_id"
      >
        <button
          v-for="side in STUDY_SIDES"
          :key="side"
          type="button"
          class="study-port"
          :class="{
            'is-target': connection?.target?.id === node.card_id && connection.target.side === side,
          }"
          :style="{
            left: `${studyAnchor({ x: 0, y: 0 }, side).x}px`,
            top: `${studyAnchor({ x: 0, y: 0 }, side).y}px`,
            width: `${portHitSize / canvas.zoom.value}px`,
            height: `${portHitSize / canvas.zoom.value}px`,
          }"
          data-role="study-port"
          :data-card="node.card_id"
          :data-side="side"
          :disabled="paused"
          :aria-label="`${cardMap.get(node.card_id)?.title}的${sideLabels[side]}侧中点，拖动连接，点击查看连线`"
          @pointerdown.stop.prevent="startConnection($event, node.card_id, side)"
          @click.stop
        >
          <span
            class="port-dot"
            aria-hidden="true"
            :style="{
              width: `${10 / canvas.zoom.value}px`,
              height: `${10 / canvas.zoom.value}px`,
              borderWidth: `${1 / canvas.zoom.value}px`,
            }"
          />
        </button>
      </div>
      <div
        v-if="canvas.marquee.value"
        class="study-marquee"
        data-role="study-marquee"
        :style="{
          left: `${canvas.marquee.value.x}px`,
          top: `${canvas.marquee.value.y}px`,
          width: `${canvas.marquee.value.width}px`,
          height: `${canvas.marquee.value.height}px`,
        }"
      />
    </div>
    <div
      v-if="menu && menuEdges.length"
      class="study-arrow-menu"
      data-role="study-arrow-menu"
      :style="{ left: `${menu.x}px`, top: `${menu.y}px` }"
      @pointerdown.stop
      @wheel.stop
    >
      <p v-if="menuEdges.length > 1">此处有 {{ menuEdges.length }} 条连线，选择要删除的一条</p>
      <div v-if="menuEdges.length > 1" class="arrow-candidates"
        ><button
          v-for="edge in menuEdges"
          :key="edge.edge_id"
          type="button"
          :aria-pressed="menu.selected === edge.edge_id"
          :data-edge="edge.edge_id"
          data-action="study-choose-edge"
          @click="menu.selected = edge.edge_id"
          >{{ edgeTitle(edge) }}</button
        ></div
      >
      <p v-else>{{ selectedEdge && edgeTitle(selectedEdge) }}</p>
      <button
        type="button"
        class="delete-arrow"
        data-action="study-delete-edge"
        :disabled="paused || !selectedEdge"
        @click="deleteArrow"
        >删除这条连线</button
      >
    </div>
    <div v-if="!allNodes.length" class="canvas-empty" data-role="study-empty">
      <span class="canvas-empty-icon" aria-hidden="true"><UiIcon name="learning-route" /></span>
      <h2>从一张卡片开始</h2>
      <p>添加学习卡片，或从参考路线带入方法。卡片可拖动、排序和连线。</p>
      <div class="canvas-empty-steps">
        <span><b>01</b>添加卡片</span>
        <span><b>02</b>建立关系</span>
        <span><b>03</b>标记进度</span>
      </div>
    </div>
    <div class="canvas-hint">Ctrl / ⌘ 多选 · Shift 框选 · 空格平移 · Alt 暂停吸附</div>
    <div class="study-zoom" data-role="study-zoom" @pointerdown.stop @wheel.stop>
      <button
        type="button"
        class="ui-icon-button"
        data-action="study-zoom-out"
        aria-label="缩小"
        @click="canvas.zoomBy(1 / 1.2)"
        ><UiIcon name="minus"
      /></button>
      <output data-role="study-zoom-value">{{ Math.round(canvas.zoom.value * 100) }}%</output>
      <button
        type="button"
        class="ui-icon-button"
        data-action="study-zoom-in"
        aria-label="放大"
        @click="canvas.zoomBy(1.2)"
        ><UiIcon name="plus"
      /></button>
      <button type="button" data-action="study-fit" @click="canvas.fit()">适应</button>
      <button type="button" data-action="study-center" @click="canvas.fit(true)">居中</button>
    </div>
  </div>
</template>

<style scoped>
.study-canvas {
  position: relative;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  outline-offset: -3px;
  touch-action: none;
  user-select: none;
  background-image: radial-gradient(circle, var(--dsw-alias-border-l1) 1px, transparent 1px);
  cursor: grab;
}
.is-panning,
.is-dragging {
  cursor: grabbing;
}
.study-stage {
  position: absolute;
  left: 0;
  top: 0;
  width: 1px;
  height: 1px;
  transform-origin: 0 0;
}
.study-stage :deep(.study-card) {
  z-index: 2;
}
.study-stage :deep(.study-card.selected) {
  z-index: 3;
}
.study-ports {
  position: absolute;
  pointer-events: none;
  z-index: 4;
}
.study-port {
  position: absolute;
  display: grid;
  place-items: center;
  box-sizing: border-box;
  appearance: none;
  transform: translate(-50%, -50%);
  border: 0;
  border-radius: 50%;
  padding: 0;
  background: transparent;
  pointer-events: auto;
  cursor: crosshair;
  touch-action: none;
}
.port-dot {
  display: block;
  box-sizing: border-box;
  border-style: solid;
  border-color: var(--dsw-alias-text-tertiary);
  border-radius: 50%;
  background: var(--dsw-alias-bg-layer-1);
  opacity: 0;
  pointer-events: none;
}
.ports-visible .port-dot,
.study-port:hover .port-dot,
.study-port:focus-visible .port-dot {
  opacity: 1;
}
.study-port:hover .port-dot,
.study-port.is-target .port-dot {
  border-color: var(--dsw-feedback-info-text);
  background: var(--dsw-selection-surface);
}
.study-port:disabled {
  cursor: default;
}
.study-arrow-menu {
  position: absolute;
  z-index: 15;
  width: 264px;
  box-sizing: border-box;
  max-height: 280px;
  overflow: auto;
  padding: 10px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: 0 5px 18px rgb(0 0 0 / 0.13);
  cursor: default;
}
.study-arrow-menu p {
  margin: 0 0 8px;
  font-size: var(--dsw-text-sm);
  line-height: 1.6;
  overflow-wrap: anywhere;
  color: var(--dsw-alias-text-secondary);
}
.study-arrow-menu button {
  width: 100%;
  border: 0;
  border-radius: 5px;
  padding: 7px 8px;
  text-align: left;
  background: transparent;
  color: var(--dsw-alias-text-primary);
  font: inherit;
  font-size: var(--dsw-text-sm);
  cursor: pointer;
}
.study-arrow-menu button:hover,
.arrow-candidates button[aria-pressed='true'] {
  background: var(--dsw-alias-bg-layer-2);
}
.arrow-candidates {
  max-height: 160px;
  overflow: auto;
  margin-bottom: 6px;
}
.study-arrow-menu .delete-arrow {
  color: var(--dsw-alias-text-primary);
  border-top: 1px solid var(--dsw-alias-border-l2);
  border-radius: 0;
}
.study-guides {
  position: absolute;
  left: 0;
  top: 0;
  width: 1px;
  height: 1px;
  overflow: visible;
  pointer-events: none;
  z-index: 3;
}
.alignment-guide,
.gap-guide {
  stroke: var(--dsw-static-deepseek-500);
  stroke-width: 1;
}
.alignment-guide {
  stroke-dasharray: 5 4;
}
.gap-label {
  fill: var(--dsw-static-deepseek-500);
  paint-order: stroke;
  stroke: var(--dsw-alias-bg-layer-1);
  stroke-width: 2px;
}
.study-marquee {
  position: absolute;
  border: 1px solid var(--dsw-focus-ring);
  background: rgb(70 110 220 / 0.1);
  pointer-events: none;
  z-index: 5;
}
.canvas-empty {
  position: absolute;
  top: 35%;
  left: 15%;
  right: 15%;
  text-align: center;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-row);
  pointer-events: none;
}
.canvas-hint {
  position: absolute;
  bottom: 16px;
  left: 16px;
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
  pointer-events: none;
}
.study-zoom {
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
.study-zoom button {
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
.study-zoom button:hover {
  background: var(--dsw-alias-bg-layer-2);
}
.study-zoom output {
  min-width: 44px;
  text-align: center;
  font-size: var(--dsw-text-sm);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 900px) {
  .canvas-hint {
    display: none;
  }
}

/* Canvas chrome */
.study-canvas::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(720px 420px at 12% -8%, rgb(248 250 253 / 0.9) 0%, transparent 66%),
    radial-gradient(620px 380px at 96% 4%, rgb(249 251 253 / 0.8) 0%, transparent 62%);
}
.canvas-empty {
  top: 50%;
  left: 50%;
  right: auto;
  width: min(520px, calc(100% - 48px));
  transform: translate(-50%, -52%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 30px 34px 32px;
  border: 1px solid #e6ecf6;
  border-radius: 22px;
  background: rgb(255 255 255 / 0.84);
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.03),
    0 30px 70px -50px rgb(20 40 80 / 0.4);
  backdrop-filter: blur(12px);
  pointer-events: none;
}
.canvas-empty-icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  border-radius: 17px;
  background: linear-gradient(145deg, #eef4ff 0%, #dfe9ff 100%);
  color: #3d63c7;
  box-shadow:
    inset 0 0 0 1px rgb(79 124 255 / 0.12),
    0 16px 30px -24px rgb(30 60 120 / 0.6);
}
.canvas-empty-icon svg {
  width: 23px;
  height: 23px;
}
.canvas-empty h2 {
  margin: 16px 0 0;
  color: #14213a;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.025em;
  line-height: 1.3;
}
.canvas-empty p {
  max-width: 390px;
  margin: 7px 0 0;
  color: #7b879c;
  font-size: 11.5px;
  line-height: 1.7;
  text-align: center;
}
.canvas-empty-steps {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 7px;
  margin-top: 16px;
}
.canvas-empty-steps span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  border: 1px solid #e6ecf6;
  border-radius: 999px;
  background: #f8faff;
  color: #8a96ab;
  font-size: 9.5px;
  line-height: 1.5;
}
.canvas-empty-steps b {
  color: #3d63c7;
  font-size: 8.5px;
  font-weight: 700;
}
.canvas-hint {
  bottom: 18px;
  left: 18px;
  padding: 4px 8px;
  border: 1px solid #e6ecf6;
  border-radius: 7px;
  background: rgb(255 255 255 / 0.75);
  color: #8a96ab;
  font-size: 9.5px;
  line-height: 1.5;
  backdrop-filter: blur(8px);
}
.study-zoom {
  right: 16px;
  bottom: 16px;
  padding: 4px;
  border-color: #e2e9f4;
  background: rgb(255 255 255 / 0.92);
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.05),
    0 12px 28px -22px rgb(20 40 80 / 0.4);
  backdrop-filter: blur(10px);
}
.study-zoom button {
  height: 28px;
  border-radius: 8px;
  color: #4f5d73;
  font-size: 11px;
}
.study-zoom button:hover {
  background: #eef3fb;
  color: #13203a;
}
.study-zoom output {
  min-width: 46px;
  color: #4f5d73;
  font-size: 11px;
  font-weight: 600;
}
@media (max-width: 900px) {
  .canvas-empty {
    padding: 24px 20px 26px;
  }
}
</style>
