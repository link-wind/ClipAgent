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
        <section className="overflow-hidden rounded-lg border border-border bg-white/88 shadow-soft">
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
                    className="inline-flex min-h-11 items-center justify-center rounded-lg bg-ink px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    开始创建
                  </Link>
                  <Link
                    href="/tasks"
                    className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-white px-5 text-sm font-semibold text-ink transition hover:bg-slate-50"
                  >
                    查看样片
                  </Link>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {WORKFLOW_STEPS.map((step, index) => (
                  <article
                    key={step.title}
                    className="grid min-h-40 gap-3 rounded-lg border border-border bg-slate-50/80 p-4"
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

            <div className="grid gap-3 rounded-lg border border-border bg-[linear-gradient(180deg,#f7f8f8_0%,#eef2f1_100%)] p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Preview</p>
                  <h2 className="mt-1 text-lg font-semibold text-ink">Agent 预览片段</h2>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-secondary ring-1 ring-border">
                  {isLoading ? '同步中' : '已更新'}
                </span>
              </div>

              <div className="relative overflow-hidden rounded-lg border border-slate-200 bg-[#dfe7e4] p-4">
                <div className="aspect-video rounded-lg bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.85),_rgba(53,94,59,0.08)_35%,_rgba(28,31,35,0.9)_100%)] p-4">
                  <div className="flex h-full flex-col justify-between rounded-lg border border-white/20 bg-[linear-gradient(135deg,rgba(12,18,21,0.82),rgba(53,94,59,0.42))] p-4 text-white">
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
                    className="grid min-h-24 gap-2 rounded-lg border border-border bg-white/92 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                        Frame 0{index + 1}
                      </span>
                      <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" aria-hidden="true" />
                    </div>
                    <p className="text-sm font-medium text-ink">{label}</p>
                    <p className="text-xs leading-5 text-secondary">让每一段画面都能对上产品信息与输出目标。</p>
                  </div>
                ))}
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-border bg-white/92 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">素材搜索</p>
                  <strong className="mt-2 block text-2xl font-semibold text-ink">
                    {formatCount(dashboard.activeTasks || 28)}
                  </strong>
                </div>
                <div className="rounded-lg border border-border bg-white/92 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">脚本镜头</p>
                  <strong className="mt-2 block text-2xl font-semibold text-ink">
                    {Math.max(12, dashboard.completedTasks || 0)}
                  </strong>
                </div>
                <div className="rounded-lg border border-border bg-white/92 p-4">
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

        {error ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-soft">
            {error}
          </p>
        ) : null}
      </div>
    </ProductShell>
  );
}
