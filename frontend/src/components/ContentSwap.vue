<script setup lang="ts">
import { opacityTransition } from '@/utils/opacity-transition';
const fade = opacityTransition(180, 120);
function deactivate(element: Element) {
  (element as HTMLElement).inert = true;
  element.setAttribute('data-content-leaving', '');
}
function activate(element: Element) {
  (element as HTMLElement).inert = false;
  element.removeAttribute('data-content-leaving');
}
</script>
<template>
  <div class="content-swap"
    ><Transition
      :css="false"
      @enter="fade.enter"
      @leave="fade.leave"
      @before-leave="deactivate"
      @before-enter="activate"
      @leave-cancelled="activate"
      ><slot /></Transition
  ></div>
</template>
<style>
.content-swap {
  position: relative;
  display: grid;
  min-width: 0;
  align-items: start;
}
.content-swap > * {
  grid-area: 1/1;
  min-width: 0;
}
.content-swap > [data-content-leaving] {
  position: absolute;
  inset: 0 0 auto;
  pointer-events: none;
}
</style>
