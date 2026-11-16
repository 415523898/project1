<script setup lang="ts">
import { computed, useId } from 'vue';
import type { StudyArrow } from '@/utils/study-arrows';
import type { CanvasRect } from '@/utils/canvas-spatial-index';
import { clippedRect } from '@/utils/canvas-visibility';
const props = defineProps<{
  arrows: StudyArrow[];
  zoom: number;
  selected: string | null;
  preview?: string;
  viewport?: CanvasRect;
}>();
const masks = computed(() =>
  props.arrows.flatMap((arrow) => {
    const bounds = clippedRect(arrow.bounds, props.viewport);
    const padding = 4 / props.zoom;
    const gaps = arrow.gaps.filter(
      (gap) =>
        gap.x + padding >= bounds.x &&
        gap.x - padding <= bounds.x + bounds.width &&
        gap.y + padding >= bounds.y &&
        gap.y - padding <= bounds.y + bounds.height,
    );
    return gaps.length ? [{ id: arrow.edge.edge_id, bounds, gaps }] : [];
  }),
);
const maskIds = computed(() => new Set(masks.value.map((mask) => mask.id)));
defineEmits<{ select: [event: PointerEvent, edgeId: string] }>();
const prefix = 'study-arrow-' + useId().replace(/[^a-zA-Z0-9_-]/g, '');
const maskId = (id: string) => `${prefix}-gap-${id}`;
</script>

<template>
  <svg class="study-arrows" data-role="study-arrows" aria-hidden="true">
    <defs>
      <marker
        :id="`${prefix}-tip`"
        viewBox="0 0 8 8"
        refX="7"
        refY="4"
        markerWidth="5"
        markerHeight="5"
        orient="auto-start-reverse"
      >
        <path d="M 0 0 L 8 4 L 0 8 z" fill="currentColor" />
      </marker>
      <mask
        v-for="mask in masks"
        :id="maskId(mask.id)"
        :key="mask.id"
        maskUnits="userSpaceOnUse"
        maskContentUnits="userSpaceOnUse"
        v-bind="mask.bounds"
        style="mask-type: luminance"
      >
        <rect v-bind="mask.bounds" fill="white" />
        <circle
          v-for="(gap, index) in mask.gaps"
          :key="index"
          :cx="gap.x"
          :cy="gap.y"
          :r="4 / zoom"
          fill="black"
          data-role="study-arrow-gap"
        />
      </mask>
    </defs>
    <path
      v-for="arrow in arrows"
      :key="arrow.edge.edge_id"
      v-memo="[
        arrow.path,
        arrow.edge.type,
        selected === arrow.edge.edge_id,
        maskIds.has(arrow.edge.edge_id),
      ]"
      :d="arrow.path"
      class="arrow-line"
      :class="{ 'is-selected': selected === arrow.edge.edge_id }"
      :mask="maskIds.has(arrow.edge.edge_id) ? `url(#${maskId(arrow.edge.edge_id)})` : undefined"
      :marker-end="
        ['related', 'alternative'].includes(arrow.edge.type) ? undefined : `url(#${prefix}-tip)`
      "
      data-role="route-arrow"
      :data-edge="arrow.edge.edge_id"
    />
    <path
      v-if="preview"
      :d="preview"
      class="arrow-line arrow-preview"
      :marker-end="`url(#${prefix}-tip)`"
      data-role="study-connection-preview"
    />
  </svg>
  <svg class="study-arrow-hits" aria-label="学习路线连线">
    <g
      v-for="arrow in arrows"
      :key="arrow.edge.edge_id"
      v-memo="[arrow.path, arrow.end, zoom]"
      :data-edge="arrow.edge.edge_id"
    >
      <path
        :d="arrow.path"
        class="arrow-hit"
        :stroke-width="12 / zoom"
        data-role="study-arrow-hit"
        @pointerdown.stop.prevent="$emit('select', $event, arrow.edge.edge_id)"
      />
      <circle
        :cx="arrow.end.x"
        :cy="arrow.end.y"
        :r="7 / zoom"
        class="arrow-tip-hit"
        data-role="study-arrow-tip-hit"
        @pointerdown.stop.prevent="$emit('select', $event, arrow.edge.edge_id)"
      />
    </g>
  </svg>
</template>

<style scoped>
.study-arrows,
.study-arrow-hits {
  position: absolute;
  left: 0;
  top: 0;
  width: 1px;
  height: 1px;
  overflow: visible;
  pointer-events: none;
}
.study-arrows {
  z-index: 0;
  color: var(--dsw-alias-text-tertiary);
}
.study-arrow-hits {
  z-index: 1;
}
.arrow-line {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4px;
}
.arrow-line.is-selected {
  color: var(--dsw-feedback-info-text);
}
.arrow-preview {
  opacity: 0.65;
}
.arrow-hit {
  fill: none;
  stroke: transparent;
  pointer-events: stroke;
  cursor: pointer;
}
.arrow-tip-hit {
  fill: transparent;
  pointer-events: all;
  cursor: pointer;
}
</style>
