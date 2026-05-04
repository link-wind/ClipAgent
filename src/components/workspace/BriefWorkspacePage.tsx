'use client';

import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import Button from '@/components/common/Button';
import {
  confirmAgentSession,
  createAgentSession,
  getAgentSession,
  getAgentSessionEvents,
  sendAgentMessage,
  type AgentSession,
} from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';
import styles from './BriefWorkspacePage.module.css';

const RUNNING_STATUSES = new Set(['queued', 'searching', 'downloading', 'rendering']);

const DIRECTION_OPTIONS = [
  {
    id: 'A',
    name: '高效团队叙事',
    summary: '从团队会议后的自然工作场景切入，强调信息被自动整理、沉淀和复用。',
    tags: ['专业可信', '官网首屏', '低风险'],
  },
  {
    id: 'B',
    name: '问题到结果转化',
    summary: '先展示轻量问题，再转向 AI 自动总结、行动项同步和团队知识沉淀。',
    tags: ['转化强', '销售演示', '结构清晰'],
  },
  {
    id: 'C',
    name: '产品能力展示',
    summary: '更直接地展示界面和能力点，适合功能说明或产品更新场景。',
    tags: ['功能清晰', '偏说明', '信息密度高'],
  },
] as const;

const STEP_DEFINITIONS = [
  {
    id: 'understand',
    title: '步骤 1：理解原始需求',
    progress: 100,
    buildResult: (session: AgentSession | null) => [
      { label: '原始诉求', value: session?.messages.find((item) => item.role === 'user')?.content || '等待输入' },
      { label: '推断目标', value: session?.plan ? `${session.plan.title} 的宣传表达` : '待分析' },
      { label: '基调判断', value: session?.plan?.style || '专业可信' },
    ],
  },
  {
    id: 'constraints',
    title: '步骤 2：提炼目标与限制条件',
    progress: 100,
    buildResult: (session: AgentSession | null) => [
      { label: '建议时长', value: session?.plan ? `${session.plan.targetDuration} 秒` : '待分析' },
      { label: '执行结构', value: session?.plan ? `${session.plan.scenes.length} 个段落` : '待分析' },
      { label: '当前状态', value: session?.currentStep || '等待需求进入系统' },
    ],
  },
  {
    id: 'directions',
    title: '步骤 3：生成多个方案方向',
    progress: 100,
  },
  {
    id: 'final',
    title: '步骤 4：输出最终执行方案',
    progress: 100,
  },
] as const;

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function toUserError(error: unknown, resetSession: () => void) {
  const message = error instanceof Error ? error.message : '请求失败，请稍后重试。';
  if (message.includes('Session not found')) {
    resetSession();
    return '会话已失效，可能是后端刚刚重启了。请重新发送需求生成新方案。';
  }
  return message;
}

function getWorkspaceStatus(session: AgentSession | null) {
  if (!session) {
    return '等待输入';
  }
  if (session.status === 'plan_ready') {
    return '等待确认';
  }
  if (session.status === 'done') {
    return '已完成';
  }
  if (session.status === 'failed') {
    return '需处理';
  }
  return '处理中';
}

function buildFinalPlanSummary(session: AgentSession | null, selectedDirection: string) {
  return [
    { label: '方案方向', value: `${selectedDirection} / ${DIRECTION_OPTIONS.find((item) => item.id === selectedDirection)?.name ?? '待选择'}` },
    { label: '时长节奏', value: session?.plan ? `${session.plan.targetDuration} 秒` : '待确认' },
    { label: '风格方向', value: session?.plan?.style || '专业可信' },
    { label: '输出目标', value: session?.status === 'done' ? '已输出结果' : '确认后生成任务' },
  ];
}

export default function BriefWorkspacePage() {
  const session = useAgentStore((state) => state.session);
  const activeSessionId = useAgentStore((state) => state.activeSessionId);
  const isSubmitting = useAgentStore((state) => state.isSubmitting);
  const setSession = useAgentStore((state) => state.setSession);
  const setActiveSessionId = useAgentStore((state) => state.setActiveSessionId);
  const setSubmitting = useAgentStore((state) => state.setSubmitting);

  const [message, setMessage] = useState('');
  const [errorText, setErrorText] = useState('');
  const [selectedDirection, setSelectedDirection] = useState<'A' | 'B' | 'C'>('B');

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
        // 恢复失败时保持当前空白状态。
      }
    };

    void restoreSession();

    return () => {
      isActive = false;
    };
  }, [activeSessionId, session, setSession]);

  useEffect(() => {
    const sessionId = session?.id;
    const sessionStatus = session?.status;

    if (!sessionId || !sessionStatus || !RUNNING_STATUSES.has(sessionStatus)) {
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
        // 轮询失败时保留当前状态。
      }
    };

    const intervalId = window.setInterval(() => {
      void pollSession();
    }, 2000);

    void pollSession();

    return () => {
      isActive = false;
      window.clearInterval(intervalId);
    };
  }, [session, setSession]);

  const trimmedMessage = message.trim();
  const canSend = Boolean(trimmedMessage) && !isSubmitting;
  const canConfirm = session?.status === 'plan_ready' && !isSubmitting;

  const submitMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSend) {
      return;
    }

    setSubmitting(true);
    setErrorText('');

    try {
      const nextSession = session
        ? await sendAgentMessage(session.id, message)
        : await createAgentSession(message);
      setActiveSessionId(nextSession.id);
      setSession(nextSession);
      setMessage('');
    } catch (error) {
      setErrorText(toUserError(error, () => setSession(null)));
    } finally {
      setSubmitting(false);
    }
  };

  const submitMessageFromKeyboard = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }

    event.preventDefault();
    if (canSend) {
      event.currentTarget.form?.requestSubmit();
    }
  };

  const confirmPlan = async () => {
    if (!session || !canConfirm) {
      return;
    }

    setSubmitting(true);
    setErrorText('');

    try {
      const nextSession = await confirmAgentSession(session.id);
      setActiveSessionId(nextSession.id);
      setSession(nextSession);
    } catch (error) {
      setErrorText(toUserError(error, () => setSession(null)));
    } finally {
      setSubmitting(false);
    }
  };

  const sessionMessages = session?.messages ?? [];
  const userMessages = sessionMessages.filter((item) => item.role === 'user');
  const assistantMessages = sessionMessages.filter((item) => item.role === 'assistant');
  const latestAssistantMessage = assistantMessages.at(-1)?.content ?? '我会按步骤处理你的需求，每一步先显示进度，再展示结果。';
  const finalPlanSummary = useMemo(() => buildFinalPlanSummary(session, selectedDirection), [selectedDirection, session]);
  const scenes = session?.plan?.scenes ?? [];

  return (
    <ProductShell>
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <nav className={styles.crumb} aria-label="面包屑">
              <Link href="/">ClipForge</Link>
              <span aria-hidden="true">/</span>
              <span>方案沟通</span>
            </nav>
            <div className={styles.titleRow}>
              <div className={styles.titleCopy}>
                <h1>方案沟通页面</h1>
                <p>单栏推进需求理解、方向选择和最终确认，AI 的每一步都先给进度，再展示结果。</p>
              </div>
              <div className={styles.status}>
                <span>当前状态</span>
                <strong>{getWorkspaceStatus(session)}</strong>
              </div>
            </div>
          </div>
        </header>

        <main className={styles.workspace} aria-label="方案工作区">
          <section className={styles.chatCard} aria-label="方案沟通">
            <div className={styles.chatHead}>
              <div>
                <h2>方案沟通</h2>
                <p>用户原始输入保留原样，目标和结构化信息由 AI 在后续步骤提炼。</p>
              </div>
              <span className={styles.chatMeta}>每一步先显示进度，再给出结果</span>
            </div>

            <div className={styles.thread}>
              {!session ? (
                <div className={styles.emptyState}>
                  <h3>描述你想完成的视频</h3>
                  <p>直接说你的想法即可，目标、格式、风格和执行拆分会由 AI 在后续步骤里提炼。</p>
                </div>
              ) : (
                <>
                  {userMessages.map((item) => (
                    <article key={item.id} className={`${styles.message} ${styles.userMessage}`}>
                      <div className={styles.messageMeta}>
                        <span>你</span>
                        <time dateTime={item.createdAt}>{formatTime(item.createdAt)}</time>
                      </div>
                      <div className={styles.bubble}>{item.content}</div>
                    </article>
                  ))}

                  <article className={`${styles.message} ${styles.agentMessage}`}>
                    <div className={styles.messageMeta}>
                      <span>ClipForge Agent</span>
                      <span>{session ? formatTime(sessionMessages.at(-1)?.createdAt ?? new Date().toISOString()) : ''}</span>
                    </div>
                    <div className={styles.bubble}>
                      <p>{latestAssistantMessage}</p>
                    </div>
                  </article>
                </>
              )}
            </div>

            <section className={styles.stepFlow} aria-label="AI 分析步骤流">
              {STEP_DEFINITIONS.map((step) => (
                <article key={step.id} className={styles.stepBlock}>
                  <div className={styles.stepHead}>
                    <strong>{step.title}</strong>
                    <span>{session ? `${step.progress}%` : '等待中'}</span>
                  </div>
                  <div className={styles.track} aria-hidden="true">
                    <span style={{ width: session ? `${step.progress}%` : '14%' }} />
                  </div>

                  {step.id === 'directions' ? (
                    <div className={styles.resultBox}>
                      <div className={styles.sectionHead}>
                        <div>
                          <span className={styles.sectionEyebrow}>方案方向</span>
                          <h3>从多个方向里确认一个主方向</h3>
                        </div>
                        <span className={styles.sectionMeta}>一次只确认一个</span>
                      </div>

                      <div className={styles.optionSet}>
                        {DIRECTION_OPTIONS.map((option) => {
                          const isSelected = option.id === selectedDirection;
                          return (
                            <button
                              key={option.id}
                              type="button"
                              className={`${styles.optionCard} ${isSelected ? styles.optionCardSelected : ''}`}
                              onClick={() => setSelectedDirection(option.id)}
                              aria-pressed={isSelected}
                            >
                              <span className={styles.optionLetter}>{option.id}</span>
                              <span className={styles.optionBody}>
                                <strong>{option.name}</strong>
                                <span>{option.summary}</span>
                                <span className={styles.tags}>
                                  {option.tags.map((tag) => (
                                    <span key={tag} className={styles.tag}>
                                      {tag}
                                    </span>
                                  ))}
                                </span>
                              </span>
                              <span className={styles.optionState}>{isSelected ? '已选择' : '可选'}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ) : step.id === 'final' ? (
                    <div className={styles.resultBox}>
                      <div className={styles.sectionHead}>
                        <div>
                          <span className={styles.sectionEyebrow}>最终执行方案</span>
                          <h3>最终方案继续显示在对话流中</h3>
                        </div>
                        <span className={styles.sectionMeta}>{session?.status === 'plan_ready' ? '可确认' : '持续更新'}</span>
                      </div>

                      <div className={styles.finalPlan}>
                        <div className={styles.finalSummary}>
                          {finalPlanSummary.map((item) => (
                            <div key={item.label} className={styles.summaryItem}>
                              <span>{item.label}</span>
                              <strong>{item.value}</strong>
                            </div>
                          ))}
                        </div>

                        <div className={styles.sceneList}>
                          {scenes.length > 0 ? (
                            scenes.map((scene) => (
                              <div key={scene.id} className={styles.scene}>
                                <div className={styles.sceneNo}>{String(scene.id).padStart(2, '0')}</div>
                                <div>
                                  <strong>{scene.description}</strong>
                                  <p>关键词：{scene.keywords.join(' / ') || '待补充'} · 检索方向：{scene.searchQuery}</p>
                                </div>
                                <div className={styles.duration}>{scene.duration}s</div>
                              </div>
                            ))
                          ) : (
                            <div className={styles.pendingPlan}>
                              <p>待 AI 生成最终方案后，这里会展示结构化段落拆分。</p>
                            </div>
                          )}
                        </div>

                        <div className={styles.approval}>
                          <Button type="button" variant="secondary" disabled={!session}>
                            继续修改
                          </Button>
                          <Button type="button" onClick={confirmPlan} disabled={!canConfirm}>
                            确认方案并生成任务
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className={styles.resultBox}>
                      <div className={styles.analysisGrid}>
                        {step.buildResult(session).map((item) => (
                          <div key={item.label} className={styles.analysisItem}>
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </section>

            {errorText ? <div className={styles.error}>{errorText}</div> : null}

            <form className={styles.composer} onSubmit={submitMessage}>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={submitMessageFromKeyboard}
                placeholder="继续补充你的修改意见，或直接确认最终方案。"
                rows={4}
                disabled={isSubmitting}
              />
              <div className={styles.composeActions}>
                <span className={styles.hint}>底部输入区用于继续补充信息、修改方案，或推动下一轮细化。</span>
                <div className={styles.composeButtons}>
                  <Button type="button" variant="secondary" onClick={confirmPlan} disabled={!canConfirm}>
                    确认方案并生成任务
                  </Button>
                  <Button type="submit" disabled={!canSend}>
                    {isSubmitting ? '处理中' : '发送'}
                  </Button>
                </div>
              </div>
            </form>
          </section>
        </main>
      </div>
    </ProductShell>
  );
}
