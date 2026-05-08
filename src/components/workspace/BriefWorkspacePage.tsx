'use client';

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import Button from '@/components/common/Button';
import {
  confirmGroundingCandidates,
  confirmAgentSession,
  createAgentSession,
  getAgentSession,
  getAgentSessionEvents,
  sendAgentMessage,
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

function getStepStatusText(status: string) {
  return STEP_STATUS_LABELS[status] ?? status;
}

function getStepProgress(step: WorkspaceStep, fallbackProgress: number) {
  const value = step.status === 'pending' ? fallbackProgress : step.progress;
  return Math.max(0, Math.min(100, value));
}

function findFailedStep(session: AgentSession | null) {
  return session?.steps?.find((step) => step.status === 'failed') ?? null;
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
  const [selectedDirection, setSelectedDirection] = useState('');
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [restoredSessionId, setRestoredSessionId] = useState<string | null>(null);
  const [hasAppliedRestoreJump, setHasAppliedRestoreJump] = useState(false);
  const executionSectionRef = useRef<HTMLElement | null>(null);
  const resultSectionRef = useRef<HTMLElement | null>(null);
  const failureSectionRef = useRef<HTMLElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

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
    setSelectedDirection('');
    setSelectedCandidateIds(session?.grounding?.selectedCandidateIds ?? []);
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
  const canConfirmPlan = session?.status === 'plan_ready' && session?.grounding?.status === 'confirmed' && !isSubmitting;

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

  const sessionMessages = session?.messages ?? [];
  const userMessages = sessionMessages.filter((item) => item.role === 'user');
  const assistantMessages = sessionMessages.filter((item) => item.role === 'assistant');
  const latestAssistantMessage = assistantMessages.at(-1)?.content ?? '我会按步骤处理你的需求，每一步先显示进度，再展示结果。';
  const scenes = session?.plan?.scenes ?? [];
  const groundingCandidates = session?.grounding?.candidates ?? [];
  const workspaceSteps = useMemo(() => {
    if (!session?.steps?.length) {
      return FALLBACK_WORKSPACE_STEPS;
    }

    return WORKSPACE_STEP_IDS
      .map((stepId) => session.steps.find((step) => step.id === stepId))
      .filter((step): step is AgentSession['steps'][number] => Boolean(step));
  }, [session?.steps]);
  const executionSteps = useMemo(() => {
    if (!session?.steps?.length) {
      return [];
    }

    return EXECUTION_STEP_IDS
      .map((stepId) => session.steps.find((step) => step.id === stepId))
      .filter((step): step is AgentSession['steps'][number] => Boolean(step));
  }, [session?.steps]);

  const failedStep = findFailedStep(session);
  const showExecutionHandoff = Boolean(session?.activeJobId || executionSteps.some((step) => step.status !== 'pending'));
  const resultUrl = getSafeResultUrl(session?.videoUrl);
  const generateOptionsStep = workspaceSteps.find((step) => step.id === 'generate_options');
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
      (session?.error || failedStep ? failureSectionRef.current : null) ||
      (showExecutionHandoff ? executionSectionRef.current : null);

    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    setHasAppliedRestoreJump(true);
  }, [failedStep, hasAppliedRestoreJump, restoredSessionId, resultUrl, session?.error, session?.id, showExecutionHandoff]);

  return (
    <ProductShell>
      <div className="min-h-full px-4 py-4 sm:px-5">
        <header className="mx-auto w-full max-w-[980px] rounded-lg border border-border bg-white p-5 shadow-soft sm:p-6">
          <div>
            <nav className="flex items-center gap-2 text-[13px] font-bold text-secondary" aria-label="面包屑">
              <Link href="/" className="text-ink no-underline">
                ClipForge
              </Link>
              <span aria-hidden="true">/</span>
              <span>方案沟通</span>
            </nav>
            <div className="mt-3.5 flex flex-col gap-4 min-[861px]:flex-row min-[861px]:items-end min-[861px]:justify-between">
              <div className="min-w-0">
                <h1 className="text-[28px] font-semibold leading-[1.12] text-ink">方案沟通页面</h1>
                <p className="mt-2 max-w-[68ch] text-sm leading-6 text-secondary sm:text-base">
                  单栏推进需求理解、方向选择和最终确认，AI 的每一步都先给进度，再展示结果。
                </p>
              </div>
              <div className="w-full rounded-full border border-[rgba(168,198,108,0.38)] bg-[#e3efd4] px-3.5 py-2.5 text-left min-[861px]:w-auto min-[861px]:min-w-[130px] min-[861px]:text-right">
                <span className="block text-xs text-secondary">当前状态</span>
                <strong className="mt-1 block text-sm font-semibold text-accentink">{getWorkspaceStatus(session)}</strong>
              </div>
            </div>
          </div>
        </header>

        <main className="mx-auto mt-5 grid w-full max-w-[980px] gap-4" aria-label="方案工作区">
          {restoredSessionId && session?.id === restoredSessionId ? (
            <section className="grid gap-3 rounded-lg border border-border bg-white p-4 shadow-soft sm:flex sm:items-center sm:justify-between" aria-label="恢复的方案会话">
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
                  className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50"
                >
                  查看任务列表
                </Link>
                <button
                  type="button"
                  className="inline-flex min-h-10 items-center justify-center rounded-lg bg-ink px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
                  onClick={focusComposer}
                >
                  继续补充方案
                </button>
              </div>
            </section>
          ) : null}

          <section className="overflow-hidden rounded-lg border border-border bg-white shadow-soft" aria-label="方案沟通">
            <div className="flex flex-col gap-3 border-b border-bordersoft px-5 py-4 min-[861px]:flex-row min-[861px]:items-start min-[861px]:justify-between">
              <div>
                <h2 className="text-lg font-semibold leading-tight text-ink">方案沟通</h2>
                <p className="mt-1 text-[13px] leading-5 text-secondary">
                  用户原始输入保留原样，目标和结构化信息由 AI 在后续步骤提炼。
                </p>
              </div>
              <span className="text-[13px] font-bold text-secondary min-[861px]:whitespace-nowrap">每一步先显示进度，再给出结果</span>
            </div>

            <div className="grid gap-3.5 bg-[linear-gradient(180deg,rgba(168,198,108,0.05),transparent_280px),#ffffff] p-5">
              {!session ? (
                <div className="max-w-[620px] px-0 pb-2.5 pt-6">
                  <h3 className="text-[22px] font-semibold leading-tight text-ink">描述你想完成的视频</h3>
                  <p className="mt-2 leading-6 text-secondary">
                    直接说你的想法即可，目标、格式、风格和执行拆分会由 AI 在后续步骤里提炼。
                  </p>
                </div>
              ) : (
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
                    <div className="rounded-lg border border-[#e2e7e1] bg-[#f7f9f6] p-3.5 leading-[1.58] text-[#303a34]">
                      <p>{latestAssistantMessage}</p>
                    </div>
                  </article>
                </>
              )}
            </div>

            <section className="grid gap-3 px-5 pb-5" aria-label="AI 分析步骤流">
              {workspaceSteps.map((step, index) => {
                const result = asRecord(step.result);
                const optionCards = step.id === 'generate_options' ? buildGenerateOptionsCards(step) : [];
                const progress = step.status === 'pending' ? (session ? 12 + index * 5 : 14) : step.progress;
                const statusText =
                  step.status === 'succeeded' ? '完成' : step.status === 'running' ? '进行中' : step.status === 'failed' ? '失败' : '等待中';
                const stepTitle = WORKSPACE_STEP_TITLES[step.id as (typeof WORKSPACE_STEP_IDS)[number]];
                const backendSelectedOptionId = step.id === 'generate_options' ? asString(result.selectedOptionId) : '';
                const localSelectedOptionId =
                  selectedDirection && optionCards.some((option) => option.id === selectedDirection) ? selectedDirection : '';
                const displayedSelectedOptionId = localSelectedOptionId || backendSelectedOptionId || optionCards[0]?.id || '';

                return (
                  <article key={step.id} className="grid gap-2.5 rounded-lg border border-[#e1e6df] bg-white p-3">
                    <div className="flex items-center justify-between gap-3">
                      <strong className="[overflow-wrap:anywhere] text-sm font-semibold text-ink">{stepTitle}</strong>
                      <span className="whitespace-nowrap text-xs font-extrabold text-secondary">{statusText}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[#edf1ed]" aria-hidden="true">
                      <span
                        className="block h-full rounded-full bg-gradient-to-r from-accentstrong to-accent"
                        style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
                      />
                    </div>

                    {step.id === 'generate_options' ? (
                      <div className="rounded-lg border border-[#e4e8e3] bg-[#fbfcfa] p-3">
                        <div className="flex flex-col gap-3 min-[861px]:flex-row min-[861px]:items-start min-[861px]:justify-between">
                          <div>
                            <span className="mb-1.5 block text-xs font-extrabold text-secondary">方案方向</span>
                            <h3 className="text-[15px] font-semibold leading-snug text-ink">
                              {step.status === 'succeeded' ? '后端返回的方案方向卡片' : '等待后端返回方案方向。'}
                            </h3>
                          </div>
                          <span className="text-xs font-extrabold text-secondary min-[861px]:whitespace-nowrap">
                            {displayedSelectedOptionId ? '当前查看' : '等待选择'}
                          </span>
                        </div>

                        <div className="mt-3 grid gap-2.5">
                          {optionCards.length ? (
                            optionCards.map((option) => (
                              <button
                                key={option.id}
                                type="button"
                                className={`grid w-full appearance-none gap-2.5 rounded-lg border border-[#e4e8e3] bg-white p-3 text-left text-inherit outline-none transition hover:border-[#c7d3bf] hover:bg-[#fbfdf8] focus-visible:shadow-[inset_0_0_0_1px_rgba(168,198,108,0.55),0_0_0_3px_rgba(168,198,108,0.18)] ${
                                  displayedSelectedOptionId === option.id
                                    ? 'border-accent bg-[#f6faef] shadow-[inset_0_0_0_1px_rgba(168,198,108,0.55)]'
                                    : ''
                                }`}
                                onClick={() => setSelectedDirection(option.id)}
                                aria-pressed={displayedSelectedOptionId === option.id}
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <strong className="text-sm font-semibold leading-snug text-ink">{option.title}</strong>
                                  <span className="whitespace-nowrap text-xs leading-5 text-secondary">
                                    {displayedSelectedOptionId === option.id ? '当前查看' : '点击查看'}
                                  </span>
                                </div>
                                <p className="[overflow-wrap:anywhere] text-[13px] leading-5 text-[#344039]">{option.description}</p>
                                <div className="grid gap-1.5 text-xs leading-5 text-secondary [overflow-wrap:anywhere]">
                                  <span>检索方向：{option.searchQuery || '待补充'}</span>
                                  <span>关键词：{option.keywords.length ? option.keywords.join(' / ') : '待补充'}</span>
                                  <span>时长：{option.duration ? `${option.duration} 秒` : '待补充'}</span>
                                </div>
                              </button>
                            ))
                          ) : (
                            <div className="rounded-lg border border-dashed border-border bg-[rgba(247,249,246,0.8)] px-3.5 py-3 leading-6 text-secondary">
                              等待后端返回方案方向。
                            </div>
                          )}
                        </div>
                      </div>
                    ) : step.id === 'finalize_plan' ? (
                      <div className="rounded-lg border border-[#e4e8e3] bg-[#fbfcfa] p-3">
                        <div className="flex flex-col gap-3 min-[861px]:flex-row min-[861px]:items-start min-[861px]:justify-between">
                          <div>
                            <span className="mb-1.5 block text-xs font-extrabold text-secondary">最终执行方案</span>
                            <h3 className="text-[15px] font-semibold leading-snug text-ink">
                              {step.status === 'succeeded' ? '后端返回的最终执行方案' : '等待后端返回最终方案。'}
                            </h3>
                          </div>
                          <span className="text-xs font-extrabold text-secondary min-[861px]:whitespace-nowrap">
                            {canConfirmPlan ? '可确认' : '持续更新'}
                          </span>
                        </div>

                        <div className="mt-3 grid gap-3">
                          <div className="grid gap-2 min-[861px]:grid-cols-3">
                            {buildFinalPlanSummaryItems(step).map((item) => (
                              <div key={item.label} className="rounded-lg border border-[#e4e8e3] bg-white p-2.5">
                                <span className="mb-1 block text-xs font-extrabold text-secondary">{item.label}</span>
                                <strong className="[overflow-wrap:anywhere] text-[13px] font-semibold leading-5 text-ink">
                                  {item.value}
                                </strong>
                              </div>
                            ))}
                          </div>

                          <div className="grid gap-2">
                            {asArray(result.scenes).length ? (
                              asArray(result.scenes).map((scene) => {
                                const sceneRecord = asRecord(scene);
                                return (
                                  <div
                                    key={asString(sceneRecord.id) || asString(sceneRecord.searchQuery)}
                                    className="grid grid-cols-[40px_minmax(0,1fr)] gap-2.5 rounded-lg border border-[#e4e8e3] bg-white p-2.5 min-[861px]:grid-cols-[40px_minmax(0,1fr)_56px] min-[861px]:items-start"
                                  >
                                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[#e3efd4] text-sm font-semibold text-accentink">
                                      {String(asString(sceneRecord.id) || '0').padStart(2, '0')}
                                    </div>
                                    <div>
                                      <strong className="mb-1 block text-[13px] font-semibold text-ink">
                                        {asString(sceneRecord.description) || '等待后端返回计划。'}
                                      </strong>
                                      <p className="text-xs leading-5 text-secondary">
                                        关键词：
                                        {asArray(sceneRecord.keywords)
                                          .map((keyword) => asString(keyword))
                                          .filter(Boolean)
                                          .join(' / ') || '待补充'}{' '}
                                        · 检索方向：{asString(sceneRecord.searchQuery)}
                                      </p>
                                    </div>
                                    <div className="col-start-2 text-left text-xs font-extrabold text-[#758078] min-[861px]:col-auto min-[861px]:text-right">
                                      {asNumber(sceneRecord.duration)}s
                                    </div>
                                  </div>
                                );
                              })
                            ) : (
                              <div className="rounded-lg border border-dashed border-border bg-[rgba(247,249,246,0.8)] p-3.5 text-secondary">
                                <p>等待后端返回最终方案。</p>
                              </div>
                            )}
                          </div>

                          <div className="flex flex-wrap gap-2.5">
                            <Button type="button" variant="secondary" disabled={!session}>
                              继续修改
                            </Button>
                            <Button type="button" onClick={confirmPlan} disabled={!canConfirmPlan}>
                              确认方案并生成任务
                            </Button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-lg border border-[#e4e8e3] bg-[#fbfcfa] p-3">
                        <div className="grid gap-2 min-[861px]:grid-cols-3">
                          {(() => {
                            const items = buildWorkspaceStepResult(step) as Array<{ label: string; value: string }>;
                            return items.map((item) => (
                              <div key={item.label} className="rounded-lg border border-[#e4e8e3] bg-white p-2.5">
                                <span className="mb-1 block text-xs font-extrabold text-secondary">{item.label}</span>
                                <strong className="[overflow-wrap:anywhere] text-[13px] font-semibold leading-5 text-ink">
                                  {item.value}
                                </strong>
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

                <div className="grid gap-3 sm:grid-cols-2">
                  {executionSteps.map((step, index) => (
                    <article key={step.id} className="grid gap-3 rounded-lg border border-[#e4e8e3] bg-white p-3">
                      <div className="flex items-start justify-between gap-3">
                        <strong className="[overflow-wrap:anywhere] text-sm text-ink">
                          {EXECUTION_STEP_TITLES[step.id as (typeof EXECUTION_STEP_IDS)[number]]}
                        </strong>
                        <span className="whitespace-nowrap text-xs font-bold text-secondary">{getStepStatusText(step.status)}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-[#edf1ed]" aria-hidden="true">
                        <span
                          className="block h-full rounded-full bg-gradient-to-r from-accentstrong to-accent"
                          style={{ width: `${getStepProgress(step, 10 + index * 8)}%` }}
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

            {session?.error || failedStep ? (
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
                <p className="mt-2 leading-6">
                  {failedStep?.error?.message || session?.error?.message || '任务执行失败，请查看任务详情。'}
                </p>
                <p className="mt-2 leading-6">
                  {failedStep?.error?.retryable || session?.error?.retryableStep
                    ? '该问题可能可以重试，请先在任务页查看事件时间线。'
                    : '请在任务页查看事件时间线和外部素材下载日志。'}
                </p>
              </section>
            ) : null}

            {errorText ? (
              <div className="mx-5 mb-4 rounded-lg border border-[#f5c2c7] bg-[#fff7f7] px-4 py-3 text-sm text-[#8b1f2d]">
                {errorText}
              </div>
            ) : null}

            <form className="grid gap-3 border-t border-bordersoft bg-[#fcfdfb] p-4" onSubmit={submitMessage}>
              <textarea
                ref={textareaRef}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={submitMessageFromKeyboard}
                placeholder="继续补充你的修改意见，或直接确认最终方案。"
                rows={4}
                disabled={isSubmitting}
                className="min-h-[92px] w-full resize-y rounded-lg border border-border bg-white p-3 text-sm text-ink outline-none [font:inherit] placeholder:text-secondary focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
              />
              <div className="flex flex-col gap-3 min-[861px]:flex-row min-[861px]:items-center min-[861px]:justify-between">
                <span className="text-xs text-secondary">底部输入区用于继续补充信息、修改方案，或推动下一轮细化。</span>
                <div className="flex flex-wrap gap-2.5">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={awaitingGroundingConfirmation ? confirmGrounding : confirmPlan}
                    disabled={awaitingGroundingConfirmation ? !canConfirmGrounding : !canConfirmPlan}
                  >
                    {awaitingGroundingConfirmation ? '确认这些画面' : '确认方案并生成任务'}
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
