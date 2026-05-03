'use client';

import { useEffect } from 'react';
import { getAgentSession, getAgentSessionEvents } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';
import AgentChat from './AgentChat';
import PlanPanel from './PlanPanel';
import ProgressPanel from './ProgressPanel';
import ResultPanel from './ResultPanel';
import styles from './AgentWorkspace.module.css';

const RUNNING_STATUSES = new Set(['queued', 'searching', 'downloading', 'rendering']);

const STATUS_LABELS: Record<string, string> = {
  idle: '等待',
  queued: '排队中',
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
  const activeSessionId = useAgentStore((state) => state.activeSessionId);
  const setSession = useAgentStore((state) => state.setSession);
  const setEvents = useAgentStore((state) => state.setEvents);

  useEffect(() => {
    if (!activeSessionId || session) {
      return;
    }

    let isActive = true;

    const restoreSession = async () => {
      try {
        const [nextSession, nextEvents] = await Promise.all([
          getAgentSession(activeSessionId),
          getAgentSessionEvents(activeSessionId),
        ]);
        if (isActive) {
          setSession({ ...nextSession, events: nextEvents });
          setEvents(nextEvents);
        }
      } catch {
        // 恢复失败时保留当前空白状态，避免打断用户继续发起新会话。
      }
    };

    void restoreSession();
    return () => {
      isActive = false;
    };
  }, [activeSessionId, session, setEvents, setSession]);

  useEffect(() => {
    if (!session || !RUNNING_STATUSES.has(session.status)) {
      return;
    }

    let isActive = true;

    const pollSession = async () => {
      try {
        const [nextSession, nextEvents] = await Promise.all([
          getAgentSession(session.id),
          getAgentSessionEvents(session.id),
        ]);
        if (isActive) {
          setSession({ ...nextSession, events: nextEvents });
          setEvents(nextEvents);
        }
      } catch {
        // 轮询失败不覆盖当前会话，交互错误由聊天组件展示。
      }
    };

    void pollSession();
    const intervalId = window.setInterval(pollSession, 2000);
    return () => {
      isActive = false;
      window.clearInterval(intervalId);
    };
  }, [session, setEvents, setSession]);

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
