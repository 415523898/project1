<script setup lang="ts">
import { ref } from 'vue';
import { vDisclosureMotion } from '@/utils/disclosure-motion';
import { useLab } from '@/composables/useLab';
import { providerApi } from '@/services/providers';
const lab = useLab(),
  password = ref(''),
  next = ref(''),
  confirm = ref(''),
  busy = ref(false),
  status = ref('');
async function run(action: 'reauthenticate' | 'password' | 'logout-all') {
  if (busy.value || !password.value) return;
  if (action === 'password' && (next.value.length < 12 || next.value !== confirm.value)) {
    status.value = '新密码至少 12 位，且两次输入须一致。';
    return;
  }
  busy.value = true;
  status.value = '';
  try {
    await providerApi.secure(action, password.value, next.value);
    status.value =
      action === 'reauthenticate'
        ? '身份已验证，15 分钟内可修改服务器密钥。'
        : action === 'password'
          ? '密码已更新，其他设备已退出。'
          : '所有设备已退出，请重新登录。';
    if (action === 'logout-all') await lab.signOut();
  } catch (error) {
    status.value = error instanceof Error ? error.message : String(error);
  } finally {
    password.value = '';
    next.value = '';
    confirm.value = '';
    busy.value = false;
  }
}
</script>
<template>
  <details v-if="lab.state.user" v-disclosure-motion class="account-security"
    ><summary>账号安全</summary>
    <fieldset :disabled="busy || lab.state.busy"
      ><label
        >当前密码<input
          v-model="password"
          type="password"
          autocomplete="current-password"
          maxlength="200"
          placeholder="输入当前账号密码，上传 API key 至云端保存"
          data-role="current-password"
      /></label>
      <div class="password-grid"
        ><label
          >新密码<input
            v-model="next"
            type="password"
            autocomplete="new-password"
            minlength="12"
            maxlength="128"
            placeholder="12–128 位，支持密码短语" /></label
        ><label
          >确认新密码<input
            v-model="confirm"
            type="password"
            autocomplete="new-password"
            maxlength="128" /></label
      ></div>
      <div class="security-actions"
        ><button type="button" :disabled="!password" @click="run('reauthenticate')">验证身份</button
        ><button type="button" :disabled="!password || !next || !confirm" @click="run('password')"
          >修改密码</button
        ><button type="button" :disabled="!password" @click="run('logout-all')"
          >退出所有设备</button
        ></div
      > </fieldset
    ><p role="status">{{ status }}</p>
  </details>
</template>
<style scoped>
.account-security {
  border-top: 1px solid var(--dsw-alias-border-l2);
  margin-top: 15px;
  padding-top: 15px;
  font-size: var(--dsw-text-sm);
  color: var(--dsw-alias-text-secondary);
}
summary {
  cursor: pointer;
  margin-bottom: 12px;
}
fieldset {
  border: 0;
  padding: 0;
  display: grid;
  gap: 12px;
  min-width: 0;
}
label {
  display: grid;
  gap: 6px;
  font-size: var(--dsw-text-sm);
}
input {
  width: 100%;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--dsw-alias-border-l2);
  border-radius: 8px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-text-primary);
  font: inherit;
}
.password-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.security-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
button {
  border: 1px solid var(--dsw-alias-border-l2);
  background: none;
  color: inherit;
  border-radius: 7px;
  padding: 6px 9px;
  font: inherit;
  cursor: pointer;
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
p {
  font-size: var(--dsw-text-xs);
  line-height: 1.8;
  margin: 8px 0 0;
}
</style>
