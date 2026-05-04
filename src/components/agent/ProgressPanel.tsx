'use client';

import type { AgentStatus } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';
import styles from './ProgressPanel.module.css';

const STEPS: AgentStatus[] = ['queued', 'planning', 'plan_ready', 'searching', 'downloading', 'rendering', 'done', 'failed'];
const RECENT_EVENT_LIMIT = 5;

const STEP_LABELS: Record<AgentStatus, string> = {
  idle: '等待',
  queued: '排队中',
  planning: '规划',
  plan_ready: '待确认',
  searching: '搜索',
  downloading: '下载',
  rendering: '渲染',
  done: '完成',
  failed: '失败',
};

const EVENT_MESSAGE_LABELS: Record<string, string> = {
  render_captioning: '正在合成字幕',
  render_audio_mix: '正在混合背景音乐',
};

export default function ProgressPanel() {
  const session = useAgentStore((state) => state.session);
  const status = session?.status ?? 'idle';
  const progress = Math.max(0, Math.min(100, session?.progress ?? 0));
  const recentEvents = session?.events?.slice(-RECENT_EVENT_LIMIT) ?? [];

  return (
    <section className={styles.panel}>
      <div className={styles.heading}>
        <h2>执行进度</h2>
        <span>{progress}%</span>
      </div>

      <div className={styles.metrics}>
        <div>
          <strong>{session?.plan?.targetDuration ? `${session.plan.targetDuration}s` : '--'}</strong>
          <span>目标时长</span>
        </div>
        <div>
          <strong>{session?.plan?.scenes.length ?? '--'}</strong>
          <span>场景</span>
        </div>
        <div>
          <strong>{STEP_LABELS[status]}</strong>
          <span>状态</span>
        </div>
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

      {recentEvents.length > 0 ? (
        <ol className={styles.steps}>
          {recentEvents.map((event) => (
            <li key={event.id}>
              <span />
              {event.message || EVENT_MESSAGE_LABELS[event.eventType] || event.eventType}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
