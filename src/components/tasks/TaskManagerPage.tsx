'use client';

import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentTask, listAgentTasks, type AgentTaskDetail, type AgentTaskSummary } from '@/lib/taskApi';
import { useAgentStore } from '@/stores/useAgentStore';

const FALLBACK_TASKS: AgentTaskSummary[] = [];

const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  pending: '待处理',
  running: '进行中',
  active: '进行中',
  completed: '已完成',
  done: '已完成',
  succeeded: '已完成',
  failed: '失败',
  error: '失败',
  canceled: '已取消',
  cancelled: '已取消',
  idle: '待处理',
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function formatProgress(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}

function getStatusLabel(status: string) {
  return STATUS_LABELS[status] ?? status;
}

function getStepStatusLabel(status: string) {
  switch (status) {
    case 'pending':
      return '等待中';
    case 'running':
      return '进行中';
    case 'succeeded':
      return '已完成';
    case 'failed':
      return '失败';
    case 'skipped':
      return '已跳过';
    default:
      return status;
  }
}

function getStatusClasses(status: string) {
  switch (status) {
    case 'completed':
    case 'done':
    case 'succeeded':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
    case 'failed':
    case 'error':
      return 'bg-rose-50 text-rose-700 ring-rose-200';
    case 'running':
    case 'active':
      return 'bg-sky-50 text-sky-700 ring-sky-200';
    case 'queued':
    case 'pending':
    case 'idle':
    case 'canceled':
    case 'cancelled':
    default:
      return 'bg-amber-50 text-amber-700 ring-amber-200';
  }
}

function getTaskResultLabel(task: AgentTaskDetail) {
  if (task.videoUrl) {
    return '已有成片';
  }
  if (task.error) {
    return '待修复';
  }
  return '执行中';
}

function getClipCountLabel(task: AgentTaskDetail) {
  return `${task.clips.length} 段素材`;
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-[#e9eee6]" aria-hidden="true">
      <span
        className="block h-full rounded-full bg-gradient-to-r from-[#8eb45f] to-[#4b8a86]"
        style={{ width: formatProgress(value) }}
      />
    </div>
  );
}

function getTaskSearchText(task: AgentTaskSummary) {
  return `${task.title} ${task.status} ${task.currentStep} ${task.currentStepId ?? ''} ${task.sessionId} ${task.id}`.toLowerCase();
}

function getEventTimestamp(value: string | null | undefined) {
  if (!value) {
    return '无时间戳';
  }
  return formatDateTime(value);
}

function isCompletedTask(status: string) {
  return status === 'completed' || status === 'done' || status === 'succeeded';
}

function isFailedTask(status: string) {
  return status === 'failed' || status === 'error';
}

function getTaskRowAccentClasses(task: AgentTaskSummary, hasResult: boolean) {
  if (isFailedTask(task.status)) {
    return 'border-rose-200 bg-rose-50/60';
  }
  if (hasResult) {
    return 'border-emerald-200 bg-emerald-50/50';
  }
  return 'border-border bg-white';
}

export default function TaskManagerPage() {
  const router = useRouter();
  const setActiveSessionId = useAgentStore((state) => state.setActiveSessionId);
  const setSession = useAgentStore((state) => state.setSession);
  const [tasks, setTasks] = useState<AgentTaskSummary[]>(FALLBACK_TASKS);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeTask, setActiveTask] = useState<AgentTaskDetail | null>(null);
  const [taskVideoUrls, setTaskVideoUrls] = useState<Record<string, string>>({});
  const [taskResultLoadingIds, setTaskResultLoadingIds] = useState<Record<string, boolean>>({});
  const [errorText, setErrorText] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshingTaskDetail, setIsRefreshingTaskDetail] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const detailRequestIdRef = useRef(0);
  const focusRestoreTokenRef = useRef(0);

  useEffect(() => {
    let isActive = true;

    const loadTasks = async () => {
      try {
        setIsLoading(true);
        const nextTasks = await listAgentTasks();
        if (isActive) {
          setTasks(nextTasks);
          setErrorText(null);
        }
      } catch {
        if (isActive) {
          setTasks(FALLBACK_TASKS);
          setErrorText('任务列表暂时不可用，请稍后重试。');
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadTasks();

    return () => {
      isActive = false;
    };
  }, []);

  const statusOptions = useMemo(() => {
    const values = new Set<string>(['all']);
    tasks.forEach((task) => values.add(task.status));
    return Array.from(values);
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return tasks.filter((task) => {
      const matchesFilter = filter === 'all' || task.status === filter;
      const matchesQuery = !keyword || getTaskSearchText(task).includes(keyword);
      return matchesFilter && matchesQuery;
    });
  }, [filter, query, tasks]);

  useEffect(() => {
    setSelectedIds((prev) => prev.filter((id) => filteredTasks.some((task) => task.id === id)));
  }, [filteredTasks]);

  const activeSelection = useMemo(
    () => filteredTasks.find((task) => task.id === selectedIds[0]) ?? null,
    [filteredTasks, selectedIds],
  );

  const hasTasks = filteredTasks.length > 0;

  const selectedTasks = useMemo(
    () => filteredTasks.filter((task) => selectedIds.includes(task.id)),
    [filteredTasks, selectedIds],
  );

  useEffect(() => {
    filteredTasks.forEach((task) => {
      if (isCompletedTask(task.status) && !taskVideoUrls[task.id] && taskResultLoadingIds[task.id] === undefined) {
        void primeTaskResult(task.id);
      }
    });
  }, [filteredTasks, taskResultLoadingIds, taskVideoUrls]);

  useEffect(() => {
    if (activeTask) {
      closeButtonRef.current?.focus();
    }
  }, [activeTask]);

  async function openTaskDetail(taskId: string) {
    detailRequestIdRef.current += 1;
    const requestId = detailRequestIdRef.current;
    focusRestoreTokenRef.current += 1;
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setErrorText(null);
    setSelectedIds((prev) => (prev.includes(taskId) ? prev : [...prev, taskId]));
    try {
      const detail = await getAgentTask(taskId);
      if (detailRequestIdRef.current !== requestId) {
        return;
      }
      setActiveTask(detail);
      if (detail.videoUrl) {
        setTaskVideoUrls((prev) => ({ ...prev, [taskId]: detail.videoUrl as string }));
      }
    } catch {
      if (detailRequestIdRef.current === requestId) {
        setErrorText('任务详情暂时加载失败。');
      }
    }
  }

  function toggleSelected(taskId: string) {
    setSelectedIds((prev) => (prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]));
  }

  async function refreshActiveTaskDetail() {
    if (!activeTask) {
      return;
    }

    const requestId = detailRequestIdRef.current + 1;
    detailRequestIdRef.current = requestId;
    setIsRefreshingTaskDetail(true);
    setErrorText(null);

    try {
      const detail = await getAgentTask(activeTask.id);
      if (detailRequestIdRef.current !== requestId) {
        return;
      }
      setActiveTask(detail);
      if (detail.videoUrl) {
        setTaskVideoUrls((prev) => ({ ...prev, [activeTask.id]: detail.videoUrl as string }));
      }
    } catch {
      if (detailRequestIdRef.current === requestId) {
        setErrorText('任务详情暂时加载失败。');
      }
    } finally {
      if (detailRequestIdRef.current === requestId) {
        setIsRefreshingTaskDetail(false);
      }
    }
  }

  async function primeTaskResult(taskId: string) {
    if (taskVideoUrls[taskId] || taskResultLoadingIds[taskId] !== undefined) {
      return;
    }

    setTaskResultLoadingIds((prev) => ({ ...prev, [taskId]: true }));

    try {
      const detail = await getAgentTask(taskId);
      if (detail.videoUrl) {
        setTaskVideoUrls((prev) => ({ ...prev, [taskId]: detail.videoUrl as string }));
      }
    } catch {
      // Keep result prefetch silent; explicit row actions surface readable errors.
    } finally {
      setTaskResultLoadingIds((prev) => ({ ...prev, [taskId]: false }));
    }
  }

  async function openTaskResult(taskId: string) {
    const cachedUrl = taskVideoUrls[taskId];
    if (cachedUrl) {
      window.open(cachedUrl, '_blank', 'noopener,noreferrer');
      return;
    }

    setErrorText(null);

    try {
      const detail = await getAgentTask(taskId);
      if (detail.videoUrl) {
        setTaskVideoUrls((prev) => ({ ...prev, [taskId]: detail.videoUrl as string }));
        window.open(detail.videoUrl, '_blank', 'noopener,noreferrer');
        return;
      }
      setErrorText('当前任务还没有可打开的成片，请稍后再试。');
    } catch {
      setErrorText('当前任务结果暂时无法读取，请稍后再试。');
    }
  }

  function openWorkspaceForTask(sessionId: string) {
    if (!sessionId) {
      setErrorText('当前任务缺少方案会话，暂时无法打开方案页。');
      return;
    }

    setSession(null);
    setActiveSessionId(sessionId);
    router.push('/workspace');
  }

  function openWorkspaceForActiveTask() {
    if (!activeTask?.sessionId) {
      setErrorText('当前任务缺少方案会话，暂时无法打开方案页。');
      return;
    }

    setSession(null);
    setActiveSessionId(activeTask.sessionId);
    router.push('/workspace');
  }

  function closeTaskDetail() {
    detailRequestIdRef.current += 1;
    focusRestoreTokenRef.current += 1;
    const restoreToken = focusRestoreTokenRef.current;
    setIsRefreshingTaskDetail(false);
    setActiveTask(null);
    requestAnimationFrame(() => {
      if (focusRestoreTokenRef.current === restoreToken) {
        returnFocusRef.current?.focus();
      }
    });
  }

  function handleModalKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.stopPropagation();
      closeTaskDetail();
      return;
    }

    if (event.key !== 'Tab' || !modalRef.current) {
      return;
    }

    const focusableElements = Array.from(
      modalRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((element) => !element.hasAttribute('disabled') && element.tabIndex !== -1);

    if (focusableElements.length === 0) {
      return;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (event.shiftKey && document.activeElement === firstElement) {
      event.preventDefault();
      lastElement.focus();
    } else if (!event.shiftKey && document.activeElement === lastElement) {
      event.preventDefault();
      firstElement.focus();
    }
  }

  return (
    <ProductShell>
      <div className="grid min-w-0 gap-4 lg:gap-5">
        <section
          className="rounded-lg border border-border bg-white/90 p-5 shadow-soft sm:p-6"
          aria-label="任务管理"
        >
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 flex-1 space-y-4">
              <nav className="flex items-center gap-2 text-xs font-medium text-secondary" aria-label="面包屑">
                <Link href="/" className="font-semibold text-ink">
                  总览
                </Link>
                <span aria-hidden="true">/</span>
                <span>任务</span>
              </nav>

              <div className="space-y-3">
                <div className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  {isLoading ? '加载中' : `${filteredTasks.length} 项`}
                </div>
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">任务控制台</h1>
                <p className="max-w-3xl text-sm leading-6 text-secondary sm:text-base">
                  统一扫读任务状态、最近活动和结果入口；先在列表判断下一步，再按需进入详情弹窗。
                </p>
              </div>
            </div>

            <div className="grid w-full gap-3 md:grid-cols-[minmax(0,1fr)_160px_auto] xl:max-w-xl">
              <label className="grid gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">搜索</span>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="按标题、ID、状态或步骤筛选"
                  aria-label="搜索任务"
                  className="min-h-11 w-full rounded-lg border border-border bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                />
              </label>

              <label className="grid gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">状态</span>
                <select
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  aria-label="筛选状态"
                  className="min-h-11 w-full rounded-lg border border-border bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                >
                  {statusOptions.map((status) => (
                    <option key={status} value={status}>
                      {status === 'all' ? '全部状态' : getStatusLabel(status)}
                    </option>
                  ))}
                </select>
              </label>

              <div className="grid gap-2">
                <button
                  type="button"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-slate-100 px-5 text-sm font-semibold text-slate-500"
                  disabled
                >
                  批量操作将在后续阶段开放
                </button>
                <p className="text-xs leading-5 text-secondary">
                  本阶段先支持单任务查看、回到方案和结果直达。
                </p>
              </div>
            </div>
          </div>
        </section>

        {errorText ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-soft">
            {errorText}
          </p>
        ) : null}

        <section className="rounded-lg border border-border bg-white/85 p-5 shadow-soft sm:p-6" aria-label="任务列表">
          <div className="flex flex-col gap-4 border-b border-border pb-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">任务列表</span>
              <div className="space-y-1">
                <h2 className="text-xl font-semibold text-ink">可管理任务列表</h2>
                <p className="text-sm leading-6 text-secondary">列表 + 弹窗详情，聚焦状态、进度与待处理异常。</p>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end">
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-secondary ring-1 ring-border">
                {selectedIds.length} 已选
              </span>
              <button
                type="button"
                className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
                onClick={() => setSelectedIds([])}
                disabled={selectedIds.length === 0}
              >
                清除选择
              </button>
              <button
                type="button"
                className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
                onClick={() => {
                  if (activeSelection) {
                    void openTaskDetail(activeSelection.id);
                  }
                }}
                disabled={!activeSelection}
              >
                查看已选
              </button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full border border-border bg-slate-50 px-3 py-1 text-xs font-semibold text-secondary">
              {tasks.length} 个任务
            </span>
            <span className="rounded-full border border-border bg-slate-50 px-3 py-1 text-xs font-semibold text-secondary">
              {selectedTasks.length} 个已选
            </span>
            <span className="rounded-full border border-border bg-slate-50 px-3 py-1 text-xs font-semibold text-secondary">
              失败优先关注
            </span>
            <span className="rounded-full border border-border bg-slate-50 px-3 py-1 text-xs font-semibold text-secondary">
              结果直达
            </span>
          </div>

          <div className="mt-4 hidden min-h-11 grid-cols-[28px_minmax(220px,1.45fr)_110px_130px_minmax(140px,0.9fr)_130px_220px] items-center gap-3 border-b border-border px-3 text-xs font-semibold text-secondary lg:grid">
            <span />
            <span>任务</span>
            <span>状态</span>
            <span>进度</span>
            <span>当前阶段</span>
            <span>更新时间</span>
            <span>操作</span>
          </div>

          <div className="mt-3 grid gap-3 lg:mt-0 lg:gap-0">
            {hasTasks ? (
              filteredTasks.map((task) => {
                const isSelected = selectedIds.includes(task.id);
                const hasResult = Boolean(taskVideoUrls[task.id]);
                const rowAccentClasses = getTaskRowAccentClasses(task, hasResult);

                return (
                  <div
                    key={task.id}
                    className={[
                      'grid gap-3 rounded-lg border p-3 shadow-soft transition lg:grid-cols-[28px_minmax(220px,1.45fr)_110px_130px_minmax(140px,0.9fr)_130px_220px] lg:items-center lg:rounded-none lg:border-x-0 lg:border-b lg:border-t-0 lg:p-3 lg:shadow-none',
                      rowAccentClasses,
                      isSelected ? 'ring-2 ring-lime-200' : 'hover:bg-slate-50/80',
                    ].join(' ')}
                  >
                    <label className="inline-grid w-[18px] place-items-start pt-[3px]">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelected(task.id)}
                        aria-label={`选择任务 ${task.title}`}
                        className="h-4 w-4 rounded border-border text-slate-900 focus:ring-slate-300"
                      />
                    </label>

                    <button
                      type="button"
                      className="grid min-w-0 gap-1 text-left text-ink"
                      onClick={() => void openTaskDetail(task.id)}
                    >
                      <span className="text-base font-semibold leading-6">{task.title}</span>
                      <span className="text-sm leading-6 text-secondary">
                        {task.sessionId} · 任务 ID {task.id}
                      </span>
                      <span className="text-xs leading-5 text-secondary">
                        {hasResult ? '已有成片，可直接打开结果。' : isFailedTask(task.status) ? '任务失败，建议先看详情或回到方案页。' : '继续关注当前阶段推进。'}
                      </span>
                    </button>

                    <div className="min-w-0">
                      <span
                        className={`inline-flex min-h-[26px] items-center rounded-full px-3 text-xs font-semibold ring-1 ${getStatusClasses(task.status)}`}
                      >
                        {getStatusLabel(task.status)}
                      </span>
                    </div>

                    <div className="grid gap-2">
                      <span className="text-xs font-semibold text-secondary">{formatProgress(task.progress)}</span>
                      <ProgressBar value={task.progress} />
                    </div>

                    <div className="text-sm leading-6 text-secondary">
                      <span>{task.currentStep || '等待下一步推进'}</span>
                    </div>

                    <div className="text-sm leading-6 text-secondary lg:text-right">
                      <span>{formatDateTime(task.updatedAt)}</span>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                      <button
                        type="button"
                        className="text-xs font-semibold text-ink transition hover:text-slate-600"
                        onClick={() => void openTaskDetail(task.id)}
                      >
                        查看详情
                      </button>
                      <button
                        type="button"
                        className="text-xs font-semibold text-ink transition hover:text-slate-600"
                        onClick={() => openWorkspaceForTask(task.sessionId)}
                      >
                        查看方案
                      </button>
                      {hasResult ? (
                        <button
                          type="button"
                          className="text-xs font-semibold text-emerald-700 transition hover:text-emerald-800"
                          onClick={() => void openTaskResult(task.id)}
                        >
                          打开结果
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="mt-4 rounded-lg border border-dashed border-border bg-slate-50/90 p-5 text-sm leading-6 text-secondary">
                <p>当前没有匹配的任务。</p>
              </div>
            )}
          </div>
        </section>
      </div>

      {activeTask ? (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4 sm:p-6"
          role="presentation"
          onClick={closeTaskDetail}
        >
          <div
            ref={modalRef}
            className="max-h-[calc(100vh-32px)] w-full max-w-6xl overflow-auto rounded-lg border border-border bg-white p-5 shadow-soft sm:max-h-[calc(100vh-48px)] sm:p-6"
            role="dialog"
            aria-modal="true"
            aria-labelledby="task-detail-title"
            tabIndex={-1}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={handleModalKeyDown}
          >
            <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
              <div className="min-w-0">
                <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  列表 + 弹窗详情
                </span>
                <h2 id="task-detail-title" className="mt-1 text-2xl font-semibold leading-tight text-ink">
                  任务详情：{activeTask.title}
                </h2>
                <p className="mt-2 text-sm leading-6 text-secondary">
                  {activeTask.sessionId} · 任务 ID {activeTask.id} · 创建于 {formatDateTime(activeTask.createdAt)}
                </p>
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-white text-xl leading-none text-ink transition hover:bg-slate-50"
                onClick={closeTaskDetail}
                aria-label="关闭详情"
              >
                ×
              </button>
            </div>

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
              <div className="grid gap-4">
                <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                  <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1">
                      <h3 className="text-sm font-semibold text-ink">状态摘要</h3>
                      <p className="text-sm leading-6 text-secondary">
                        当前步骤、最近更新时间和产出状态会在这里汇总。
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      <span
                        className={`inline-flex min-h-[28px] items-center rounded-full px-3 text-xs font-semibold ring-1 ${getStatusClasses(activeTask.status)}`}
                      >
                        {getStatusLabel(activeTask.status)}
                      </span>
                      <span className="text-sm font-semibold text-secondary">{formatProgress(activeTask.progress)}</span>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <article className="rounded-lg border border-border bg-white/90 p-4">
                      <span className="block text-xs font-semibold text-secondary">当前步骤</span>
                      <strong className="mt-2 block text-base font-semibold text-ink">
                        {activeTask.currentStep || '等待下一步推进'}
                      </strong>
                    </article>
                    <article className="rounded-lg border border-border bg-white/90 p-4">
                      <span className="block text-xs font-semibold text-secondary">最近更新时间</span>
                      <strong className="mt-2 block text-base font-semibold text-ink">
                        {formatDateTime(activeTask.updatedAt)}
                      </strong>
                    </article>
                    <article className="rounded-lg border border-border bg-white/90 p-4">
                      <span className="block text-xs font-semibold text-secondary">产出状态</span>
                      <strong className="mt-2 block text-base font-semibold text-ink">
                        {getTaskResultLabel(activeTask)}
                      </strong>
                    </article>
                  </div>

                  <div className="mt-4">
                    <ProgressBar value={activeTask.progress} />
                  </div>

                  <div className="mt-4 rounded-lg border border-slate-200 bg-white/85 p-4">
                    <span className="block text-xs font-semibold text-secondary">错误信息</span>
                    <p className="mt-2 text-sm leading-6 text-ink">
                      {activeTask.error ? activeTask.error.message ?? '任务存在错误信息，但未返回详细文案。' : '未检测到错误。'}
                    </p>
                  </div>

                  {activeTask.diagnostic ? (
                    <div className="mt-4 rounded-lg border border-rose-200 bg-white/85 p-4">
                      <span className="block text-xs font-semibold text-secondary">诊断摘要</span>
                      <strong className="mt-2 block text-sm font-semibold text-ink">
                        {activeTask.diagnostic.title}
                      </strong>
                      <p className="mt-2 text-sm leading-6 text-ink">{activeTask.diagnostic.message}</p>
                    </div>
                  ) : null}
                </section>

                <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                  <h3 className="text-sm font-semibold text-ink">标准步骤</h3>
                  <div className="mt-3 grid gap-3">
                    {activeTask.steps.length > 0 ? (
                      activeTask.steps.map((step) => (
                        <article key={step.id} className="grid gap-3 rounded-lg border border-border bg-white/90 p-4">
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                              <strong className="block text-sm font-semibold leading-6 text-ink">{step.title}</strong>
                              <p className="mt-1 text-xs leading-5 text-secondary">{step.description}</p>
                            </div>
                            <span className="inline-flex w-fit items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-secondary">
                              {getStepStatusLabel(step.status)}
                            </span>
                          </div>
                          <div className="grid gap-2">
                            <span className="text-xs font-semibold text-secondary">{formatProgress(step.progress)}</span>
                            <ProgressBar value={step.progress} />
                          </div>
                          <p className="text-sm leading-6 text-ink">{step.summary || '暂无步骤摘要。'}</p>
                          {step.error ? <p className="text-sm leading-6 text-rose-700">{step.error.message}</p> : null}
                        </article>
                      ))
                    ) : (
                      <p className="text-sm leading-6 text-secondary">暂无标准步骤。</p>
                    )}
                  </div>
                </section>

                <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                  <h3 className="text-sm font-semibold text-ink">事件时间线</h3>
                  <div className="mt-3 grid gap-3">
                    {activeTask.events.length > 0 ? (
                      activeTask.events.map((event, index) => (
                        <article key={`${event.id}-${index}`} className="rounded-lg border border-border bg-white/90 p-4">
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div className="space-y-1">
                              <strong className="block text-sm font-semibold text-ink">{event.eventType}</strong>
                              <span className="text-xs font-medium text-secondary">
                                {event.step ? `步骤：${event.step}` : '步骤：系统事件'}
                              </span>
                            </div>
                            <span className="text-xs font-medium text-secondary">{getEventTimestamp(event.createdAt)}</span>
                          </div>
                          <p className="mt-3 text-sm leading-6 text-ink">{String(event.message ?? '暂无事件描述。')}</p>
                        </article>
                      ))
                    ) : (
                      <p className="text-sm leading-6 text-secondary">暂无事件。</p>
                    )}
                  </div>
                </section>
              </div>

              <div className="grid gap-4">
                <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                  <h3 className="text-sm font-semibold text-ink">素材与结果</h3>
                  <div className="mt-3 rounded-lg border border-border bg-white/90 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-semibold text-secondary">素材概况</span>
                      <strong className="text-sm font-semibold text-ink">{getClipCountLabel(activeTask)}</strong>
                    </div>
                    <div className="mt-3 grid gap-3">
                      {activeTask.clips.length > 0 ? (
                        activeTask.clips.map((clip, index) => (
                          <article key={`${clip.publicUrl}-${index}`} className="rounded-lg border border-border bg-slate-50/80 p-3">
                            <div className="flex flex-col gap-2">
                              <div className="flex items-start justify-between gap-3">
                                <strong className="text-sm font-semibold text-ink">Scene {clip.sceneId}</strong>
                                <span className="text-xs font-medium text-secondary">{clip.duration}s</span>
                              </div>
                              <p className="text-sm leading-6 text-secondary">{clip.caption || '暂无素材说明。'}</p>
                              <a
                                href={clip.publicUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs font-semibold text-ink underline-offset-2 hover:underline"
                              >
                                查看素材片段
                              </a>
                            </div>
                          </article>
                        ))
                      ) : (
                        <p className="text-sm leading-6 text-secondary">当前还没有可用素材。</p>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 rounded-lg border border-border bg-white/90 p-4">
                    <span className="block text-xs font-semibold text-secondary">输出视频</span>
                    <p className="mt-2 text-sm leading-6 text-ink">
                      {activeTask.videoUrl ? '已生成成片，可继续预览或下载。' : '还没有最终视频，等待渲染完成。'}
                    </p>
                    {activeTask.videoUrl ? (
                      <a
                        href={activeTask.videoUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-3 inline-flex min-h-10 items-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white no-underline transition hover:bg-slate-800"
                      >
                        打开当前成片
                      </a>
                    ) : null}
                  </div>
                </section>

                <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                  <h3 className="text-sm font-semibold text-ink">结果与操作</h3>
                  <div className="mt-3 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void refreshActiveTaskDetail()}
                      disabled={isRefreshingTaskDetail}
                      className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink transition hover:bg-slate-50"
                    >
                      {isRefreshingTaskDetail ? '刷新中' : '刷新状态'}
                    </button>
                    <button
                      type="button"
                      onClick={openWorkspaceForActiveTask}
                      className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink transition hover:bg-slate-50"
                    >
                      查看方案
                    </button>
                    {activeTask.status === 'failed' || activeTask.status === 'error' ? (
                      <div className="grid gap-2">
                        <button
                          type="button"
                          disabled
                          className="inline-flex min-h-10 items-center rounded-lg bg-slate-300 px-4 text-sm font-medium text-slate-600"
                        >
                          重新执行
                        </button>
                        <p className="text-xs leading-5 text-secondary">
                          任务级重新执行暂未开放，请返回方案页重新发起。
                        </p>
                      </div>
                    ) : null}
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </ProductShell>
  );
}
