<script setup lang="ts">
import { computed } from 'vue';
import UiIcon from '@/components/UiIcon.vue';
import type { MethodGraph, MethodLayer } from '@/types';

const props = defineProps<{
  graph: MethodGraph | null;
  learned: string[];
  studying: string[];
}>();
defineEmits<{ enter: [] }>();

const counts = computed(() => props.graph?.counts);
const stages = computed(() => props.graph?.layers ?? []);
const categories = computed(() => props.graph?.tree ?? []);
const learnedSet = computed(() => new Set(props.learned));
const learnedCount = computed(() => props.learned.length);
const studyingCount = computed(() => props.studying.length);
const methodTotal = computed(() => counts.value?.methods ?? 0);

const progressPercent = computed(() => {
  const total = methodTotal.value;
  return total > 0 ? Math.min(100, (learnedCount.value / total) * 100) : 0;
});
const progressLabel = computed(() =>
  progressPercent.value > 0 && progressPercent.value < 10
    ? progressPercent.value.toFixed(1)
    : String(Math.round(progressPercent.value)),
);
const stageDone = computed(
  () =>
    stages.value.filter((stage) => stage.count > 0 && stageLearned(stage) >= stage.count).length,
);
const maxCategory = computed(() =>
  categories.value.reduce((max, category) => Math.max(max, category.count), 1),
);

function pad(level: number): string {
  return String(level).padStart(2, '0');
}

function stageLearned(stage: { methods: string[] }): number {
  return stage.methods.reduce((sum, id) => sum + (learnedSet.value.has(id) ? 1 : 0), 0);
}

function stagePercent(stage: { methods: string[]; count: number }): number {
  return stage.count > 0 ? Math.min(100, (stageLearned(stage) / stage.count) * 100) : 0;
}

function stageLabel(stage: MethodLayer): string {
  const done = stageLearned(stage);
  return done > 0 ? done + ' / ' + stage.count + ' 已学' : stage.count + ' 个方法';
}
</script>

<template>
  <section class="reference-overview" data-role="reference-overview" aria-label="参考路线总览">
    <div v-if="!graph" class="overview-loading" role="status">正在加载参考路线…</div>
    <div v-else class="overview-inner">
      <header class="overview-hero">
        <span class="hero-grid" aria-hidden="true"></span>
        <span class="hero-glow" aria-hidden="true"></span>
        <div class="hero-copy">
          <p class="hero-eyebrow">
            <span class="eyebrow-rule" aria-hidden="true"></span>
            <span>REFERENCE ROUTE</span>
            <span class="eyebrow-dot" aria-hidden="true"></span>
            <span class="eyebrow-cn">参考路线</span>
          </p>
          <h2 class="hero-title">
            一张图看懂 <em>{{ methodTotal }}</em> 个方法的学习顺序
          </h2>
          <p class="hero-lede">
            从数据认知到因果与评价，按前置关系分成
            {{ counts?.levels ?? 0 }}
            个阶段。先看总览，再进入图谱按阶段推进，也可以直接在顶部搜索方法。
          </p>
          <div class="hero-actions">
            <button
              type="button"
              class="hero-cta"
              data-action="enter-method-graph"
              @click="$emit('enter')"
            >
              <span>进入方法图谱</span>
              <UiIcon name="arrow-up-right" />
            </button>
            <span class="hero-hint">
              <UiIcon name="sparkles" />
              按顺序推进，或从任意阶段开始
            </span>
          </div>
        </div>

        <aside class="hero-progress" aria-label="学习进度概览">
          <div class="progress-ring">
            <svg viewBox="0 0 120 120" aria-hidden="true">
              <defs>
                <linearGradient id="reference-ring-fill" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0" stop-color="#6b93ff" />
                  <stop offset="0.55" stop-color="#8cc4ff" />
                  <stop offset="1" stop-color="#7ce7ff" />
                </linearGradient>
              </defs>
              <circle class="ring-track" cx="60" cy="60" r="52" />
              <circle
                class="ring-value"
                cx="60"
                cy="60"
                r="52"
                pathLength="100"
                stroke-dasharray="100"
                :stroke-dashoffset="100 - progressPercent"
                transform="rotate(-90 60 60)"
              />
            </svg>
            <div class="ring-center">
              <b>{{ learnedCount }}</b>
              <span>/ {{ methodTotal }}</span>
              <em>已学习</em>
            </div>
          </div>
          <div class="progress-copy">
            <p class="progress-head"
              ><span>学习进度</span><b>{{ progressLabel }}%</b></p
            >
            <p class="progress-sub">
              已学习 {{ learnedCount }} 个 · 学习中 {{ studyingCount }} 个
            </p>
            <div class="progress-track" aria-hidden="true">
              <span :style="{ width: progressPercent + '%' }"></span>
            </div>
            <p class="progress-foot"> 已完成 {{ stageDone }} / {{ counts?.levels ?? 0 }} 个阶段 </p>
          </div>
          <dl class="hero-stats">
            <div>
              <dt><UiIcon name="learning-route" />阶段</dt>
              <dd>{{ counts?.levels ?? 0 }}</dd>
            </div>
            <div>
              <dt><UiIcon name="grid" />分类</dt>
              <dd>{{ counts?.categories ?? 0 }}</dd>
            </div>
            <div>
              <dt><UiIcon name="branch" />前置关系</dt>
              <dd>{{ counts?.prerequisite ?? 0 }}</dd>
            </div>
            <div>
              <dt><UiIcon name="sparkles" />可替代</dt>
              <dd>{{ counts?.alternative ?? 0 }}</dd>
            </div>
          </dl>
        </aside>
      </header>

      <div class="overview-board">
        <section class="stages-panel" aria-labelledby="stages-title">
          <header class="panel-top">
            <div class="panel-heading">
              <p class="panel-kicker">LEARNING PATH</p>
              <h3 id="stages-title">{{ counts?.levels ?? 0 }} 个学习阶段</h3>
            </div>
            <p class="panel-note">按前置关系排序 · 每个阶段是一段可独立完成的学习单元</p>
          </header>
          <ol class="stage-list" aria-label="学习阶段">
            <li
              v-for="(stage, index) in stages"
              :key="stage.level"
              class="stage-card"
              :class="{ 'is-wide': index === stages.length - 1 }"
              :style="{ '--row': index }"
            >
              <span class="stage-node" aria-hidden="true">{{ pad(stage.level) }}</span>
              <div class="stage-content">
                <div class="stage-heading">
                  <h4>{{ stage.name }}</h4>
                  <span class="stage-count" :class="{ 'is-active': stageLearned(stage) > 0 }">{{
                    stageLabel(stage)
                  }}</span>
                </div>
                <p class="stage-hint">{{ stage.hint }}</p>
                <div v-if="index === stages.length - 1" class="stage-groups">
                  <span v-for="group in stage.groups" :key="group">{{ group }}</span>
                </div>
              </div>
              <div
                class="stage-meter"
                role="progressbar"
                :aria-label="stage.name + ' 学习进度'"
                aria-valuemin="0"
                aria-valuemax="100"
                :aria-valuenow="Math.round(stagePercent(stage))"
              >
                <span :style="{ width: stagePercent(stage) + '%' }"></span>
              </div>
              <span v-if="index === stages.length - 1" class="stage-watermark" aria-hidden="true">{{
                pad(stage.level)
              }}</span>
            </li>
          </ol>
        </section>

        <aside class="directions-panel" aria-labelledby="directions-title">
          <header class="panel-top directions-head">
            <div class="panel-heading">
              <p class="panel-kicker">COVERAGE</p>
              <h3 id="directions-title">覆盖方向</h3>
            </div>
            <span class="panel-badge">{{ categories.length }} 个分类</span>
          </header>
          <ul class="directions-list">
            <li
              v-for="(category, index) in categories"
              :key="category.key"
              :style="{ '--cat': index }"
            >
              <div class="direction-row">
                <span class="direction-dot" aria-hidden="true"></span>
                <span class="direction-name">{{ category.name }}</span>
                <b>{{ category.count }}</b>
              </div>
              <div class="direction-track" aria-hidden="true">
                <i :style="{ width: (category.count / maxCategory) * 100 + '%' }"></i>
              </div>
            </li>
          </ul>
          <footer class="directions-foot">
            <span>{{ counts?.methods ?? 0 }} 个方法 · {{ counts?.groups ?? 0 }} 个方法组</span>
            <button type="button" class="directions-link" @click="$emit('enter')"
              >查看图谱<UiIcon name="arrow-up-right"
            /></button>
          </footer>
        </aside>
      </div>
    </div>
  </section>
</template>

<style scoped>
.reference-overview {
  --ro-bg: #f4f7fc;
  --ro-panel: rgb(255 255 255 / 0.92);
  --ro-panel-solid: #ffffff;
  --ro-line: #e7ecf6;
  --ro-line-soft: #eff3fa;
  --ro-text: #1a2233;
  --ro-text-2: #5f6b80;
  --ro-text-3: #758196;
  --ro-accent: #4f7cff;
  position: relative;
  min-width: 0;
  height: 100%;
  overflow: auto;
  background:
    radial-gradient(1100px 520px at 8% -16%, #e6eeff 0%, transparent 58%),
    radial-gradient(900px 460px at 102% -4%, #eaf6f1 0%, transparent 54%), var(--ro-bg);
  color: var(--ro-text);
}
:global(body[data-theme='dark'] .reference-overview) {
  --ro-bg: #0f1115;
  --ro-panel: rgb(27 28 32 / 0.92);
  --ro-panel-solid: #1b1c20;
  --ro-line: #2c2e34;
  --ro-line-soft: #24262b;
  --ro-text: #f2f5fa;
  --ro-text-2: #a7b0c0;
  --ro-text-3: #95a0b2;
  --ro-accent: #8ab4ff;
  background:
    radial-gradient(1100px 520px at 8% -16%, rgb(58 86 160 / 0.28) 0%, transparent 58%),
    radial-gradient(900px 460px at 102% -4%, rgb(38 96 82 / 0.2) 0%, transparent 54%), var(--ro-bg);
}
.overview-inner {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 100%;
  gap: 18px;
  padding: 26px 32px 24px;
}
.overview-loading {
  padding: 60px 10px;
  color: var(--ro-text-3);
  font-size: var(--dsw-text-sm);
}

/* Hero */
.overview-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 424px);
  align-items: center;
  gap: clamp(24px, 3.6vw, 58px);
  flex: none;
  padding: 30px 38px;
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 0.08);
  border-radius: 26px;
  background:
    radial-gradient(430px 300px at 88% 4%, rgb(84 132 255 / 0.42) 0%, transparent 70%),
    radial-gradient(340px 260px at 100% 96%, rgb(64 220 255 / 0.16) 0%, transparent 72%),
    linear-gradient(118deg, #0a1228 0%, #0d1b3c 52%, #102a5c 100%);
  box-shadow: 0 28px 60px -34px rgb(14 35 86 / 0.62);
  color: #f6f8ff;
  isolation: isolate;
  animation: overview-rise 480ms cubic-bezier(0.22, 1, 0.36, 1) both;
}
.hero-grid {
  position: absolute;
  inset: 0;
  z-index: -1;
  background-image:
    linear-gradient(rgb(255 255 255 / 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgb(255 255 255 / 0.035) 1px, transparent 1px);
  background-size: 34px 34px;
  -webkit-mask-image: linear-gradient(118deg, #000 0%, transparent 72%);
  mask-image: linear-gradient(118deg, #000 0%, transparent 72%);
}
.hero-glow {
  position: absolute;
  top: -180px;
  right: 24%;
  z-index: -1;
  width: 420px;
  height: 420px;
  border: 1px solid rgb(142 177 255 / 0.16);
  border-radius: 50%;
  box-shadow:
    0 0 0 46px rgb(142 177 255 / 0.05),
    0 0 0 92px rgb(142 177 255 / 0.03);
  pointer-events: none;
}
.hero-copy {
  position: relative;
  z-index: 1;
  min-width: 0;
  max-width: 850px;
}
.hero-eyebrow {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0 0 13px;
  color: #8fb6ff;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.2em;
  line-height: 1.4;
}
.eyebrow-rule {
  width: 24px;
  height: 1px;
  background: linear-gradient(90deg, #6b93ff, transparent);
}
.eyebrow-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgb(143 182 255 / 0.7);
}
.eyebrow-cn {
  letter-spacing: 0.14em;
  color: #a9c3f2;
}
.hero-title {
  margin: 0;
  font-size: clamp(30px, 2.25vw, 42px);
  font-weight: 600;
  letter-spacing: -0.028em;
  line-height: 1.2;
  color: #f7f9ff;
}
.hero-title em {
  padding: 0 0.05em;
  background: linear-gradient(96deg, #8fb8ff 0%, #d5e6ff 48%, #7ce7ff 100%);
  background-clip: text;
  color: transparent;
  font-style: normal;
  font-weight: 750;
  font-variant-numeric: tabular-nums;
}
.hero-lede {
  max-width: 720px;
  margin: 13px 0 0;
  color: #a8b7d4;
  font-size: 13px;
  line-height: 1.75;
}
.hero-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px 18px;
  margin-top: 21px;
}
.hero-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 40px;
  padding: 0 18px;
  border: 0;
  border-radius: 11px;
  background: #f6f9ff;
  color: #102046;
  font: inherit;
  font-size: var(--dsw-text-sm);
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: 0 10px 24px -10px rgb(3 10 28 / 0.7);
  transition:
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1),
    background 180ms ease,
    box-shadow 180ms ease;
}
.hero-cta:hover {
  background: #ffffff;
  box-shadow: 0 14px 30px -10px rgb(3 10 28 / 0.72);
  transform: translateY(-1px);
}
.hero-cta:active {
  transform: translateY(0);
}
.hero-cta svg {
  width: 14px;
  height: 14px;
}
.hero-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #8ea3c8;
  font-size: var(--dsw-text-xs);
}
.hero-hint svg {
  width: 13px;
  height: 13px;
  color: #7fb0ff;
}

/* Hero progress */
.hero-progress {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 16px 20px;
  min-width: 0;
  padding: 18px;
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 20px;
  background: linear-gradient(155deg, rgb(255 255 255 / 0.09), rgb(255 255 255 / 0.025));
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.08);
  backdrop-filter: blur(10px);
}
.progress-ring {
  position: relative;
  width: 112px;
  height: 112px;
  flex: none;
}
.progress-ring svg {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.ring-track {
  fill: none;
  stroke: rgb(255 255 255 / 0.1);
  stroke-width: 8;
}
.ring-value {
  fill: none;
  stroke: url(#reference-ring-fill);
  stroke-width: 8;
  stroke-linecap: round;
  filter: drop-shadow(0 0 6px rgb(110 160 255 / 0.55));
  transition: stroke-dashoffset 900ms cubic-bezier(0.22, 1, 0.36, 1);
}
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  line-height: 1;
}
.ring-center b {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}
.ring-center span {
  color: #9fb3d8;
  font-size: 10px;
  letter-spacing: 0.04em;
}
.ring-center em {
  margin-top: 5px;
  color: #8096bd;
  font-size: 9px;
  font-style: normal;
  letter-spacing: 0.12em;
}
.progress-copy {
  min-width: 0;
}
.progress-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 0;
  color: #cfdcf6;
  font-size: var(--dsw-text-xs);
}
.progress-head b {
  color: #eff5ff;
  font-size: 19px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.progress-sub {
  margin: 5px 0 0;
  color: #8ea3c8;
  font-size: 10.5px;
  line-height: 1.5;
}
.progress-track {
  height: 4px;
  margin-top: 11px;
  overflow: hidden;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.1);
}
.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #5f8dff, #7ce7ff);
  transition: width 900ms cubic-bezier(0.22, 1, 0.36, 1);
}
.progress-foot {
  margin: 8px 0 0;
  color: #7f94ba;
  font-size: 10px;
  letter-spacing: 0.02em;
}
.hero-stats {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 4px;
  margin: 0;
  padding-top: 14px;
  border-top: 1px solid rgb(255 255 255 / 0.08);
}
.hero-stats > div {
  min-width: 0;
  padding: 0 8px;
  border-left: 1px solid rgb(255 255 255 / 0.07);
}
.hero-stats > div:first-child {
  padding-left: 0;
  border-left: 0;
}
.hero-stats dt {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #8ea3c8;
  font-size: 10px;
  line-height: 1.4;
  white-space: nowrap;
}
.hero-stats dt svg {
  width: 12px;
  height: 12px;
  color: #7fa6ef;
}
.hero-stats dd {
  margin: 3px 0 0;
  color: #f4f8ff;
  font-size: 18px;
  font-weight: 650;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

/* Board */
.overview-board {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 336px;
  align-items: stretch;
  gap: 18px;
  flex: 1;
  min-height: 0;
}
.stages-panel,
.directions-panel {
  position: relative;
  min-width: 0;
  border: 1px solid var(--ro-line);
  border-radius: 20px;
  background: var(--ro-panel);
  box-shadow:
    0 1px 2px rgb(20 40 80 / 0.03),
    0 22px 44px -38px rgb(20 40 80 / 0.3);
  backdrop-filter: blur(8px);
}
.stages-panel {
  display: flex;
  flex-direction: column;
  padding: 16px 18px 18px;
  animation: overview-rise 520ms cubic-bezier(0.22, 1, 0.36, 1) 60ms both;
}
.directions-panel {
  display: flex;
  flex-direction: column;
  padding: 18px 20px 16px;
  animation: overview-rise 520ms cubic-bezier(0.22, 1, 0.36, 1) 120ms both;
}
.panel-top {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 1px 3px 13px;
}
.panel-heading {
  min-width: 0;
}
.panel-kicker {
  margin: 0 0 4px;
  color: var(--ro-text-3);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.18em;
  line-height: 1.3;
}
.panel-heading h3 {
  margin: 0;
  color: var(--ro-text);
  font-size: 16px;
  font-weight: 650;
  letter-spacing: -0.015em;
  line-height: 1.3;
}
.panel-note {
  max-width: 360px;
  margin: 0;
  color: var(--ro-text-3);
  font-size: 10.5px;
  line-height: 1.55;
  text-align: right;
}
.panel-badge {
  flex: none;
  padding: 4px 9px;
  border: 1px solid var(--ro-line);
  border-radius: 999px;
  background: var(--ro-line-soft);
  color: var(--ro-text-2);
  font-size: 10px;
  line-height: 1.4;
  white-space: nowrap;
}

/* Stages */
.stage-list {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  align-content: start;
  gap: 14px 11px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.stage-card {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) auto;
  column-gap: 10px;
  min-width: 0;
  min-height: 106px;
  padding: 12px 14px 11px;
  overflow: hidden;
  border: 1px solid var(--ro-line);
  border-radius: 14px;
  background: linear-gradient(
    180deg,
    var(--ro-panel-solid),
    color-mix(in srgb, var(--ro-panel-solid) 94%, #eef4ff)
  );
  box-shadow: 0 1px 2px rgb(20 40 80 / 0.03);
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
  animation: stage-in 420ms cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: calc(80ms + var(--row) * 24ms);
}
.stage-card:hover {
  border-color: color-mix(in srgb, var(--ro-accent) 32%, var(--ro-line));
  box-shadow: 0 12px 26px -18px rgb(27 58 130 / 0.42);
  transform: translateY(-2px);
}
.stage-node {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid color-mix(in srgb, var(--ro-accent) 18%, transparent);
  border-radius: 8px;
  background: linear-gradient(
    140deg,
    color-mix(in srgb, var(--ro-accent) 12%, var(--ro-panel-solid)),
    color-mix(in srgb, var(--ro-accent) 5%, var(--ro-panel-solid))
  );
  color: color-mix(in srgb, var(--ro-accent) 12%, #2455c4);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
:global(body[data-theme='dark'] .stage-node) {
  color: #a9c6ff;
}
.stage-content {
  min-width: 0;
}
.stage-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}
.stage-heading h4 {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--ro-text);
  font-size: 13.5px;
  font-weight: 650;
  letter-spacing: -0.005em;
  line-height: 1.55;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stage-count {
  flex: none;
  color: var(--ro-text-2);
  font-size: 10.5px;
  line-height: 1.5;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.stage-count.is-active {
  color: var(--ro-accent);
  font-weight: 600;
}
.stage-hint {
  display: -webkit-box;
  margin: 4px 0 0;
  overflow: hidden;
  color: var(--ro-text-2);
  font-size: 11px;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.stage-meter {
  grid-column: 1 / -1;
  height: 3px;
  margin-top: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--ro-line) 72%, transparent);
}
.stage-meter span {
  display: block;
  width: 0;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--ro-accent), #6fe0ef);
  transition: width 800ms cubic-bezier(0.22, 1, 0.36, 1);
}
.stage-card.is-wide {
  grid-column: 1 / -1;
  grid-template-columns: auto minmax(0, 1fr);
  min-height: 86px;
  padding: 13px 16px 12px;
  border-color: color-mix(in srgb, var(--ro-accent) 16%, var(--ro-line));
  background:
    radial-gradient(
      420px 140px at 92% 0%,
      color-mix(in srgb, var(--ro-accent) 10%, transparent) 0%,
      transparent 70%
    ),
    linear-gradient(
      105deg,
      color-mix(in srgb, var(--ro-accent) 4%, var(--ro-panel-solid)),
      var(--ro-panel-solid)
    );
}
.stage-card.is-wide .stage-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 2px 24px;
}
.stage-card.is-wide .stage-heading,
.stage-card.is-wide .stage-hint {
  grid-column: 1;
}
.stage-groups {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  grid-column: 2;
  grid-row: 1 / span 2;
  gap: 5px;
}
.stage-groups span {
  padding: 3px 8px;
  border: 1px solid color-mix(in srgb, var(--ro-accent) 14%, var(--ro-line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--ro-accent) 5%, var(--ro-panel-solid));
  color: var(--ro-text-2);
  font-size: 9.5px;
  line-height: 1.4;
  white-space: nowrap;
}
.stage-watermark {
  position: absolute;
  right: 12px;
  top: 50%;
  z-index: 0;
  color: color-mix(in srgb, var(--ro-accent) 6%, transparent);
  font-size: 78px;
  font-weight: 800;
  letter-spacing: -0.06em;
  line-height: 1;
  transform: translateY(-50%);
  pointer-events: none;
  user-select: none;
}
.stage-card.is-wide .stage-content,
.stage-card.is-wide .stage-meter {
  position: relative;
  z-index: 1;
}

/* Directions */
.directions-head {
  align-items: center;
  padding-bottom: 12px;
}
.directions-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}
.directions-list li {
  padding: 7px 0 8px;
  border-top: 1px solid var(--ro-line-soft);
}
.directions-list li:first-child {
  border-top: 0;
}
.direction-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.direction-dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: hsl(calc(212 + var(--cat) * 6) 72% 58%);
  box-shadow: 0 0 0 3px hsl(calc(212 + var(--cat) * 6) 72% 58% / 0.1);
}
.direction-name {
  min-width: 0;
  overflow: hidden;
  color: var(--ro-text-2);
  font-size: 11.5px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.direction-row b {
  margin-left: auto;
  color: var(--ro-text);
  font-size: 11.5px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.direction-track {
  height: 3px;
  margin: 5px 0 0 14px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--ro-line) 68%, transparent);
}
.direction-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    hsl(calc(212 + var(--cat) * 6) 72% 62%),
    hsl(calc(220 + var(--cat) * 6) 80% 72%)
  );
}
.directions-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--ro-line-soft);
  color: var(--ro-text-3);
  font-size: 10px;
}
.directions-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 2px;
  border: 0;
  background: transparent;
  color: var(--ro-accent);
  font: inherit;
  font-size: 10.5px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}
.directions-link:hover {
  color: color-mix(in srgb, var(--ro-accent) 80%, #000);
}
.directions-link svg {
  width: 12px;
  height: 12px;
}

:focus-visible {
  outline: 2px solid var(--ro-accent);
  outline-offset: 2px;
}

@keyframes overview-rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@keyframes stage-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1599px) {
  .overview-inner {
    padding: 24px 26px 22px;
  }
  .overview-hero {
    grid-template-columns: minmax(0, 1fr) minmax(340px, 400px);
    gap: 30px;
    padding: 28px 30px;
  }
  .overview-board {
    grid-template-columns: minmax(0, 1fr) 310px;
  }
}
@media (max-width: 1399px) {
  .overview-board {
    grid-template-columns: minmax(0, 1fr);
  }
  .directions-panel {
    padding-bottom: 18px;
  }
  .directions-list {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0 22px;
  }
  .directions-list li {
    border-top: 1px solid var(--ro-line-soft);
  }
  .directions-list li:nth-child(-n + 3) {
    border-top: 0;
  }
}
@media (max-width: 1249px) {
  .overview-hero {
    grid-template-columns: minmax(0, 1fr);
    align-items: stretch;
    gap: 22px;
  }
  .hero-copy {
    max-width: none;
  }
  .hero-progress {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .hero-title {
    font-size: 34px;
  }
}
@media (max-width: 900px) {
  .overview-inner {
    gap: 14px;
    padding: 18px 16px 20px;
  }
  .overview-hero {
    padding: 24px 22px;
    border-radius: 20px;
  }
  .hero-title {
    font-size: 30px;
  }
  .hero-lede {
    font-size: 12.5px;
  }
  .stage-list {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
  .panel-top {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }
  .panel-note {
    max-width: none;
    text-align: left;
  }
  .directions-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .directions-list li:nth-child(3) {
    border-top: 1px solid var(--ro-line-soft);
  }
  .directions-list li:nth-child(-n + 2) {
    border-top: 0;
  }
  .stage-card.is-wide .stage-content {
    grid-template-columns: minmax(0, 1fr);
  }
  .stage-groups {
    grid-column: 1;
    grid-row: auto;
    justify-content: flex-start;
    margin-top: 4px;
  }
  .stage-watermark {
    display: none;
  }
}
@media (max-width: 640px) {
  .overview-inner {
    padding: 14px 12px 18px;
  }
  .overview-hero {
    padding: 22px 18px;
  }
  .hero-title {
    font-size: 26px;
  }
  .hero-eyebrow {
    font-size: 9px;
    letter-spacing: 0.16em;
  }
  .hero-actions {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
  .hero-progress {
    grid-template-columns: minmax(0, 1fr);
    justify-items: center;
    padding: 16px;
  }
  .progress-copy {
    width: 100%;
  }
  .hero-stats {
    width: 100%;
  }
  .hero-stats > div {
    padding: 0 4px;
  }
  .hero-stats dd {
    font-size: 16px;
  }
  .stages-panel,
  .directions-panel {
    padding-inline: 14px;
  }
  .stage-list {
    grid-template-columns: minmax(0, 1fr);
  }
  .directions-list {
    grid-template-columns: minmax(0, 1fr);
  }
  .directions-list li:nth-child(2) {
    border-top: 1px solid var(--ro-line-soft);
  }
  .directions-list li:nth-child(-n + 1) {
    border-top: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .overview-hero,
  .stages-panel,
  .directions-panel,
  .stage-card {
    animation: none;
  }
  .ring-value,
  .progress-track span,
  .stage-meter span {
    transition: none;
  }
  .stage-card:hover,
  .hero-cta:hover {
    transform: none;
  }
}
</style>
