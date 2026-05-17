'use client';

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import Button from '@/components/common/Button';
import AiStepFlow from '@/components/workspace/AiStepFlow';
import {
  confirmGroundingCandidates,
  confirmAgentSession,
  createAgentSession,
  getAgentSession,
  getAgentSessionEvents,
  isTerminalTraceEvent,
  sendAgentMessage,
  subscribeAgentSessionTrace,
  type AgentSession,
} from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';

const RUNNING_STATUSES = new Set(['queued', 'searching', 'downloading', 'rendering']);
const WORKSPACE_STEP_IDS = ['understand_request', 'extract_requirements', 'generate_options', 'finalize_plan'] as const;
const WORKSPACE_STEP_TITLES: Record<(typeof WORKSPACE_STEP_IDS)[number], string> = {
  understand_request: '步骤 1：理解原始需求',
  extract_requirements: '步骤 2：提炼目标与限制',
  generate_options: '步骤 3：生成多个方案方向',
  finalize_plan: '步骤 4：输出最终执行方案',
} as const;
const EXECUTION_STEP_IDS = ['create_task', 'search_assets', 'prepare_assets', 'render_video'] as const;
const EXECUTION_STEP_TITLES: Record<(typeof EXECUTION_STEP_IDS)[number], string> = {
  create_task: '创建执行任务',
  search_assets: '搜索素材',
  prepare_assets: '准备素材',
  render_video: '渲染视频',
} as const;

const STEP_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '进行中',
  succeeded: '已完成',
  failed: '失败',
  skipped: '已跳过',
};

const TRACE_STATUS_LABELS: Record<string, string> = {
  running: '进行中',
  succeeded: '已完成',
  failed: '失败',
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function getSafeResultUrl(value: string | null | undefined) {
  const candidate = value?.trim() ?? '';
  if (!candidate) {
    return '';
  }

  if (candidate.startsWith('/') && !candidate.startsWith('//')) {
    return candidate;
  }

  try {
    const url = new URL(candidate);
    return url.protocol === 'http:' || url.protocol === 'https:' ? candidate : '';
  } catch {
    return '';
  }
}

function asNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function formatConfidence(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return '待评估';
  }
  return `${Math.round(value * 100)}%`
}

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

function getStepStatusText(status: string) {
  return STEP_STATUS_LABELS[status] ?? status;
}

function clampDisplayProgress(value: number) {
  return Math.max(0, Math.min(100, value));
}

function getProgressIncrement(currentProgress: number) {
  if (currentProgress < 18) {
    return 6;
  }
  if (currentProgress < 44) {
    return 4;
  }
  if (currentProgress < 78) {
    return 2;
  }
  return 1;
}

function getExecutionStepTargetProgress(step: AgentSession['steps'][number], index: number) {
  if (step.status === 'succeeded') {
    return 100;
  }
  if (step.status === 'failed') {
    return Math.max(90, clampDisplayProgress(step.progress));
  }
  if (step.status === 'running') {
    return Math.min(99, Math.max(18 + index * 4, clampDisplayProgress(step.progress)));
  }
  if (step.status === 'pending') {
    return 0;
  }
  return clampDisplayProgress(step.progress);
}

function getProgressBarStyle(progress: number) {
  const normalized = clampDisplayProgress(progress) / 100;
  const opacity = 0.58 + normalized * 0.42;
  const brightness = 0.88 + normalized * 0.24;
  const saturate = 0.82 + normalized * 0.38;

  return {
    width: `${clampDisplayProgress(progress)}%`,
    opacity,
    filter: `brightness(${brightness}) saturate(${saturate})`,
  };
}

function formatDiagnosticPhase(phase: string) {
  return (
    {
      planning: '方案规划',
      search_assets: '搜索素材',
      prepare_assets: '准备素材',
      render_video: '渲染视频',
      unknown: '未知阶段',
    }[phase] ?? phase
  );
}

function formatSceneIds(sceneIds: number[]) {
  return sceneIds.length ? sceneIds.map((sceneId) => `场景 ${sceneId}`).join('、') : '未指定';
}

function findFailedStep(session: AgentSession | null) {
  return session?.steps?.find((step) => step.status === 'failed') ?? null;
}

type WorkspaceStep = AgentSession['steps'][number];

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

export default function BriefWorkspacePage() {
  const session = useAgentStore((state) => state.session);
  const activeSessionId = useAgentStore((state) => state.activeSessionId);
  const isSubmitting = useAgentStore((state) => state.isSubmitting);
  const setSession = useAgentStore((state) => state.setSession);
  const setActiveSessionId = useAgentStore((state) => state.setActiveSessionId);
  const setSubmitting = useAgentStore((state) => state.setSubmitting);
  const appendTraceEvent = useAgentStore((state) => state.appendTraceEvent);
  const lastTraceSequence = useAgentStore((state) => state.lastTraceSequence);
  const setStreamState = useAgentStore((state) => state.setStreamState);
  const currentTraceStream = useAgentStore((state) => state.currentTraceStream);

  const [message, setMessage] = useState('');
  const [errorText, setErrorText] = useState('');
  const [selectedDirection, setSelectedDirection] = useState('');
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [restoredSessionId, setRestoredSessionId] = useState<string | null>(null);
  const [hasAppliedRestoreJump, setHasAppliedRestoreJump] = useState(false);
  const [showPlanUpdatedNotice, setShowPlanUpdatedNotice] = useState(false);
  const [displayedExecutionProgress, setDisplayedExecutionProgress] = useState<Record<string, number>>({});
  const executionSectionRef = useRef<HTMLElement | null>(null);
  const resultSectionRef = useRef<HTMLElement | null>(null);
  const failureSectionRef = useRef<HTMLElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
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
          setRestoredSessionId(activeSessionId);
          setHasAppliedRestoreJump(false);
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
    if (!session?.id || !restoredSessionId) {
      return;
    }

    if (session.id !== restoredSessionId) {
      setRestoredSessionId(null);
      setHasAppliedRestoreJump(false);
    }
  }, [restoredSessionId, session?.id]);

  useEffect(() => {
    const targetSessionId = session?.id;
    const targetStatus = session?.status;

    if (!targetSessionId || !targetStatus) {
      return;
    }

    let isActive = true;
    setStreamState('connecting');
    const subscription = subscribeAgentSessionTrace(
      targetSessionId,
      {
        onEvent: (event) => {
          if (!isActive) {
            return;
          }

          setStreamState('open');
          appendTraceEvent(event);
          if (isTerminalTraceEvent(event.eventType)) {
            void refreshSessionSnapshot(targetSessionId);
          }
        },
        onClosed: () => {
          if (isActive) {
            setStreamState('closed');
            void refreshSessionSnapshot(targetSessionId);
          }
        },
        onError: () => {
          if (isActive) {
            setStreamState('error');
            if (RUNNING_STATUSES.has(targetStatus)) {
              void refreshSessionSnapshot(targetSessionId);
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
  }, [appendTraceEvent, session?.id, session?.status, setSession, setStreamState]);

  useEffect(() => {
    setSelectedDirection('');
    setSelectedCandidateIds(session?.grounding?.selectedCandidateIds ?? []);
    setShowPlanUpdatedNotice(false);
  }, [session?.id]);

  useEffect(() => {
    if (!session) {
      setSelectedCandidateIds([]);
      return;
    }

    if (session?.grounding?.status === 'confirmed') {
      setSelectedCandidateIds(session.grounding.selectedCandidateIds ?? []);
      return;
    }

    if (session.grounding?.status !== 'needs_confirmation') {
      setSelectedCandidateIds([]);
    }
  }, [session?.grounding?.status]);

  useEffect(() => {
    const sessionId = session?.id;
    const sessionStatus = session?.status;

    if (!sessionId || !sessionStatus || !RUNNING_STATUSES.has(sessionStatus)) {
      return;
    }

    setShowPlanUpdatedNotice(false);

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
  const awaitingGroundingConfirmation = session?.grounding?.status === 'needs_confirmation';
  const canConfirmGrounding = awaitingGroundingConfirmation && selectedCandidateIds.length > 0 && !isSubmitting && !trimmedMessage;
  const canConfirmPlan = session?.status === 'plan_ready' && (!session?.grounding || session.grounding.status === 'confirmed') && !isSubmitting;

  const submitMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSend) {
      return;
    }

    setSubmitting(true);
    setErrorText('');
    const basePlanVersion = session?.plan && typeof session.currentPlanVersion === 'number' ? session.currentPlanVersion : null;
    setShowPlanUpdatedNotice(false);

    try {
      const nextSession = session
        ? await sendAgentMessage(session.id, message)
        : await createAgentSession(message);
      setActiveSessionId(nextSession.id);
      setSession(nextSession);
      setShowPlanUpdatedNotice(
        basePlanVersion !== null &&
          typeof nextSession.currentPlanVersion === 'number' &&
          nextSession.currentPlanVersion > basePlanVersion
      );
      setMessage('');
    } catch (error) {
      setShowPlanUpdatedNotice(false);
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

  const confirmGrounding = async () => {
    if (!session || !canConfirmGrounding) {
      return;
    }

    setSubmitting(true);
    setErrorText('');

    try {
      const nextSession = await confirmGroundingCandidates(session.id, selectedCandidateIds);
      setActiveSessionId(nextSession.id);
      setSession(nextSession);
    } catch (error) {
      setErrorText(toUserError(error, () => setSession(null)));
    } finally {
      setSubmitting(false);
    }
  };

  const confirmPlan = async () => {
    if (!session || !canConfirmPlan) {
      return;
    }

    setSubmitting(true);
    setErrorText('');

    try {
      const pendingMessage = message.trim();
      const sessionToConfirm = pendingMessage ? await sendAgentMessage(session.id, pendingMessage) : session;
      const nextSession = await confirmAgentSession(sessionToConfirm.id);
      setActiveSessionId(nextSession.id);
      setSession(nextSession);
      setMessage('');
    } catch (error) {
      setErrorText(toUserError(error, () => setSession(null)));
    } finally {
      setSubmitting(false);
    }
  };

  const focusComposer = () => {
    textareaRef.current?.focus();
  };

  function applyDiagnosticRepairPrompt() {
    if (!diagnostic?.repairPrompt) {
      return;
    }
    setMessage(diagnostic.repairPrompt);
    textareaRef.current?.focus();
  }

  const sessionMessages = session?.messages ?? [];
  const userMessages = sessionMessages.filter((item) => item.role === 'user');
  const assistantMessages = sessionMessages.filter((item) => item.role === 'assistant');
  const latestAssistantMessage = assistantMessages.at(-1)?.content ?? '我会按步骤处理你的需求，每一步先显示进度，再展示结果。';
  const scenes = session?.plan?.scenes ?? [];
  const groundingCandidates = session?.grounding?.candidates ?? [];
  const executionSteps = useMemo(() => {
    if (!session?.steps?.length) {
      return [];
    }

    return EXECUTION_STEP_IDS
      .map((stepId) => session.steps.find((step) => step.id === stepId))
      .filter((step): step is AgentSession['steps'][number] => Boolean(step));
  }, [session?.steps]);

  const failedStep = findFailedStep(session);
  const diagnostic = session?.diagnostic ?? null;
  const isSessionActivelyExecuting = Boolean(
    session?.status === 'queued' ||
      session?.status === 'searching' ||
      session?.status === 'downloading' ||
      session?.status === 'rendering'
  );
  const showFailurePanel = Boolean((session?.status === 'failed' || failedStep) && !isSessionActivelyExecuting);
  const showExecutionHandoff = Boolean(session?.activeJobId || executionSteps.some((step) => step.status !== 'pending'));
  const showPlanConfirmAction = Boolean(canConfirmPlan || session?.status === 'plan_ready');
  const hasExecutionFeedbackRequeue = Boolean(
    isSessionActivelyExecuting &&
      session?.events?.some((event) => event.eventType === 'job_requeued_after_replan')
  );
  const resultUrl = getSafeResultUrl(session?.videoUrl);
  const generateOptionsStep = useMemo(
    () => session?.steps?.find((step) => step.id === 'generate_options') ?? null,
    [session?.steps]
  );
  const generateOptionsStateSignature = useMemo(() => {
    if (!generateOptionsStep) {
      return '';
    }

    const result = asRecord(generateOptionsStep.result);
    const optionIds = asArray(result.options)
      .map((option) => {
        const optionRecord = asRecord(option);
        return asString(optionRecord.id) || asString(optionRecord.sceneId);
      })
      .filter(Boolean);

    return JSON.stringify({
      selectedOptionId: asString(result.selectedOptionId),
      optionIds,
    });
  }, [generateOptionsStep]);

  useEffect(() => {
    setSelectedDirection('');
  }, [session?.id, generateOptionsStateSignature]);

  useEffect(() => {
    if (!restoredSessionId || hasAppliedRestoreJump || session?.id !== restoredSessionId) {
      return;
    }

    const target =
      (resultUrl ? resultSectionRef.current : null) ||
      (showFailurePanel ? failureSectionRef.current : null) ||
      (showExecutionHandoff ? executionSectionRef.current : null);

    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    setHasAppliedRestoreJump(true);
  }, [hasAppliedRestoreJump, restoredSessionId, resultUrl, session?.id, showExecutionHandoff, showFailurePanel]);

  useEffect(() => {
    if (!executionSteps.length) {
      setDisplayedExecutionProgress({});
      return;
    }

    setDisplayedExecutionProgress((current) => {
      const next = { ...current };

      executionSteps.forEach((step) => {
        if (typeof next[step.id] !== 'number') {
          next[step.id] = 0;
        }
      });

      Object.keys(next).forEach((key) => {
        if (!executionSteps.some((step) => step.id === key)) {
          delete next[key];
        }
      });

      return next;
    });
  }, [executionSteps]);

  useEffect(() => {
    if (!executionSteps.length) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setDisplayedExecutionProgress((current) => {
        const next = { ...current };

        executionSteps.forEach((step, index) => {
          const currentProgress = next[step.id] ?? 0;
          const targetProgress = getExecutionStepTargetProgress(step, index);

          if (currentProgress >= targetProgress) {
            next[step.id] = targetProgress;
            return;
          }

          next[step.id] = clampDisplayProgress(
            Math.min(targetProgress, currentProgress + getProgressIncrement(currentProgress))
          );
        });

        return next;
      });
    }, 320);

    return () => window.clearInterval(intervalId);
  }, [executionSteps]);

  return (
    <ProductShell>
      <div className="min-h-full">
        <main
          className="grid min-h-[calc(100vh-7.5rem)] w-full max-w-none overflow-hidden rounded-[24px] border border-border bg-white/88 shadow-soft xl:grid-cols-[minmax(0,1fr)_380px]"
          aria-label="方案工作台"
        >
          <div className="grid min-h-0 min-w-0 content-stretch gap-4 p-4 sm:p-5 lg:p-6">
            {restoredSessionId && session?.id === restoredSessionId ? (
              <section className="grid gap-3 rounded-[18px] border border-border bg-[color:var(--surface-muted)] p-4 sm:flex sm:items-center sm:justify-between" aria-label="恢复的方案会话">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-ink">已恢复到当前方案会话</h2>
                  <p className="mt-1 text-sm leading-6 text-secondary">你可以继续查看执行进度、回到任务列表，或补充新的方案修改意见。</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-sm text-secondary">
                    <span className="rounded-lg border border-border bg-slate-50 px-3 py-1.5">
                      <span className="font-semibold text-ink">当前状态：</span>
                      {getWorkspaceStatus(session)}
                    </span>
                    {session?.activeJobId ? (
                      <span className="rounded-lg border border-border bg-slate-50 px-3 py-1.5 [overflow-wrap:anywhere]">
                        <span className="font-semibold text-ink">Job ID：</span>
                        {session.activeJobId}
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2.5">
                  <Link
                    href="/tasks"
                    className="inline-flex min-h-10 items-center justify-center rounded-full border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-[color:var(--surface-subtle)]"
                  >
                    查看任务列表
                  </Link>
                  <button
                    type="button"
                    className="inline-flex min-h-10 items-center justify-center rounded-full bg-ink px-4 text-sm font-semibold text-white transition hover:opacity-90"
                    onClick={focusComposer}
                  >
                    继续补充方案
                  </button>
                </div>
              </section>
            ) : null}

            <section className="flex min-h-full flex-col overflow-hidden rounded-[20px] border border-border bg-white" aria-label="方案工作会话">
              <div className="flex items-center justify-between gap-3 border-b border-bordersoft px-5 py-4">
                <span className="text-sm font-semibold text-ink">Clip Chat</span>
                <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
                  {currentTraceStream ? (
                    <div
                      className="grid min-w-[12rem] max-w-[18rem] gap-1.5 rounded-lg border border-[rgba(45,138,164,0.24)] bg-[#eef8f8] px-3 py-2 text-xs text-secondary"
                      data-status={currentTraceStream.status}
                      aria-label="实时执行状态"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate font-semibold text-ink">{currentTraceStream.label}</span>
                        <strong className="font-semibold text-accentink">
                          {Math.round(currentTraceStream.progress * 100)}%
                        </strong>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white" aria-hidden="true">
                        <span
                          className="block h-full rounded-full bg-gradient-to-r from-accentstrong to-accent transition-[width] duration-200"
                          style={{ width: `${Math.round(currentTraceStream.progress * 100)}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate">{currentTraceStream.message}</span>
                        <span className="shrink-0 font-semibold">{TRACE_STATUS_LABELS[currentTraceStream.status] || currentTraceStream.status}</span>
                      </div>
                    </div>
                  ) : null}
                  <span className="w-fit rounded-full border border-[rgba(31,106,91,0.18)] bg-[#e7f1ec] px-3 py-1.5 text-xs font-semibold text-accentink">
                    {getWorkspaceStatus(session)}
                  </span>
                </div>
              </div>

              <div className="grid flex-1 content-end gap-3.5 bg-[linear-gradient(180deg,rgba(31,106,91,0.05),transparent_280px),#ffffff] p-5" aria-label="对话消息">
                {session ? (
                  <>
                    {userMessages.map((item) => (
                      <article key={item.id} className="ml-auto grid w-full gap-2 min-[861px]:max-w-[84%]">
                        <div className="flex items-center justify-between gap-3 text-xs font-extrabold text-secondary">
                          <span>你</span>
                          <time dateTime={item.createdAt}>{formatTime(item.createdAt)}</time>
                        </div>
                        <div className="rounded-lg border border-[#1f2522] bg-[#1f2522] p-3.5 leading-[1.58] text-white">
                          {item.content}
                        </div>
                      </article>
                    ))}

                    <article className="mr-auto grid w-full gap-2 min-[861px]:max-w-[84%]">
                      <div className="flex items-center justify-between gap-3 text-xs font-extrabold text-secondary">
                        <span>ClipForge Agent</span>
                        <span>{session ? formatTime(sessionMessages.at(-1)?.createdAt ?? new Date().toISOString()) : ''}</span>
                      </div>
                      <div className="grid gap-3 rounded-[18px] border border-[#e2e7e1] bg-[#f7f9f6] p-3.5 leading-[1.58] text-[#303a34]">
                        <p>{latestAssistantMessage}</p>
                        {showPlanConfirmAction ? (
                          <div className="flex flex-wrap items-center gap-2.5 border-t border-[#e3e9e0] pt-3" aria-label="Agent 操作">
                            <Button type="button" variant="secondary" onClick={confirmPlan} disabled={!canConfirmPlan}>
                              确认方案并生成任务
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    </article>
                  </>
                ) : null}
              </div>

              {awaitingGroundingConfirmation ? (
                <section className="mx-5 mb-5 grid gap-3 rounded-lg border border-border bg-[#fbfcfa] p-4" aria-label="候选产品画面确认">
                  <div className="flex flex-col gap-3 min-[861px]:flex-row min-[861px]:items-start min-[861px]:justify-between">
                    <div>
                      <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">候选产品画面确认</span>
                      <h2 className="mt-1 text-lg font-semibold text-ink">确认这些画面是否代表正确的产品</h2>
                      <p className="mt-1 text-sm leading-6 text-secondary">
                        先锁定真实产品画面，再生成最终方案。已选 {selectedCandidateIds.length} 项，确认后会把这些选择写入 grounded plan。
                      </p>
                    </div>
                    <span className="text-xs font-extrabold text-secondary min-[861px]:whitespace-nowrap">
                      selectedCandidateIds: {selectedCandidateIds.length}
                    </span>
                  </div>

                  <div className="grid gap-3">
                    {groundingCandidates.map((candidate) => {
                      const checked = selectedCandidateIds.includes(candidate.id);
                      const candidatePreviewUrl = candidate.previewUrl || candidate.imageUrl;
                      return (
                        <label
                          key={candidate.id}
                          className={`grid gap-3 rounded-lg border p-3 transition sm:grid-cols-[6rem_minmax(0,1fr)] ${
                            checked ? 'border-accent bg-[#f6faef]' : 'border-[#e4e8e3] bg-white hover:border-[#c7d3bf]'
                          }`}
                        >
                          <div className="overflow-hidden rounded-lg border border-[#e4e8e3] bg-[#f4f7f1]">
                            {candidatePreviewUrl ? (
                              <img
                                src={candidate.previewUrl || candidate.imageUrl}
                                alt={candidate.title}
                                className="h-24 w-24 object-cover"
                              />
                            ) : (
                              <div className="flex h-24 w-24 items-center justify-center px-2 text-center text-xs font-medium text-secondary">
                                暂无预览
                              </div>
                            )}
                          </div>

                          <div className="grid gap-2.5">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <strong className="text-sm font-semibold text-ink">{candidate.title}</strong>
                                  <span className="rounded-full border border-border bg-[#f7f9f6] px-2 py-0.5 text-[11px] font-bold text-secondary">
                                    {candidate.providerLabel}
                                  </span>
                                  {candidate.isOfficial ? (
                                    <span className="rounded-full border border-[rgba(168,198,108,0.38)] bg-[#e3efd4] px-2 py-0.5 text-[11px] font-bold text-accentink">
                                      官方候选
                                    </span>
                                  ) : null}
                                </div>
                                <p className="mt-1 text-sm leading-6 text-secondary">{candidate.summary || '等待候选摘要。'}</p>
                              </div>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() =>
                                  setSelectedCandidateIds((current) =>
                                    checked ? current.filter((item) => item !== candidate.id) : [...current, candidate.id]
                                  )
                                }
                                className="mt-1 h-4 w-4 rounded border-border text-accent focus:ring-accent"
                              />
                            </div>
                            <div className="grid gap-1 text-xs leading-5 text-secondary [overflow-wrap:anywhere]">
                              <span>产品：{candidate.productName || '待识别'}</span>
                              <span>受众：{candidate.audience || '待识别'}</span>
                              <span>匹配度：{formatConfidence(candidate.confidence)}</span>
                              <span>来源：{candidate.sourceUrl}</span>
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>

                  <div className="flex flex-wrap gap-2.5">
                    <Button type="button" variant="secondary" onClick={focusComposer}>
                      继续补充需求
                    </Button>
                    <Button
                      type="button"
                      onClick={confirmGrounding}
                      disabled={!canConfirmGrounding}
                      title={trimmedMessage ? '请先发送当前补充需求，再确认候选画面。' : undefined}
                    >
                      确认这些画面
                    </Button>
                  </div>
                </section>
              ) : null}

              {showExecutionHandoff ? (
                <section ref={executionSectionRef} className="mx-5 mb-5 grid gap-3 rounded-lg border border-border bg-[#fbfcfa] p-4" aria-label="执行交接">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">执行交接</span>
                      <h2 className="mt-1 text-lg font-semibold text-ink">方案已进入任务执行</h2>
                      <p className="mt-1 text-sm leading-6 text-secondary">
                        后端会继续搜索素材、准备素材并渲染视频；更完整的事件时间线可以在任务页查看。
                      </p>
                    </div>
                    <Link
                      href="/tasks"
                      className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50"
                    >
                      查看任务详情
                    </Link>
                  </div>

                  <div className="rounded-lg border border-[#e4e8e3] bg-white p-3 text-sm text-secondary">
                    <span className="font-bold text-ink">Job ID：</span>
                    <span className="[overflow-wrap:anywhere]">{session?.activeJobId || '等待后端返回任务编号'}</span>
                  </div>
                  {hasExecutionFeedbackRequeue ? (
                    <div className="rounded-lg border border-[rgba(168,198,108,0.38)] bg-[#f6faef] px-3 py-2 text-sm font-semibold text-accentink">
                      已根据上一次失败自动调整方案并重新入队
                    </div>
                  ) : null}

                  <div className="grid gap-3 sm:grid-cols-2">
                    {executionSteps.map((step) => (
                      <article key={step.id} className="grid gap-3 rounded-lg border border-[#e4e8e3] bg-white p-3">
                        <div className="flex items-start justify-between gap-3">
                          <strong className="[overflow-wrap:anywhere] text-sm text-ink">
                            {EXECUTION_STEP_TITLES[step.id as (typeof EXECUTION_STEP_IDS)[number]]}
                          </strong>
                          <span className="whitespace-nowrap text-xs font-bold text-secondary">{getStepStatusText(step.status)}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-[#edf1ed]" aria-hidden="true">
                          <span
                            className="block h-full rounded-full bg-gradient-to-r from-accentstrong to-accent transition-[width,opacity,filter] duration-300 ease-out"
                            style={getProgressBarStyle(displayedExecutionProgress[step.id] ?? 0)}
                          />
                        </div>
                        <p className="[overflow-wrap:anywhere] text-sm leading-6 text-secondary">{step.summary || step.description}</p>
                      </article>
                    ))}
                  </div>
                </section>
              ) : null}

              {resultUrl ? (
                <section ref={resultSectionRef} className="mx-5 mb-5 grid gap-3 rounded-lg border border-border bg-white p-4" aria-label="结果预览">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">结果预览</span>
                      <h2 className="mt-1 text-lg font-semibold text-ink">视频已经生成</h2>
                      <p className="mt-1 text-sm leading-6 text-secondary">可以在这里预览结果，也可以进入任务页查看完整事件和素材信息。</p>
                    </div>
                    <a
                      href={resultUrl}
                      className="inline-flex min-h-10 items-center justify-center rounded-lg bg-ink px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
                    >
                      打开视频
                    </a>
                  </div>
                  <video className="aspect-video w-full rounded-lg border border-border bg-black" src={resultUrl} controls preload="metadata" />
                </section>
              ) : null}

              {showFailurePanel ? (
                <section
                  ref={failureSectionRef}
                  className="mx-5 mb-5 rounded-lg border border-[#f5c2c7] bg-[#fff7f7] p-4 text-sm text-[#8b1f2d]"
                  aria-label="失败步骤"
                >
                  <span className="text-xs font-bold uppercase tracking-[0.02em]">失败步骤</span>
                  <h2 className="mt-1 text-base font-semibold">
                    {failedStep
                      ? WORKSPACE_STEP_TITLES[failedStep.id as (typeof WORKSPACE_STEP_IDS)[number]] ||
                        EXECUTION_STEP_TITLES[failedStep.id as (typeof EXECUTION_STEP_IDS)[number]] ||
                        failedStep.title
                      : '执行失败'}
                  </h2>
                  {diagnostic ? (
                    <div className="mt-3 grid gap-3">
                      <div className="rounded-lg border border-[#f5c2c7] bg-white/75 p-3">
                        <strong className="block text-sm text-[#641421]">{diagnostic.title}</strong>
                        <p className="mt-2 leading-6">{diagnostic.message}</p>
                        <div className="mt-3 grid gap-2 text-xs leading-5 sm:grid-cols-3">
                          <span>
                            <strong>阶段：</strong>
                            {formatDiagnosticPhase(diagnostic.phase)}
                          </span>
                          <span>
                            <strong>素材源：</strong>
                            {diagnostic.primaryProvider || '未指定'}
                          </span>
                          <span>
                            <strong>场景：</strong>
                            {formatSceneIds(diagnostic.failedSceneIds)}
                          </span>
                        </div>
                      </div>
                      {diagnostic.repairPrompt ? (
                        <button
                          type="button"
                          onClick={applyDiagnosticRepairPrompt}
                          className="inline-flex min-h-10 w-fit items-center justify-center rounded-lg bg-[#8b1f2d] px-4 text-sm font-semibold text-white transition hover:bg-[#721827]"
                        >
                          用建议修复方案继续修改
                        </button>
                      ) : null}
                    </div>
                  ) : (
                    <>
                      <p className="mt-2 leading-6">
                        {failedStep?.error?.message || session?.error?.message || '任务执行失败，请查看任务详情。'}
                      </p>
                      <p className="mt-2 leading-6">
                        {failedStep?.error?.retryable || session?.error?.retryableStep
                          ? '该问题可能可以重试，请先在任务页查看事件时间线。'
                          : '请在任务页查看事件时间线和外部素材下载日志。'}
                      </p>
                    </>
                  )}
                </section>
              ) : null}

              {errorText ? (
                <div className="mx-5 mb-4 rounded-lg border border-[#f5c2c7] bg-[#fff7f7] px-4 py-3 text-sm text-[#8b1f2d]">
                  {errorText}
                </div>
              ) : null}

              <form className="grid gap-3 border-t border-bordersoft bg-[#fcfdfb] p-4" onSubmit={submitMessage}>
                {awaitingGroundingConfirmation ? (
                  <div className="flex flex-wrap items-center justify-end gap-2.5">
                    <Button type="button" variant="secondary" onClick={confirmGrounding} disabled={!canConfirmGrounding}>
                      确认这些画面
                    </Button>
                  </div>
                ) : null}
                <div className="relative">
                  <textarea
                    ref={textareaRef}
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    onKeyDown={submitMessageFromKeyboard}
                    placeholder="继续补充你的修改意见。"
                    rows={4}
                    disabled={isSubmitting}
                    className="min-h-[112px] w-full resize-y rounded-[16px] border border-border bg-white px-3 pb-14 pt-3 text-sm text-ink outline-none [font:inherit] placeholder:text-secondary focus:border-[rgba(31,106,91,0.42)] focus:ring-2 focus:ring-[rgba(31,106,91,0.12)]"
                  />
                  <button
                    type="submit"
                    disabled={!canSend}
                    className={`absolute bottom-3 right-3 inline-flex min-h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${
                      canSend ? 'bg-accentstrong text-white shadow-[0_10px_24px_rgba(31,106,91,0.18)] hover:bg-accentink' : 'bg-[#e6ece8] text-[#9aa7a1]'
                    }`}
                  >
                    {isSubmitting ? '处理中' : '发送'}
                  </button>
                </div>
              </form>
            </section>
          </div>

          <aside className="min-w-0 border-t border-border bg-[color:var(--surface-muted)] p-4 xl:border-l xl:border-t-0 xl:p-5" aria-label="步骤进度">
            <AiStepFlow />
          </aside>
        </main>
      </div>
    </ProductShell>
  );
}
