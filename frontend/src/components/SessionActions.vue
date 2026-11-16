<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue';
import UiIcon from '@/components/UiIcon.vue';

defineProps<{ title: string }>();
const emit = defineEmits<{ (event: 'rename'): void; (event: 'delete'): void }>();
const open = ref(false);
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const position = ref({ left: '0px', top: '0px' });
const id = useId();

function close(): void {
  open.value = false;
}
function outside(event: PointerEvent): void {
  const target = event.target as Node;
  if (!trigger.value?.contains(target) && !menu.value?.contains(target)) close();
}
function escape(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault();
    close();
    trigger.value?.focus();
  }
}
function listeners(enabled: boolean): void {
  if (enabled) {
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    document.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
  } else {
    document.removeEventListener('pointerdown', outside);
    document.removeEventListener('keydown', escape);
    document.removeEventListener('scroll', close, true);
    window.removeEventListener('resize', close);
  }
}
watch(open, listeners, { flush: 'sync' });
onBeforeUnmount(() => listeners(false));

async function toggle(): Promise<void> {
  if (open.value) {
    close();
    return;
  }
  const box = trigger.value?.getBoundingClientRect();
  if (!box) return;
  const height = 92,
    width = 160,
    margin = 8;
  position.value = {
    left: `${Math.max(margin, Math.min(box.right - width, innerWidth - width - margin))}px`,
    top: `${box.bottom + height + margin <= innerHeight ? box.bottom + 6 : Math.max(margin, box.top - height - 6)}px`,
  };
  open.value = true;
  await nextTick();
  menu.value?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true });
}
function choose(action: 'rename' | 'delete'): void {
  close();
  trigger.value?.focus({ preventScroll: true });
  if (action === 'rename') emit('rename');
  else emit('delete');
}
function navigate(event: KeyboardEvent): void {
  if (event.key === 'Tab') {
    close();
    trigger.value?.focus({ preventScroll: true });
    return;
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const items = Array.from(menu.value?.querySelectorAll<HTMLButtonElement>('button') ?? []);
  const current = items.indexOf(document.activeElement as HTMLButtonElement);
  const index =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? items.length - 1
        : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
  items[index]?.focus({ preventScroll: true });
}
</script>

<template>
  <button
    ref="trigger"
    type="button"
    class="session-actions-trigger opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 [@media(pointer:coarse)]:opacity-100"
    data-action="session-menu"
    :aria-label="`会话操作：${title}`"
    title="更多会话操作"
    aria-haspopup="menu"
    :aria-expanded="open"
    :aria-controls="id"
    @click.stop="toggle"
  >
    <UiIcon name="more" class="h-4 w-4" />
  </button>
  <Teleport to="body">
    <Transition name="fade-content">
      <div
        v-if="open"
        :id="id"
        ref="menu"
        class="session-actions-menu"
        :style="position"
        role="menu"
        aria-label="会话操作"
        data-role="session-menu"
        @click.stop
        @keydown="navigate"
      >
        <button
          type="button"
          role="menuitem"
          data-action="rename-session"
          @click="choose('rename')"
        >
          <UiIcon name="edit" class="h-4 w-4" /><span>重命名</span>
        </button>
        <button
          type="button"
          role="menuitem"
          class="danger"
          data-action="delete-session"
          @click="choose('delete')"
        >
          <UiIcon name="trash" class="h-4 w-4" /><span>删除会话</span>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.session-actions-trigger {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: var(--dsw-radius-sm);
  cursor: pointer;
  background: transparent;
  color: var(--dsw-alias-text-tertiary);
}
.session-actions-trigger:hover,
.session-actions-trigger[aria-expanded='true'] {
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
}
.session-actions-trigger[aria-expanded='true'] {
  opacity: 1;
}
.session-actions-trigger:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 1px;
}
.session-actions-menu {
  position: fixed;
  z-index: 65;
  width: 160px;
  padding: 5px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: var(--dsw-radius-md);
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: var(--dsw-elevation-panel);
}
.session-actions-menu button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 9px;
  border: 0;
  border-radius: var(--dsw-radius-sm);
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: var(--dsw-text-sm);
  text-align: left;
}
.session-actions-menu button:hover,
.session-actions-menu button:focus-visible {
  outline: none;
  background: var(--dsw-alias-bg-skeleton);
  color: var(--dsw-alias-text-primary);
}
.session-actions-menu button.danger {
  color: var(--dsw-feedback-error-text);
}
</style>
