<script setup lang="ts">
import { computed } from 'vue';
import { presetFor } from '@/utils/model-providers';
const props = defineProps<{ id: string }>();
const assets = import.meta.glob<string>('../assets/providers/*.{svg,png,webp}', {
  eager: true,
  query: '?url',
  import: 'default',
});
const logo = computed(() => assets['../assets/providers/' + presetFor(props.id).logo]);
</script>
<template>
  <span class="provider-mark" aria-hidden="true"
    ><img v-if="logo" :src="logo" alt="" /><svg v-else viewBox="0 0 32 32">
      <path
        d="m9 12 7-4 7 4v8l-7 4-7-4z M9 12l7 4 7-4 M16 16v8"
        fill="none"
        stroke="currentColor"
        stroke-width="1.7"
        stroke-linejoin="round"
      /></svg
  ></span>
</template>
<style scoped>
.provider-mark {
  width: 30px;
  height: 30px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px solid #e7e9ed;
  border-radius: 7px;
  padding: 3px;
  box-sizing: border-box;
}
.provider-mark img,
.provider-mark svg {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.provider-mark svg {
  color: #426b64;
}
</style>
