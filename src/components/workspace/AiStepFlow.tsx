'use client';

import { useAgentStore } from '@/stores/useAgentStore';
import styles from './AiStepFlow.module.css';

const STEPS = [
  { key: 'queued', label: '排队中', summary: '已接收需求，准备进入规划。' },
  { key: 'planning', label: '规划中', summary: '正在拆解目标、风格和执行结构。' },
  { key: 'plan_ready', label: '待确认', summary: '方案已生成，等待你确认后继续。' },
  { key: 'searching', label: '搜索中', summary: '开始整理素材线索和检索方向。' },
  { key: 'downloading', label: '下载中', summary: '正在拉取可用素材和资源。' },
  { key: 'rendering', label: '渲染中', summary: '正在组装成片并输出预览。' },
  { key: 'done', label: '完成', summary: '结果已经生成，可以回看。' },
  { key: 'failed', label: '失败', summary: '当前步骤中断，等待重新确认。' },
] as const;

const STEP_ORDER = STEPS.map((step) => step.key);

type StepKey = (typeof STEPS)[number]['key'];

type ConversationalStepCard = {
  key: StepKey;
  label: string;
  statusText: string;
  message: string;
  progress: number;
  isComplete: boolean;
  isActive: boolean;
  isFailed: boolean;
  isVisible: boolean;
  isPlaceholder: boolean;
};

function clampProgress(value: number) {
  return Math.max(0, Math.min(100, value));
}

function buildStepMessage(step: (typeof STEPS)[number], index: number, activeStepIndex: number) {
  if (index < activeStepIndex) {
    return `我已经完成${step.label}，${step.summary}`;
  }
  if (index === activeStepIndex) {
    return `我正在处理${step.label}，${step.summary}`;
  }
  return '下一张卡片会在当前步骤完成后出现。';
}

function getStepIndex(status: string) {
  const index = STEP_ORDER.indexOf(status as (typeof STEP_ORDER)[number]);
  return index === -1 ? 0 : index;
}

function buildConversationalStepCards(status: string, progress: number) {
  const activeStepIndex = getStepIndex(status);

  return STEPS.map((step, index) => {
    const isComplete = index < activeStepIndex || status === 'done';
    const isActive = step.key === status;
    const isFailed = status === 'failed' && step.key === 'failed';
    const isVisible = index <= activeStepIndex;
    const isPlaceholder = index === activeStepIndex + 1 && status !== 'done' && status !== 'failed';
    const stepProgress = isComplete ? 100 : isActive ? clampProgress(progress) : 0;

    return {
      key: step.key,
      label: step.label,
      statusText: isComplete ? '已完成' : isActive ? '进行中' : '等待中',
      message: isPlaceholder
        ? '下一张卡片会在当前步骤完成后出现。'
        : buildStepMessage(step, index, activeStepIndex),
      progress: stepProgress,
      isComplete,
      isActive,
      isFailed,
      isVisible,
      isPlaceholder,
    };
  }).filter((card) => card.isVisible || card.isPlaceholder);
}

export default function AiStepFlow() {
  const session = useAgentStore((state) => state.session);
  const status = session?.status ?? 'idle';
  const totalProgress = clampProgress(session?.progress ?? 0);
  const currentStep = session?.currentStep || '等待你描述需求';
  const cards = buildConversationalStepCards(status, totalProgress);

  return (
    <section className={styles.flow} aria-label="AI 步骤进度">
      <div className={styles.header}>
        <div>
          <span className={styles.eyebrow}>AI STEP FLOW</span>
          <h2>先看进度，再看每一步结果</h2>
        </div>
        <div className={styles.progressLabel}>
          <strong>{totalProgress}%</strong>
          <span>{currentStep}</span>
        </div>
      </div>

      <div className={styles.progressTrack} aria-label="方案进度">
        <div className={styles.progressBar} style={{ width: `${totalProgress}%` }} />
      </div>

      <ol className={styles.steps}>
        {/* 只展示已经开始或已经完成的步骤 */}
        {cards.map((step) => (
          <li
            key={step.key}
            className={[
              styles.step,
              step.isComplete ? styles.stepComplete : '',
              step.isActive ? styles.stepActive : '',
              step.isFailed ? styles.stepFailed : '',
              step.isPlaceholder ? styles.stepPlaceholder : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <div className={styles.stepMark} aria-hidden="true">
              <span />
            </div>
            <div className={styles.stepBody}>
              <div className={styles.stepTitleRow}>
                <h3>{step.label}</h3>
                <span>{step.statusText}</span>
              </div>
              <p>{step.message}</p>
              <div className={styles.stepProgress}>
                <div className={styles.stepProgressMeta}>
                  <span>步骤进度</span>
                  <span>{step.progress}%</span>
                </div>
                <div className={styles.stepProgressTrack}>
                  <div className={styles.stepProgressBar} style={{ width: `${step.progress}%` }} />
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
