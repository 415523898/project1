<script setup lang="ts">
defineProps<{ modelValue: boolean; label: string; disabled?: boolean }>();
defineEmits<{ 'update:modelValue': [value: boolean] }>();
</script>
<template>
  <button
    type="button"
    role="switch"
    :aria-label="label"
    :aria-checked="modelValue"
    :disabled="disabled"
    class="settings-switch"
    :class="{ on: modelValue }"
    @click="$emit('update:modelValue', !modelValue)"
    ><span
  /></button>
</template>
<style scoped>
.settings-switch {
  width: 32px;
  height: 32px;
  flex: none;
  display: grid;
  place-items: center;
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
}
.settings-switch span {
  box-sizing: border-box;
  display: block;
  width: 32px;
  height: 19px;
  padding: 2px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 999px;
  background: var(--dsw-alias-bg-layer-2);
  transition: background 140ms ease;
}
.settings-switch span::before {
  content: '';
  display: block;
  width: 13px;
  height: 13px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 1px 3px #0002;
  transition: transform 140ms ease;
}
.settings-switch.on span {
  background: var(--dsw-alias-link);
  border-color: transparent;
}
.on span::before {
  transform: translateX(12px);
}
.settings-switch:disabled {
  opacity: 0.45;
  cursor: default;
}
@media (prefers-reduced-motion: reduce) {
  .settings-switch,
  .settings-switch span,
  .settings-switch span::before {
    transition: none;
  }
}
</style>
