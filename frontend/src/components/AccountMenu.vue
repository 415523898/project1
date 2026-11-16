<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue';
import UiIcon from '@/components/UiIcon.vue';

const props = defineProps<{ username: string; compact: boolean }>();
const emit = defineEmits<{ (event: 'logout'): void }>();
const open = ref(false);
const anchor = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const position = ref({ left: '0px', bottom: '0px' });
const id = useId();
const initial = computed(() => props.username.slice(0, 1).toUpperCase());

async function toggle(): Promise<void> {
  const box = anchor.value?.getBoundingClientRect();
  if (box)
    position.value = {
      left: `${Math.max(8, Math.min(box.left, innerWidth - 192))}px`,
      bottom: `${innerHeight - box.top + 8}px`,
    };
  open.value = !open.value;
  if (open.value) {
    await nextTick();
    menu.value?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true });
  }
}
function focusMenu(): void {
  if (!open.value) void toggle();
  else menu.value?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true });
}
function navigate(event: KeyboardEvent): void {
  if (event.key === 'Tab') {
    open.value = false;
    trigger.value?.focus({ preventScroll: true });
  } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    event.preventDefault();
    focusMenu();
  }
}
function outside(event: PointerEvent): void {
  const target = event.target as Node;
  if (!anchor.value?.contains(target) && !menu.value?.contains(target)) open.value = false;
}
function key(event: KeyboardEvent): void {
  if (event.key === 'Escape' && open.value) {
    event.preventDefault();
    open.value = false;
    trigger.value?.focus();
  }
}
function close(): void {
  open.value = false;
}
function logout(): void {
  close();
  emit('logout');
}
onMounted(() => {
  document.addEventListener('pointerdown', outside);
  document.addEventListener('keydown', key);
  window.addEventListener('resize', close);
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', outside);
  document.removeEventListener('keydown', key);
  window.removeEventListener('resize', close);
});
</script>

<template>
  <div
    ref="anchor"
    class="account-row"
    :class="{ compact }"
    data-role="current-user"
    :title="username"
  >
    <span class="account-avatar" aria-hidden="true">{{ initial }}</span>
    <span class="account-name width-reveal" :class="{ 'is-revealed': !compact }">{{
      username
    }}</span>
    <button
      ref="trigger"
      type="button"
      class="account-trigger"
      data-action="account-menu"
      :aria-label="compact ? `${username}，账号操作` : '账号操作'"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="id"
      title="账号操作"
      @click.stop="toggle"
      @keydown.down.prevent="focusMenu"
      @keydown.up.prevent="focusMenu"
    >
      <UiIcon
        name="more"
        class="width-reveal h-[18px] w-[18px]"
        :class="{ 'is-revealed': !compact }"
      />
    </button>
  </div>
  <Teleport to="body">
    <Transition name="fade-content">
      <div
        v-if="open"
        :id="id"
        ref="menu"
        class="account-menu"
        :style="position"
        role="menu"
        @keydown="navigate"
        aria-label="账号操作"
      >
        <button type="button" role="menuitem" data-action="sign-out" @click="logout">
          <UiIcon name="log-out" class="h-[18px] w-[18px]" /><span>退出登录</span>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.account-row {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  height: 34px;
  padding: 0;
  overflow: hidden;
  border-radius: var(--dsw-radius-sm);
  background: transparent;
}
.account-avatar {
  display: grid;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  place-items: center;
  margin: 0 7px;
  border-radius: 50%;
  font-size: var(--dsw-text-xs);
  font-weight: 500;
  border: 1px solid #d7e3fb;
  background: #f7faff;
  color: #315fbd;
  font-weight: 650;
}
.account-name {
  color: #1a2740;
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--dsw-text-sm);
}
.account-trigger {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 32px;
  height: 30px;
  padding: 0;
  cursor: pointer;
  border: 1px solid transparent;
  border-radius: var(--dsw-radius-sm);
  background: transparent;
  color: var(--dsw-alias-text-secondary);
}
.compact .account-trigger {
  position: absolute;
  left: 0;
  top: 0;
  width: 36px;
  height: 34px;
}
.account-trigger:hover,
.account-trigger[aria-expanded='true'] {
  color: var(--dsw-alias-text-primary);
  background: var(--dsw-alias-bg-skeleton);
  border-color: var(--dsw-alias-border-l2);
}
.account-trigger:focus-visible {
  outline: 2px solid var(--dsw-alias-brand-primary);
  outline-offset: 2px;
}
.account-menu {
  position: fixed;
  z-index: 60;
  min-width: 184px;
  padding: 5px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: var(--dsw-radius-md);
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: var(--dsw-elevation-panel);
}
.account-menu button {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: var(--dsw-radius-sm);
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
  font-size: var(--dsw-text-sm);
}
.account-menu button:hover,
.account-menu button:focus-visible {
  background: var(--dsw-alias-bg-skeleton);
  color: var(--dsw-alias-text-primary);
}
</style>
