'use client';

import { useEffect, useRef } from 'react';
import { getAgentSession, getAgentSessionEvents, isTerminalTraceEvent, subscribeAgentSessionTrace } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';
import AgentChat from './AgentChat';
import PlanPanel from './PlanPanel';
import ProgressPanel from './ProgressPanel';
import ResultPanel from './ResultPanel';
import { resolveSessionVideoUrl } from './sessionMedia';
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

const TRACE_STATUS_LABELS: Record<string, string> = {
  running: '进行中',
  succeeded: '已完成',
  failed: '失败',
};

export default function AgentWorkspace() {
  const session = useAgentStore((state) => state.session);
  const activeSessionId = useAgentStore((state) => state.activeSessionId);
  const setSession = useAgentStore((state) => state.setSession);
  const appendTraceEvent = useAgentStore((state) => state.appendTraceEvent);
  const lastTraceSequence = useAgentStore((state) => state.lastTraceSequence);
  const setStreamState = useAgentStore((state) => state.setStreamState);
  const currentTraceStream = useAgentStore((state) => state.currentTraceStream);
  const videoUrl = resolveSessionVideoUrl(session);
  const sceneCount = session?.plan?.scenes.length ?? 0;
  const targetDuration = session?.plan?.targetDuration ?? null;
  const sessionId = session?.id ?? null;
  const sessionStatus = session?.status ?? 'idle';
  const lastTraceSequenceRef = useRef(lastTraceSequence);

  useEffect(() => {
    lastTraceSequenceRef.current = lastTraceSequence;
  }, [lastTraceSequence]);

  const refreshSessionSnapshot = async (targetSessionId: string) => {
    const [nextSession, nextEvents] = await Promise.all([
      getAgentSession(targetSessionId),
      getAgentSessionEvents(targetSessionId),
    ]);
    setSession({ ...nextSession, events: nextEvents });
  };

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
        }
      } catch {
        // 恢复失败时保留当前空白状态，避免打断用户继续发起新会话。
      }
    };

    void restoreSession();
    return () => {
      isActive = false;
    };
  }, [activeSessionId, session, setSession]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    let isActive = true;
    setStreamState('connecting');
    const subscription = subscribeAgentSessionTrace(
      sessionId,
      {
        onEvent: (event) => {
          if (!isActive) {
            return;
          }

          setStreamState('open');
          appendTraceEvent(event);
          if (isTerminalTraceEvent(event.eventType)) {
            void refreshSessionSnapshot(sessionId);
          }
        },
        onClosed: () => {
          if (isActive) {
            setStreamState('closed');
            void refreshSessionSnapshot(sessionId);
          }
        },
        onError: () => {
          if (isActive) {
            setStreamState('error');
            if (RUNNING_STATUSES.has(sessionStatus)) {
              void refreshSessionSnapshot(sessionId);
            }
          }
        },
      },
      lastTraceSequenceRef.current
    );

    return () => {
      isActive = false;
      setStreamState('closed');
      subscription.close();
    };
  }, [appendTraceEvent, sessionId, sessionStatus, setSession, setStreamState]);

  useEffect(() => {
    if (!sessionId || !RUNNING_STATUSES.has(sessionStatus)) {
      return;
    }

    let isActive = true;

    const pollSession = async () => {
      try {
        const [nextSession, nextEvents] = await Promise.all([
          getAgentSession(sessionId),
          getAgentSessionEvents(sessionId),
        ]);
        if (isActive) {
          setSession({ ...nextSession, events: nextEvents });
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
  }, [sessionId, sessionStatus, setSession]);

  return (
    <div className={styles.workspace}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true" />
          <div>
            <h1>ClipForge Agent</h1>
            <p>{currentTraceStream?.message || session?.currentStep || '等待需求'}</p>
          </div>
        </div>
        <div className={styles.headerStatus}>
          {currentTraceStream ? (
            <div className={styles.traceStatus} data-status={currentTraceStream.status} aria-label="实时执行状态">
              <div className={styles.traceStatusMeta}>
                <span>{currentTraceStream.label}</span>
                <strong>{Math.round(currentTraceStream.progress * 100)}%</strong>
              </div>
              <div className={styles.traceProgress} aria-hidden="true">
                <span style={{ width: `${Math.round(currentTraceStream.progress * 100)}%` }} />
              </div>
              <p>
                <span>{currentTraceStream.message}</span>
                <strong>{TRACE_STATUS_LABELS[currentTraceStream.status] || currentTraceStream.status}</strong>
              </p>
            </div>
          ) : null}
          <span className={styles.statusPill}>{STATUS_LABELS[session?.status || 'idle']}</span>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.canvasColumn} aria-label="Agent 创作画布">
          <section className={styles.previewPanel} aria-label="结果预览">
            <div className={styles.previewFrame}>
              {videoUrl ? (
                <video src={videoUrl} controls preload="metadata" />
              ) : (
                <div className={styles.previewEmpty}>
                  <span className={styles.previewBadge}>RESULT PREVIEW</span>
                  <h2>{session?.plan?.title || '你的成片会出现在这里'}</h2>
                  <p>
                    {session?.plan
                      ? `${session.plan.style} · ${session.plan.targetDuration} 秒 · ${session.plan.scenes.length} 个场景`
                      : '描述主题、风格、时长和素材偏好后，Agent 会先生成剪辑计划。'}
                  </p>
                </div>
              )}
            </div>

            <div className={styles.previewInfo}>
              <span className={styles.previewEyebrow}>CREATOR CANVAS</span>
              <h2>{session?.plan?.title || '把一个想法锻造成短视频'}</h2>
              <p>
                {session?.currentStep ||
                  '从需求、计划、素材到最终视频，ClipForge 会把每一步创作过程呈现在同一个工作台里。'}
              </p>
              <div className={styles.previewStats}>
                <div>
                  <strong>{targetDuration ? `${targetDuration}s` : '--'}</strong>
                  <span>目标时长</span>
                </div>
                <div>
                  <strong>{sceneCount || '--'}</strong>
                  <span>场景</span>
                </div>
                <div>
                  <strong>{session?.progress ?? 0}%</strong>
                  <span>进度</span>
                </div>
              </div>
            </div>
          </section>

          <section className={styles.chatColumn} aria-label="Agent 对话">
            <AgentChat />
          </section>
        </section>

        <aside className={styles.panelColumn} aria-label="Agent 工作状态">
          <ProgressPanel />
          <PlanPanel />
          <ResultPanel />
        </aside>
      </main>
    </div>
  );
}
