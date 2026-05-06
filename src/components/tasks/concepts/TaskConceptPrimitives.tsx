'use client'

import Link from 'next/link'
import { useMemo, useState, type ReactNode } from 'react'
import type { TaskConceptDetail, TaskConceptSummary } from './mockTaskConceptData'

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
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatProgress(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`
}

function getStatusLabel(status: string) {
  return STATUS_LABELS[status] ?? status
}

function getStatusClasses(status: string) {
  switch (status) {
    case 'succeeded':
    case 'completed':
    case 'done':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-200'
    case 'failed':
    case 'error':
      return 'bg-rose-50 text-rose-700 ring-rose-200'
    case 'running':
    case 'active':
      return 'bg-sky-50 text-sky-700 ring-sky-200'
    case 'queued':
    case 'pending':
    default:
      return 'bg-amber-50 text-amber-700 ring-amber-200'
  }
}

function getStepStatusClasses(status: string) {
  switch (status) {
    case 'succeeded':
      return 'text-emerald-700'
    case 'failed':
      return 'text-rose-700'
    case 'running':
      return 'text-sky-700'
    default:
      return 'text-secondary'
  }
}

export function ConceptShell({
  variant,
  title,
  description,
  children,
}: {
  variant: string
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="grid min-w-0 gap-5">
      <section className="rounded-lg border border-border bg-white/88 p-5 shadow-soft sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0 space-y-3">
            <nav className="flex items-center gap-2 text-xs font-semibold text-secondary" aria-label="面包屑">
              <Link href="/" className="text-ink">
                总览
              </Link>
              <span aria-hidden="true">/</span>
              <Link href="/tasks" className="text-ink">
                任务
              </Link>
              <span aria-hidden="true">/</span>
              <Link href="/tasks/concepts" className="text-ink">
                Concepts
              </Link>
              <span aria-hidden="true">/</span>
              <span>{variant}</span>
            </nav>
            <div className="space-y-2">
              <span className="inline-flex rounded-full bg-[#edf4df] px-3 py-1 text-xs font-bold text-accentink">
                /tasks 参考方案 {variant}
              </span>
              <h1 className="text-2xl font-semibold text-ink sm:text-3xl">{title}</h1>
              <p className="max-w-[72ch] text-sm leading-6 text-secondary">{description}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <ConceptLink href="/tasks/concepts/b1" label="B1" />
            <ConceptLink href="/tasks/concepts/b2" label="B2" />
            <ConceptLink href="/tasks/concepts/b3" label="B3" />
          </div>
        </div>
      </section>

      {children}
    </div>
  )
}

function ConceptLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:border-[#c8d6bb] hover:bg-[#fbfcf9]"
    >
      {label}
    </Link>
  )
}

export function ConceptIndexCard({
  href,
  title,
  description,
  notes,
}: {
  href: string
  title: string
  description: string
  notes: string[]
}) {
  return (
    <article className="grid gap-4 rounded-lg border border-border bg-white p-5 shadow-soft">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-ink">{title}</h2>
        <p className="text-sm leading-6 text-secondary">{description}</p>
      </div>
      <div className="grid gap-2">
        {notes.map((note) => (
          <div key={note} className="rounded-md bg-[#f7f9f6] px-3 py-2 text-sm text-ink">
            {note}
          </div>
        ))}
      </div>
      <Link
        href={href}
        className="inline-flex min-h-10 w-fit items-center rounded-lg border border-[#1f2522] bg-[#1f2522] px-4 text-sm font-semibold text-white"
      >
        打开方案
      </Link>
    </article>
  )
}

export function TaskList({
  tasks,
  activeTaskId,
  onSelect,
  emphasizeModal,
}: {
  tasks: TaskConceptSummary[]
  activeTaskId: string
  onSelect?: (taskId: string) => void
  emphasizeModal?: boolean
}) {
  return (
    <section className="grid gap-3 rounded-lg border border-border bg-white p-4 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">任务列表</span>
          <h2 className="mt-1 text-lg font-semibold text-ink">按更新时间查看最近任务</h2>
        </div>
        <div className="flex gap-2 text-xs font-semibold text-secondary">
          <span className="rounded-full border border-border px-3 py-1">{tasks.length} 个任务</span>
          {emphasizeModal ? <span className="rounded-full border border-border px-3 py-1">详情以弹窗打开</span> : null}
        </div>
      </div>

      <div className="grid gap-3">
        {tasks.map((task) => {
          const isActive = task.id === activeTaskId
          return (
            <button
              key={task.id}
              type="button"
              onClick={() => onSelect?.(task.id)}
              className={`grid gap-3 rounded-lg border p-4 text-left transition ${
                isActive
                  ? 'border-[#bfd4a2] bg-[#f6faef] shadow-[inset_0_0_0_1px_rgba(168,198,108,0.45)]'
                  : 'border-border bg-white hover:border-[#d1dbca] hover:bg-[#fbfcfa]'
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <strong className="block text-base font-semibold text-ink">{task.title}</strong>
                  <span className="mt-1 block text-xs text-secondary">
                    {task.sessionId} · 任务 ID {task.id}
                  </span>
                </div>
                <StatusBadge status={task.status} />
              </div>

              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_120px] sm:items-center">
                <div className="grid gap-2">
                  <span className="text-sm text-secondary">{task.currentStep}</span>
                  <ProgressBar value={task.progress} />
                </div>
                <div className="text-right text-sm font-semibold text-ink">{formatProgress(task.progress)}</div>
              </div>

              <div className="flex items-center justify-between gap-3 text-xs text-secondary">
                <span>{task.currentStepId}</span>
                <span>{formatDateTime(task.updatedAt)}</span>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ${getStatusClasses(status)}`}>
      {getStatusLabel(status)}
    </span>
  )
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-[#e9eee6]" aria-hidden="true">
      <span
        className="block h-full rounded-full bg-gradient-to-r from-[#8eb45f] to-[#4b8a86]"
        style={{ width: formatProgress(value) }}
      />
    </div>
  )
}

export function DetailPanel({
  task,
  modeLabel,
  chrome,
}: {
  task: TaskConceptDetail
  modeLabel: string
  chrome?: ReactNode
}) {
  return (
    <section className="grid gap-4 rounded-lg border border-border bg-white p-4 shadow-soft">
      <div className="flex flex-col gap-4 border-b border-bordersoft pb-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">{modeLabel}</span>
          <div className="space-y-1">
            <h2 className="text-xl font-semibold text-ink">{task.title}</h2>
            <p className="text-sm text-secondary">
              {task.sessionId} · 任务 ID {task.id} · 创建于 {formatDateTime(task.createdAt)}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={task.status} />
          <span className="rounded-full bg-[#f4f6f2] px-3 py-1 text-xs font-semibold text-secondary">
            {formatProgress(task.progress)}
          </span>
        </div>
      </div>

      {chrome}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="grid gap-4">
          <section className="grid gap-3 rounded-lg border border-border bg-[#fbfcfa] p-4">
            <h3 className="text-sm font-semibold text-ink">状态摘要</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <SummaryCard label="当前步骤" value={task.currentStep} />
              <SummaryCard label="最后更新时间" value={formatDateTime(task.updatedAt)} />
              <SummaryCard label="产出状态" value={task.videoUrl ? '已有成片' : task.error ? '待修复' : '执行中'} />
            </div>
            <ProgressBar value={task.progress} />
            {task.error ? (
              <div className="rounded-lg border border-[#f4c7cc] bg-[#fff7f7] px-4 py-3 text-sm text-[#8b1f2d]">
                {task.error.message}
              </div>
            ) : null}
          </section>

          <section className="grid gap-3 rounded-lg border border-border bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">标准步骤</h3>
              <span className="text-xs font-semibold text-secondary">{task.steps.length} 个阶段</span>
            </div>
            <div className="grid gap-3">
              {task.steps.map((step) => (
                <article key={step.id} className="grid gap-2 rounded-lg border border-border bg-[#fbfcfa] p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <strong className="text-sm font-semibold text-ink">{step.title}</strong>
                      <p className="text-sm text-secondary">{step.description}</p>
                    </div>
                    <span className={`text-xs font-semibold ${getStepStatusClasses(step.status)}`}>
                      {getStatusLabel(step.status)}
                    </span>
                  </div>
                  <ProgressBar value={step.progress} />
                  <p className="text-sm text-ink">{step.summary}</p>
                  {step.error?.message ? <p className="text-sm text-[#8b1f2d]">{step.error.message}</p> : null}
                </article>
              ))}
            </div>
          </section>
        </div>

        <div className="grid gap-4">
          <section className="grid gap-3 rounded-lg border border-border bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">事件时间线</h3>
              <span className="text-xs font-semibold text-secondary">{task.events.length} 条事件</span>
            </div>
            <div className="grid gap-3">
              {task.events.map((event) => (
                <div key={event.id} className="grid gap-1 rounded-lg border border-border bg-[#fbfcfa] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <strong className="text-sm text-ink">{event.eventType}</strong>
                    <span className="text-xs text-secondary">{formatDateTime(event.createdAt)}</span>
                  </div>
                  <span className="text-xs font-semibold uppercase tracking-[0.02em] text-secondary">{event.step}</span>
                  <p className="text-sm text-ink">{event.message}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-3 rounded-lg border border-border bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">素材与结果</h3>
              <span className="text-xs font-semibold text-secondary">{task.clips.length} 段 clips</span>
            </div>
            <div className="grid gap-3">
              {task.clips.map((clip) => (
                <div key={`${clip.sceneId}-${clip.publicUrl}`} className="rounded-lg border border-border bg-[#fbfcfa] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <strong className="text-sm text-ink">Scene {clip.sceneId}</strong>
                    <span className="text-xs text-secondary">
                      {clip.duration}s / 源 {clip.sourceDuration}s
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-ink">{clip.caption}</p>
                  <p className="mt-1 truncate text-xs text-secondary">{clip.sourceUrl}</p>
                </div>
              ))}
              <div className="rounded-lg border border-dashed border-[#cfd8cb] bg-[#f7faf4] p-4">
                <span className="block text-xs font-semibold uppercase tracking-[0.02em] text-secondary">输出视频</span>
                <p className="mt-2 text-sm text-ink">{task.videoUrl ?? '当前还没有可播放视频，详情区会继续显示失败或进行中的状态。'}</p>
              </div>
            </div>
          </section>

          <section className="grid gap-3 rounded-lg border border-border bg-white p-4">
            <h3 className="text-sm font-semibold text-ink">操作区</h3>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink"
              >
                刷新状态
              </button>
              <button
                type="button"
                className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink"
              >
                打开 workspace
              </button>
              <button
                type="button"
                className="inline-flex min-h-10 items-center rounded-lg border border-[#1f2522] bg-[#1f2522] px-4 text-sm font-semibold text-white"
              >
                {task.error ? '重试任务' : '查看成片'}
              </button>
            </div>
          </section>
        </div>
      </div>
    </section>
  )
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-white p-3">
      <span className="block text-xs font-semibold uppercase tracking-[0.02em] text-secondary">{label}</span>
      <strong className="mt-2 block text-sm font-semibold text-ink">{value}</strong>
    </div>
  )
}

export function TaskConceptModalPage({
  tasks,
  initialTask,
}: {
  tasks: TaskConceptSummary[]
  initialTask: TaskConceptDetail
}) {
  const [activeTaskId, setActiveTaskId] = useState(initialTask.id)
  const activeTask = useMemo(
    () => tasks.find((task) => task.id === activeTaskId)?.id ?? initialTask.id,
    [activeTaskId, initialTask.id, tasks],
  )

  return (
    <TaskConceptModalContent tasks={tasks} activeTaskId={activeTask} setActiveTaskId={setActiveTaskId} />
  )
}

function TaskConceptModalContent({
  tasks,
  activeTaskId,
  setActiveTaskId,
}: {
  tasks: TaskConceptSummary[]
  activeTaskId: string
  setActiveTaskId: (taskId: string) => void
}) {
  const detailMap = require('./mockTaskConceptData') as typeof import('./mockTaskConceptData')
  const activeTask = detailMap.taskConceptDetailById[activeTaskId]
  const [isModalOpen, setIsModalOpen] = useState(true)

  return (
    <>
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
        <TaskList tasks={tasks} activeTaskId={activeTaskId} onSelect={setActiveTaskId} emphasizeModal />
        <aside className="grid gap-3 rounded-lg border border-dashed border-[#cfd8cb] bg-[#fbfcfa] p-4">
          <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">交互说明</span>
          <h2 className="text-lg font-semibold text-ink">B1 仍旧是列表页主导</h2>
          <p className="text-sm leading-6 text-secondary">
            任务列表保持完整扫描能力，详情通过弹窗叠加到当前上下文，适合低改动迁移，但长时间排查时会频繁开合。
          </p>
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex min-h-10 items-center justify-center rounded-lg border border-[#1f2522] bg-[#1f2522] px-4 text-sm font-semibold text-white"
          >
            再次打开详情弹窗
          </button>
        </aside>
      </section>

      {isModalOpen ? (
        <div className="fixed inset-0 z-30 bg-[rgba(18,24,20,0.42)] p-4">
          <div className="mx-auto mt-6 max-w-6xl rounded-lg border border-border bg-[#f4f6f2] p-4 shadow-[0_24px_80px_rgba(21,28,24,0.24)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">列表 + 弹窗详情</span>
                <h2 className="mt-1 text-lg font-semibold text-ink">Modal 任务详情</h2>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-white text-lg text-ink"
              >
                ×
              </button>
            </div>
            <DetailPanel task={activeTask} modeLabel="弹窗详情" />
          </div>
        </div>
      ) : null}
    </>
  )
}

export function TaskConceptSidePanelPage({
  tasks,
  initialTask,
}: {
  tasks: TaskConceptSummary[]
  initialTask: TaskConceptDetail
}) {
  const [activeTaskId, setActiveTaskId] = useState(initialTask.id)
  const detailMap = require('./mockTaskConceptData') as typeof import('./mockTaskConceptData')
  const activeTask = detailMap.taskConceptDetailById[activeTaskId]

  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,0.92fr)_minmax(420px,1.08fr)]">
      <TaskList tasks={tasks} activeTaskId={activeTaskId} onSelect={setActiveTaskId} />
      <DetailPanel
        task={activeTask}
        modeLabel="列表 + 右侧详情面板"
        chrome={
          <div className="rounded-lg border border-border bg-[#f7faf4] px-4 py-3 text-sm text-secondary">
            当前页保持列表可扫读，详情常驻在右侧。切换任务时，右侧直接更新，不需要打开/关闭弹窗。
          </div>
        }
      />
    </section>
  )
}

export function TaskConceptRouteDetailPage({
  tasks,
  initialTask,
}: {
  tasks: TaskConceptSummary[]
  initialTask: TaskConceptDetail
}) {
  const [view, setView] = useState<'list' | 'detail'>('detail')
  const [activeTaskId, setActiveTaskId] = useState(initialTask.id)
  const detailMap = require('./mockTaskConceptData') as typeof import('./mockTaskConceptData')
  const activeTask = detailMap.taskConceptDetailById[activeTaskId]

  return (
    <div className="grid gap-4">
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-white p-4 shadow-soft">
        <div>
          <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">独立详情页</span>
          <h2 className="mt-1 text-lg font-semibold text-ink">B3 把任务详情当成独立路由</h2>
        </div>
        <div className="inline-flex rounded-lg border border-border bg-[#f7f9f6] p-1">
          <button
            type="button"
            onClick={() => setView('list')}
            className={`min-h-9 rounded-md px-4 text-sm font-semibold ${
              view === 'list' ? 'bg-white text-ink shadow-soft' : 'text-secondary'
            }`}
          >
            列表页
          </button>
          <button
            type="button"
            onClick={() => setView('detail')}
            className={`min-h-9 rounded-md px-4 text-sm font-semibold ${
              view === 'detail' ? 'bg-white text-ink shadow-soft' : 'text-secondary'
            }`}
          >
            详情页
          </button>
        </div>
      </section>

      {view === 'list' ? (
        <TaskList tasks={tasks} activeTaskId={activeTaskId} onSelect={setActiveTaskId} />
      ) : (
        <div className="grid gap-4">
          <div className="flex items-center gap-2 text-sm text-secondary">
            <Link href="/tasks/concepts/b3" className="font-semibold text-ink">
              返回任务列表
            </Link>
            <span aria-hidden="true">/</span>
            <span>{activeTask.id}</span>
          </div>
          <DetailPanel
            task={activeTask}
            modeLabel="独立详情页"
            chrome={
              <div className="rounded-lg border border-border bg-[#f7faf4] px-4 py-3 text-sm text-secondary">
                详情获得最大的纵向空间，更适合后续加入重试、下载、日志折叠、产物预览等更重的任务排查操作。
              </div>
            }
          />
        </div>
      )}
    </div>
  )
}
