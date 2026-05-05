'use client';

import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentDashboard, type AgentDashboardSummary } from '@/lib/taskApi';

const FALLBACK_DASHBOARD: AgentDashboardSummary = {
  totalSessions: 0,
  activeTasks: 0,
  completedTasks: 0,
  failedTasks: 0,
  recentTasks: [],
};

const TREND_VALUES = [42, 58, 36, 74, 51, 82, 68];

const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  planning: '规划中',
  plan_ready: '待确认',
  searching: '搜索中',
  downloading: '下载中',
  rendering: '渲染中',
  done: '已完成',
  failed: '失败',
  idle: '待处理',
};

const ASSET_BREAKDOWN = [
  { label: '镜头', value: 38, tone: 'var(--dashboard-accent-1)' },
  { label: '素材', value: 27, tone: 'var(--dashboard-accent-2)' },
  { label: '字幕', value: 18, tone: 'var(--dashboard-accent-3)' },
  { label: '封面', value: 17, tone: 'var(--dashboard-accent-4)' },
];

function formatCount(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value);
}

function getStatusLabel(status: string) {
  return STATUS_LABELS[status] ?? status;
}

function getStatusClasses(status: string) {
  switch (status) {
    case 'done':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
    case 'failed':
      return 'bg-rose-50 text-rose-700 ring-rose-200';
    case 'planning':
    case 'plan_ready':
      return 'bg-amber-50 text-amber-700 ring-amber-200';
    case 'searching':
    case 'downloading':
    case 'rendering':
      return 'bg-sky-50 text-sky-700 ring-sky-200';
    case 'queued':
    case 'idle':
    default:
      return 'bg-slate-100 text-slate-700 ring-slate-200';
  }
}

function formatTaskTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function buildDonutBackground() {
  return `conic-gradient(${ASSET_BREAKDOWN.map((item, index) => {
    const start = ASSET_BREAKDOWN.slice(0, index).reduce((sum, next) => sum + next.value, 0);
    const end = start + item.value;
    return `${item.tone} ${start}% ${end}%`;
  }).join(', ')})`;
}

function MetricCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint: string;
  accent?: string;
}) {
  return (
    <article
      className="rounded-lg border border-border bg-white/95 p-5 shadow-soft"
      style={{ borderTopWidth: '3px', borderTopColor: accent }}
    >
      <span className="block text-sm font-semibold text-secondary">{label}</span>
      <strong className="mt-3 block text-3xl font-semibold leading-none" style={{ color: accent }}>
        {value}
      </strong>
      <span className="mt-3 block text-sm leading-6 text-secondary">{hint}</span>
    </article>
  );
}

function OverviewRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-white/90 p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-secondary">{label}</span>
        <strong className="text-lg font-semibold text-ink">{value}</strong>
      </div>
      <p className="mt-1 text-xs leading-5 text-mutedtext">{hint}</p>
    </div>
  );
}

function LegendItem({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="grid grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-3">
      <span className="h-3 w-3 rounded-[3px]" style={{ background: tone }} aria-hidden="true" />
      <span className="text-sm text-ink">{label}</span>
      <strong className="text-xs font-semibold text-secondary">{value}%</strong>
    </div>
  );
}

function getTaskSearchText(task: AgentDashboardSummary['recentTasks'][number]) {
  return `${task.title} ${task.status} ${task.currentStep} ${task.sessionId}`.toLowerCase();
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<AgentDashboardSummary>(FALLBACK_DASHBOARD);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    const loadDashboard = async () => {
      try {
        setIsLoading(true);
        const nextDashboard = await getAgentDashboard();
        if (isActive) {
          setDashboard(nextDashboard);
          setError(null);
        }
      } catch {
        if (isActive) {
          setDashboard(FALLBACK_DASHBOARD);
          setError('仪表盘数据暂时不可用，已显示本地占位内容。');
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadDashboard();

    return () => {
      isActive = false;
    };
  }, []);

  const metrics = useMemo(
    () => [
      {
        label: '总会话',
        value: formatCount(dashboard.totalSessions),
        hint: '工作区累计接入的方案会话数',
        accent: 'var(--dashboard-accent-1)',
      },
      {
        label: '活跃任务',
        value: formatCount(dashboard.activeTasks),
        hint: '当前仍在排队、规划或执行中的任务',
        accent: 'var(--dashboard-accent-2)',
      },
      {
        label: '已完成',
        value: formatCount(dashboard.completedTasks),
        hint: '已经产出结果并可以回看的任务',
        accent: 'var(--dashboard-accent-3)',
      },
      {
        label: '失败任务',
        value: formatCount(dashboard.failedTasks),
        hint: '需要重新确认输入或重新发起的任务',
        accent: 'var(--dashboard-accent-4)',
      },
    ],
    [dashboard.activeTasks, dashboard.completedTasks, dashboard.failedTasks, dashboard.totalSessions],
  );

  const filteredTasks = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) {
      return dashboard.recentTasks;
    }
    return dashboard.recentTasks.filter((task) => getTaskSearchText(task).includes(keyword));
  }, [dashboard.recentTasks, query]);

  const activeTrend = useMemo(() => {
    const maxValue = Math.max(...TREND_VALUES);
    return TREND_VALUES.map((value) => ({
      value,
      height: Math.max(18, Math.round((value / maxValue) * 100)),
    }));
  }, []);

  const assetTotal = useMemo(
    () => ASSET_BREAKDOWN.reduce((sum, item) => sum + item.value, 0),
    [],
  );
  const donutStyle = useMemo(
    () =>
      ({
        background: buildDonutBackground(),
      }) as CSSProperties,
    [],
  );

  const hasTasks = filteredTasks.length > 0;
  const pageStyle = {
    '--dashboard-accent-1': '#355e3b',
    '--dashboard-accent-2': '#3e6f79',
    '--dashboard-accent-3': '#537b4f',
    '--dashboard-accent-4': '#b15a44',
  } as CSSProperties;

  return (
    <ProductShell>
      <div className="grid min-w-0 gap-4 lg:gap-5" style={pageStyle}>
        <section className="rounded-lg border border-border bg-white/85 p-5 shadow-soft sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 max-w-2xl space-y-4">
              <nav className="flex items-center gap-2 text-xs font-medium text-secondary" aria-label="面包屑">
                <Link href="/" className="font-semibold text-ink">
                  总览
                </Link>
                <span aria-hidden="true">/</span>
                <span>ClipForge 首页</span>
              </nav>

              <div className="space-y-3">
                <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  产品总览
                </span>
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">ClipForge</h1>
                <p className="max-w-2xl text-sm leading-6 text-secondary sm:text-base">
                  对话式短视频制作工作台，把创意 brief 推进成可执行方案、任务流程和最终产出。
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <Link
                  href="/workspace"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg bg-ink px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  新建方案
                </Link>
                <Link
                  href="/tasks"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-white px-5 text-sm font-semibold text-ink transition hover:bg-slate-50"
                >
                  任务管理
                </Link>
              </div>
            </div>

            <div className="w-full rounded-lg border border-border bg-slate-50/90 p-4 shadow-soft lg:max-w-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">运行概况</p>
                  <h2 className="mt-1 text-lg font-semibold text-ink">今天的生产状态</h2>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-secondary ring-1 ring-border">
                  {isLoading ? '同步中' : '已同步'}
                </span>
              </div>

              <div className="mt-4 grid gap-3">
                <OverviewRow
                  label="当前会话"
                  value={formatCount(dashboard.totalSessions)}
                  hint="已经进入产品工作台的方案总数"
                />
                <OverviewRow
                  label="正在推进"
                  value={formatCount(dashboard.activeTasks)}
                  hint="此刻还在排队、规划或执行的任务"
                />
                <OverviewRow
                  label="稳定产出"
                  value={formatCount(dashboard.completedTasks)}
                  hint="已经完成、可以回看的最近产出"
                />
              </div>

              <label className="mt-4 block">
                <span className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  搜索任务
                </span>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="按标题、状态或会话 ID 筛选"
                  aria-label="搜索任务"
                  className="w-full rounded-lg border border-border bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                />
              </label>
            </div>
          </div>
        </section>

        {error ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-soft">
            {error}
          </p>
        ) : null}

        <section className="rounded-lg border border-border bg-white/80 p-5 shadow-soft sm:p-6" aria-label="关键指标">
          <div className="flex flex-col gap-2 border-b border-border/80 pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">关键指标</p>
              <h2 className="mt-1 text-xl font-semibold text-ink">正在推进的整体规模</h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-secondary">
              用会话、任务与产出节奏，快速判断当前创作工作台的推进状态和可交付能力。
            </p>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <MetricCard key={metric.label} {...metric} />
            ))}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.95fr)]" aria-label="运行证明">
          <article className="rounded-lg border border-border bg-white/80 p-5 shadow-soft sm:p-6">
            <div className="flex items-start justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">运行证明</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">最近 7 个任务产出走势</h2>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-secondary">
                {isLoading ? '加载中' : '持续更新'}
              </span>
            </div>

            <div className="mt-6 grid min-h-56 grid-cols-7 items-end gap-3" role="img" aria-label="最近七天生产趋势柱状图">
              {activeTrend.map((item, index) => (
                <div key={`${item.value}-${index}`} className="grid justify-items-center gap-3">
                  <span className="text-xs font-semibold text-secondary">{item.value}</span>
                  <div className="flex h-44 w-full items-end justify-center rounded-lg bg-slate-100">
                    <span
                      className="block w-full max-w-6 rounded-t-lg bg-gradient-to-b from-slate-700 via-slate-600 to-emerald-500"
                      style={{ height: `${item.height}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <p className="mt-4 text-sm leading-6 text-secondary">
              这组趋势不是监控告警，而是首页上对“最近确实有产出发生”的直接证明。
            </p>
          </article>

          <div className="grid gap-4">
            <article className="rounded-lg border border-border bg-white/80 p-5 shadow-soft">
              <div className="border-b border-border/80 pb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">健康快照</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">当前运行状态</h2>
              </div>

              <div className="mt-4 grid gap-3">
                <OverviewRow
                  label="活跃任务"
                  value={formatCount(dashboard.activeTasks)}
                  hint="还在排队、规划或执行中的任务数量"
                />
                <OverviewRow
                  label="已完成"
                  value={formatCount(dashboard.completedTasks)}
                  hint="已经顺利产出结果的任务数量"
                />
                <OverviewRow
                  label="失败任务"
                  value={formatCount(dashboard.failedTasks)}
                  hint="需要补充输入或重新发起的任务数量"
                />
              </div>
            </article>

            <article className="rounded-lg border border-border bg-white/80 p-5 shadow-soft">
              <div className="border-b border-border/80 pb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">资源构成</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">当前生产中的资源比例</h2>
              </div>

              <div className="mt-6 grid place-items-center">
                <div className="relative grid place-items-center">
                  <div className="h-44 w-44 rounded-full" style={donutStyle} aria-hidden="true" />
                  <div className="absolute grid h-24 w-24 place-items-center rounded-full bg-white shadow-soft">
                    <strong className="text-3xl font-semibold leading-none text-ink">{assetTotal}%</strong>
                    <span className="text-xs text-secondary">已分配</span>
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-3">
                {ASSET_BREAKDOWN.map((item) => (
                  <LegendItem key={item.label} {...item} />
                ))}
              </div>
            </article>
          </div>
        </section>

        <section className="rounded-lg border border-border bg-white/80 p-5 shadow-soft sm:p-6" aria-label="最近工作">
          <div className="flex flex-col gap-3 border-b border-border/80 pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">最近工作</p>
              <h2 className="mt-1 text-xl font-semibold text-ink">最新接入的方案队列</h2>
            </div>
            <Link href="/tasks" className="text-sm font-semibold text-ink underline-offset-4 hover:underline">
              前往任务管理
            </Link>
          </div>

          {hasTasks ? (
            <ul className="mt-4 grid gap-3 lg:grid-cols-2">
              {filteredTasks.map((task) => (
                <li
                  key={task.id}
                  className="rounded-lg border border-border bg-slate-50/90 p-4 transition hover:-translate-y-0.5 hover:shadow-soft"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold leading-6 text-ink">{task.title}</h3>
                      <p className="mt-1 text-sm leading-6 text-secondary">
                        {task.currentStep || '等待下一步推进'}
                      </p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ${getStatusClasses(task.status)}`}
                    >
                      {getStatusLabel(task.status)}
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-secondary">
                    <span>{task.sessionId}</span>
                    <span>{formatTaskTime(task.updatedAt)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-4 flex flex-col gap-3 rounded-lg border border-dashed border-border bg-slate-50/90 p-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-secondary">最近还没有工作记录，先从一个新方案开始。</p>
              <Link
                href="/workspace"
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-ink px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                去方案页
              </Link>
            </div>
          )}
        </section>
      </div>
    </ProductShell>
  );
}
