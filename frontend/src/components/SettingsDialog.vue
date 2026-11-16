<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import ProviderMark from '@/components/ProviderMark.vue';
import SettingsSwitch from '@/components/SettingsSwitch.vue';
import ProviderModelList from '@/components/ProviderModelList.vue';
import ModelConfigDialog from '@/components/ModelConfigDialog.vue';
import AccountSecurity from '@/components/AccountSecurity.vue';
import ContentSwap from '@/components/ContentSwap.vue';
import { vDisclosureMotion } from '@/utils/disclosure-motion';
import '@/styles/settings-motion.css';
import { useConsent } from '@/composables/useConsent';
import { useLab } from '@/composables/useLab';
import {
  useDialogMotion,
  useDialogSizeMotion,
  useDialogViewport,
} from '@/composables/useDialogMotion';
import { opacityTransition } from '@/utils/opacity-transition';
import {
  presets,
  protocols,
  modelFamily,
  presetFor,
  endpointFor,
  profileLabel,
} from '@/utils/model-providers';
import { modelDefaults, selectedModelOptions, type ConfiguredModel } from '@/utils/model-config';
import { ApiBase } from '@/utils/api-base';
import { readableError, type ProviderConfig } from '@/services/agent';

const lab = useLab(),
  consent = useConsent(),
  dialog = ref<HTMLDialogElement | null>(null);
type Profile = ReturnType<typeof lab.providerProfile>;
const profiles = reactive<Record<string, Profile>>({});
const baselines = new Map<string, string>();
const selected = ref(lab.raw.settings.provider_id),
  newProfile = ref(false);
const draft = computed(() => profiles[selected.value]);
const preset = computed(() => presetFor(selected.value, draft.value?.settings));
const selectedEndpoint = computed(() =>
  draft.value
    ? endpointFor(preset.value, draft.value.settings.base_url, draft.value.settings.protocol)
    : undefined,
);
const protocolChoices = computed(() => {
  const base = draft.value?.settings.base_url.replace(/\/$/, '');
  const endpoint = preset.value.endpoints.find((item) => item.base_url === base);
  return Object.fromEntries(
    Object.entries(protocols).filter(
      ([key]) => !endpoint || endpoint.protocols.includes(key as keyof typeof protocols),
    ),
  );
});
const source = computed(() => selectedEndpoint.value?.source ?? preset.value.source);
const backend = ref(lab.state.backend),
  showKey = ref(false),
  status = ref(''),
  listing = ref(false);
const editing = ref<{ model: ConfiguredModel; adding: boolean } | null>(null);
const screen = ref<'overview' | 'editor'>('overview');
const pageFade = opacityTransition(180, 120);
const pages = ref<HTMLElement | null>(null);
useDialogSizeMotion(dialog, pages, () => lab.settingsOpen.value);
useDialogViewport(dialog);
function leavePage(element: Element) {
  element.setAttribute('data-page-leaving', '');
}
function enterPage(element: Element) {
  element.removeAttribute('data-page-leaving');
}
const providerMenu = ref<HTMLElement | null>(null),
  providerMenuOpen = ref(false);
const added = computed(() =>
  lab.addedProviderIds.value.map((id) => {
    const profile = lab.providerProfile(id);
    return {
      id,
      ...profile,
      preset: presetFor(id, profile.settings),
      label: profileLabel(id, profile.settings),
    };
  }),
);
function choose(id: string) {
  profiles[id] ??= lab.providerProfile(id);
  if (!baselines.has(id)) baselines.set(id, JSON.stringify(profiles[id]));
  selected.value = id;
  status.value = '';
  showKey.value = false;
  providerMenuOpen.value = false;
}
const { onNativeClose } = useDialogMotion(dialog, () => lab.settingsOpen.value, {
  beforeOpen: () => {
    screen.value = 'overview';
    resetDrafts();
  },
  afterClose: () => {
    editing.value = null;
    showKey.value = false;
    baselines.clear();
    for (const id of Object.keys(profiles)) delete profiles[id];
  },
  requestClose: () => lab.closeSettings(),
});
function close() {
  providerMenuOpen.value = false;
  lab.closeSettings();
}
function closeMenuOutside(event: PointerEvent) {
  if (event.target instanceof Node && !providerMenu.value?.contains(event.target))
    providerMenuOpen.value = false;
}
async function toggleProviderMenu() {
  providerMenuOpen.value = !providerMenuOpen.value;
  if (providerMenuOpen.value) {
    await nextTick();
    providerMenu.value?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
  }
}
function navigateProviderMenu(event: KeyboardEvent) {
  const items = [
    ...(providerMenu.value?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? []),
  ];
  if (!items.length || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const current = items.indexOf(document.activeElement as HTMLButtonElement);
  const index =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? items.length - 1
        : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
  items[index]?.focus();
}
function closeMenuOnBlur(event: FocusEvent) {
  if (!(event.relatedTarget instanceof Node) || !providerMenu.value?.contains(event.relatedTarget))
    providerMenuOpen.value = false;
}
function escapeMenu(event: KeyboardEvent) {
  if (event.key === 'Escape' && providerMenuOpen.value) {
    event.preventDefault();
    event.stopPropagation();
    providerMenuOpen.value = false;
    providerMenu.value?.querySelector('button')?.focus();
  }
}
function resetDrafts(id = lab.raw.settings.provider_id) {
  for (const name of Object.keys(profiles)) delete profiles[name];
  baselines.clear();
  newProfile.value = false;
  backend.value = lab.state.backend;
  choose(id);
}
function choosePreset(presetId: string) {
  if (!newProfile.value) return;
  const provider = presetFor(presetId);
  const id = provider.id + '-profile-' + crypto.randomUUID().replace(/-/g, '').slice(0, 12);
  for (const name of Object.keys(profiles)) delete profiles[name];
  baselines.clear();
  const initial = lab.providerProfile(id);
  profiles[id] = {
    settings: {
      ...initial.settings,
      provider_id: id,
      preset_id: provider.id,
      profile_name: '',
      provider_family: provider.family,
      base_url: provider.base_url,
      protocol: provider.protocol,
      model: provider.models[0]?.id ?? '',
      models: provider.models.map((model) =>
        modelDefaults(model.id, provider.id, provider.protocol),
      ),
      reasoning_effort: 'auto',
      enabled: false,
    },
    key: '',
    saved: false,
    clearKey: false,
  };
  selected.value = id;
  baselines.set(id, JSON.stringify(profiles[id]));
  status.value = '';
  showKey.value = false;
}
function editProvider(id?: string) {
  resetDrafts(id ?? lab.raw.settings.provider_id);
  if (!id) {
    newProfile.value = true;
    choosePreset('deepseek');
  }
  screen.value = 'editor';
}
function back() {
  if (lab.state.busy || listing.value) return;
  resetDrafts();
  screen.value = 'overview';
}
function keyChanged() {
  if (draft.value)
    draft.value.settings.enabled =
      Boolean(draft.value.key.trim()) || (draft.value.saved && !draft.value.clearKey);
}
function clearKey() {
  if (!draft.value) return;
  draft.value.key = '';
  draft.value.clearKey = true;
  draft.value.saved = false;
  keyChanged();
  showKey.value = false;
}
async function toggleProvider(id: string, enabled: boolean) {
  const trigger = document.activeElement;
  const profile = lab.providerProfile(id);
  profile.settings.enabled = enabled;
  listing.value = true;
  try {
    await lab.saveServerProvider(profile);
  } catch (error) {
    status.value = String((error as Error).message);
  } finally {
    listing.value = false;
    await nextTick();
    if (
      dialog.value?.open &&
      document.activeElement === document.body &&
      trigger instanceof HTMLElement &&
      trigger.isConnected
    )
      trigger.focus();
  }
}
async function deleteProvider(id: string) {
  listing.value = true;
  try {
    await lab.deleteServerProvider(id);
  } catch (error) {
    status.value = String((error as Error).message);
  } finally {
    listing.value = false;
  }
}
function finish() {
  if (backend.value !== lab.state.backend && !lab.setBackend(backend.value)) {
    status.value = '后端地址无效。';
    return;
  }
  if (draft.value) {
    lab.setAllowTools(draft.value.settings.allow_tools);
    lab.setDetail(draft.value.settings.detail);
  }
  close();
}
function protocolChanged() {
  if (draft.value) draft.value.settings.reasoning_effort = 'auto';
}
function chooseEndpoint(id: string) {
  const endpoint = preset.value.endpoints.find((item) => item.id === id);
  if (!draft.value || !endpoint) return;
  draft.value.settings.base_url = endpoint.base_url;
  if (!endpoint.protocols.includes(draft.value.settings.protocol))
    draft.value.settings.protocol = endpoint.protocols[0]!;
  draft.value.settings.reasoning_effort = 'auto';
}
function toggleModel(id: string, enabled: boolean) {
  const settings = draft.value!.settings,
    model = settings.models.find((m) => m.id === id);
  if (!model) return;
  model.enabled = enabled;
  if (!enabled && settings.model === id)
    settings.model = settings.models.find((m) => m.enabled)?.id ?? '';
  if (enabled && !settings.model) settings.model = id;
}
function modelSaved(model: ConfiguredModel) {
  const settings = draft.value!.settings,
    old = editing.value!;
  if (old.adding) {
    settings.models.push(model);
    settings.model = model.id;
  } else {
    const index = settings.models.findIndex((m) => m.id === old.model.id);
    if (index >= 0) settings.models[index] = model;
    if (settings.model === old.model.id) settings.model = model.id;
  }
  settings.reasoning_effort = 'auto';
  editing.value = null;
  status.value = '模型配置已加入草稿，保存后生效。';
}
function config(model?: ConfiguredModel): ProviderConfig {
  const profile = draft.value!,
    settings = profile.settings,
    id = model?.id ?? settings.model;
  const chosen = model ?? settings.models.find((m) => m.id === id);
  return {
    base_url: settings.base_url.trim(),
    model: id,
    api_key: profile.key.trim(),
    allow_tools: settings.allow_tools,
    ...(!profile.key.trim() && profile.saved && !profile.clearKey
      ? { credential_id: settings.provider_id }
      : {}),
    protocol: settings.protocol,
    provider_family: modelFamily(settings.provider_id, id, settings.preset_id),
    reasoning_effort: 'auto',
    model_options: selectedModelOptions(chosen),
  };
}
async function test(model?: ConfiguredModel) {
  status.value = '连接中…';
  await lab.testConnection(config(model));
  status.value = lab.state.status;
}
async function fetchModels() {
  if (!consent.agreed.value) {
    close();
    consent.revoke();
    return;
  }
  const provider = config();
  if (!provider.base_url || (!provider.api_key && !provider.credential_id)) {
    status.value = '请先填写上游地址和 API Key。';
    return;
  }
  listing.value = true;
  status.value = '正在获取模型目录…';
  try {
    const response = await ApiBase.request('/api/ai/models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(provider),
      signal: AbortSignal.timeout(25000),
    });
    if (!response.ok) throw new Error(await readableError(response));
    const result = (await response.json()) as { models: Array<{ id: string }> };
    const models = draft.value!.settings.models;
    let added = 0;
    for (const item of result.models) {
      if (!models.some((m) => m.id === item.id) && models.length < 100) {
        models.push(modelDefaults(item.id, selected.value, provider.protocol!));
        added++;
      }
    }
    if (!draft.value!.settings.model)
      draft.value!.settings.model = models.find((m) => m.enabled)?.id ?? '';
    status.value = `获取完成，新增 ${added} 个模型；已有配置保留。`;
  } catch (error) {
    const message = String(error instanceof Error ? error.message : error);
    status.value = provider.api_key ? message.split(provider.api_key).join('[已隐藏]') : message;
  } finally {
    listing.value = false;
  }
}
async function save() {
  status.value = '';
  const changed = Object.entries(profiles)
    .filter(
      ([id, profile]) => id === selected.value || JSON.stringify(profile) !== baselines.get(id),
    )
    .map(([, profile]) => profile);
  for (const profile of changed) {
    if (!profile.settings.enabled) continue;
    try {
      const url = new URL(profile.settings.base_url);
      if (
        !['http:', 'https:'].includes(url.protocol) ||
        url.username ||
        url.password ||
        url.search ||
        url.hash
      )
        throw new Error();
    } catch {
      status.value = '请为已编辑的上游填写有效的 http(s) API 地址。';
      return;
    }
  }
  if (backend.value !== lab.state.backend && !lab.setBackend(backend.value)) {
    status.value = '后端地址无效。';
    return;
  }
  listing.value = true;
  try {
    for (const profile of changed) {
      if (!profile.key.trim() && (!profile.saved || profile.clearKey))
        profile.settings.enabled = false;
      await lab.saveServerProvider(profile);
    }
    lab.selectProvider(selected.value);
    screen.value = 'overview';
  } catch (error) {
    status.value = String((error as Error).message);
  } finally {
    listing.value = false;
    if (screen.value === 'overview') resetDrafts();
  }
}
function reset() {
  profiles[selected.value] = {
    ...lab.providerProfile(selected.value),
    settings: {
      ...lab.providerProfile(selected.value).settings,
      base_url: preset.value.base_url,
      protocol: preset.value.protocol,
      models: preset.value.models.map((m) =>
        modelDefaults(m.id, preset.value.id, preset.value.protocol),
      ),
      model: preset.value.models[0]?.id ?? '',
      reasoning_effort: 'auto',
      enabled: Boolean(draft.value?.key.trim()),
    },
  };
  status.value = '已恢复该供应商的默认配置，保存后生效。';
}
</script>

<template>
  <dialog
    ref="dialog"
    class="settings-dialog"
    aria-labelledby="settings-title"
    @cancel.prevent="close"
    @close="onNativeClose"
    @pointerdown="closeMenuOutside"
    @keydown.capture="escapeMenu"
  >
    <form
      class="settings-shell"
      @submit.prevent="screen === 'overview' ? finish() : save()"
      v-if="draft"
    >
      <header class="dialog-header"
        ><div><h2 id="settings-title">模型与接口设置</h2><p>配置供应商、接入方案与可用模型</p></div
        ><button type="button" class="icon-button" aria-label="关闭" @click="close"
          ><UiIcon name="close" /></button
      ></header>
      <div class="settings-scroll">
        <div ref="pages" class="settings-pages">
          <Transition
            :css="false"
            @before-enter="enterPage"
            @before-leave="leavePage"
            @leave-cancelled="enterPage"
            @enter="pageFade.enter"
            @leave="pageFade.leave"
          >
            <section
              v-show="screen === 'overview'"
              :inert="screen !== 'overview'"
              class="provider-overview"
              data-role="provider-overview"
            >
              <p class="intro"
                >添加供应商配置并填写 API
                密钥，启用后即可选择模型。同一家可添加多套配置，分别使用不同套餐或密钥。</p
              >
              <TransitionGroup
                v-memo="[added, lab.state.busy, listing]"
                name="settings-list"
                tag="div"
                class="provider-list"
              >
                <div
                  v-for="item in added"
                  :key="item.id"
                  class="added-provider"
                  :data-added-provider="item.id"
                >
                  <ProviderMark :id="item.preset.id" /><div class="added-identity"
                    ><strong>{{ item.label }}</strong
                    ><span class="provider-state" :data-ready="lab.providerReady(item.id)"
                      ><i></i
                      >{{
                        !item.key.trim() && !item.saved
                          ? '未配置密钥'
                          : lab.providerReady(item.id)
                            ? '已启用'
                            : '已关闭'
                      }}</span
                    ></div
                  >
                  <SettingsSwitch
                    :model-value="lab.providerReady(item.id)"
                    :label="`启用提供商 ${item.label}`"
                    :disabled="lab.state.busy || listing || (!item.key.trim() && !item.saved)"
                    @update:model-value="toggleProvider(item.id, $event)"
                  />
                  <button
                    type="button"
                    class="secondary"
                    :disabled="lab.state.busy"
                    :data-edit-provider="item.id"
                    @click="editProvider(item.id)"
                    >编辑</button
                  >
                  <button
                    type="button"
                    class="icon-button delete-provider"
                    :aria-label="`删除提供商 ${item.label}`"
                    :disabled="lab.state.busy || listing"
                    @click="deleteProvider(item.id)"
                    ><UiIcon name="trash"
                  /></button>
                </div>
              </TransitionGroup>
              <p v-if="!added.length" class="empty-providers">尚未添加提供商</p>
              <button
                type="button"
                class="add-provider"
                data-action="add-provider"
                :disabled="lab.state.busy"
                @click="editProvider()"
                ><UiIcon name="plus" />添加模型提供商</button
              >
            </section>
          </Transition>
          <Transition
            :css="false"
            @before-enter="enterPage"
            @before-leave="leavePage"
            @leave-cancelled="enterPage"
            @enter="pageFade.enter"
            @leave="pageFade.leave"
          >
            <section
              v-show="screen === 'editor'"
              :inert="screen !== 'editor'"
              class="provider-editor"
              data-role="provider-editor"
            >
              <button
                type="button"
                class="back-providers"
                :disabled="lab.state.busy || listing"
                @click="back"
                ><UiIcon name="chevron-left" />提供商列表</button
              >
              <p class="intro"
                >选择供应商与接入地址，再配置密钥和模型。已有配置保持绑定的供应商；使用其他供应商时可另行添加。</p
              >
              <fieldset :disabled="lab.state.busy || listing" class="provider-fields">
                <label class="field"
                  >供应商<select
                    id="ai-provider"
                    :value="preset.id"
                    :disabled="!newProfile"
                    @change="choosePreset(($event.target as HTMLSelectElement).value)"
                    ><option v-for="item in presets" :key="item.id" :value="item.id">{{
                      item.label
                    }}</option></select
                  ></label
                >
                <label class="field"
                  >配置名称（可选）<input
                    id="ai-profile-name"
                    v-model="draft.settings.profile_name"
                    maxlength="80"
                    :placeholder="`${preset.label} · 例如个人套餐、按量账户`"
                /></label>
                <ContentSwap>
                  <section :key="selected" class="provider-card">
                    <div class="provider-heading"
                      ><ProviderMark :id="preset.id" /><strong>{{ preset.label }}</strong
                      ><SettingsSwitch
                        v-model="draft.settings.enabled"
                        label="启用当前供应商配置"
                        :disabled="!draft.key.trim() && !draft.saved"
                      />
                      <div ref="providerMenu" class="provider-menu" @focusout="closeMenuOnBlur"
                        ><button
                          type="button"
                          class="icon-button"
                          aria-label="更多平台操作"
                          aria-haspopup="menu"
                          aria-controls="provider-operations"
                          :aria-expanded="providerMenuOpen"
                          @click="toggleProviderMenu"
                          @keydown.down.prevent="toggleProviderMenu"
                          ><UiIcon name="more" /></button
                        ><Transition name="settings-popover"
                          ><div
                            v-if="providerMenuOpen"
                            id="provider-operations"
                            role="menu"
                            aria-label="平台操作"
                            @keydown="navigateProviderMenu"
                            ><button
                              type="button"
                              role="menuitem"
                              @click="
                                reset();
                                providerMenuOpen = false;
                              "
                              >恢复平台默认配置</button
                            ><button
                              type="button"
                              role="menuitem"
                              @click="
                                clearKey();
                                providerMenuOpen = false;
                              "
                              >清除已保存密钥</button
                            ></div
                          ></Transition
                        ></div
                      ></div
                    >
                    <label v-if="preset.endpoints.length" class="field"
                      >接入地址 / 套餐<select
                        id="ai-endpoint"
                        :value="selectedEndpoint?.id ?? 'manual'"
                        @change="chooseEndpoint(($event.target as HTMLSelectElement).value)"
                        ><option
                          v-for="endpoint in preset.endpoints"
                          :key="endpoint.id"
                          :value="endpoint.id"
                          >{{ endpoint.label }} · {{ endpoint.plans.join(' / ') }}</option
                        ><option value="manual" disabled>自定义地址（在下方填写）</option></select
                      ></label
                    >
                    <div class="connection-grid"
                      ><label class="field"
                        >Base URL<input
                          id="ai-base-url"
                          v-model="draft.settings.base_url"
                          type="url"
                          autocomplete="off"
                          placeholder="https://api.example.com/v1" /></label
                      ><label class="field"
                        >API 格式<select
                          id="ai-protocol"
                          v-model="draft.settings.protocol"
                          @change="protocolChanged"
                          ><option
                            v-for="(label, key) in protocolChoices"
                            :key="key"
                            :value="key"
                            >{{ label }}</option
                          ></select
                        ></label
                      ></div
                    >
                    <label class="field"
                      ><span class="key-label"
                        >API Key<a
                          v-if="source"
                          :href="source"
                          target="_blank"
                          rel="noopener noreferrer"
                          >官方接入文档<UiIcon name="arrow-up-right" /></a></span
                      ><span class="key-field"
                        ><input
                          id="ai-api-key"
                          v-model="draft.key"
                          :type="showKey ? 'text' : 'password'"
                          autocomplete="off"
                          placeholder="输入 API Key"
                          @input="keyChanged" /><button
                          type="button"
                          class="icon-button"
                          :aria-label="showKey ? '隐藏 API Key' : '显示 API Key'"
                          @click="showKey = !showKey"
                          ><UiIcon name="eye" /></button></span
                    ></label>
                    <p class="platform-hint">{{
                      draft.saved && !draft.clearKey
                        ? '服务器已加密保存密钥，留空保留原密钥；更换地址或协议需重新填写。'
                        : '未保存密钥；填写后将在服务器加密保存。'
                    }}</p>
                    <p v-if="selectedEndpoint?.note" class="platform-hint">{{
                      selectedEndpoint.note
                    }}</p>
                    <ProviderModelList
                      :models="draft.settings.models"
                      :selected="draft.settings.model"
                      :disabled="lab.state.busy || listing"
                      :loading="listing"
                      @add="
                        editing = {
                          model: modelDefaults('', selected, draft.settings.protocol),
                          adding: true,
                        }
                      "
                      @edit="editing = { model: $event, adding: false }"
                      @toggle="toggleModel"
                      @select="
                        draft.settings.model = $event;
                        draft.settings.reasoning_effort = 'auto';
                      "
                      @test="test"
                      @fetch="fetchModels"
                    />
                  </section>
                </ContentSwap>
              </fieldset>
            </section>
          </Transition>
        </div>
        <details v-disclosure-motion class="general-settings"
          ><summary>通用设置</summary
          ><label class="field"
            >后端地址<input
              id="ai-backend-url"
              v-model="backend"
              type="url"
              :disabled="lab.state.busy || listing" /></label
          ><label class="checkbox-row"
            ><input
              id="ai-tools-enabled"
              type="checkbox"
              v-model="draft.settings.allow_tools"
            />允许工具实验</label
          ><div class="detail-row"
            ><span>回复详略</span
            ><button
              v-for="level in ['concise', 'normal', 'detailed'] as const"
              :key="level"
              type="button"
              :data-active="draft.settings.detail === level"
              @click="draft.settings.detail = level"
              >{{ { concise: '简洁', normal: '正常', detailed: '详细' }[level] }}</button
            ><button
              type="button"
              class="consent-link"
              @click="
                close();
                consent.revoke();
              "
              >数据使用说明</button
            ></div
          ></details
        >
        <AccountSecurity /><p class="privacy-note"
          >API Key 按账号在服务器加密保存，不向浏览器返回完整密钥。</p
        >
        <output id="ai-test-status" role="status">{{ status }}</output>
      </div>
      <footer class="dialog-footer"
        ><template v-if="screen === 'editor'"
          ><button
            type="button"
            class="secondary"
            id="ai-test"
            :disabled="
              lab.state.busy ||
              listing ||
              !draft.settings.model ||
              (!draft.key.trim() && !draft.saved)
            "
            @click="test()"
            >测试连接</button
          ><button
            type="button"
            class="secondary cancel"
            :disabled="lab.state.busy || listing"
            @click="back"
            >取消</button
          ><button
            type="submit"
            class="primary"
            data-action="save-provider-settings"
            :disabled="lab.state.busy || listing"
            >保存</button
          ></template
        ><button
          v-else
          type="submit"
          class="primary"
          :disabled="lab.state.busy || listing"
          data-action="finish-provider-settings"
          >完成</button
        ></footer
      >
    </form>
  </dialog>
  <ModelConfigDialog
    v-if="editing && draft"
    :model="editing.model"
    :adding="editing.adding"
    :upstream="selected"
    :protocol="draft.settings.protocol"
    :existing="draft.settings.models.map((m) => m.id)"
    @save="modelSaved"
    @close="editing = null"
  />
</template>

<style scoped>
.settings-dialog::backdrop {
  transition: background-color 180ms ease-out;
}
.settings-dialog[data-motion='closing']::backdrop {
  background: transparent;
}
.settings-dialog[data-motion='closing'] {
  pointer-events: none;
}
@starting-style {
  dialog.settings-dialog::backdrop {
    background: transparent;
  }
}
@media (prefers-reduced-motion: reduce) {
  .settings-dialog::backdrop {
    transition: none;
  }
}
.provider-overview {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.provider-overview .intro {
  margin: 0 0 5px;
}
.added-provider {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  min-width: 0;
}
.added-identity {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.added-identity strong {
  font-size: var(--dsw-text-row);
  font-weight: 600;
}
.provider-state {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
}
.provider-state i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #c0846d;
}
.provider-state[data-ready='true'] {
  color: var(--dsw-feedback-success-text);
}
.provider-state[data-ready='true'] i {
  background: currentColor;
}
.added-provider .secondary {
  padding: 5px 10px;
  font-size: var(--dsw-text-xs);
}
.delete-provider:hover {
  color: #cc5d53;
}
.add-provider {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 7px;
  border: 1px dashed var(--dsw-alias-border-l2);
  border-radius: 10px;
  padding: 12px;
  background: none;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-sm);
  cursor: pointer;
}
.add-provider:hover {
  background: var(--dsw-specific-input-major);
}
.add-provider svg {
  width: 15px;
  height: 15px;
}
.empty-providers {
  margin: 0;
  text-align: center;
  padding: 22px;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-sm);
}
.back-providers {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: none;
  padding: 0 0 12px;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
  cursor: pointer;
}
.back-providers svg {
  width: 12px;
  height: 12px;
}
.settings-dialog {
  border: 1px solid var(--dsw-alias-border-l2);
  padding: 0;
  border-radius: 16px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  width: min(700px, 94vw);
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 18px 70px #1d2d4826;
}
.settings-dialog::backdrop {
  background: #18243845;
}
.settings-shell {
  display: flex;
  flex-direction: column;
  max-height: calc(90vh - 2px);
  min-height: 0;
  overflow: hidden;
  border-radius: inherit;
}
.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px var(--settings-inset) 12px;
  border-bottom: 1px solid var(--dsw-alias-border-l2);
}
h2 {
  font-size: var(--dsw-text-lg);
  font-weight: 600;
  margin: 0;
}
.dialog-header p {
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
  margin: 5px 0 0;
}
.icon-button {
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border: 0;
  border-radius: 6px;
  background: none;
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.icon-button svg {
  width: 15px;
  height: 15px;
}
.icon-button:hover {
  background: var(--dsw-specific-input-major);
  color: var(--dsw-alias-text-primary);
}
.settings-scroll {
  overflow: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  padding: 16px var(--settings-inset) 10px;
  min-height: 0;
}
.intro {
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
  line-height: 1.8;
  margin: 10px 0 14px;
}
.provider-fields {
  padding: 0;
  margin: 0;
  border: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
}
.field input,
.field select {
  box-sizing: border-box;
  min-width: 0;
  width: 100%;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  padding: 7px 10px;
  line-height: 1.6;
  font: inherit;
  font-size: var(--dsw-text-sm);
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
}
#ai-provider {
  max-width: 340px;
}
.provider-card {
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.provider-heading {
  display: flex;
  align-items: center;
  gap: 9px;
}
.provider-heading strong {
  font-size: var(--dsw-text-title);
  font-weight: 600;
  flex: 1;
  min-width: 0;
}
.connection-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 12px;
}
.key-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.key-label a {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  font-size: var(--dsw-text-xs);
  color: var(--settings-action-text);
  text-decoration: none;
}
.key-label svg {
  width: 12px;
  height: 12px;
}
.key-field {
  position: relative;
  display: block;
}
.key-field input {
  padding-right: 42px;
}
.key-field .icon-button {
  position: absolute;
  top: 5px;
  right: 7px;
}
.platform-hint,
.privacy-note {
  margin: 0;
  color: var(--dsw-alias-text-secondary);
  font-size: var(--dsw-text-xs);
  line-height: 1.7;
}
.platform-hint {
  margin-top: -10px;
}
.privacy-note {
  margin: 13px 0 0;
}
.provider-menu {
  position: relative;
}
.provider-menu summary {
  list-style: none;
  cursor: pointer;
  color: var(--dsw-alias-text-secondary);
  padding: 3px;
}
.provider-menu summary::-webkit-details-marker {
  display: none;
}
.provider-menu svg {
  width: 17px;
  height: 17px;
}
.provider-menu > div {
  position: absolute;
  right: 0;
  top: 100%;
  z-index: 3;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  padding: 5px;
  background: var(--dsw-alias-bg-layer-1);
  box-shadow: 0 8px 20px #14263b16;
  min-width: 150px;
}
.provider-menu button {
  display: block;
  width: 100%;
  border: 0;
  padding: 8px;
  background: none;
  text-align: left;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
  cursor: pointer;
}
.provider-menu button:hover {
  background: var(--dsw-specific-input-major);
}
.general-settings {
  margin-top: 16px;
  border-top: 1px solid var(--dsw-alias-border-l2);
  padding-top: 15px;
}
.general-settings summary {
  cursor: pointer;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
  margin-bottom: 12px;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 14px 0;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
}
.detail-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--dsw-text-xs);
  color: var(--dsw-alias-text-secondary);
}
.detail-row button {
  border: 0;
  border-radius: 5px;
  background: none;
  color: inherit;
  padding: 5px 7px;
  font: inherit;
  cursor: pointer;
}
.detail-row [data-active='true'] {
  background: var(--dsw-selection-surface);
  color: var(--settings-action-text);
}
.detail-row .consent-link {
  margin-left: auto;
  color: var(--settings-action-text);
}
.dialog-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
  flex: none;
  padding: 12px var(--settings-inset);
  border-top: 1px solid var(--dsw-alias-border-l2);
}
output {
  display: block;
  margin-top: 12px;
  min-width: 0;
  flex: 1;
  font-size: var(--dsw-text-xs);
  line-height: 1.6;
  overflow-wrap: anywhere;
  color: var(--dsw-alias-text-secondary);
}
output:empty {
  display: none;
}
:disabled {
  opacity: 0.45;
  cursor: default;
}
@media (max-width: 560px) {
  .settings-scroll {
    padding: 16px;
  }
  .dialog-header,
  .dialog-footer {
    padding: 15px 16px;
  }
  .provider-card {
    padding: 12px;
  }
  .connection-grid {
    grid-template-columns: 1fr;
  }
}
</style>
<style scoped>
.provider-list {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.added-provider {
  box-sizing: border-box;
}
.provider-menu > .icon-button {
  display: grid;
  width: 27px;
  height: 27px;
  padding: 0;
  text-align: center;
}
.provider-menu > div button {
  border-radius: 5px;
}
.settings-dialog {
  margin-block: min(5dvh, 40px) auto;
}
.dialog-header {
  flex: none;
}
.settings-scroll {
  scrollbar-gutter: stable;
  contain: layout style;
}
.settings-pages {
  position: relative;
  display: grid;
  align-items: start;
}
.settings-pages > section {
  grid-area: 1/1;
  min-width: 0;
}
.settings-pages > [data-page-leaving] {
  position: absolute;
  inset: 0 0 auto;
  pointer-events: none;
}
.settings-dialog[data-resizing] .settings-shell {
  height: 100%;
  max-height: 100%;
}
.settings-dialog[data-resizing] .settings-scroll {
  flex: 1;
}

/* Unified settings surface */
.settings-dialog {
  width: min(760px, 94vw);
  border-color: #e3eaf5;
  border-radius: 22px;
  box-shadow: 0 30px 90px -30px rgb(15 30 60 / 0.5);
}
.settings-dialog::backdrop {
  background: rgb(11 21 48 / 0.45);
  backdrop-filter: blur(4px);
}
.dialog-header {
  padding: 20px 26px 15px;
  border-bottom-color: #edf1f8;
}
h2 {
  color: #13203a;
  font-size: 18px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.dialog-header p {
  color: #7b879c;
  font-size: 10.5px;
}
.icon-button {
  width: 30px;
  height: 30px;
  border: 1px solid #e6ecf6;
  border-radius: 8px;
  background: #f8faff;
  color: #4f5d73;
}
.icon-button:hover {
  border-color: #c9d9f8;
  background: #f4f8ff;
  color: #14213a;
}
.settings-scroll {
  padding: 16px 26px 12px;
}
.intro {
  color: #647086;
}
.provider-card {
  padding: 15px;
  border-color: #e6ecf6;
  border-radius: 14px;
  background: #fbfcff;
}
.field input,
.field select {
  min-height: 40px;
  border-color: #e2e9f4;
  border-radius: 10px;
  background: #ffffff;
  font-size: 11.5px;
}
.field input:focus,
.field select:focus {
  border-color: #9db5ee;
  box-shadow: 0 0 0 3px rgb(79 124 255 / 0.09);
  outline: none;
}
.add-provider {
  padding: 14px;
  border-color: #cfdcf1;
  border-radius: 12px;
  background: #fbfcff;
  color: #4f5d73;
  font-size: 11.5px;
}
.add-provider:hover {
  border-color: #9db5ee;
  background: #f4f8ff;
  color: #14213a;
}
.empty-providers {
  color: #8a96ab;
  font-size: 11.5px;
}
.dialog-footer {
  padding: 13px 26px;
  border-top-color: #edf1f8;
}
.dialog-footer .primary {
  padding: 8px 15px;
  border: 0;
  border-radius: 10px;
  border: 1px solid #d7e3fb;
  background: #eef3ff;
  color: #274a9a;
  font-size: 11.5px;
  font-weight: 600;
  box-shadow: 0 10px 22px -18px rgb(11 25 58 / 0.9);
}
.dialog-footer .secondary {
  border-radius: 9px;
  border-color: #e5ebf5;
  background: #ffffff;
  color: #4f5d73;
}
@media (max-width: 560px) {
  .settings-dialog {
    width: calc(100vw - 20px);
    border-radius: 18px;
  }
  .settings-scroll {
    padding: 14px 16px;
  }
  .dialog-header,
  .dialog-footer {
    padding: 15px 16px;
  }
}
</style>
