<script setup lang="ts">
import { learnerText } from '@/utils/learner-text';
import { computed, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import AccountMenu from '@/components/AccountMenu.vue';
import SessionActions from '@/components/SessionActions.vue';
import ConfirmDialog from '@/components/ConfirmDialog.vue';
import AssociationWarning from '@/components/AssociationWarning.vue';
import { useStudy } from '@/composables/useStudy';
import UiIcon from '@/components/UiIcon.vue';
import { useLab } from '@/composables/useLab';
import { useLearning } from '@/composables/useLearning';
import { useReferenceNavigation } from '@/composables/useReferenceNavigation';
import { useSidebar } from '@/composables/useSidebar';
import type { SessionSummary } from '@/types';

const lab = useLab();
const referenceNavigation = useReferenceNavigation();
const pendingDelete = ref<SessionSummary | null>(null),
  deleting = ref(false);
const deleteError = ref('');
async function askDelete(session: SessionSummary) {
  deleteError.value = '';
  try {
    await lab.refreshSessions();
    pendingDelete.value = lab.state.sessions.find((s) => s.id === session.id) ?? null;
  } catch {
    deleteError.value = '无法读取最新关联状态，请稍后重试删除。';
  }
}
const hasBoundDelete = computed(
  () => !!pendingDelete.value?.binding && !pendingDelete.value.binding.card_missing,
);
async function confirmDelete(sync = false) {
  if (!pendingDelete.value || deleting.value) return;
  deleting.value = true;
  try {
    if (await lab.dropSession(pendingDelete.value.id, sync)) {
      pendingDelete.value = null;
      await useStudy().open(lab.state.user, true);
    }
  } finally {
    deleting.value = false;
  }
}
const sidebar = useSidebar();
const learning = useLearning();
const study = useStudy();
const route = useRoute();
const router = useRouter();

const query = ref('');
const renaming = ref<string | null>(null);
const renameDraft = ref('');

const wide = computed(() => sidebar.wide.value);
const signedIn = computed(() => Boolean(lab.state.user));
const sessions = computed(() => lab.state.sessions);
const currentId = computed(() => lab.state.sessionId);

function startSession(): void {
  sidebar.closeMobile();
  lab.newSession();
  if (route.name !== 'chat') void router.push('/');
}

function openSession(id: string): void {
  sidebar.closeMobile();
  if (route.name !== 'chat') void router.push('/');
  void lab.openSession(id);
}

function startRename(session: SessionSummary): void {
  renaming.value = session.id;
  renameDraft.value = session.title;
}

async function commitRename(): Promise<void> {
  const id = renaming.value;
  if (!id) return;
  renaming.value = null;
  const title = renameDraft.value.trim();
  if (title) await lab.renameSession(id, title);
}

function focusRename(element: unknown): void {
  const input = element as HTMLInputElement | null;
  if (!input) return;
  input.focus();
  input.select();
}

const filtered = computed<SessionSummary[]>(() => {
  const text = query.value.trim().toLowerCase();
  if (!text) return sessions.value;
  return sessions.value.filter((session) =>
    learnerText(session.title).toLowerCase().includes(text),
  );
});

const resultCount = computed(() => filtered.value.length);
const referenceBadge = computed(() => {
  const curriculum = learning.curriculum.value;
  return curriculum ? `${learning.learned.value.length}/${curriculum.total}` : '';
});

const routeBadge = computed(() => {
  const total = study.workspace.value?.cards.length ?? 0;
  return total ? String(total) : '';
});

watch(
  () => lab.state.user,
  (user) => {
    learning.reset();
    if (user) {
      void learning.load();
      void study.open(user);
    }
  },
  { immediate: true },
);

const connectionState = computed(() => {
  const access = lab.modelAccess.value;
  if (access.kind === 'auth') return { label: '未登录', message: access.message };
  if (access.kind === 'loading') return { label: '读取中', message: access.message };
  if (access.kind === 'load-error') return { label: '读取失败', message: access.message };
  if (access.kind === 'configuration')
    return {
      label:
        lab.state.settings.enabled === false &&
        (lab.state.apiKey.trim() || lab.hasSavedCredential())
          ? '已停用'
          : '未配置',
      message: access.message,
    };
  if (access.kind === 'consent') return { label: '待授权', message: access.message };
  if (lab.state.busy) return { label: '运行中', message: '正在使用模型配置处理请求。' };
  return {
    label: '已配置',
    message: 'API Key、接口地址和当前模型已配置；实际可用性以连接测试或请求结果为准。',
  };
});

function shortTime(value?: string): string {
  if (!value) return '';
  const parsed = Date.parse(value.replace(' ', 'T'));
  if (Number.isNaN(parsed)) return '';
  const minutes = Math.floor((Date.now() - parsed) / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时`;
  return `${Math.floor(hours / 24)} 天`;
}
</script>

<template>
  <aside
    class="app-rail rail-shell flex flex-col gap-1 overflow-hidden border-r-[0.5px] border-r-line bg-sidebar"
    aria-label="主导航"
  >
    <div class="rail-header flex w-full items-center gap-1.5 pt-0.5 pb-1.5">
      <button
        type="button"
        class="grid h-7 w-9 flex-none cursor-pointer place-items-center rounded-card border-0 bg-transparent p-0 text-ink-2 hover:bg-skeleton hover:text-ink"
        :data-action="wide ? 'collapse-sidebar' : 'expand-sidebar'"
        :aria-label="wide ? '收起侧栏' : '展开侧栏'"
        :aria-expanded="wide"
        @click="sidebar.toggle()"
      >
        <UiIcon
          name="chevron-left"
          class="sidebar-chevron h-[18px] w-[18px]"
          :class="{ 'is-collapsed': !wide }"
        />
      </button>
      <button
        type="button"
        class="rail-brand width-reveal flex min-w-0 cursor-pointer items-center gap-2 overflow-hidden whitespace-nowrap rounded-card border-0 border-current bg-transparent px-1 py-0.5 text-[length:var(--dsw-text-base)] leading-[1.6] text-ink hover:bg-skeleton"
        :class="{ 'is-revealed': wide }"
        :inert="!wide"
        :aria-hidden="!wide"
        aria-label="新建会话"
        @click="lab.newSession()"
      >
        <span class="brand-mark" aria-hidden="true">知</span>
        <span class="truncate text-[length:var(--dsw-text-row)] font-medium leading-[1.6]"
          >知模实验室</span
        >
      </button>
    </div>

    <button
      v-if="signedIn"
      type="button"
      class="rail-item rail-new-session is-primary cursor-pointer rounded-panel border-[0.5px] border-line bg-surface text-[length:var(--dsw-text-row)] leading-[1.6] text-ink hover:border-ink hover:text-ink"
      data-action="new-session"
      @click="startSession()"
    >
      <span class="rail-icon" aria-hidden="true"
        ><UiIcon name="plus" class="h-[18px] w-[18px]"
      /></span>
      <span class="rail-label width-reveal" :class="{ 'is-revealed': wide }">新会话</span>
    </button>

    <nav class="rail-nav flex w-full flex-col gap-1 pb-2" aria-label="视图">
      <RouterLink
        to="/learning"
        class="rail-item rail-nav-item cursor-pointer rounded-panel text-[length:var(--dsw-text-sm)] no-underline"
        :class="route.name === 'learning' ? 'is-active' : ''"
        data-role="nav-learning"
        aria-label="参考路线"
        title="参考路线"
        @click="
          referenceNavigation.openOverview();
          sidebar.closeMobile();
        "
      >
        <span class="rail-icon" aria-hidden="true"
          ><span class="nav-icon reference"
            ><UiIcon name="book-open" class="h-[17px] w-[17px]" /></span
        ></span>
        <span class="rail-label width-reveal" :class="{ 'is-revealed': wide }">参考路线</span>
        <span
          v-if="referenceBadge"
          class="rail-badge width-reveal ml-1 flex-none rounded-[999px] px-1.5 py-[1px] text-[length:var(--dsw-text-xs)] tabular-nums"
          :class="{ 'is-revealed': wide }"
          >{{ referenceBadge }}</span
        >
      </RouterLink>
      <RouterLink
        v-if="signedIn"
        to="/route"
        class="rail-item rail-nav-item cursor-pointer rounded-panel text-[length:var(--dsw-text-sm)] no-underline"
        :class="route.name === 'route' ? 'is-active' : ''"
        data-role="nav-route"
        aria-label="学习路线"
        title="学习路线"
        @click="sidebar.closeMobile()"
      >
        <span class="rail-icon" aria-hidden="true"
          ><span class="nav-icon learning"
            ><UiIcon name="learning-route" class="h-[17px] w-[17px]" /></span
        ></span>
        <span class="rail-label width-reveal" :class="{ 'is-revealed': wide }">学习路线</span>
        <span
          v-if="routeBadge"
          class="rail-badge width-reveal ml-1 flex-none rounded-[999px] px-1.5 py-[1px] text-[length:var(--dsw-text-xs)] tabular-nums"
          :class="{ 'is-revealed': wide }"
          >{{ routeBadge }}</span
        >
      </RouterLink>
      <RouterLink
        v-if="signedIn"
        to="/datasets"
        class="rail-item rail-nav-item cursor-pointer rounded-panel text-[length:var(--dsw-text-sm)] no-underline"
        :class="route.name === 'datasets' ? 'is-active' : ''"
        data-role="nav-datasets"
        aria-label="数据集"
        title="数据集"
        @click="sidebar.closeMobile()"
      >
        <span class="rail-icon" aria-hidden="true"
          ><span class="nav-icon datasets"><UiIcon name="table" class="h-[17px] w-[17px]" /></span
        ></span>
        <span class="rail-label width-reveal" :class="{ 'is-revealed': wide }">数据集</span>
      </RouterLink>
    </nav>

    <div
      v-if="signedIn"
      class="rail-sessions width-reveal mt-3 flex min-h-0 flex-1 flex-col border-t-[0.5px] border-t-[rgba(0,0,0,0.04)] pt-2.5"
      :class="{ 'is-revealed': wide }"
      :inert="!wide"
      :aria-hidden="!wide"
      data-role="session-section"
    >
      <div class="rail-section-head flex items-center justify-between px-1.5 pb-1.5">
        <span class="text-[length:var(--dsw-text-xs)] tracking-[0.04em] text-ink-3">会话</span>
        <span class="text-[length:var(--dsw-text-xs)] text-ink-3" data-role="session-count">{{
          resultCount
        }}</span>
      </div>
      <label
        class="rail-search mb-1.5 flex flex-none items-center gap-1.5 rounded-card px-2 py-[5px] text-[length:var(--dsw-text-sm)] text-ink-3"
        data-role="session-search-field"
      >
        <UiIcon name="search" class="h-[14px] w-[14px] flex-none" />
        <input
          v-model="query"
          type="search"
          class="min-w-0 flex-1 border-0 border-current bg-transparent text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink outline-none"
          data-role="session-search"
          placeholder="搜索会话"
          aria-label="搜索会话"
        />
      </label>
      <div class="min-h-0 flex-1 overflow-y-auto" data-role="session-scroll">
        <div data-role="sessions" role="list">
          <p v-if="!resultCount" class="mx-2 my-1.5 text-[length:var(--dsw-text-xs)] text-ink-3">
            {{ query ? '没有匹配的会话' : '还没有会话，点“新会话”开始' }}
          </p>
          <div
            v-for="session in filtered"
            :key="session.id"
            class="session-row group flex cursor-pointer items-center gap-1.5 rounded-card px-2 py-1.5"
            :class="session.id === currentId && 'is-current'"
            role="listitem"
            :data-session="session.id"
            @click="openSession(session.id)"
          >
            <input
              v-if="renaming === session.id"
              :ref="focusRename"
              v-model="renameDraft"
              type="text"
              maxlength="60"
              class="min-w-0 flex-1 rounded-xs border-[0.5px] border-line bg-surface px-1 py-[1px] text-[length:var(--dsw-text-sm)] leading-[1.6] text-ink outline-none"
              data-role="session-rename"
              aria-label="会话名称"
              @click.stop
              @keydown.enter.prevent="commitRename()"
              @keydown.esc.prevent="renaming = null"
              @blur="commitRename()"
            />
            <span v-else class="min-w-0 flex-1 truncate text-[length:var(--dsw-text-sm)]">{{
              learnerText(session.title)
            }}</span>
            <span
              v-if="lab.runningSessionIds.value.includes(session.id)"
              data-role="session-running"
              class="flex-none text-ink-2"
              title="会话正在后台运行"
              aria-label="正在运行"
              ><UiIcon name="spinner" class="h-3 w-3 animate-spin"
            /></span>
            <span class="whitespace-nowrap text-[length:var(--dsw-text-xs)] text-ink-3">{{
              shortTime(session.updated_at)
            }}</span>
            <AssociationWarning
              v-if="session.binding?.card_missing"
              message="关联卡片已删除；会话仍可继续。"
            />
            <SessionActions
              :title="learnerText(session.title)"
              @rename="startRename(session)"
              @delete="askDelete(session)"
            />
          </div>
        </div>
      </div>
    </div>

    <div
      class="rail-footer rail-account mt-auto flex flex-col gap-0.5 self-stretch border-t-[0.5px] border-t-[rgba(0,0,0,0.04)] pt-2.5"
    >
      <RouterLink
        v-if="!signedIn"
        to="/signin"
        class="rail-item cursor-pointer rounded-card border-0 bg-transparent text-[length:var(--dsw-text-row)] leading-[1.6] text-ink-2 hover:bg-skeleton hover:text-ink"
        data-action="sign-in"
      >
        <span class="rail-icon" aria-hidden="true"
          ><UiIcon name="arrow-right" class="h-[18px] w-[18px]"
        /></span>
        <span class="rail-label width-reveal" :class="{ 'is-revealed': wide }">登录 / 注册</span>
      </RouterLink>
      <AccountMenu
        v-if="signedIn"
        :username="lab.state.user"
        :compact="!wide"
        @logout="lab.signOut()"
      />
      <button
        type="button"
        class="rail-item rail-settings cursor-pointer rounded-card border-0 bg-transparent text-[length:var(--dsw-text-row)] leading-[1.6] text-ink-2 hover:bg-skeleton hover:text-ink"
        data-action="settings"
        aria-label="接口设置"
        title="接口设置"
        @click="lab.openSettings()"
      >
        <span class="rail-icon" aria-hidden="true"><UiIcon name="settings" class="h-5 w-5" /></span>
        <span class="rail-label width-reveal" :class="{ 'is-revealed': wide }">接口设置</span>
        <span
          class="width-reveal ml-1 flex-none whitespace-nowrap text-[length:var(--dsw-text-xs)] text-ink-3"
          :class="{ 'is-revealed': wide }"
          :title="connectionState.message"
          data-role="connection"
          >{{ connectionState.label }}</span
        >
      </button>
    </div>
    <p v-if="deleteError" role="alert" class="text-[length:var(--dsw-text-xs)] text-ink-3">{{
      deleteError
    }}</p>
    <ConfirmDialog
      :open="!!pendingDelete"
      title="删除会话"
      :message="
        hasBoundDelete
          ? '是否同步删除对应的卡片？仅删除会话时会保留卡片与采用事实，并标记来源缺失。'
          : '确定删除这个会话？'
      "
      :confirm="hasBoundDelete ? '同步删除' : '删除会话'"
      :secondary="hasBoundDelete ? '仅删除会话' : undefined"
      :busy="deleting"
      @confirm="confirmDelete(hasBoundDelete)"
      @secondary="confirmDelete(false)"
      @cancel="pendingDelete = null"
    />
  </aside>
</template>

<style scoped>
/* The icon column and row heights stay fixed while the parent width animates. */
.app-rail {
  min-width: 0;
  padding: 6px 10px;
}
.rail-header {
  height: 36px;
  flex-shrink: 0;
  overflow: hidden;
}
.rail-nav,
.rail-footer {
  flex-shrink: 0;
}
.rail-item {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  height: 38px;
  flex-shrink: 0;
  padding: 0;
  overflow: hidden;
  text-align: left;
}
.rail-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 100%;
  flex: 0 0 36px;
}
.rail-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rail-new-session {
  height: 36px;
}
.rail-new-session .rail-icon {
  margin-left: -1px;
}
.rail-settings {
  height: 34px;
  padding-right: 8px;
}
.nav-icon {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border-radius: 7px;
}
.nav-icon.reference {
  background: var(--dsw-selection-surface);
  color: var(--dsw-feedback-info-text);
}
.nav-icon.learning {
  background: #f0ebff;
  color: #7354b6;
}
.nav-icon.datasets {
  background: var(--dsw-selection-surface);
  color: var(--dsw-feedback-info-text);
}
.sidebar-chevron {
  transform-origin: center;
  transform-box: view-box;
  transition: transform 240ms cubic-bezier(0.22, 1, 0.36, 1);
}
.sidebar-chevron.is-collapsed {
  transform: rotate(180deg);
}
@media (prefers-reduced-motion: reduce) {
  .sidebar-chevron {
    transition: none;
  }
}

/* Refined rail surface */
.rail-shell {
  padding: 9px 10px 8px;
  border-right-color: #e9eef8;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
}
.rail-header {
  height: 40px;
  gap: 8px;
  padding-bottom: 8px;
}
.rail-brand {
  padding: 3px 5px;
  border-radius: 10px;
  transition:
    background 160ms ease,
    box-shadow 160ms ease;
}
.rail-brand:hover {
  background: #ffffff;
  box-shadow: 0 2px 8px -4px rgb(20 40 80 / 0.26);
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 29px;
  height: 29px;
  flex: none;
  border-radius: 10px;
  background: #eef3ff;
  color: #315fbd;
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.02em;
  box-shadow: inset 0 0 0 1px #d7e3fb;
}
.rail-new-session {
  height: 42px;
  padding-right: 10px;
  border: 1px solid #dfe7f3;
  border-radius: 12px;
  background: #ffffff;
  color: #1a2740;
  box-shadow: 0 1px 2px rgb(20 40 80 / 0.04);
  transition:
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms ease,
    filter 180ms ease;
}
.rail-new-session:hover {
  border-color: #c3d4f1;
  color: #14213a;
  background: #f7faff;
  transform: none;
  box-shadow: 0 1px 2px rgb(20 40 80 / 0.04);
}
.rail-new-session .rail-icon {
  color: #315fbd;
}
.rail-nav {
  gap: 3px;
  padding-bottom: 4px;
}
.rail-nav-item {
  position: relative;
  height: 40px;
  padding-right: 8px;
  border-radius: 10px;
  color: var(--dsw-alias-text-secondary);
  transition:
    background 160ms ease,
    color 160ms ease,
    box-shadow 160ms ease;
}
.rail-nav-item:hover {
  background: #eef3fb;
  color: #12233f;
}
.rail-nav-item.is-active {
  background: #ffffff;
  color: #0d1b35;
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.05),
    inset 0 0 0 1px #e3eaf6;
}
.rail-nav-item.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 11px;
  bottom: 11px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: linear-gradient(180deg, #4f7cff, #7ce7ff);
}
.rail-item {
  transition:
    background 160ms ease,
    color 160ms ease;
}
.rail-icon {
  width: 36px;
  flex: 0 0 36px;
}
.nav-icon {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  box-shadow: inset 0 0 0 1px rgb(20 40 80 / 0.04);
}
.nav-icon.reference {
  background: linear-gradient(140deg, #e9f1ff, #d8e6ff);
  color: #2f5dcc;
  box-shadow: inset 0 0 0 1px rgb(79 124 255 / 0.12);
}
.nav-icon.learning {
  background: linear-gradient(140deg, #f3edff, #e6dbff);
  color: #6b46c1;
  box-shadow: inset 0 0 0 1px rgb(115 84 182 / 0.1);
}
.nav-icon.datasets {
  background: linear-gradient(140deg, #e7f8f1, #d8f0e5);
  color: #1c7a58;
  box-shadow: inset 0 0 0 1px rgb(28 122 88 / 0.08);
}
.rail-badge {
  border: 1px solid #dbe5fb;
  background: #eaf0ff;
  color: #3d63c7;
  font-weight: 600;
}
.rail-sessions {
  margin-top: 14px;
  border-top-color: #e9eef8 !important;
  padding-top: 12px;
}
.rail-section-head {
  padding-bottom: 7px;
  color: #7b879c !important;
  letter-spacing: 0.12em !important;
}
.rail-section-head > span:last-child {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #eef3fb;
  color: #7b879c;
  text-align: center;
  line-height: 18px;
}
.rail-search {
  margin-bottom: 7px;
  padding: 6px 9px;
  border: 1px solid #e5ebf5;
  border-radius: 9px;
  background: #ffffff;
  color: #8a96ab;
  box-shadow: 0 1px 2px rgb(20 40 80 / 0.03);
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}
.rail-search:focus-within {
  border-color: #9db5ee;
  box-shadow: 0 0 0 3px rgb(79 124 255 / 0.1);
}
.session-row {
  min-height: 34px;
  margin-bottom: 2px;
  padding: 7px 8px;
  border-radius: 9px;
  color: var(--dsw-alias-text-secondary);
  transition:
    background 150ms ease,
    box-shadow 150ms ease,
    color 150ms ease;
}
.session-row:hover {
  background: #eef3fb;
  color: var(--dsw-alias-text-primary);
}
.session-row.is-current {
  background: #ffffff;
  color: #0d1b35;
  box-shadow:
    inset 3px 0 0 #4f7cff,
    0 1px 2px rgb(20 40 80 / 0.04);
}
.session-row.is-current > span:nth-child(2) {
  font-weight: 550;
}
.rail-footer,
.rail-account {
  border-top-color: #e9eef8 !important;
  padding-top: 10px;
}
.account-row {
  height: 42px;
  padding: 0 2px;
  border-radius: 10px;
}
.account-row:hover {
  background: #eef3fb;
}
:global(.account-avatar) {
  width: 26px;
  height: 26px;
  margin: 0 8px 0 4px;
  background: #f7faff;
  color: #315fbd;
  box-shadow: inset 0 0 0 1px #d7e3fb;
}
.rail-settings {
  height: 36px;
  border-radius: 9px;
  padding-right: 8px;
}
.rail-settings:hover {
  background: #eef3fb;
  color: #12233f;
}
</style>
