'use client';

import type { AgentStatus } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';
import styles from './ProgressPanel.module.css';

const STEPS: AgentStatus[] = ['planning', 'plan_ready', 'searching', 'downloading', 'rendering', 'done', 'failed'];

const STEP_LABELS: Record<AgentStatus, string> = {
  idle: '等待',
  planning: '规划',
  plan_ready: '待确认',
  searching: '搜索',
  downloading: '下载',
  rendering: '渲染',
  done: '完成',
  failed: '失败',
};

export default function ProgressPanel() {
  const session = useAgentStore((state) => state.session);
  const status = session?.status ?? 'idle';
  const progress = Math.max(0, Math.min(100, session?.progress ?? 0));

  return (
    <section className={styles.panel}>
      <div className={styles.heading}>
        <h2>执行进度</h2>
        <span>{progress}%</span>
      </div>

      <div className={styles.progressTrack} aria-label="当前进度">
        <div className={styles.progressBar} style={{ width: `${progress}%` }} />
      </div>

      <dl className={styles.current}>
        <div>
          <dt>状态</dt>
          <dd>{STEP_LABELS[status]}</dd>
        </div>
        <div>
          <dt>当前步骤</dt>
          <dd>{session?.currentStep || '等待需求'}</dd>
        </div>
      </dl>

      <ol className={styles.steps}>
        {STEPS.map((step) => (
          <li key={step} className={step === status ? styles.active : ''}>
            <span />
            {STEP_LABELS[step]}
          </li>
        ))}
      </ol>
    </section>
  );
}
