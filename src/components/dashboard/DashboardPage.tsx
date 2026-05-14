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

const FLOW_CARDS = [
  {
    title: '读取产品',
    description: '链接、卖点、受众先变成清晰 brief。',
  },
  {
    title: '匹配素材',
    description: '围绕场景抓取真实画面线索。',
  },
  {
    title: '生成草案',
    description: '输出脚本、镜头节奏和可评审结果。',
  },
];

function formatCount(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value);
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<AgentDashboardSummary>(FALLBACK_DASHBOARD);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    const loadDashboard = async () => {
      try {
        setIsLoading(true);
        const nextDashboard = await getAgentDashboard();
        if (isActive) {
          setDashboard(nextDashboard);
        }
      } catch {
        if (isActive) {
          setDashboard(FALLBACK_DASHBOARD);
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
        <section className="overflow-hidden rounded-[24px] border border-border bg-white/86 shadow-soft">
          <div className="grid min-h-[680px] gap-8 p-5 sm:p-7 lg:grid-cols-[minmax(0,1.02fr)_minmax(360px,0.98fr)] lg:p-8 xl:min-h-[620px]">
            <div className="flex min-w-0 flex-col justify-between gap-10">
              <div className="max-w-[720px] space-y-5 pt-2 lg:pt-8">
                <h1 className="max-w-[720px] text-6xl font-semibold leading-[0.98] tracking-normal text-ink sm:text-7xl lg:text-8xl">
                  把产品 brief 交给 Agent，
                  <span className="block">自动产出可用成片。</span>
                </h1>
                <p className="max-w-xl text-lg leading-8 text-secondary">
                  从链接、卖点和受众开始，快速得到脚本、素材方向和可评审的视频草案。
                </p>
                <div className="flex flex-wrap gap-3 pt-2">
                  <Link
                    href="/workspace"
                    className="inline-flex min-h-12 items-center justify-center rounded-full bg-ink px-6 text-sm font-semibold text-white transition hover:opacity-90"
                  >
                    开始创建
                  </Link>
                  <Link
                    href="/tasks"
                    className="inline-flex min-h-12 items-center justify-center rounded-full border border-border bg-white px-6 text-sm font-semibold text-ink transition hover:bg-[color:var(--surface-subtle)]"
                  >
                    查看样片
                  </Link>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {FLOW_CARDS.map((card) => (
                  <article key={card.title} className="min-h-32 rounded-[20px] border border-border bg-[color:var(--surface-muted)] p-4">
                    <h2 className="text-lg font-semibold text-ink">{card.title}</h2>
                    <p className="mt-3 text-sm leading-6 text-secondary">{card.description}</p>
                  </article>
                ))}
              </div>
            </div>

            <div className="grid content-between gap-4 rounded-[24px] border border-border bg-[linear-gradient(180deg,#f8fbfa_0%,#e9f0ed_100%)] p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-ink">Agent preview</h2>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-secondary ring-1 ring-border">
                  {isLoading ? '同步中' : '已更新'}
                </span>
              </div>

              <div className="rounded-[22px] border border-border bg-[#dfe8e4] p-4">
                <div className="aspect-[4/3] rounded-[18px] bg-[radial-gradient(circle_at_20%_10%,rgba(255,255,255,0.92),rgba(37,92,79,0.16)_34%,rgba(13,22,20,0.92)_100%)] p-5">
                  <div className="flex h-full flex-col justify-between rounded-[16px] border border-white/20 bg-[linear-gradient(135deg,rgba(10,18,16,0.82),rgba(36,86,70,0.48))] p-5 text-white">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-white/72">00:31</p>
                      <span className="h-2.5 w-2.5 rounded-full bg-white/80" aria-hidden="true" />
                    </div>
                    <h3 className="max-w-sm text-3xl font-semibold leading-tight tracking-normal">
                      真实素材进入脚本镜头
                    </h3>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <article className="rounded-[18px] border border-border bg-white/90 p-4">
                  <p className="text-sm text-secondary">会话</p>
                  <strong className="mt-2 block text-3xl font-semibold text-ink">
                    {formatCount(dashboard.totalSessions)}
                  </strong>
                </article>
                <article className="rounded-[18px] border border-border bg-white/90 p-4">
                  <p className="text-sm text-secondary">推进中</p>
                  <strong className="mt-2 block text-3xl font-semibold text-ink">
                    {formatCount(dashboard.activeTasks)}
                  </strong>
                </article>
                <article className="rounded-[18px] border border-border bg-white/90 p-4">
                  <p className="text-sm text-secondary">已完成</p>
                  <strong className="mt-2 block text-3xl font-semibold text-ink">
                    {formatCount(dashboard.completedTasks)}
                  </strong>
                </article>
              </div>
            </div>
          </div>
        </section>

      </div>
    </ProductShell>
  );
}
