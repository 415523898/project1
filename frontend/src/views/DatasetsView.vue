<script setup lang="ts">
import { useRouter } from 'vue-router';
import DatasetLibrary from '@/components/DatasetLibrary.vue';
import UiIcon from '@/components/UiIcon.vue';

const router = useRouter();
function close(): void {
  void router.push('/');
}
</script>

<template>
  <main class="datasets-view" data-view="datasets" aria-label="数据集">
    <header class="datasets-head">
      <div class="datasets-heading">
        <p class="datasets-eyebrow">DATASET LIBRARY</p>
        <h1>数据集</h1>
        <p>浏览内置数据、上传自己的表格并保存默认分析配置；在会话右侧可指定该会话使用的数据。</p>
      </div>
      <div class="datasets-facts" aria-label="数据集能力">
        <span><UiIcon name="table" />CSV / Excel</span>
        <span><UiIcon name="lock" />数据留在本机</span>
        <span><UiIcon name="sparkles" />自动识别字段角色</span>
      </div>
    </header>
    <section class="datasets-body">
      <DatasetLibrary @close="close" />
    </section>
  </main>
</template>

<style scoped>
.datasets-view {
  display: flex;
  min-width: 0;
  min-height: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
  background: #ffffff;
  color: var(--dsw-alias-text-primary);
}
.datasets-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex: none;
  padding: 26px 32px 22px;
  border-bottom: 1px solid #e9eef8;
  background: color-mix(in srgb, #ffffff 74%, transparent);
  backdrop-filter: blur(16px);
}
.datasets-heading {
  min-width: 0;
  max-width: 780px;
}
.datasets-eyebrow {
  margin: 0 0 7px;
  color: #7f8da5;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.2em;
  line-height: 1.4;
}
.datasets-head h1 {
  margin: 0;
  color: #13203a;
  font-size: 27px;
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.2;
}
.datasets-head p {
  margin: 8px 0 0;
  color: #647086;
  font-size: 13px;
  line-height: 1.7;
}
.datasets-facts {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
  flex: none;
  max-width: 420px;
  padding-bottom: 2px;
}
.datasets-facts span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  border: 1px solid #e2eaf5;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.72);
  color: #74839a;
  font-size: 10.5px;
  line-height: 1.5;
  white-space: nowrap;
}
.datasets-facts svg {
  width: 12px;
  height: 12px;
  color: #4f7cff;
}
.datasets-body {
  min-height: 0;
  flex: 1;
  overflow: auto;
  padding: 22px 32px 30px;
}
@media (max-width: 1000px) {
  .datasets-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
    padding: 22px 24px 18px;
  }
  .datasets-facts {
    justify-content: flex-start;
  }
}
@media (max-width: 720px) {
  .datasets-head {
    padding: 18px 16px 14px;
  }
  .datasets-head h1 {
    font-size: 24px;
  }
  .datasets-body {
    padding: 14px 16px 22px;
  }
}
</style>
