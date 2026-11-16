<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useLab } from '@/composables/useLab';
import UiIcon from '@/components/UiIcon.vue';
import ModelAccessAction from '@/components/ModelAccessAction.vue';
import ProviderMark from '@/components/ProviderMark.vue';
import { presetFor, profileLabel, effortLabels } from '@/utils/model-providers';
import { availableEfforts, configuredModels } from '@/utils/model-config';
const lab = useLab(),
  root = ref<HTMLElement | null>(null),
  trigger = ref<HTMLButtonElement | null>(null);
const open = ref(false),
  reasoningOpen = ref(false),
  hovered = ref('');
const popup = ref<HTMLElement | null>(null),
  popupLeft = ref(0);
const popupBottom = ref(0),
  reasoningPopup = ref<HTMLElement | null>(null),
  reasoningTrigger = ref<HTMLElement | null>(null);
const reasoningPosition = ref({ left: '12px', bottom: '60px' });
const settings = computed(() => lab.state.settings);
const providerLabel = computed(() => profileLabel(settings.value.provider_id, settings.value));
const groups = computed(() =>
  lab.addedProviderIds.value.flatMap((id) => {
    const config = id === settings.value.provider_id ? settings.value : lab.providerProfiles?.[id];
    if (!config || !lab.providerReady(id)) return [];
    const preset = presetFor(id, config);
    const models = configuredModels(
      preset.id,
      config.protocol ?? preset.protocol,
      config.model ?? '',
      config.models,
    ).filter((model) => model.enabled);
    return models.length
      ? [{ ...preset, id, preset_id: preset.id, label: profileLabel(id, config), models }]
      : [];
  }),
);
const activeGroup = computed(
  () => groups.value.find((group) => group.id === hovered.value) ?? groups.value[0],
);
const currentModel = computed(() =>
  settings.value.models?.find((model) => model.id === settings.value.model),
);
const efforts = computed(() =>
  availableEfforts(
    settings.value.provider_id,
    settings.value.protocol,
    settings.value.model,
    currentModel.value,
    settings.value.preset_id,
  ),
);
const effortLabel = computed(() =>
  settings.value.reasoning_effort === 'auto'
    ? '默认'
    : (effortLabels[settings.value.reasoning_effort] ?? settings.value.reasoning_effort),
);
async function toggle() {
  reasoningOpen.value = false;
  open.value = !open.value;
  hovered.value =
    groups.value.find((g) => g.id === settings.value.provider_id)?.id ?? groups.value[0]?.id ?? '';
  popupLeft.value = 0;
  if (open.value) {
    await nextTick();
    if (!trigger.value) return;
    const rect = trigger.value.getBoundingClientRect(),
      width = Math.min(560, window.innerWidth - 24);
    popupLeft.value = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    popupBottom.value = window.innerHeight - rect.top + 8;
  }
}
function toggleReasoning() {
  open.value = false;
  reasoningOpen.value = !reasoningOpen.value;
  const rect = reasoningTrigger.value?.getBoundingClientRect();
  if (rect)
    reasoningPosition.value = {
      left: `${Math.max(12, Math.min(rect.left, window.innerWidth - 164))}px`,
      bottom: `${window.innerHeight - rect.top + 8}px`,
    };
}
function close() {
  open.value = false;
  reasoningOpen.value = false;
}
watch(
  () => lab.providerLoading.value,
  (loading) => {
    if (loading) close();
  },
);
function outside(event: PointerEvent) {
  if (
    event.target instanceof Node &&
    !root.value?.contains(event.target) &&
    !popup.value?.contains(event.target) &&
    !reasoningPopup.value?.contains(event.target)
  )
    close();
}
onMounted(() => document.addEventListener('pointerdown', outside));
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside));
async function choose(provider: string, model: string) {
  if (lab.state.busy) return;
  if (provider !== settings.value.provider_id) lab.selectProvider(provider);
  lab.selectModel(model);
  close();
  await nextTick();
  trigger.value?.focus();
}
function manage() {
  close();
  lab.openSettings();
}
async function focusModel() {
  await nextTick();
  popup.value?.querySelector<HTMLButtonElement>('[data-model-choice]')?.focus();
}
function navigate(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    close();
    trigger.value?.focus();
    return;
  }
  if (event.key === 'ArrowRight' && open.value) {
    event.preventDefault();
    void focusModel();
    return;
  }
  if (event.key === 'ArrowLeft' && open.value) {
    event.preventDefault();
    popup.value
      ?.querySelector<HTMLButtonElement>(`[data-provider-choice="${hovered.value}"]`)
      ?.focus();
    return;
  }
  if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
  const menu = (event.target as HTMLElement).closest('[role=menu]');
  if (!menu) return;
  const items = [...menu.querySelectorAll<HTMLButtonElement>(':scope > button:not(:disabled)')];
  if (!items.length) return;
  event.preventDefault();
  const index = items.indexOf(document.activeElement as HTMLButtonElement);
  items[(index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
}
</script>
<template>
  <div ref="root" class="model-controls" data-role="model-controls" @keydown="navigate">
    <div class="model-picker-anchor">
      <ModelAccessAction
        v-if="lab.modelAccess.value.kind === 'load-error'"
        prefix="chat-model"
        class="model-trigger"
      />
      <button
        v-else
        ref="trigger"
        type="button"
        class="model-trigger"
        :disabled="lab.state.busy || lab.providerLoading.value"
        :title="
          lab.providerLoading.value
            ? '正在读取账号模型配置'
            : lab.providerReady(settings.provider_id)
              ? `${providerLabel} / ${settings.model}`
              : '选择已配置的模型'
        "
        aria-haspopup="menu"
        :aria-expanded="open"
        data-action="choose-chat-model"
        @click="toggle"
        @keydown.down.prevent="
          toggle();
          nextTick(() =>
            popup?.querySelector<HTMLButtonElement>('[data-provider-choice]')?.focus(),
          );
        "
        ><span>{{
          lab.providerLoading.value
            ? '正在加载模型…'
            : lab.providerReady(settings.provider_id) && !lab.configurationIssue.value
              ? `${providerLabel} / ${settings.model}`
              : '选择模型'
        }}</span
        ><UiIcon name="chevron-down"
      /></button>
      <Teleport to="body">
        <Transition name="control-menu">
          <div
            v-if="open"
            ref="popup"
            class="model-picker-popup"
            data-role="model-picker"
            :style="{ left: `${popupLeft}px`, bottom: `${popupBottom}px` }"
            @keydown="navigate"
          >
            <div class="provider-menu" role="menu" aria-label="上游请求平台">
              <button
                v-for="group in groups"
                :key="group.id"
                type="button"
                role="menuitem"
                :data-provider-choice="group.id"
                aria-haspopup="menu"
                :aria-expanded="activeGroup?.id === group.id"
                :class="{ hovered: activeGroup?.id === group.id }"
                @pointerenter="hovered = group.id"
                @focus="hovered = group.id"
                @click="
                  hovered = group.id;
                  focusModel();
                "
                ><ProviderMark :id="group.preset_id" /><span>{{ group.label }}</span
                ><UiIcon v-if="settings.provider_id === group.id" name="check" /><UiIcon
                  name="chevron-right"
              /></button>
              <p v-if="!groups.length" class="empty">暂无已启用的模型</p>
              <div class="menu-divider"></div
              ><button
                type="button"
                role="menuitem"
                class="manage"
                data-action="manage-models"
                @click="manage"
                >管理模型<UiIcon name="settings"
              /></button>
            </div>
            <div
              v-if="activeGroup"
              class="model-submenu"
              role="menu"
              :aria-label="`${activeGroup.label} 模型`"
            >
              <button
                v-for="model in activeGroup.models"
                :key="model.id"
                type="button"
                role="menuitemradio"
                :title="model.id"
                :aria-checked="
                  settings.provider_id === activeGroup.id && settings.model === model.id
                "
                data-model-choice
                :data-choice="model.id"
                @click="choose(activeGroup.id, model.id)"
                ><span>{{ model.id }}</span
                ><UiIcon
                  v-if="settings.provider_id === activeGroup.id && settings.model === model.id"
                  name="check"
              /></button>
            </div>
          </div>
        </Transition>
      </Teleport>
    </div>
    <div class="reasoning-anchor">
      <button
        ref="reasoningTrigger"
        type="button"
        class="reasoning-trigger"
        :disabled="lab.state.busy"
        data-action="choose-reasoning"
        aria-haspopup="menu"
        :aria-expanded="reasoningOpen"
        @click="toggleReasoning"
        ><UiIcon name="brain" /><span>{{ effortLabel }}</span
        ><UiIcon name="chevron-down"
      /></button>
      <Teleport to="body">
        <Transition name="control-menu">
          <div
            v-if="reasoningOpen"
            ref="reasoningPopup"
            class="reasoning-menu"
            :style="reasoningPosition"
            role="menu"
            aria-label="思考强度"
            @keydown="navigate"
            ><button
              v-for="value in efforts"
              :key="value"
              type="button"
              role="menuitemradio"
              :aria-checked="settings.reasoning_effort === value"
              :data-effort="value"
              @click="
                lab.setReasoningEffort(value);
                close();
              "
              ><span>{{ effortLabels[value] ?? value }}</span
              ><UiIcon v-if="settings.reasoning_effort === value" name="check" /></button
          ></div>
        </Transition>
      </Teleport>
    </div>
  </div>
</template>
<style scoped>
.model-picker-popup {
  position: fixed !important;
  width: min(560px, calc(100vw - 24px));
  max-width: calc(100vw - 24px) !important;
  z-index: 80 !important;
  font-size: var(--dsw-text-sm);
}
.model-picker-popup .provider-menu {
  width: 38%;
  min-width: 0;
}
.model-picker-popup .model-submenu {
  width: 62%;
  min-width: 0;
  max-width: none;
}
.model-picker-popup .model-submenu > button > span {
  white-space: normal;
  overflow-wrap: anywhere;
}
.reasoning-anchor .reasoning-menu,
.reasoning-menu {
  position: fixed !important;
  z-index: 80 !important;
  font-size: var(--dsw-text-sm);
}
.provider-menu > button > .provider-mark {
  flex: none;
  width: 22px;
  height: 22px;
  min-width: 22px;
}
.control-menu-enter-active {
  transition:
    opacity 180ms ease-out,
    transform 180ms cubic-bezier(0.2, 0.7, 0.2, 1);
}
.control-menu-leave-active {
  transition:
    opacity 120ms ease-out,
    transform 120ms ease-out;
  pointer-events: none;
}
.control-menu-enter-from,
.control-menu-leave-to {
  opacity: 0;
  transform: translateY(5px);
}
.model-trigger[aria-expanded='true'] > svg:last-child,
.reasoning-trigger[aria-expanded='true'] > svg:last-child {
  transform: rotate(180deg);
}
.model-trigger > svg:last-child,
.reasoning-trigger > svg:last-child {
  transition: transform 180ms ease-out;
}
@media (prefers-reduced-motion: reduce) {
  .control-menu-enter-active,
  .control-menu-leave-active,
  .model-trigger > svg:last-child,
  .reasoning-trigger > svg:last-child {
    transition: none;
  }
  .control-menu-enter-from,
  .control-menu-leave-to {
    transform: none;
  }
}
.model-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 4px 3px 6px;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
}
.model-picker-anchor,
.reasoning-anchor {
  position: relative;
}
.model-trigger,
.reasoning-trigger {
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: 360px;
  border: 0;
  border-radius: 7px;
  background: var(--dsw-specific-input-major);
  color: inherit;
  padding: 6px 8px;
  font: inherit;
  cursor: pointer;
}
.model-trigger > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-trigger svg,
.reasoning-trigger svg {
  width: 13px;
  height: 13px;
  flex: none;
}
.reasoning-trigger {
  background: transparent;
}
.reasoning-trigger svg:first-child {
  width: 16px;
  height: 16px;
}
.model-trigger:hover,
.reasoning-trigger:hover {
  background: var(--dsw-alias-bg-layer-2);
}
.model-picker-popup {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 35;
  display: flex;
  align-items: stretch;
  max-width: calc(100vw - 50px);
  filter: drop-shadow(0 7px 15px #1b304218);
}
.provider-menu,
.model-submenu,
.reasoning-menu {
  padding: 5px;
  background: var(--dsw-alias-bg-layer-1);
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 9px;
  box-sizing: border-box;
  max-height: min(360px, 50vh);
  overflow-y: auto;
  min-width: 190px;
}
.provider-menu {
  width: 210px;
  flex: none;
}
.model-submenu {
  margin-left: -1px;
  width: max-content;
  min-width: 220px;
  max-width: 330px;
  align-self: flex-start;
}
.provider-menu > button,
.model-submenu > button,
.reasoning-menu > button {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 9px;
  min-height: 33px;
  padding: 7px 9px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--dsw-alias-text-secondary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.provider-menu > button > span,
.model-submenu > button > span,
.reasoning-menu > button > span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.provider-menu svg,
.model-submenu svg,
.reasoning-menu svg {
  width: 12px;
  height: 12px;
  flex: none;
}
.provider-menu > .hovered,
.provider-menu > button:hover,
.model-submenu > button:hover,
.reasoning-menu > button:hover {
  background: var(--dsw-specific-input-major);
  color: var(--dsw-alias-text-primary);
}
.provider-menu > button:focus-visible,
.model-submenu > button:focus-visible,
.reasoning-menu > button:focus-visible {
  outline: 2px solid var(--dsw-focus-ring);
  outline-offset: -2px;
}
.model-submenu small {
  flex: none;
  font-size: var(--dsw-text-xs);
  border: 1px solid var(--dsw-alias-border-l2);
  padding: 0 4px;
  border-radius: 5px;
  color: var(--dsw-alias-text-tertiary);
}
.menu-divider {
  height: 1px;
  background: var(--dsw-alias-border-l2);
  margin: 5px 0;
}
.provider-menu > .manage {
  color: var(--dsw-alias-text-primary);
}
.reasoning-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  min-width: 140px;
  z-index: 35;
  box-shadow: 0 7px 20px #1b304218;
}
.empty {
  font-size: var(--dsw-text-xs);
  padding: 8px;
  margin: 0;
  color: var(--dsw-alias-text-tertiary);
}
:disabled {
  opacity: 0.45;
  cursor: default;
}
@media (max-width: 700px) {
  .model-trigger {
    max-width: 260px;
  }
  .provider-menu {
    width: 160px;
    min-width: 160px;
  }
  .model-submenu {
    min-width: 160px;
    max-width: 45vw;
  }
  .model-picker-popup {
    max-width: calc(100vw - 30px);
  }
}
</style>
