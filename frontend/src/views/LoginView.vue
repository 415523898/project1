<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import { useLab } from '@/composables/useLab';
import { cleanError, connectionError } from '@/services/agent';
import UiIcon from '@/components/UiIcon.vue';

const lab = useLab();
const route = useRoute();
const router = useRouter();

const mode = ref<'login' | 'register'>('login');
const name = ref('');
const password = ref('');
const confirm = ref('');
const busy = ref(false);
const message = ref('');
const tone = ref<'muted' | 'error'>('muted');

const isRegister = computed(() => mode.value === 'register');
const canSubmit = computed(
  () =>
    Boolean(name.value.trim()) &&
    Boolean(password.value) &&
    (!isRegister.value || Boolean(confirm.value)) &&
    !busy.value,
);

function switchMode(next: 'login' | 'register'): void {
  mode.value = next;
  message.value = '';
  tone.value = 'muted';
  confirm.value = '';
}

async function submit(): Promise<void> {
  if (!canSubmit.value) return;
  const username = name.value.trim();
  if (isRegister.value && password.value !== confirm.value) {
    message.value = '两次输入的密码不一致。';
    tone.value = 'error';
    return;
  }
  busy.value = true;
  message.value = isRegister.value ? '正在创建账号…' : '正在登录…';
  tone.value = 'muted';
  try {
    if (isRegister.value) await lab.signUp(username, password.value);
    else await lab.signIn(username, password.value);
    password.value = '';
    confirm.value = '';
    const next = route.query.next;
    await router.replace(typeof next === 'string' && next.startsWith('/') ? next : '/learning');
  } catch (error) {
    const text = connectionError(error);
    message.value = text.includes('连接中断')
      ? '无法连接账号服务，请检查网络后重试。'
      : cleanError(text);
    tone.value = 'error';
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="auth-page">
    <aside class="auth-brand" aria-hidden="true">
      <div class="auth-brand-grid"></div>
      <div class="auth-brand-glow"></div>
      <div class="auth-brand-inner">
        <span class="auth-brand-mark">知</span>
        <p class="auth-brand-eyebrow">FOREST LEARNING LAB</p>
        <h2>把方法、实验与<br /><em>学习进度</em>放在一起。</h2>
        <p class="auth-brand-lede">
          从 116 个方法的图谱出发，选择合适的方法、在自己的数据上跑实验，再把理解沉淀成学习路线。
        </p>
        <ul class="auth-points">
          <li><span>01</span>方法图谱与前置关系</li>
          <li><span>02</span>服务端实验与可核查解释</li>
          <li><span>03</span>本地数据与学习进度</li>
        </ul>
        <p class="auth-brand-foot">本地部署 · 数据留在本机 · 无需邀请码</p>
      </div>
    </aside>
    <div class="auth-panel">
      <form class="auth-form" data-role="auth-form" @submit.prevent="submit()">
        <header class="flex flex-col items-center gap-1.5 text-center">
          <span
            class="grid h-[34px] w-[34px] place-items-center rounded-panel bg-ink text-[length:var(--dsw-text-row)] font-medium text-brand-ink"
            aria-hidden="true"
            >知</span
          >
          <h1 class="m-0 text-[length:var(--dsw-text-lg)] font-medium">知模实验室</h1>
          <p class="m-0 text-[length:var(--dsw-text-sm)] text-ink-3"
            >方法库不需要登录就能看。登录后可以对话、跑实验，会话只对自己可见。</p
          >
        </header>

        <div
          class="grid grid-cols-2 gap-1 rounded-panel bg-skeleton p-[3px]"
          role="tablist"
          aria-label="登录或注册"
        >
          <button
            type="button"
            role="tab"
            class="cursor-pointer rounded-card border-0 border-current px-0 py-1.5 text-[length:var(--dsw-text-row)] leading-[1.6]"
            data-action="mode-login"
            :aria-selected="!isRegister"
            :class="!isRegister ? 'bg-surface font-medium text-ink' : 'bg-transparent text-ink-2'"
            @click="switchMode('login')"
            >登录</button
          >
          <button
            type="button"
            role="tab"
            class="cursor-pointer rounded-card border-0 border-current px-0 py-1.5 text-[length:var(--dsw-text-row)] leading-[1.6]"
            data-action="mode-register"
            :aria-selected="isRegister"
            :class="isRegister ? 'bg-surface font-medium text-ink' : 'bg-transparent text-ink-2'"
            @click="switchMode('register')"
            >注册</button
          >
        </div>

        <label class="flex flex-col gap-1 text-[length:var(--dsw-text-sm)] text-ink-2">
          <span>用户名</span>
          <input
            v-model="name"
            type="text"
            class="rounded-card border-[0.5px] border-line bg-surface px-2.5 py-2 text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink outline-none focus:border-ink"
            data-role="auth-username"
            autocomplete="username"
            placeholder="2–24 位字母、数字、下划线、连字符或中文"
            required
          />
        </label>

        <label class="flex flex-col gap-1 text-[length:var(--dsw-text-sm)] text-ink-2">
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            class="rounded-card border-[0.5px] border-line bg-surface px-2.5 py-2 text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink outline-none focus:border-ink"
            data-role="auth-password"
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            :placeholder="isRegister ? '12–128 位，支持密码短语' : '输入当前密码'"
            :minlength="isRegister ? 12 : undefined"
            maxlength="200"
            required
          />
        </label>

        <label
          v-if="isRegister"
          class="flex flex-col gap-1 text-[length:var(--dsw-text-sm)] text-ink-2"
        >
          <span>确认密码</span>
          <input
            v-model="confirm"
            type="password"
            class="rounded-card border-[0.5px] border-line bg-surface px-2.5 py-2 text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink outline-none focus:border-ink"
            data-role="auth-confirm"
            autocomplete="new-password"
            placeholder="再输入一次"
            required
          />
        </label>

        <button
          type="submit"
          class="mt-1 cursor-pointer rounded-card border-0 border-current bg-ink px-0 py-[9px] text-[length:var(--dsw-text-row)] font-medium leading-[1.6] text-brand-ink disabled:cursor-not-allowed disabled:opacity-50"
          data-role="auth-submit"
          :disabled="!canSubmit"
        >
          {{ busy ? '请稍候…' : isRegister ? '注册并进入' : '登录' }}
        </button>

        <p
          class="m-0 min-h-[18px] text-center text-[length:var(--dsw-text-sm)]"
          :class="tone === 'error' ? 'text-error-ink' : 'text-ink-3'"
          :data-tone="tone"
          data-role="auth-message"
          role="status"
          >{{ message }}</p
        >
        <p class="m-0 text-center text-[length:var(--dsw-text-xs)] text-ink-3">
          还没有账号？点上面的「注册」即可创建，不需要邀请码。
        </p>
        <RouterLink class="auth-back" to="/learning" data-action="auth-back">
          <span class="auth-back-icon"><UiIcon name="book-open" class="h-[18px] w-[18px]" /></span>
          <span class="auth-back-copy"
            ><span class="auth-back-title">先看看方法库</span
            ><span class="auth-back-note">116 个方法 · 无需登录</span></span
          >
          <UiIcon name="arrow-right" class="auth-back-arrow h-[16px] w-[16px]" />
        </RouterLink>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-back {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 58px;
  padding: 10px 12px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 10px;
  background: var(--dsw-alias-bg-layer-2);
  color: var(--dsw-alias-text-primary);
  text-decoration: none;
  transition:
    background 160ms,
    border-color 160ms;
}
.auth-back-icon {
  display: grid;
  place-items: center;
  flex: 0 0 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--dsw-selection-surface);
  color: var(--dsw-feedback-info-text);
}
.auth-back-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 1px;
}
.auth-back-title {
  font-size: var(--dsw-text-row);
  font-weight: 500;
}
.auth-back-note {
  color: var(--dsw-alias-text-tertiary);
  font-size: var(--dsw-text-xs);
}
.auth-back-arrow {
  flex-shrink: 0;
  color: var(--dsw-alias-text-secondary);
  transition: transform 160ms;
}
.auth-back:hover {
  border-color: var(--dsw-selection-border);
  background: var(--dsw-selection-surface);
}
.auth-back:hover .auth-back-arrow {
  transform: translateX(2px);
}
.auth-back:focus-visible {
  outline: 2px solid var(--dsw-focus-ring);
  outline-offset: 3px;
}
@media (prefers-reduced-motion: reduce) {
  .auth-back,
  .auth-back-arrow {
    transition: none;
  }
}

/* Split editorial sign-in */
.auth-page {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(420px, 0.92fr);
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  background: #f8fafc;
}
.auth-brand {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 0;
  padding: clamp(34px, 4.2vw, 68px);
  overflow: hidden;
  color: #14213a;
  border-right: 1px solid #e2eaf5;
  background:
    radial-gradient(520px 360px at 86% 4%, rgb(79 124 255 / 0.1) 0%, transparent 70%),
    linear-gradient(135deg, #ffffff 0%, #f8fbff 58%, #f4f8ff 100%);
}
.auth-brand-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgb(20 40 80 / 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgb(20 40 80 / 0.05) 1px, transparent 1px);
  background-size: 34px 34px;
  -webkit-mask-image: linear-gradient(122deg, #000 0%, transparent 76%);
  mask-image: linear-gradient(122deg, #000 0%, transparent 76%);
  pointer-events: none;
}
.auth-brand-glow {
  position: absolute;
  top: -160px;
  right: 8%;
  width: 440px;
  height: 440px;
  border: 1px solid rgb(79 124 255 / 0.14);
  border-radius: 50%;
  box-shadow:
    0 0 0 48px rgb(79 124 255 / 0.05),
    0 0 0 96px rgb(79 124 255 / 0.03);
  pointer-events: none;
}
.auth-brand-inner {
  position: relative;
  z-index: 1;
  width: min(540px, 100%);
}
.auth-brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: #eef3ff;
  color: #315fbd;
  box-shadow: inset 0 0 0 1px #d7e3fb;
  font-size: 18px;
  font-weight: 650;
  box-shadow: inset 0 0 0 1px #d7e3fb;
}
.auth-brand-eyebrow {
  margin: 22px 0 0;
  color: #315fbd;
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.2em;
  line-height: 1.4;
}
.auth-brand h2 {
  margin: 12px 0 0;
  color: #13203a;
  font-size: clamp(30px, 3vw, 44px);
  font-weight: 650;
  letter-spacing: -0.035em;
  line-height: 1.22;
}
.auth-brand h2 em {
  background: linear-gradient(100deg, #315fbd 0%, #4f7cff 52%, #2f9fc4 100%);
  background-clip: text;
  color: transparent;
  font-style: normal;
  font-weight: 700;
}
.auth-brand-lede {
  max-width: 440px;
  margin: 16px 0 0;
  color: #5f6b80;
  font-size: 12.5px;
  line-height: 1.8;
}
.auth-points {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin: 24px 0 0;
  padding: 0;
  list-style: none;
}
.auth-points li {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #4f5d73;
  font-size: 11.5px;
  line-height: 1.6;
}
.auth-points li span {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  flex: none;
  border: 1px solid #d8e4fb;
  border-radius: 7px;
  background: #f6faff;
  color: #315fbd;
  font-size: 8.5px;
  font-weight: 700;
}
.auth-brand-foot {
  margin: 30px 0 0;
  color: #7b879c;
  font-size: 10px;
  letter-spacing: 0.02em;
}
.auth-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 40px 28px;
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: min(400px, 100%);
  padding: 28px 28px 22px;
  border: 1px solid #e3eaf5;
  border-radius: 24px;
  background: #ffffff;
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.03),
    0 30px 70px -48px rgb(20 40 80 / 0.4);
}
.auth-form header {
  gap: 6px;
}
.auth-form header > span {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 11px;
  background: #eef3ff;
  color: #315fbd;
  box-shadow: inset 0 0 0 1px #d7e3fb;
  font-size: 12px;
  font-weight: 650;
}
.auth-form h1 {
  margin: 4px 0 0;
  color: #13203a;
  font-size: 19px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.auth-form header p {
  max-width: 300px;
  color: #7b879c;
  font-size: 11px;
  line-height: 1.65;
}
.auth-form [role='tablist'] {
  margin-top: 2px;
  padding: 3px;
  border: 1px solid #e6ecf6;
  border-radius: 11px;
  background: #f3f6fb;
}
.auth-form [role='tab'] {
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  color: #7b879c;
  font-size: 11.5px;
  transition:
    background 160ms ease,
    color 160ms ease,
    box-shadow 160ms ease;
}
.auth-form [role='tab'][aria-selected='true'] {
  background: #ffffff;
  color: #14213a;
  font-weight: 600;
  box-shadow: 0 1px 3px rgb(20 40 80 / 0.08);
}
.auth-form label {
  gap: 5px;
  color: #5f6b80;
  font-size: 10.5px;
}
.auth-form label > span {
  font-weight: 500;
}
.auth-form input {
  height: 40px;
  padding: 0 11px;
  border: 1px solid #e2e9f4;
  border-radius: 10px;
  background: #fbfcff;
  color: #14213a;
  font-size: 12px;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    box-shadow 160ms ease;
}
.auth-form input:focus {
  border-color: #9db5ee;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgb(79 124 255 / 0.09);
}
.auth-form input::placeholder {
  color: #9aa7ba;
}
.auth-form [data-role='auth-submit'] {
  height: 42px;
  margin-top: 6px;
  border-radius: 10px;
  border: 1px solid #d7e3fb;
  background: #eef3ff;
  color: #274a9a;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 12px 24px -18px rgb(11 25 58 / 0.9);
}
.auth-form [data-role='auth-submit']:hover:not(:disabled) {
  background: #e1ebff;
}
.auth-form [data-role='auth-submit']:disabled {
  background: #eef2f8;
  color: #9aa7ba;
  box-shadow: none;
  opacity: 1;
}
.auth-form [data-role='auth-message'] {
  min-height: 16px;
  font-size: 10.5px;
}
.auth-form > p {
  color: #8a96ab;
}
.auth-back {
  min-height: 56px;
  padding: 9px 11px;
  border-color: #e5ebf5;
  border-radius: 11px;
  background: #f8faff;
}
.auth-back:hover {
  border-color: #c9d9f8;
  background: #f4f8ff;
}
.auth-back-title {
  font-size: 11.5px;
  font-weight: 600;
}
.auth-back-note {
  font-size: 10px;
}
.auth-back-icon {
  border-radius: 9px;
  background: #eef4ff;
  color: #3d63c7;
}
@media (max-width: 1000px) {
  .auth-page {
    grid-template-columns: minmax(0, 1fr);
  }
  .auth-brand {
    display: none;
  }
  .auth-panel {
    padding: 24px 16px;
  }
}
@media (max-width: 480px) {
  .auth-form {
    padding: 22px 18px 18px;
    border-radius: 19px;
  }
}
</style>
