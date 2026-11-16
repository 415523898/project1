<script setup lang="ts">
import { computed, watch } from 'vue';
import { useLab } from '@/composables/useLab';
import { useStudy } from '@/composables/useStudy';
import { useLearning } from '@/composables/useLearning';
import StudyWorkspaceView from '@/views/StudyWorkspaceView.vue';

const lab = useLab(),
  study = useStudy();
const ready = computed(
  () => study.owner.value === lab.state.user && Boolean(study.workspace.value),
);
watch(
  () => lab.state.user,
  (user, previous) => {
    if (previous !== undefined && previous !== user) useLearning().reset();
    if (user) void useLearning().load();
    void study.open(user, true);
  },
  { immediate: true },
);
</script>

<template>
  <StudyWorkspaceView v-if="ready" />
  <main
    v-else
    class="flex h-full flex-col items-center justify-center gap-3 bg-surface p-5"
    data-view="route"
    data-role="study-loading"
  >
    <p role="status">{{ study.loadError.value || '正在读取学习路线…' }}</p>
    <button
      v-if="study.loadError.value"
      type="button"
      class="ui-button ui-button-primary"
      @click="study.open(lab.state.user, true)"
      >重新加载</button
    >
  </main>
</template>
