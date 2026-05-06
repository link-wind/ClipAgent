'use client';

import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentTask, listAgentTasks, type AgentTaskDetail, type AgentTaskSummary } from '@/lib/taskApi';

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

const STATUS_TONES: Record<string, string> = {
  queued: 'bg-slate-100 text-slate-700',
  pending: 'bg-slate-100 text-slate-700',
  running: 'bg-sky-100 text-sky-700',
  active: 'bg-sky-100 text-sky-700',
  completed: 'bg-emerald-100 text-emerald-700',
  done: 'bg-emerald-100 text-emerald-700',
  succeeded: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-rose-100 text-rose-700',
  error: 'bg-rose-100 text-rose-700',
  canceled: 'bg-zinc-100 text-zinc-600',
  cancelled: 'bg-zinc-100 text-zinc-600',
  idle: 'bg-slate-100 text-slate-700',
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

function getStatusTone(status: string) {
  return STATUS_TONES[status] ?? 'bg-sky-100 text-sky-700';
}

function getTaskSearchText(task: AgentTaskSummary) {
  return `${task.title} ${task.status} ${task.currentStep} ${task.currentStepId ?? ''} ${task.sessionId} ${task.id}`.toLowerCase();
}

function buildTaskSummary(task: AgentTaskDetail) {
  return [
    { label: '状态', value: getStatusLabel(task.status) },
    { label: '当前步骤', value: task.currentStep || '无' },
    { label: '总进度', value: formatProgress(task.progress) },
    { label: '最近更新时间', value: formatDateTime(task.updatedAt) },
  ];
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

function findFailedStep(task: AgentTaskDetail | null) {
  return task?.steps.find((step) => step.status === 'failed') ?? null;
}

function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
      <span
        className="block h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400"
        style={{ width: formatProgress(progress) }}
      />
    </div>
  );
}

export default function TaskManagerPage() {
  const [tasks, setTasks] = useState<AgentTaskSummary[]>(FALLBACK_TASKS);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeTask, setActiveTask] = useState<AgentTaskDetail | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
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

  const selectedTasks = useMemo(
    () => filteredTasks.filter((task) => selectedIds.includes(task.id)),
    [filteredTasks, selectedIds],
  );

  const hasTasks = filteredTasks.length > 0;
  const failedStep = findFailedStep(activeTask);
  const resultUrl = getSafeResultUrl(activeTask?.videoUrl);

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
    } catch {
      if (detailRequestIdRef.current === requestId) {
        setErrorText('任务详情暂时加载失败。');
      }
    }
  }

  function toggleSelected(taskId: string) {
    setSelectedIds((prev) => (prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]));
  }

  function closeTaskDetail() {
    detailRequestIdRef.current += 1;
    focusRestoreTokenRef.current += 1;
    const restoreToken = focusRestoreTokenRef.current;
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
      <div className="min-h-full space-y-4">
        <section className="rounded-lg border border-border bg-white/85 p-5 shadow-soft sm:p-6" aria-label="任务管理">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0 flex-1 space-y-3">
              <nav className="flex items-center gap-2 text-xs font-medium text-secondary" aria-label="面包屑">
                <Link href="/" className="font-semibold text-ink">
                  总览
                </Link>
                <span aria-hidden="true">/</span>
                <span>任务</span>
              </nav>
              <div className="space-y-2">
                <div className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  {isLoading ? '加载中' : `${filteredTasks.length} 项`}
                </div>
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">任务管理页面</h1>
                <p className="max-w-3xl text-sm leading-6 text-secondary sm:text-base">
                  统一查看任务队列、状态和最近结果；在列表里筛选、搜索、批量理解任务状态，并通过弹窗查看和处理单个任务。
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

              <button
                type="button"
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-45"
                disabled={selectedIds.length === 0}
              >
                批量操作
              </button>
            </div>
          </div>
        </section>

        {errorText ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-soft">
            {errorText}
          </p>
        ) : null}

        <section className="rounded-lg border border-border bg-white/80 p-5 shadow-soft sm:p-6" aria-label="任务列表">
          <div className="flex flex-col gap-4 border-b border-border pb-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">任务列表</span>
              <div className="space-y-1">
                <h2 className="text-xl font-semibold text-ink">可管理任务列表</h2>
                <p className="text-sm leading-6 text-secondary">聚焦状态、进度和最近更新时间，快速定位需要处理的任务。</p>
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
              按更新时间查看
            </span>
          </div>

          <div className="mt-4 hidden min-h-11 grid-cols-[28px_minmax(220px,1.45fr)_110px_130px_minmax(140px,0.9fr)_130px_110px] items-center gap-3 border-b border-border px-3 text-xs font-semibold text-secondary lg:grid">
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

                return (
                  <div
                    key={task.id}
                    className={[
                      'grid gap-3 rounded-lg border border-border bg-white p-3 shadow-soft transition lg:grid-cols-[28px_minmax(220px,1.45fr)_110px_130px_minmax(140px,0.9fr)_130px_110px] lg:items-center lg:rounded-none lg:border-x-0 lg:border-b lg:border-t-0 lg:p-3 lg:shadow-none',
                      isSelected ? 'border-lime-200 bg-lime-50/70' : 'hover:bg-slate-50/70',
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
                    </button>

                    <div className="min-w-0">
                      <span className={`inline-flex min-h-[26px] items-center rounded-full px-3 text-xs font-semibold ${getStatusTone(task.status)}`}>
                        {getStatusLabel(task.status)}
                      </span>
                    </div>

                    <div className="grid gap-2">
                      <span className="text-xs font-semibold text-secondary">{formatProgress(task.progress)}</span>
                      <ProgressBar progress={task.progress} />
                    </div>

                    <div className="text-sm leading-6 text-secondary">
                      <span>{task.currentStep || '等待下一步推进'}</span>
                    </div>

                    <div className="text-sm leading-6 text-secondary lg:text-right">
                      <span>{formatDateTime(task.updatedAt)}</span>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                      {task.status === 'failed' || task.status === 'error' ? (
                        <button type="button" className="text-xs font-semibold text-rose-700 transition hover:text-rose-800">
                          重试
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="text-xs font-semibold text-ink transition hover:text-slate-600"
                        onClick={() => void openTaskDetail(task.id)}
                      >
                        查看详情
                      </button>
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
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4 sm:p-6" role="presentation" onClick={closeTaskDetail}>
          <div
            ref={modalRef}
            className="max-h-[calc(100vh-32px)] w-full max-w-5xl overflow-auto rounded-lg border border-border bg-white p-5 shadow-soft sm:max-h-[calc(100vh-48px)] sm:p-6"
            role="dialog"
            aria-modal="true"
            aria-labelledby="task-detail-title"
            tabIndex={-1}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={handleModalKeyDown}
          >
            <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
              <div className="min-w-0">
                <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">任务详情</span>
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

            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {buildTaskSummary(activeTask).map((item) => (
                <div key={item.label} className="rounded-lg border border-border bg-slate-50/90 p-4">
                  <span className="block text-xs font-semibold text-secondary">{item.label}</span>
                  <strong className="mt-2 block break-words text-base font-semibold text-ink">{item.value}</strong>
                </div>
              ))}
            </div>

            <div className="mt-4 grid gap-4">
              <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                <h3 className="text-sm font-semibold text-ink">状态与进度</h3>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <span className={`inline-flex min-h-[26px] items-center rounded-full px-3 text-xs font-semibold ${getStatusTone(activeTask.status)}`}>
                    {getStatusLabel(activeTask.status)}
                  </span>
                  <span className="text-sm font-semibold text-secondary">{formatProgress(activeTask.progress)}</span>
                </div>
                <div className="mt-3">
                  <ProgressBar progress={activeTask.progress} />
                </div>
              </section>

              <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                <h3 className="text-sm font-semibold text-ink">错误信息</h3>
                <div className="mt-2 space-y-2 text-sm leading-6 text-secondary">
                  <p>{activeTask.error ? activeTask.error.message ?? '任务存在错误信息，但未返回详细文案。' : '未检测到错误。'}</p>
                  {failedStep ? <p className="text-rose-700">失败步骤：{failedStep.title}</p> : null}
                </div>
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
                          <ProgressBar progress={step.progress} />
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
                <ul className="mt-3 grid gap-0">
                  {activeTask.events.length > 0 ? (
                    activeTask.events.map((event, index) => (
                      <li
                        key={`${event.id}-${index}`}
                        className="grid gap-1 border-b border-slate-200 py-3 last:border-b-0"
                      >
                        <strong className="text-sm font-semibold text-ink">{event.eventType}</strong>
                        <span className="text-sm leading-6 text-secondary">
                          {event.step ? `${event.step} · ` : ''}
                          {String(event.message ?? '')}
                        </span>
                      </li>
                    ))
                  ) : (
                    <li className="text-sm leading-6 text-secondary">暂无事件。</li>
                  )}
                </ul>
              </section>

              <section className="rounded-lg border border-border bg-slate-50/80 p-4">
                <h3 className="text-sm font-semibold text-ink">结果与操作</h3>
                <div className="mt-3 flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink transition hover:bg-slate-50"
                  >
                    刷新状态
                  </button>
                  <button
                    type="button"
                    className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink transition hover:bg-slate-50"
                  >
                    查看方案
                  </button>
                  {resultUrl ? (
                    <>
                      <a
                        href={resultUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex min-h-10 items-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white no-underline transition hover:bg-slate-800"
                      >
                        结果预览
                      </a>
                      <a
                        href={resultUrl}
                        download
                        className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink no-underline transition hover:bg-slate-50"
                      >
                        下载结果
                      </a>
                    </>
                  ) : null}
                  {(activeTask.status === 'failed' || activeTask.status === 'error') && activeTask.error ? (
                    <button
                      type="button"
                      className="inline-flex min-h-10 items-center rounded-lg bg-rose-600 px-4 text-sm font-medium text-white transition hover:bg-rose-700"
                    >
                      重新执行
                    </button>
                  ) : null}
                </div>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </ProductShell>
  );
}
