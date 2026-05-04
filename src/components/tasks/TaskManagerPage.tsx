'use client';

import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentTask, listAgentTasks, type AgentTaskDetail, type AgentTaskSummary } from '@/lib/taskApi';
import styles from './TaskManagerPage.module.css';

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
  queued: 'var(--task-accent-1)',
  pending: 'var(--task-accent-1)',
  running: 'var(--task-accent-2)',
  active: 'var(--task-accent-2)',
  completed: 'var(--task-accent-3)',
  done: 'var(--task-accent-3)',
  succeeded: 'var(--task-accent-3)',
  failed: 'var(--task-accent-4)',
  error: 'var(--task-accent-4)',
  canceled: 'var(--task-accent-5)',
  cancelled: 'var(--task-accent-5)',
  idle: 'var(--task-accent-1)',
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

function getStatusTone(status: string) {
  return STATUS_TONES[status] ?? 'var(--task-accent-2)';
}

function getTaskSearchText(task: AgentTaskSummary) {
  return `${task.title} ${task.status} ${task.currentStep} ${task.sessionId} ${task.id}`.toLowerCase();
}

function buildTaskSummary(task: AgentTaskDetail) {
  return [
    { label: '任务 ID', value: task.id },
    { label: '会话 ID', value: task.sessionId },
    { label: '当前步骤', value: task.currentStep || '无' },
    { label: '进度', value: formatProgress(task.progress) },
    { label: '创建时间', value: formatDateTime(task.createdAt) },
    { label: '更新时间', value: formatDateTime(task.updatedAt) },
  ];
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

  const hasTasks = filteredTasks.length > 0;

  useEffect(() => {
    if (activeTask) {
      closeButtonRef.current?.focus();
    }
  }, [activeTask]);

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
      <div className={styles.page}>
        <section className={styles.hero} aria-label="任务管理">
          <div className={styles.heroTop}>
            <nav className={styles.crumb} aria-label="面包屑">
              <Link href="/">总览</Link>
              <span aria-hidden="true">/</span>
              <span>任务</span>
            </nav>
            <div className={styles.heroActions}>
              <span className={styles.heroMeta}>{isLoading ? '加载中' : `${filteredTasks.length} 项`}</span>
            </div>
          </div>

          <div className={styles.heroBody}>
            <div className={styles.heroCopy}>
              <h1>Task Manager</h1>
              <p>
                统一查看任务队列、状态和最近结果；点开任一任务会以 modal 形式展示完整详情，方便在列表和细节之间来回切换。
              </p>
            </div>

            <div className={styles.toolbar}>
              <label className={styles.searchField}>
                <span className={styles.fieldLabel}>搜索</span>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="按标题、ID、状态或步骤筛选"
                  aria-label="搜索任务"
                />
              </label>

              <label className={styles.filterField}>
                <span className={styles.fieldLabel}>状态</span>
                <select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="筛选状态">
                  {statusOptions.map((status) => (
                    <option key={status} value={status}>
                      {status === 'all' ? '全部状态' : getStatusLabel(status)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        </section>

        {errorText ? <p className={styles.errorBanner}>{errorText}</p> : null}

        <section className={styles.contentGrid} aria-label="任务列表和详情">
          <article className={styles.listPane} aria-label="任务列表">
            <div className={styles.panelHeader}>
              <div>
                <span className={styles.panelEyebrow}>列表</span>
                <h2>可管理任务列表</h2>
              </div>
              <span className={styles.panelMeta}>{selectedIds.length} 已选</span>
            </div>

            <div className={styles.listTools}>
              <button
                type="button"
                className={styles.secondaryAction}
                onClick={() => setSelectedIds([])}
                disabled={selectedIds.length === 0}
              >
                清除选择
              </button>
              <button
                type="button"
                className={styles.secondaryAction}
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

            <div className={styles.taskList}>
              {hasTasks ? (
                filteredTasks.map((task) => {
                  const isSelected = selectedIds.includes(task.id);
                  return (
                    <div key={task.id} className={`${styles.taskRow} ${isSelected ? styles.taskRowSelected : ''}`}>
                      <label className={styles.taskSelect}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelected(task.id)}
                          aria-label={`选择任务 ${task.title}`}
                        />
                        <span />
                      </label>

                      <button
                        type="button"
                        className={styles.taskMain}
                        onClick={() => void openTaskDetail(task.id)}
                      >
                        <span className={styles.taskTitle}>{task.title}</span>
                        <span className={styles.taskMeta}>
                          {task.sessionId} · {task.currentStep || '无当前步骤'}
                        </span>
                      </button>

                      <div className={styles.taskStatus}>
                        <span className={styles.statusBadge} style={{ '--task-status-tone': getStatusTone(task.status) } as CSSProperties}>
                          {getStatusLabel(task.status)}
                        </span>
                        <span className={styles.progressText}>{formatProgress(task.progress)}</span>
                      </div>

                      <div className={styles.taskTimes}>
                        <span>{formatDateTime(task.updatedAt)}</span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className={styles.emptyState}>
                  <p>当前没有匹配的任务。</p>
                </div>
              )}
            </div>
          </article>

          <aside className={styles.detailPane} aria-label="任务详情">
            <div className={styles.panelHeader}>
              <div>
                <span className={styles.panelEyebrow}>详情</span>
                <h2>Modal 任务详情</h2>
              </div>
              <span className={styles.panelMeta}>{activeTask ? '已打开' : '未打开'}</span>
            </div>

            <div className={styles.detailPrompt}>
              <p>点击列表中的任务即可打开详情弹窗。这里保留详情面板作为入口说明，主内容通过 modal 呈现。</p>
            </div>
          </aside>
        </section>
      </div>

      {activeTask ? (
        <div className={styles.modalBackdrop} role="presentation" onClick={closeTaskDetail}>
          <div
            ref={modalRef}
            className={styles.modal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="task-detail-title"
            tabIndex={-1}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={handleModalKeyDown}
          >
            <div className={styles.modalHeader}>
              <div>
                <span className={styles.panelEyebrow}>任务详情</span>
                <h2 id="task-detail-title">{activeTask.title}</h2>
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                className={styles.iconButton}
                onClick={closeTaskDetail}
                aria-label="关闭详情"
              >
                ×
              </button>
            </div>

            <div className={styles.modalSummary}>
              {buildTaskSummary(activeTask).map((item) => (
                <div key={item.label} className={styles.summaryItem}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>

            <div className={styles.modalBody}>
              <section className={styles.modalSection}>
                <h3>状态与进度</h3>
                <p>
                  <span className={styles.statusBadge} style={{ '--task-status-tone': getStatusTone(activeTask.status) } as CSSProperties}>
                    {getStatusLabel(activeTask.status)}
                  </span>
                  <span className={styles.modalProgress}>{formatProgress(activeTask.progress)}</span>
                </p>
              </section>

              <section className={styles.modalSection}>
                <h3>错误信息</h3>
                <p>{activeTask.error ? activeTask.error.message ?? '任务存在错误信息，但未返回详细文案。' : '未检测到错误。'}</p>
              </section>

              <section className={styles.modalSection}>
                <h3>事件</h3>
                <ul className={styles.eventList}>
                  {activeTask.events.length > 0 ? (
                    activeTask.events.map((event, index) => (
                      <li key={`${event.id}-${index}`}>
                        <strong>{event.eventType}</strong>
                        <span>
                          {event.step ? `${event.step} · ` : ''}
                          {String(event.message ?? '')}
                        </span>
                      </li>
                    ))
                  ) : (
                    <li>暂无事件。</li>
                  )}
                </ul>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </ProductShell>
  );
}
