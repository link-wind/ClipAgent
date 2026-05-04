'use client';

import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentDashboard, type AgentDashboardSummary } from '@/lib/taskApi';
import styles from './DashboardPage.module.css';

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

function Metric({
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
  const style = accent ? ({ '--metric-accent': accent } as CSSProperties) : undefined;

  return (
    <article className={styles.metricCard} style={style}>
      <span className={styles.metricLabel}>{label}</span>
      <strong className={styles.metricValue}>{value}</strong>
      <span className={styles.metricHint}>{hint}</span>
    </article>
  );
}

function Legend({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={styles.legendItem}>
      <span className={styles.legendSwatch} style={{ background: tone }} aria-hidden="true" />
      <span className={styles.legendLabel}>{label}</span>
      <strong className={styles.legendValue}>{value}%</strong>
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

  const hasTasks = filteredTasks.length > 0;

  return (
    <ProductShell>
      <div className={styles.page}>
        <section className={styles.hero} aria-label="Dashboard 概览">
          <div className={styles.heroTop}>
            <nav className={styles.crumb} aria-label="面包屑">
              <Link href="/">总览</Link>
              <span aria-hidden="true">/</span>
              <span>Dashboard</span>
            </nav>
            <Link href="/workspace" className={styles.primaryAction}>
              新建方案
            </Link>
          </div>

          <div className={styles.heroBody}>
            <div className={styles.heroCopy}>
              <h1>Dashboard Home</h1>
              <p>
                把最近的会话、产能趋势和任务健康度放在同一页，方便快速判断下一步要推进哪一个方案。
              </p>
            </div>

            <label className={styles.searchField}>
              <span className={styles.searchLabel}>搜索任务</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="按标题、状态或会话 ID 筛选"
                aria-label="搜索任务"
              />
            </label>
          </div>
        </section>

        {error ? <p className={styles.errorBanner}>{error}</p> : null}

        <section className={styles.metricsGrid} aria-label="关键指标">
          {metrics.map((metric) => (
            <Metric key={metric.label} {...metric} />
          ))}
        </section>

        <section className={styles.contentGrid}>
          <article className={styles.panel} aria-label="生产趋势">
            <div className={styles.panelHeader}>
              <div>
                <span className={styles.panelEyebrow}>生产趋势</span>
                <h2>最近 7 个任务产出走势</h2>
              </div>
              <span className={styles.panelMeta}>{isLoading ? '加载中' : '已同步'}</span>
            </div>
            <div className={styles.trendChart} role="img" aria-label="最近七天生产趋势柱状图">
              {activeTrend.map((item, index) => (
                <div key={`${item.value}-${index}`} className={styles.trendBarWrap}>
                  <span className={styles.trendValue}>{item.value}</span>
                  <div className={styles.trendBarTrack}>
                    <span className={styles.trendBar} style={{ height: `${item.height}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <p className={styles.panelFootnote}>数值越高，表示最近一次工作流中的推进密度越高。</p>
          </article>

          <article className={styles.panel} aria-label="资产构成">
            <div className={styles.panelHeader}>
              <div>
                <span className={styles.panelEyebrow}>资产构成</span>
                <h2>当前生产中的资源比例</h2>
              </div>
              <span className={styles.panelMeta}>{assetTotal}%</span>
            </div>

            <div className={styles.donutWrap}>
              <div
                className={styles.donut}
                style={{
                  background: `conic-gradient(${ASSET_BREAKDOWN.map((item, index) => {
                    const start = ASSET_BREAKDOWN.slice(0, index).reduce((sum, next) => sum + next.value, 0);
                    const end = start + item.value;
                    return `${item.tone} ${start}% ${end}%`;
                  }).join(', ')})`,
                }}
                aria-hidden="true"
              />
              <div className={styles.donutCenter}>
                <strong>{assetTotal}%</strong>
                <span>已分配</span>
              </div>
            </div>

            <div className={styles.legendList}>
              {ASSET_BREAKDOWN.map((item) => (
                <Legend key={item.label} {...item} />
              ))}
            </div>
          </article>
        </section>

        <section className={styles.panel} aria-label="最近任务">
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelEyebrow}>最近任务</span>
              <h2>最新接入的方案队列</h2>
            </div>
            <span className={styles.panelMeta}>{formatCount(filteredTasks.length)} 条</span>
          </div>

          {hasTasks ? (
            <ul className={styles.taskList}>
              {filteredTasks.map((task) => (
                <li key={task.id} className={styles.taskItem}>
                  <div className={styles.taskMain}>
                    <div className={styles.taskTitleRow}>
                      <h3>{task.title}</h3>
                      <span className={`${styles.statusPill} ${styles[`status_${task.status}`] ?? ''}`.trim()}>
                        {getStatusLabel(task.status)}
                      </span>
                    </div>
                    <p>{task.currentStep || '等待下一步推进'}</p>
                  </div>
                  <div className={styles.taskMeta}>
                    <span>{task.sessionId}</span>
                    <span>{task.updatedAt}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className={styles.emptyState}>
              <p>暂无任务，先进入方案页创建一个新项目。</p>
              <Link href="/workspace" className={styles.emptyAction}>
                去方案页
              </Link>
            </div>
          )}
        </section>
      </div>
    </ProductShell>
  );
}
