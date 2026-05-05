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
const WORKSPACE_STEP_IDS = ['understand_request', 'extract_requirements', 'generate_options', 'finalize_plan'] as const;
const WORKSPACE_STEP_TITLES: Record<(typeof WORKSPACE_STEP_IDS)[number], string> = {
  understand_request: '步骤 1：理解原始需求',
  extract_requirements: '步骤 2：提炼目标与限制',
  generate_options: '步骤 3：生成多个方案方向',
  finalize_plan: '步骤 4：输出最终执行方案',
} as const;

const FALLBACK_WORKSPACE_STEPS = [
  {
    id: 'understand_request',
    title: '步骤 1：理解原始需求',
    status: 'pending',
    progress: 0,
    summary: '等待后端返回需求分析结果。',
    error: null,
    result: null,
    startedAt: null,
    finishedAt: null,
  },
  {
    id: 'extract_requirements',
    title: '步骤 2：提炼目标与限制',
    status: 'pending',
    progress: 0,
    summary: '等待后端返回约束分析结果。',
    error: null,
    result: null,
    startedAt: null,
    finishedAt: null,
  },
  {
    id: 'generate_options',
    title: '步骤 3：生成多个方案方向',
    status: 'pending',
    progress: 0,
    summary: '等待后端返回方案方向。',
    error: null,
    result: null,
    startedAt: null,
    finishedAt: null,
  },
  {
    id: 'finalize_plan',
    title: '步骤 4：输出最终执行方案',
    status: 'pending',
    progress: 0,
    summary: '等待后端返回最终方案。',
    error: null,
    result: null,
    startedAt: null,
    finishedAt: null,
  },
] as const;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

type WorkspaceStep = (typeof FALLBACK_WORKSPACE_STEPS)[number] | AgentSession['steps'][number];

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

function buildWorkspaceStepResult(step: WorkspaceStep) {
  const result = asRecord(step.result);

  if (step.id === 'understand_request' || step.id === 'extract_requirements') {
    return [
      { label: '原始诉求', value: asString(result.originalPrompt) || '等待后端返回结果。' },
      { label: '建议时长', value: asNumber(result.targetDuration) ? `${asNumber(result.targetDuration)} 秒` : '待分析' },
      { label: '风格方向', value: asString(result.style) || '待分析' },
    ];
  }

  if (step.id === 'finalize_plan') {
    const scenes = asArray(result.scenes).map((scene) => {
      const sceneRecord = asRecord(scene);
      return {
        id: asString(sceneRecord.id) || '',
        description: asString(sceneRecord.description) || '',
        searchQuery: asString(sceneRecord.searchQuery) || '',
        duration: asNumber(sceneRecord.duration),
      };
    });

    return [
      { label: '方案标题', value: asString(result.title) || '等待后端返回最终方案。' },
      { label: '风格', value: asString(result.style) || '待确认' },
      { label: '时长', value: asNumber(result.targetDuration) ? `${asNumber(result.targetDuration)} 秒` : '待确认' },
      { label: '镜头数', value: scenes.length ? `${scenes.length} 个` : '待确认' },
    ];
  }

  return [];
}

function buildGenerateOptionsCards(step: WorkspaceStep) {
  const result = asRecord(step.result);
  return asArray(result.options).map((option, index) => {
    const optionRecord = asRecord(option);
    const keywords = asArray(optionRecord.keywords).map((keyword) => asString(keyword)).filter(Boolean);
    const sceneId = asNumber(optionRecord.sceneId);
    const title = sceneId > 0 ? `场景 ${sceneId}` : `场景 ${index + 1}`;
    const description = asString(optionRecord.description) || '等待后端返回方案方向。';
    const searchQuery = asString(optionRecord.searchQuery);
    const duration = asNumber(optionRecord.duration);

    return {
      id: asString(optionRecord.id) || asString(optionRecord.sceneId) || String(index + 1),
      title,
      description,
      keywords,
      searchQuery,
      duration,
    };
  });
}

function buildFinalPlanSummaryItems(step: WorkspaceStep) {
  const result = asRecord(step.result);
  const scenes = asArray(result.scenes);
  return [
    { label: '方案标题', value: asString(result.title) || '等待后端返回最终方案。' },
    { label: '风格', value: asString(result.style) || '待确认' },
    { label: '时长', value: asNumber(result.targetDuration) ? `${asNumber(result.targetDuration)} 秒` : '待确认' },
    { label: '镜头数', value: scenes.length ? `${scenes.length} 个` : '待确认' },
  ];
}

function buildFinalPlanScenes(step: WorkspaceStep) {
  const result = asRecord(step.result);
  const scenes = asArray(result.scenes);
  return scenes.map((scene) => {
    const sceneRecord = asRecord(scene);
    return {
      id: asNumber(sceneRecord.id),
      description: asString(sceneRecord.description),
      keywords: asArray(sceneRecord.keywords).map((keyword) => asString(keyword)).filter(Boolean),
      searchQuery: asString(sceneRecord.searchQuery),
      duration: asNumber(sceneRecord.duration),
    };
  });
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
  const scenes = session?.plan?.scenes ?? [];
  const workspaceSteps = useMemo(() => {
    if (!session?.steps?.length) {
      return FALLBACK_WORKSPACE_STEPS;
    }

    return WORKSPACE_STEP_IDS
      .map((stepId) => session.steps.find((step) => step.id === stepId))
      .filter((step): step is AgentSession['steps'][number] => Boolean(step));
  }, [session?.steps]);

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
              {workspaceSteps.map((step, index) => {
                const result = asRecord(step.result);
                const optionCards = step.id === 'generate_options' ? buildGenerateOptionsCards(step) : [];
                const progress = step.status === 'pending' ? (session ? 12 + index * 5 : 14) : step.progress;
                const statusText =
                  step.status === 'succeeded' ? '完成' : step.status === 'running' ? '进行中' : step.status === 'failed' ? '失败' : '等待中';
                const stepTitle = WORKSPACE_STEP_TITLES[step.id as (typeof WORKSPACE_STEP_IDS)[number]];

                return (
                  <article key={step.id} className={styles.stepBlock}>
                    <div className={styles.stepHead}>
                      <strong>{stepTitle}</strong>
                      <span>{statusText}</span>
                    </div>
                    <div className={styles.track} aria-hidden="true">
                      <span style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
                    </div>

                    {step.id === 'generate_options' ? (
                      <div className={styles.resultBox}>
                        <div className={styles.sectionHead}>
                          <div>
                            <span className={styles.sectionEyebrow}>方案方向</span>
                            <h3>{step.status === 'succeeded' ? '后端返回的方案方向卡片' : '等待后端返回方案方向。'}</h3>
                          </div>
                          <span className={styles.sectionMeta}>纯展示</span>
                        </div>

                        <div className={styles.optionSet}>
                          {optionCards.length ? (
                            optionCards.map((option) => (
                              <article key={option.id} className={styles.optionPreviewCard}>
                                <div className={styles.optionPreviewHead}>
                                  <strong>{option.title}</strong>
                                  <span>{option.duration ? `${option.duration} 秒` : '时长待定'}</span>
                                </div>
                                <p>{option.description}</p>
                                <div className={styles.optionPreviewMeta}>
                                  <span>检索方向：{option.searchQuery || '待补充'}</span>
                                  <span>关键词：{option.keywords.length ? option.keywords.join(' / ') : '待补充'}</span>
                                </div>
                              </article>
                            ))
                          ) : (
                            <div className={styles.emptyInline}>等待后端返回方案方向。</div>
                          )}
                        </div>
                      </div>
                    ) : step.id === 'finalize_plan' ? (
                      <div className={styles.resultBox}>
                        <div className={styles.sectionHead}>
                          <div>
                            <span className={styles.sectionEyebrow}>最终执行方案</span>
                            <h3>{step.status === 'succeeded' ? '后端返回的最终执行方案' : '等待后端返回最终方案。'}</h3>
                          </div>
                          <span className={styles.sectionMeta}>{session?.status === 'plan_ready' ? '可确认' : '持续更新'}</span>
                        </div>

                        <div className={styles.finalPlan}>
                          <div className={styles.finalSummary}>
                            {buildFinalPlanSummaryItems(step).map((item) => (
                              <div key={item.label} className={styles.summaryItem}>
                                <span>{item.label}</span>
                                <strong>{item.value}</strong>
                              </div>
                            ))}
                          </div>

                          <div className={styles.sceneList}>
                            {asArray(result.scenes).length ? (
                              asArray(result.scenes).map((scene) => {
                                const sceneRecord = asRecord(scene);
                                return (
                                  <div key={asString(sceneRecord.id) || asString(sceneRecord.searchQuery)} className={styles.scene}>
                                    <div className={styles.sceneNo}>{String(asString(sceneRecord.id) || '0').padStart(2, '0')}</div>
                                    <div>
                                      <strong>{asString(sceneRecord.description) || '等待后端返回计划。'}</strong>
                                      <p>关键词：{asArray(sceneRecord.keywords).map((keyword) => asString(keyword)).filter(Boolean).join(' / ') || '待补充'} · 检索方向：{asString(sceneRecord.searchQuery)}</p>
                                    </div>
                                    <div className={styles.duration}>{asNumber(sceneRecord.duration)}s</div>
                                  </div>
                                );
                              })
                            ) : (
                              <div className={styles.pendingPlan}>
                                <p>等待后端返回最终方案。</p>
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
                          {(() => {
                            const items = buildWorkspaceStepResult(step) as Array<{ label: string; value: string }>;
                            return items.map((item) => (
                              <div key={item.label} className={styles.analysisItem}>
                                <span>{item.label}</span>
                                <strong>{item.value}</strong>
                              </div>
                            ));
                          })()}
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
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
