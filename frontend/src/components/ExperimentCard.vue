<script setup lang="ts">
import { computed } from 'vue';
import ExperimentOutcome from '@/components/ExperimentOutcome.vue';

import type { ExperimentResult } from '@/types';
import { figureSrc } from '@/utils/figure-url';

const props = defineProps<{ result: ExperimentResult }>();

const title = computed(() => props.result.title ?? '实验结果');
const figures = computed(() =>
  (props.result.figures ?? [])
    .filter((figure) => Boolean(figure.url))
    .map((figure) => ({ name: figure.name, url: figureSrc(figure.name, figure.url) })),
);
const emit = defineEmits<{ (event: 'zoom', url: string, name: string): void }>();
</script>

<template>
  <article class="result-block" data-kind="experiment">
    <header class="result-head">
      <h3>{{ title }}</h3>
      <span v-if="props.result.elapsed_ms" class="result-elapsed"
        >{{ (props.result.elapsed_ms / 1000).toFixed(2) }} 秒</span
      >
    </header>
    <ExperimentOutcome :result="result" compact />
    <div v-if="figures.length" class="experiment-figures tool-figures">
      <figure v-for="figure in figures" :key="figure.name" class="tool-figure">
        <img
          :src="figure.url"
          :alt="figure.name"
          loading="lazy"
          @click="emit('zoom', figure.url ?? '', figure.name)"
        />
      </figure>
    </div>
  </article>
</template>
