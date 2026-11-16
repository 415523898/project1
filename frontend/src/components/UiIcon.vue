<script setup lang="ts">
defineProps<{
  name:
    | 'chevron-left'
    | 'chevron-right'
    | 'chevron-down'
    | 'chevrons-left'
    | 'grid'
    | 'search'
    | 'chart-results'
    | 'panel-right'
    | 'fit'
    | 'self-check'
    | 'file-document'
    | 'image'
    | 'settings'
    | 'more'
    | 'log-out'
    | 'edit'
    | 'trash'
    | 'book-open'
    | 'learning-route'
    | 'eye'
    | 'lock'
    | 'brain'
    | 'plus'
    | 'minus'
    | 'close'
    | 'arrow-left'
    | 'arrow-right'
    | 'arrow-left-dashed'
    | 'undo'
    | 'redo'
    | 'copy'
    | 'regenerate'
    | 'branch'
    | 'arrow-right-dashed'
    | 'arrows-horizontal'
    | 'arrow-up-right'
    | 'check'
    | 'warning'
    | 'clock'
    | 'spinner'
    | 'table'
    | 'paperclip'
    | 'microphone'
    | 'dot'
    | 'check-circle'
    | 'play-circle'
    | 'sparkles';
}>();

const gear = Array.from({ length: 8 }, (_, tooth) =>
  [
    [-9, 8],
    [-6, 10],
    [6, 10],
    [9, 8],
    [22.5, 8],
  ]
    .map(([offset, radius]) => {
      const angle = ((tooth * 45 + offset!) * Math.PI) / 180;
      return `${(12 + Math.cos(angle) * radius!).toFixed(2)},${(12 + Math.sin(angle) * radius!).toFixed(2)}`;
    })
    .join(' '),
).join(' ');
</script>

<template>
  <svg
    class="ui-icon"
    :data-icon="name"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <template v-if="name === 'file-document'">
      <path d="M14 3H5v18h14V8Z M14 3v5h5 M8 12h8 M8 16h6" />
    </template>
    <template v-else-if="name === 'image'">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8" cy="8" r="1.5" />
      <path d="m3 17 5-5 4 4 4-6 5 7" />
    </template>
    <template v-else-if="name === 'copy'">
      <rect x="8" y="8" width="12" height="13" rx="2" />
      <path d="M16 4V3H4v13h1" />
    </template>
    <path
      v-else-if="name === 'regenerate'"
      d="M20 9a8 8 0 0 0-13-4L4 8 M4 3v5h5 M4 15a8 8 0 0 0 13 4l3-3 M20 21v-5h-5"
    />
    <path
      v-else-if="name === 'branch'"
      d="M4 18h3c5 0 5-12 10-12h3 M15 2l5 4-5 4 M4 6h3c1.8 0 2.7 1.6 3.5 3 M13.5 15c.9 1.8 1.9 3 3.5 3h3 M16 14l4 4-4 4"
    />
    <path
      v-else-if="name === 'sparkles'"
      d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z M20 3v4 M18 5h4"
    />
    <path v-else-if="name === 'chevron-left'" d="M15 6 9 12 15 18" />
    <path v-else-if="name === 'chevron-right'" d="m9 6 6 6-6 6" />
    <path v-else-if="name === 'chevron-down'" d="m6 9 6 6 6-6" />
    <path v-else-if="name === 'panel-right'" d="M5 5h14v14H5z M14 5v14" />
    <path v-else-if="name === 'fit'" d="M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5 M8 8h8v8H8z" />
    <path v-else-if="name === 'chevrons-left'" d="m11 7-5 5 5 5 m7-10-5 5 5 5" />
    <path v-else-if="name === 'plus'" d="M12 5v14 M5 12h14" />
    <path v-else-if="name === 'minus'" d="M5 12h14" />
    <path v-else-if="name === 'close'" d="m6 6 12 12 M18 6 6 18" />
    <path v-else-if="name === 'arrow-left'" d="M20 12H4 m6-6-6 6 6 6" />
    <path v-else-if="name === 'arrow-right'" d="M4 12h16 m-6-6 6 6-6 6" />
    <!-- One diagonal return curve, mirrored for redo. -->
    <g
      v-else-if="name === 'undo' || name === 'redo'"
      :transform="name === 'redo' ? 'translate(24 0) scale(-1 1)' : undefined"
    >
      <path
        transform="translate(-.17 -1.24) rotate(-45 12 12)"
        d="m9 3-4 4 4 4 M5 7h10a6 6 0 0 1 0 12H5"
      />
    </g>
    <template v-else-if="name === 'arrow-left-dashed'">
      <path d="M20 12H4" stroke-dasharray="2.5 3.5" />
      <path d="m10 6-6 6 6 6" />
    </template>
    <template v-else-if="name === 'arrow-right-dashed'">
      <path d="M4 12h16" stroke-dasharray="2.5 3.5" />
      <path d="m14 6 6 6-6 6" />
    </template>
    <path v-else-if="name === 'arrows-horizontal'" d="M4 12h16 m-6-6 6 6-6 6 M10 6l-6 6 6 6" />
    <path v-else-if="name === 'arrow-up-right'" d="M6 18 18 6 M6 6h12v12" />
    <path v-else-if="name === 'check'" d="m5 12 4 4L19 6" />
    <template v-else-if="name === 'warning'">
      <path d="M10.3 4.5a2 2 0 0 1 3.4 0l7 12.5a2 2 0 0 1-1.7 3H5a2 2 0 0 1-1.7-3Z M12 8v5" />
      <circle cx="12" cy="16.5" r=".8" fill="currentColor" stroke="none" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </template>
    <template v-else-if="name === 'spinner'">
      <circle cx="12" cy="12" r="8.5" opacity=".2" />
      <path d="M12 3.5a8.5 8.5 0 0 1 8.5 8.5" />
    </template>
    <template v-else-if="name === 'table'">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9h18 M3 14h18 M9 9v11 M15 9v11" />
    </template>
    <path v-else-if="name === 'paperclip'" d="m9 13 7-7a3 3 0 0 1 4 4l-9 9a5 5 0 0 1-7-7l9-9" />
    <template v-else-if="name === 'microphone'">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0 M12 18v3 M9 21h6" />
    </template>
    <circle v-else-if="name === 'dot'" cx="12" cy="12" r="6" fill="currentColor" stroke="none" />
    <template v-else-if="name === 'check-circle'">
      <circle cx="12" cy="12" r="9" />
      <path d="m7 12 3 3 7-7" />
    </template>
    <template v-else-if="name === 'self-check'">
      <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
      <rect x="8" y="2" width="8" height="4" rx="1.5" />
      <path d="m7.5 11 1.5 1.5 3-3 M15 11h1.5 M8 17h8" />
    </template>
    <template v-else-if="name === 'play-circle'">
      <circle cx="12" cy="12" r="9" />
      <path d="m10 8 6 4-6 4Z" fill="currentColor" stroke="none" />
    </template>
    <template v-else-if="name === 'grid'">
      <rect
        v-for="cell in 9"
        :key="cell"
        :x="3 + ((cell - 1) % 3) * 7"
        :y="3 + Math.floor((cell - 1) / 3) * 7"
        width="4"
        height="4"
        rx=".5"
        stroke-width="1.5"
      />
    </template>
    <template v-else-if="name === 'search'">
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </template>
    <path v-else-if="name === 'chart-results'" d="M4 4v16h16 M8 16v-4 M13 16V8 M18 16V4" />
    <template v-else-if="name === 'brain'">
      <path
        d="M12 4v16 M12 5a4 4 0 0 0-7-1 4 4 0 0 0-2 6 4 4 0 0 0 1 7 4 4 0 0 0 8 2 M12 5a4 4 0 0 1 7-1 4 4 0 0 1 2 6 4 4 0 0 1-1 7 4 4 0 0 1-8 2 M7 8v3l3 2 M17 8v3l-3 2 M6 16l3-1 M18 16l-3-1"
      />
    </template>
    <template v-else-if="name === 'eye'">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </template>
    <template v-else-if="name === 'lock'">
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </template>
    <template v-else-if="name === 'settings'">
      <polygon :points="gear" />
      <circle cx="12" cy="12" r="3.2" />
    </template>
    <template v-else-if="name === 'more'">
      <circle
        v-for="x in [5, 12, 19]"
        :key="x"
        :cx="x"
        cy="12"
        r="1.7"
        fill="currentColor"
        stroke="none"
      />
    </template>
    <template v-else-if="name === 'edit'">
      <path d="m15 5 4 4 M4 20l1-5L16 4a2.8 2.8 0 0 1 4 4L9 19l-5 1Z" />
    </template>
    <template v-else-if="name === 'trash'">
      <path d="M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7" />
    </template>
    <template v-else-if="name === 'book-open'">
      <path d="M12 6v15 M12 6C9 4 6 3 3 4v15c3-1 6 0 9 2 3-2 6-3 9-2V4c-3-1-6 0-9 2Z" />
    </template>
    <template v-else-if="name === 'learning-route'">
      <path d="M5 14V9a4 4 0 0 1 4-4h.5 M14.5 5H15a4 4 0 0 1 4 4v5" />
      <circle cx="5" cy="17" r="2.5" />
      <circle cx="12" cy="5" r="2.5" />
      <circle cx="19" cy="17" r="2.5" />
    </template>
    <template v-else>
      <path d="M10 4H4v16h6 M9 12h11 M16 8l4 4-4 4" />
    </template>
  </svg>
</template>

<style scoped>
.ui-icon {
  display: block;
  flex-shrink: 0;
  transform-origin: center;
  transform-box: view-box;
}
.ui-icon[data-icon='spinner'] {
  animation: icon-spin 900ms linear infinite;
}
@keyframes icon-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .ui-icon[data-icon='spinner'] {
    animation: none;
  }
}
</style>
