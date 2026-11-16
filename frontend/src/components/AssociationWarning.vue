<script setup lang="ts">
defineProps<{ message: string }>();
</script>
<template>
  <span
    class="association-warning"
    role="img"
    :aria-label="message"
    :title="message"
    data-role="association-warning"
  >
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M10.3 4.3a2 2 0 0 1 3.4 0l8 13.6a2 2 0 0 1-1.7 3H4a2 2 0 0 1-1.7-3Z"
        fill="#fff3df"
        stroke="#db8a20"
        stroke-width="1.7"
        stroke-linejoin="round"
      />
      <path d="M12 9v5" stroke="#b9690a" stroke-width="2" stroke-linecap="round" />
      <circle cx="12" cy="17" r="1" fill="#b9690a" />
    </svg>
  </span>
</template>
<style scoped>
.association-warning {
  display: inline-flex;
  align-items: center;
  flex: none;
  vertical-align: middle;
  cursor: help;
}
</style>
