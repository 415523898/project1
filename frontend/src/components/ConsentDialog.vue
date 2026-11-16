<script setup lang="ts">
import { useDialogViewport } from '@/composables/useDialogMotion';
import { computed, ref, watch } from 'vue';

import { useConsent } from '@/composables/useConsent';
import { useLab } from '@/composables/useLab';

const consent = useConsent();
const lab = useLab();
const dialog = ref<HTMLDialogElement | null>(null);

useDialogViewport(dialog);
const shouldOpen = computed(
  () => lab.state.authChecked && Boolean(lab.state.user) && !consent.reviewed.value,
);
const visible = ref(false);

function sync(): void {
  const element = dialog.value;
  const wanted = shouldOpen.value;
  visible.value = wanted;
  if (!element || element.open === wanted) return;
  if (wanted) element.showModal();
  else element.close();
}

watch([shouldOpen, dialog], sync, { immediate: true, flush: 'post' });

const rows = [
  {
    title: '方法库与导航图',
    body: '116 个方法的说明、关系和排列随页面一起加载，不发往任何服务器，断网也能看。',
  },
  {
    title: '服务端实验',
    body: '实验由当前连接的后端服务器执行并返回结果。数据按账号隔离存放，云端访问时处理发生在服务器。',
  },
  {
    title: '对话内容',
    body: '你输入的问题、附件已提取的正文、支持的图片和工具摘要，会发往你选择的模型服务商。文件上传成功不代表正文可读，请查看附件状态。语音由后端服务器的 SenseVoice 转写；API Key 按账号在服务器加密保存。',
  },
  {
    title: '浏览器存储',
    body: '只保存用户名、界面偏好和后端地址。登录凭据是 HttpOnly Cookie，页面脚本读不到。',
  },
];
</script>

<template>
  <dialog
    ref="dialog"
    class="consent-dialog m-auto w-[min(38rem,calc(100vw-2rem))] rounded-panel border border-line bg-surface p-0 text-ink shadow-panel"
    :data-open="visible ? 'yes' : 'no'"
    aria-labelledby="consent-title"
  >
    <div class="p-6" data-role="consent">
      <h2 id="consent-title" class="text-lg font-semibold text-ink">数据使用说明</h2>
      <p class="mt-1 text-sm text-ink-2">知模实验室分成两部分，请先了解它们各自处理了什么。</p>

      <dl class="mt-5 grid gap-3">
        <div
          v-for="row in rows"
          :key="row.title"
          class="rounded-card border border-line bg-surface-2 p-3"
        >
          <dt class="text-sm font-medium text-ink">{{ row.title }}</dt>
          <dd class="mt-1 text-sm leading-relaxed text-ink-2">{{ row.body }}</dd>
        </div>
      </dl>

      <p class="mt-4 rounded-card bg-surface-2 px-3 py-2 text-xs text-ink-3">
        请不要在对话里提交身份证号、手机号、病历等个人敏感信息。
      </p>

      <div class="mt-5 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          class="ui-button ui-button-ghost"
          data-action="consent-decline"
          @click="consent.localOnly()"
          >暂不连接模型服务商</button
        >
        <button
          type="button"
          class="ui-button ui-button-primary"
          data-action="consent-accept"
          @click="consent.accept()"
          >我知道了</button
        >
      </div>
    </div>
  </dialog>
</template>
