<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { RouterView } from 'vue-router';

import AppRail from '@/components/AppRail.vue';
import PanelResizeHandle from '@/components/PanelResizeHandle.vue';
import ConsentDialog from '@/components/ConsentDialog.vue';
import ImageLightbox from '@/components/ImageLightbox.vue';
import SettingsDialog from '@/components/SettingsDialog.vue';
import { useLab } from '@/composables/useLab';
import { useSidebar } from '@/composables/useSidebar';
import { usePanelWidth } from '@/composables/usePanelWidth';

const lab = useLab();
const sidebar = useSidebar();
const navigation = usePanelWidth('navigation');

const ready = computed(() => lab.state.authChecked);

onMounted(async () => {
  lab.setBodyView(lab.viewName());
  const ok = await lab.checkAuth();
  if (ok) await lab.restoreActive();
});
</script>

<template>
  <div
    v-if="!ready"
    class="flex h-full flex-col items-center justify-center gap-3"
    aria-live="polite"
  >
    <span
      class="grid h-[34px] w-[34px] place-items-center rounded-panel bg-ink text-[length:var(--dsw-text-row)] font-medium text-brand-ink"
      aria-hidden="true"
      >知</span
    >
    <p class="m-0 text-[length:var(--dsw-text-row)] text-ink-3">正在准备方法库…</p>
  </div>
  <div
    v-else
    class="panel-layout grid h-full overflow-hidden"
    :style="{
      gridTemplateColumns: `min(${sidebar.wide.value && !sidebar.narrow.value ? navigation.width.value : 56}px, 35vw) minmax(0,1fr)`,
    }"
  >
    <div class="relative min-h-0 min-w-0" data-panel="navigation">
      <div
        class="navigation-panel relative h-full min-w-0"
        data-role="navigation-panel"
        :class="{ 'is-narrow': sidebar.narrow.value, 'is-open': sidebar.wide.value }"
        :style="{
          width: sidebar.narrow.value
            ? `min(${sidebar.wide.value ? navigation.width.value : 56}px, calc(100vw - 48px))`
            : undefined,
        }"
      >
        <AppRail class="h-full" />
        <Transition name="panel-content">
          <PanelResizeHandle
            v-if="sidebar.wide.value"
            edge="right"
            label="主导航宽度"
            :width="navigation.width.value"
            :initial="navigation.initial"
            :min="navigation.min"
            :max="navigation.max"
            @resize="navigation.set"
          />
        </Transition>
      </div>
    </div>
    <Transition name="navigation-backdrop">
      <button
        v-if="sidebar.narrow.value && sidebar.wide.value"
        type="button"
        class="fixed inset-0 z-40 cursor-default border-0 bg-black/20 p-0"
        data-action="navigation-backdrop"
        aria-label="收起侧栏"
        tabindex="-1"
        @click="sidebar.close()"
      />
    </Transition>
    <RouterView />
    <SettingsDialog />
    <ConsentDialog />
    <ImageLightbox />
  </div>
</template>

<style scoped>
.navigation-panel.is-narrow {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  transition: width 240ms cubic-bezier(0.22, 1, 0.36, 1);
}
.navigation-panel.is-narrow.is-open {
  z-index: 50;
  box-shadow: 8px 0 24px rgb(0 0 0 / 0.12);
}
:global(body[data-panel-resizing='yes'] .navigation-panel.is-narrow) {
  transition: none;
}
.navigation-backdrop-enter-active,
.navigation-backdrop-leave-active {
  transition: opacity 180ms ease;
}
.navigation-backdrop-enter-from,
.navigation-backdrop-leave-to {
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .navigation-panel.is-narrow,
  .navigation-backdrop-enter-active,
  .navigation-backdrop-leave-active {
    transition: none;
  }
}
</style>
