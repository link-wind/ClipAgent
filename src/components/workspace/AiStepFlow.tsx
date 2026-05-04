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

function getStepIndex(status: string) {
  const index = STEP_ORDER.indexOf(status as (typeof STEP_ORDER)[number]);
  return index === -1 ? 0 : index;
}

export default function AiStepFlow() {
  const session = useAgentStore((state) => state.session);
  const status = session?.status ?? 'idle';
  const progress = Math.max(0, Math.min(100, session?.progress ?? 0));
  const currentStep = session?.currentStep || '等待你描述需求';
  const activeStepIndex = getStepIndex(status);

  return (
    <section className={styles.flow} aria-label="AI 步骤进度">
      <div className={styles.header}>
        <div>
          <span className={styles.eyebrow}>AI STEP FLOW</span>
          <h2>先看进度，再看每一步结果</h2>
        </div>
        <div className={styles.progressLabel}>
          <strong>{progress}%</strong>
          <span>{currentStep}</span>
        </div>
      </div>

      <div className={styles.progressTrack} aria-label="方案进度">
        <div className={styles.progressBar} style={{ width: `${progress}%` }} />
      </div>

      <ol className={styles.steps}>
        {STEPS.map((step, index) => {
          const isComplete = index < activeStepIndex || status === 'done';
          const isActive = step.key === status;
          const isFailed = status === 'failed' && step.key === 'failed';

          return (
            <li
              key={step.key}
              className={[
                styles.step,
                isComplete ? styles.stepComplete : '',
                isActive ? styles.stepActive : '',
                isFailed ? styles.stepFailed : '',
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
                  <span>{isComplete || isActive ? '已展开' : '等待中'}</span>
                </div>
                <p>{step.summary}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
