<script setup lang="ts">
import { RouterLink } from 'vue-router';
import { useLab } from '@/composables/useLab';

withDefaults(defineProps<{ prefix?: string }>(), { prefix: 'model' });
const lab = useLab();
</script>

<template>
  <RouterLink
    v-if="lab.modelAccess.value.kind === 'auth'"
    :to="{ path: '/signin', query: { next: '/' } }"
    :data-action="`${prefix}-sign-in`"
    >{{ lab.modelAccess.value.label }}</RouterLink
  >
  <button
    v-else-if="lab.modelAccess.value.kind !== 'ready'"
    type="button"
    :data-action="`${prefix}-${lab.modelAccess.value.kind === 'configuration' ? 'settings' : lab.modelAccess.value.kind}`"
    :disabled="lab.modelAccess.value.kind === 'loading'"
    @click="lab.resolveModelAccess()"
    >{{ lab.modelAccess.value.label }}</button
  >
</template>
