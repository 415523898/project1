import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { ApiBase } from '@/utils/api-base'
import { modelFamily, validProfileId } from '@/utils/model-providers'
import { availableEfforts, selectedModelOptions } from '@/utils/model-config'
import { providerApi } from '@/services/providers'
import { connectionError, type ProviderConfig } from '@/services/agent'
import { useConsent } from '@/composables/useConsent'
import type { DetailLevel } from '@/types'
import type { LabState, StatusTone } from './state'
import {
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  SETTINGS_KEY,
  defaultSettings,
  profileSettings,
  type StoredSettings,
} from './settings'

type ProviderState = Pick<
  LabState,
  'settings' | 'apiKey' | 'user' | 'authExpired' | 'busy' | 'connected'
>
interface ProviderActions {
  setStatus(text: string, tone?: StatusTone): void
  openSettings(): void
  closeSettings(): void
}

// Called once inside the lab store scope. This owns configuration resources,
// but settings/apiKey remain the exact objects exposed by the stable facade.
export function createProviderSettings(state: ProviderState, actions: ProviderActions) {
  const { setStatus, openSettings, closeSettings } = actions
  function saveSettings(): void {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings))
    } catch {
      // Keep in-memory preferences when browser storage is unavailable.
    }
  }

  // Only non-secret preferences are persisted. Every provider has a separate in-memory key.
  const providerKeys = reactive(new Map<string, string>())
  const savedCredentials = reactive<Record<string, boolean>>({})
  const vaultOwner = ref('')
  const providerLoading = ref(false),
    providerLoadError = ref('')
  let credentialEpoch = 0,
    providerSequence = 0
  let disposed = false
  interface ProviderRequest {
    owner: string
    backend: string
    controller: AbortController
    promise: Promise<void>
    timeout?: ReturnType<typeof setTimeout>
  }
  let providerRequest: ProviderRequest | null = null
  onScopeDispose(() => {
    disposed = true
    credentialEpoch++
    invalidateProviderLoad()
  })
  const providerProfiles = reactive<Record<string, StoredSettings>>({})
  try {
    const saved = JSON.parse(localStorage.getItem('forest-provider-profiles-v1') ?? '{}')
    for (const [id, item] of Object.entries(saved)) {
      if (!validProfileId(id) || !item || typeof item !== 'object') continue
      const value = item as StoredSettings
      providerProfiles[id] = profileSettings(id, value)
    }
  } catch {
    /* Ignore malformed local preferences. */
  }
  const addedProviderIds = ref<string[]>([])
  try {
    const raw = localStorage.getItem('forest-added-providers-v1')
    const ids = raw
      ? JSON.parse(raw)
      : [
          ...Object.keys(providerProfiles),
          ...(localStorage.getItem(SETTINGS_KEY) ? [state.settings.provider_id] : []),
        ]
    if (Array.isArray(ids)) addedProviderIds.value = [...new Set(ids.filter(validProfileId))]
  } catch {
    /* An empty provider list is safe when preferences are malformed. */
  }
  function persistProviders() {
    try {
      localStorage.setItem('forest-added-providers-v1', JSON.stringify(addedProviderIds.value))
      localStorage.setItem('forest-provider-profiles-v1', JSON.stringify(providerProfiles))
    } catch {
      /* Storage is optional. */
    }
  }
  function providerConfigured(id: string, profile: StoredSettings | undefined): boolean {
    const key = id === state.settings.provider_id ? state.apiKey : providerKeys.get(id)
    return (
      !!profile &&
      profile.enabled !== false &&
      Boolean(profile.base_url.trim()) &&
      profile.models.some((model) => model.enabled) &&
      (Boolean(key?.trim()) || hasSavedCredential(id))
    )
  }
  function providerReady(id: string): boolean {
    return (
      addedProviderIds.value.includes(id) &&
      providerConfigured(
        id,
        id === state.settings.provider_id ? state.settings : providerProfiles[id],
      )
    )
  }
  function hasSavedCredential(id = state.settings.provider_id) {
    return vaultOwner.value === state.user && Boolean(state.user) && savedCredentials[id] === true
  }
  function keyAvailable(id = state.settings.provider_id) {
    const typed = id === state.settings.provider_id ? state.apiKey : providerKeys.get(id)
    return Boolean(typed?.trim()) || hasSavedCredential(id)
  }
  function invalidateProviderLoad() {
    providerSequence++
    if (providerRequest) {
      clearTimeout(providerRequest.timeout)
      providerRequest.controller.abort()
    }
    providerRequest = null
    providerLoading.value = false
    providerLoadError.value = ''
  }
  function rememberedModel() {
    try {
      const value = JSON.parse(localStorage.getItem('forest-account-models-v1') ?? '{}')[
        JSON.stringify([ApiBase.get(), state.user])
      ]
      return value && validProfileId(value.provider) && typeof value.model === 'string'
        ? (value as { provider: string; model: string })
        : undefined
    } catch {
      return undefined
    }
  }
  function rememberModel() {
    if (!state.user || vaultOwner.value !== state.user || providerLoading.value) return
    try {
      const saved = JSON.parse(localStorage.getItem('forest-account-models-v1') ?? '{}')
      saved[JSON.stringify([ApiBase.get(), state.user])] = {
        provider: state.settings.provider_id,
        model: state.settings.model,
      }
      localStorage.setItem('forest-account-models-v1', JSON.stringify(saved))
    } catch {
      /* Non-secret selection persistence is optional. */
    }
  }
  function clearCredentials() {
    credentialEpoch++
    invalidateProviderLoad()
    providerKeys.clear()
    state.apiKey = ''
    for (const id of Object.keys(savedCredentials)) delete savedCredentials[id]
    vaultOwner.value = ''
    for (const id of Object.keys(providerProfiles)) delete providerProfiles[id]
    addedProviderIds.value = []
    Object.assign(state.settings, defaultSettings())
    persistProviders()
  }
  async function refreshProviders() {
    if (disposed || !state.user || state.authExpired) return
    const owner = state.user,
      backend = ApiBase.get(),
      epoch = credentialEpoch
    if (providerRequest?.owner === owner && providerRequest.backend === backend)
      return providerRequest.promise
    const ticket = ++providerSequence,
      wasLoaded = vaultOwner.value === owner
    const current = () =>
      ticket === providerSequence &&
      epoch === credentialEpoch &&
      state.user === owner &&
      ApiBase.get() === backend &&
      !state.authExpired
    providerLoading.value = true
    providerLoadError.value = ''
    const request: ProviderRequest = {
      owner,
      backend,
      controller: new AbortController(),
      promise: Promise.resolve(),
    }
    providerRequest = request
    request.timeout = setTimeout(() => request.controller.abort(), 15000)
    request.promise = (async () => {
      try {
        const result = await providerApi.list(request.controller.signal)
        if (!current()) return
        if (!Array.isArray(result.providers)) throw new Error('模型配置响应无效，请重试读取。')
        const preferred = wasLoaded
          ? { provider: state.settings.provider_id, model: state.settings.model }
          : rememberedModel()
        const manual = addedProviderIds.value.filter((id) =>
          Boolean(
            (id === state.settings.provider_id ? state.apiKey : providerKeys.get(id))?.trim(),
          ),
        )
        for (const id of Object.keys(savedCredentials)) delete savedCredentials[id]
        for (const id of Object.keys(providerProfiles))
          if (!manual.includes(id)) delete providerProfiles[id]
        addedProviderIds.value = [...manual]
        vaultOwner.value = owner
        for (const row of result.providers) {
          if (!validProfileId(row.id)) continue
          const value = profileSettings(row.id, row.settings)
          if (!value.models.some((model) => model.id === value.model && model.enabled))
            value.model = value.models.find((model) => model.enabled)?.id ?? value.model
          if (!manual.includes(row.id)) providerProfiles[row.id] = value
          savedCredentials[row.id] = row.has_key
          if (!addedProviderIds.value.includes(row.id)) addedProviderIds.value.push(row.id)
        }
        const usable = (id: string | undefined) =>
          !!id &&
          providerConfigured(
            id,
            providerProfiles[id] ??
              (state.settings.provider_id === id ? state.settings : undefined),
          )
        const chosen =
          [preferred?.provider, state.settings.provider_id, ...addedProviderIds.value].find(
            usable,
          ) ??
          (preferred?.provider && providerProfiles[preferred.provider]
            ? preferred.provider
            : addedProviderIds.value[0])
        if (chosen) {
          const settings = providerProfiles[chosen] ?? state.settings
          const key =
            chosen === state.settings.provider_id ? state.apiKey : (providerKeys.get(chosen) ?? '')
          if (
            preferred?.provider === chosen &&
            settings.models.some((model) => model.id === preferred.model && model.enabled)
          )
            settings.model = preferred.model
          Object.assign(state.settings, JSON.parse(JSON.stringify(settings)))
          state.apiKey = key
          state.connected = false
        }
        persistProviders()
      } catch (error) {
        if (current()) {
          providerLoadError.value = connectionError(error)
          setStatus('读取账号模型配置失败：' + providerLoadError.value, 'error')
        }
      } finally {
        clearTimeout(request.timeout)
        if (ticket === providerSequence) {
          providerLoading.value = false
          providerRequest = null
          if (current()) rememberModel()
        }
      }
    })()
    return request.promise
  }
  async function saveServerProvider(profile: {
    settings: StoredSettings
    key: string
    saved?: boolean
    clearKey?: boolean
  }) {
    if (!state.user || state.authExpired) throw new Error('请先登录后保存服务器密钥。')
    const owner = state.user,
      backend = ApiBase.get(),
      epoch = credentialEpoch
    const result = await providerApi.save(
      profile.settings.provider_id,
      profile.settings,
      profile.clearKey ? '' : profile.key.trim() || undefined,
    )
    if (state.user !== owner || backend !== ApiBase.get() || epoch !== credentialEpoch)
      throw new Error('账号或后端已变化，请重新打开设置。')
    invalidateProviderLoad()
    const clean = { settings: result.settings as unknown as StoredSettings, key: '' }
    savedCredentials[result.id] = result.has_key
    vaultOwner.value = owner
    applyProviderProfiles([clean], result.id)
    state.apiKey = ''
    providerKeys.delete(result.id)
  }
  async function deleteServerProvider(id: string) {
    const owner = state.user,
      backend = ApiBase.get(),
      epoch = credentialEpoch
    if (hasSavedCredential(id) || vaultOwner.value === state.user) await providerApi.remove(id)
    if (state.user !== owner || backend !== ApiBase.get() || epoch !== credentialEpoch) return
    invalidateProviderLoad()
    delete savedCredentials[id]
    removeProvider(id)
  }
  watch(
    () => state.settings,
    () => {
      saveSettings()
      providerProfiles[state.settings.provider_id] = { ...state.settings }
      persistProviders()
    },
    { deep: true },
  )
  watch(
    () => [state.settings.provider_id, state.settings.model],
    () => {
      state.settings.provider_family = modelFamily(
        state.settings.provider_id,
        state.settings.model,
        state.settings.preset_id,
      )
      if (
        !availableEfforts(
          state.settings.provider_id,
          state.settings.protocol,
          state.settings.model,
          state.settings.models.find((m) => m.id === state.settings.model),
          state.settings.preset_id,
        ).includes(state.settings.reasoning_effort)
      )
        state.settings.reasoning_effort = 'auto'
      rememberModel()
    },
  )
  function selectProvider(id: string): void {
    if (state.busy) return
    if (!validProfileId(id)) return
    providerKeys.set(state.settings.provider_id, state.apiKey)
    providerProfiles[state.settings.provider_id] = { ...state.settings }
    const saved = providerProfiles[id]
    Object.assign(state.settings, saved ?? profileSettings(id))
    if (
      !availableEfforts(
        id,
        state.settings.protocol,
        state.settings.model,
        state.settings.models.find((m) => m.id === state.settings.model),
        state.settings.preset_id,
      ).includes(state.settings.reasoning_effort)
    )
      state.settings.reasoning_effort = 'auto'
    state.apiKey = providerKeys.get(id) ?? ''
    state.connected = false
  }
  function selectModel(model: string): void {
    state.settings.model = model
    state.settings.reasoning_effort = 'auto'
  }
  function setReasoningEffort(value: string): void {
    state.settings.reasoning_effort = value
  }
  function providerOptions() {
    const family = modelFamily(
      state.settings.provider_id,
      state.settings.model,
      state.settings.preset_id,
    )
    const model = state.settings.models.find((m) => m.id === state.settings.model)
    const effort = availableEfforts(
      state.settings.provider_id,
      state.settings.protocol,
      state.settings.model,
      model,
      state.settings.preset_id,
    ).includes(state.settings.reasoning_effort)
      ? state.settings.reasoning_effort
      : 'auto'
    return {
      protocol: state.settings.protocol,
      provider_family: family,
      reasoning_effort: effort,
      model_options: selectedModelOptions(model),
    }
  }
  function providerProfile(id: string) {
    const settings = id === state.settings.provider_id ? state.settings : providerProfiles[id]
    const key = id === state.settings.provider_id ? state.apiKey : (providerKeys.get(id) ?? '')
    return {
      settings: {
        ...(JSON.parse(JSON.stringify(settings ?? profileSettings(id))) as StoredSettings),
        enabled: (Boolean(key.trim()) || hasSavedCredential(id)) && settings?.enabled !== false,
      },
      key,
      saved: hasSavedCredential(id),
      clearKey: false,
    }
  }
  function applyProviderProfiles(
    rows: Array<{ settings: StoredSettings; key: string }>,
    selected: string,
  ) {
    if (state.busy) return
    providerKeys.set(state.settings.provider_id, state.apiKey)
    providerProfiles[state.settings.provider_id] = { ...state.settings }
    for (const row of rows) {
      if (!validProfileId(row.settings.provider_id)) continue
      providerProfiles[row.settings.provider_id] = {
        ...JSON.parse(JSON.stringify(row.settings)),
        enabled:
          row.settings.enabled &&
          (Boolean(row.key.trim()) || hasSavedCredential(row.settings.provider_id)),
      }
      providerKeys.set(row.settings.provider_id, row.key.trim())
      if (!addedProviderIds.value.includes(row.settings.provider_id))
        addedProviderIds.value.push(row.settings.provider_id)
    }
    const chosen = providerProfiles[selected]
    if (chosen) {
      Object.assign(state.settings, JSON.parse(JSON.stringify(chosen)))
      state.apiKey = providerKeys.get(selected) ?? ''
      state.connected = false
      saveSettings()
    }
    persistProviders()
  }
  function removeProvider(id: string) {
    if (state.busy) return
    addedProviderIds.value = addedProviderIds.value.filter((value) => value !== id)
    delete providerProfiles[id]
    providerKeys.delete(id)
    if (id === state.settings.provider_id) {
      const next = addedProviderIds.value.find(providerReady) ?? addedProviderIds.value[0]
      state.apiKey = ''
      state.settings.enabled = false
      state.connected = false
      if (next) selectProvider(next)
      saveSettings()
    }
    persistProviders()
  }

  const configurationIssue = computed(() => {
    if (state.authExpired) return '登录已失效，请重新登录后继续。'
    if (providerLoading.value) return '正在读取账号模型配置，请稍候。'
    if (providerLoadError.value && !state.apiKey.trim())
      return '读取账号模型配置失败，请重试读取。'
    if (!keyAvailable()) return '请先在「接口设置」中填写 API Key。'
    if (state.settings.enabled === false) return '当前上游请求平台已停用，请在接口设置中启用。'
    if (state.settings.models.find((m) => m.id === state.settings.model)?.enabled === false)
      return '当前模型已停用，请选择已启用的模型。'
    if (!state.settings.models.some((model) => model.enabled))
      return '当前没有已启用的模型，请先启用模型。'
    if (!state.settings.base_url.trim()) return '请先填写接口 Base URL。'
    if (!state.settings.model.trim()) return '请先填写模型名。'
    if (
      hasSavedCredential() &&
      !state.settings.models.some((model) => model.id === state.settings.model && model.enabled)
    )
      return '当前模型不可用，请选择已启用的模型。'
    return ''
  })
  const modelAccess = computed(() => {
    if (!state.user || state.authExpired)
      return {
        kind: 'auth',
        message: '重新登录后可继续使用模型，已有结果仍保留。',
        label: '重新登录',
      }
    if (providerLoading.value)
      return { kind: 'loading', message: '正在读取账号模型配置，请稍候。', label: '正在加载模型…' }
    if (providerLoadError.value && !state.apiKey.trim())
      return {
        kind: 'load-error',
        message: '读取账号模型配置失败，请重试读取。',
        label: '重试读取配置',
      }
    if (configurationIssue.value)
      return { kind: 'configuration', message: configurationIssue.value, label: '配置模型' }
    if (!useConsent().agreed.value)
      return {
        kind: 'consent',
        message: '允许连接模型服务商后，可使用 AI 功能。',
        label: '阅读使用说明',
      }
    return { kind: 'ready', message: '', label: '' }
  })
  const modelReady = computed(() => modelAccess.value.kind === 'ready')
  async function resolveModelAccess() {
    if (modelAccess.value.kind === 'load-error') await refreshProviders()
    else if (modelAccess.value.kind === 'consent') {
      closeSettings()
      useConsent().revoke()
    } else if (modelAccess.value.kind === 'configuration') openSettings()
  }

  function config(): ProviderConfig {
    if (configurationIssue.value) throw new Error(configurationIssue.value)
    const base = state.settings.base_url.trim()
    const model = state.settings.model.trim()
    const consent = useConsent()
    if (!consent.agreed.value) {
      closeSettings()
      consent.revoke()
      throw new Error('当前只使用本地功能。请先阅读数据使用说明，再允许连接模型服务商。')
    }
    return {
      base_url: base,
      model,
      api_key: state.apiKey,
      ...(!state.apiKey.trim() && hasSavedCredential()
        ? { credential_id: state.settings.provider_id }
        : {}),
      allow_tools: state.settings.allow_tools,
      ...providerOptions(),
    }
  }

  function setDetail(detail: DetailLevel): void {
    state.settings.detail = detail
    saveSettings()
  }

  function setAllowTools(value: boolean): void {
    state.settings.allow_tools = value
    saveSettings()
  }

  function setApiKey(value: string): void {
    const empty = !state.apiKey.trim()
    state.apiKey = value
    if (value.trim()) {
      if (!addedProviderIds.value.includes(state.settings.provider_id))
        addedProviderIds.value.push(state.settings.provider_id)
      if (empty) state.settings.enabled = true
    } else if (!hasSavedCredential()) state.settings.enabled = false
    persistProviders()
  }

  function resetProvider(): void {
    selectProvider('deepseek')
    state.settings.provider_family = 'deepseek'
    state.settings.protocol = 'chat'
    state.settings.reasoning_effort = 'auto'
    state.settings.base_url = DEFAULT_BASE_URL
    state.settings.model = DEFAULT_MODEL
    state.connected = false
    saveSettings()
  }

  return {
    saveSettings,
    providerLoading,
    providerLoadError,
    providerProfiles,
    addedProviderIds,
    clearCredentials,
    invalidateProviderLoad,
    refreshProviders,
    saveServerProvider,
    deleteServerProvider,
    hasSavedCredential,
    keyAvailable,
    selectProvider,
    selectModel,
    setReasoningEffort,
    providerReady,
    providerProfile,
    applyProviderProfiles,
    removeProvider,
    configurationIssue,
    modelAccess,
    modelReady,
    resolveModelAccess,
    config,
    setDetail,
    setAllowTools,
    setApiKey,
    resetProvider,
    get credentialEpoch() {
      return credentialEpoch
    },
  }
}
