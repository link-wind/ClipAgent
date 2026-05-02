'use client';

import { useEffect } from 'react';
import { getAgentSession } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';
import AgentChat from './AgentChat';
import PlanPanel from './PlanPanel';
import ProgressPanel from './ProgressPanel';
import ResultPanel from './ResultPanel';
import styles from './AgentWorkspace.module.css';

const SETTLED_STATUSES = new Set(['idle', 'plan_ready', 'done', 'failed']);

const STATUS_LABELS: Record<string, string> = {
  idle: '等待',
  planning: '规划',
  plan_ready: '待确认',
  searching: '搜索中',
  downloading: '下载中',
  rendering: '渲染中',
  done: '完成',
  failed: '失败',
};

export default function AgentWorkspace() {
  const session = useAgentStore((state) => state.session);
  const setSession = useAgentStore((state) => state.setSession);

  useEffect(() => {
    if (!session || SETTLED_STATUSES.has(session.status)) {
      return;
    }

    let isActive = true;

    const pollSession = async () => {
      try {
        const nextSession = await getAgentSession(session.id);
        if (isActive) {
          setSession(nextSession);
        }
      } catch {
        // 轮询失败不覆盖当前会话，交互错误由聊天组件展示。
      }
    };

    const intervalId = window.setInterval(pollSession, 2000);
    return () => {
      isActive = false;
      window.clearInterval(intervalId);
    };
  }, [session, setSession]);

  return (
    <div className={styles.workspace}>
      <header className={styles.header}>
        <div>
          <h1>ClipForge Agent</h1>
          <p>{session?.currentStep || '等待需求'}</p>
        </div>
        <span className={styles.statusPill}>{STATUS_LABELS[session?.status || 'idle']}</span>
      </header>

      <main className={styles.main}>
        <section className={styles.chatColumn} aria-label="Agent 对话">
          <AgentChat />
        </section>
        <aside className={styles.panelColumn} aria-label="Agent 工作状态">
          <PlanPanel />
          <ProgressPanel />
          <ResultPanel />
        </aside>
      </main>
    </div>
  );
}
