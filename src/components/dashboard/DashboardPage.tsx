'use client';

import { useEffect, useState } from 'react';
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

const WORKFLOW_STEPS = [
  {
    title: '理解产品信息',
    description: '读取产品链接、卖点、受众和风格方向，先把 brief 整理成可执行的创作上下文。',
  },
  {
    title: '搜索真实素材',
    description: '围绕产品特性与使用场景抓取可信素材，让脚本和镜头不只停留在概念层。',
  },
  {
    title: '输出成片方案',
    description: '自动生成脚本、镜头节奏与成片建议，把一条可看的结果尽快交到团队手里。',
  },
];

const INPUT_OUTPUT_ITEMS = [
  {
    label: 'Input',
    title: '产品链接、卖点与受众',
    description: '把现有产品资料、投放目标和风格要求交给工作区，先形成一份清晰的创作 brief。',
  },
  {
    label: 'Output',
    title: '脚本、镜头节奏与结果资产',
    description: 'Agent 会把搜索素材、脚本结构和成片方向整理成团队可以继续评审与迭代的输出。',
  },
];

function formatCount(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value);
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<AgentDashboardSummary>(FALLBACK_DASHBOARD);
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

  return (
    <ProductShell>
      <div className="grid gap-4 lg:gap-5">
        <section className="overflow-hidden rounded-[16px] border border-border bg-white/88 shadow-soft">
          <div className="grid gap-8 px-5 py-6 sm:px-6 sm:py-7 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)] xl:items-stretch">
            <div className="flex min-w-0 flex-col justify-between gap-8">
              <div className="space-y-5">
                <span className="inline-flex w-fit items-center rounded-full border border-border bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  Product-to-video agent
                </span>

                <div className="space-y-4">
                  <h1 className="max-w-3xl text-4xl font-semibold leading-tight text-ink sm:text-5xl">
                    把产品 brief 交给 Agent，自动产出可用成片。
                  </h1>
                  <p className="max-w-2xl text-base leading-7 text-secondary">
                    输入产品链接、卖点、受众与风格方向，ClipForge 会自动理解产品、搜索真实素材、生成脚本与成片结果，
                    让团队更快看到能讨论、能继续推进的视频成片方案。
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/workspace"
                    className="inline-flex min-h-11 items-center justify-center rounded-[16px] bg-ink px-5 text-sm font-semibold text-white transition hover:opacity-90"
                  >
                    开始创建
                  </Link>
                  <Link
                    href="/tasks"
                    className="inline-flex min-h-11 items-center justify-center rounded-[16px] border border-border bg-white px-5 text-sm font-semibold text-ink transition hover:bg-[color:var(--surface-subtle)]"
                  >
                    查看样片
                  </Link>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {WORKFLOW_STEPS.map((step, index) => (
                  <article
                    key={step.title}
                    className="grid min-h-40 gap-3 rounded-[16px] border border-border bg-[color:var(--surface-muted)] p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                        Step {index + 1}
                      </span>
                      <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-secondary ring-1 ring-border">
                        Agent flow
                      </span>
                    </div>
                    <div className="space-y-2">
                      <h2 className="text-lg font-semibold text-ink">{step.title}</h2>
                      <p className="text-sm leading-6 text-secondary">{step.description}</p>
                    </div>
                  </article>
                ))}
              </div>
            </div>

            <div className="grid gap-3 rounded-[16px] border border-border bg-[linear-gradient(180deg,#f7f8f8_0%,#eef2f1_100%)] p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Preview</p>
                  <h2 className="mt-1 text-lg font-semibold text-ink">Agent 预览片段</h2>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-secondary ring-1 ring-border">
                  {isLoading ? '同步中' : '已更新'}
                </span>
              </div>

              <div className="relative overflow-hidden rounded-[16px] border border-border bg-[#dfe7e4] p-4">
                <div className="aspect-video rounded-[16px] bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.85),_rgba(53,94,59,0.08)_35%,_rgba(28,31,35,0.9)_100%)] p-4">
                  <div className="flex h-full flex-col justify-between rounded-[16px] border border-white/20 bg-[linear-gradient(135deg,rgba(12,18,21,0.82),rgba(53,94,59,0.42))] p-4 text-white">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-white/70">Hero sequence</p>
                        <h3 className="mt-2 text-xl font-semibold">真实素材进入脚本镜头</h3>
                      </div>
                      <span className="rounded-full bg-white/12 px-3 py-1 text-xs font-medium text-white/80 ring-1 ring-white/15">
                        00:31
                      </span>
                    </div>

                    <div className="grid gap-2 text-sm text-white/78">
                      <p>1. 抓取产品卖点与适用人群</p>
                      <p>2. 拼接真实场景与画面证明</p>
                      <p>3. 输出可继续细化的成片节奏</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                {['产品卖点拆解', '真实素材候选', '成片节奏卡'].map((label, index) => (
                  <div
                    key={label}
                    className="grid min-h-24 gap-2 rounded-[16px] border border-border bg-white/92 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                        Frame 0{index + 1}
                      </span>
                      <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--accent)]" aria-hidden="true" />
                    </div>
                    <p className="text-sm font-medium text-ink">{label}</p>
                    <p className="text-xs leading-5 text-secondary">让每一段画面都能对上产品信息与输出目标。</p>
                  </div>
                ))}
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-[16px] border border-border bg-white/92 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">素材搜索</p>
                  <strong className="mt-2 block text-2xl font-semibold text-ink">
                    {formatCount(dashboard.activeTasks)}
                  </strong>
                </div>
                <div className="rounded-[16px] border border-border bg-white/92 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">脚本镜头</p>
                  <strong className="mt-2 block text-2xl font-semibold text-ink">
                    {formatCount(dashboard.completedTasks)}
                  </strong>
                </div>
                <div className="rounded-[16px] border border-border bg-white/92 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">成片时长</p>
                  <strong className="mt-2 block text-2xl font-semibold text-ink">0:31</strong>
                </div>
              </div>

              <p className="text-sm leading-6 text-secondary">
                从产品信息到真实素材，再到脚本与成片预览，这里展示的是 Agent 先给团队一条可评估结果的工作方式。
              </p>
            </div>
          </div>
        </section>

        <section className="grid gap-5 rounded-[16px] border border-border bg-white/88 p-5 shadow-soft sm:p-6 lg:grid-cols-[0.82fr_1.18fr]">
          <div className="space-y-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">How it works</p>
            <h2 className="text-2xl font-semibold leading-tight text-ink">
              把产品资料变成一条可以讨论的视频方案。
            </h2>
            <p className="text-sm leading-6 text-secondary">
              ClipForge 不把首页做成传统数据面板，而是把已有任务数据放回产品流程里：它解释 Agent 如何接收 brief、
              使用素材搜索，并把结果交给团队继续判断。
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {WORKFLOW_STEPS.map((step, index) => (
              <article key={step.title} className="grid gap-3 rounded-[16px] border border-border bg-[color:var(--surface-muted)] p-4">
                <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  Stage {index + 1}
                </span>
                <div className="space-y-2">
                  <h3 className="text-base font-semibold text-ink">{step.title}</h3>
                  <p className="text-sm leading-6 text-secondary">{step.description}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-5 rounded-[16px] border border-border bg-surface p-5 shadow-soft sm:p-6 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="space-y-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Input / Output</p>
            <h2 className="text-2xl font-semibold leading-tight text-ink">从零散产品信息到可交付资产。</h2>
            <p className="text-sm leading-6 text-secondary">
              下半屏用产品语言解释工作区的价值：输入是什么、Agent 会整理什么、团队最终拿到什么。
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {INPUT_OUTPUT_ITEMS.map((item) => (
              <article key={item.label} className="grid min-h-44 gap-4 rounded-[16px] border border-border bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                    {item.label}
                  </span>
                  <span className="rounded-full bg-[color:var(--surface-muted)] px-3 py-1 text-xs font-medium text-secondary ring-1 ring-border">
                    Workspace
                  </span>
                </div>
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-ink">{item.title}</h3>
                  <p className="text-sm leading-6 text-secondary">{item.description}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-5 rounded-[16px] border border-border bg-white/88 p-5 shadow-soft sm:p-6 lg:grid-cols-[0.78fr_1.22fr]">
          <div className="space-y-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Example results</p>
            <h2 className="text-2xl font-semibold leading-tight text-ink">用当前任务记录说明 Agent 输出形态。</h2>
            <p className="text-sm leading-6 text-secondary">
              这些数字来自后端返回的任务摘要，只作为当前工作区状态的解释，不包装成客户案例或增长承诺。
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <article className="rounded-[16px] border border-border bg-[color:var(--surface-muted)] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Sessions</p>
              <strong className="mt-2 block text-2xl font-semibold text-ink">{formatCount(dashboard.totalSessions)}</strong>
              <p className="mt-2 text-sm leading-6 text-secondary">已进入 Agent 流程的产品创作会话。</p>
            </article>
            <article className="rounded-[16px] border border-border bg-[color:var(--surface-muted)] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">In progress</p>
              <strong className="mt-2 block text-2xl font-semibold text-ink">{formatCount(dashboard.activeTasks)}</strong>
              <p className="mt-2 text-sm leading-6 text-secondary">正在整理素材、脚本或结果的任务。</p>
            </article>
            <article className="rounded-[16px] border border-border bg-[color:var(--surface-muted)] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Ready</p>
              <strong className="mt-2 block text-2xl font-semibold text-ink">{formatCount(dashboard.completedTasks)}</strong>
              <p className="mt-2 text-sm leading-6 text-secondary">已经产出可评审结果的任务。</p>
            </article>
            <article className="rounded-[16px] border border-border bg-[color:var(--surface-muted)] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Needs attention</p>
              <strong className="mt-2 block text-2xl font-semibold text-ink">{formatCount(dashboard.failedTasks)}</strong>
              <p className="mt-2 text-sm leading-6 text-secondary">需要重新检查输入或素材链路的任务。</p>
            </article>
          </div>
        </section>

        <section className="grid gap-4 rounded-[16px] border border-border bg-ink p-5 text-white shadow-soft sm:p-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div className="space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-white/65">Final CTA</p>
            <h2 className="text-2xl font-semibold leading-tight">把下一条产品 brief 放进工作区。</h2>
            <p className="max-w-2xl text-sm leading-6 text-white/72">
              从一个产品链接开始，让 Agent 先交出脚本、素材方向和成片草案，再由团队继续判断和精修。
            </p>
          </div>
          <Link
            href="/workspace"
            className="inline-flex min-h-11 items-center justify-center rounded-[16px] bg-white px-5 text-sm font-semibold text-ink transition hover:bg-[color:var(--surface-muted)]"
          >
            开始创建
          </Link>
        </section>

        {error ? (
          <p className="rounded-[16px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-soft">
            {error}
          </p>
        ) : null}
      </div>
    </ProductShell>
  );
}
