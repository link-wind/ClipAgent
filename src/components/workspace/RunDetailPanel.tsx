'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  getAgentRunDetail,
  type AgentRunDetail,
  type AgentTraceEvent,
} from '@/lib/agentApi';

type RunDetailPanelProps = {
  sessionId: string | null;
  traceEvents: AgentTraceEvent[];
};

const STATUS_LABELS: Record<string, string> = {
  running: '进行中',
  succeeded: '已完成',
  failed: '失败',
  skipped: '已跳过',
  pending: '等待中',
};

export function findLatestRunId(traceEvents: AgentTraceEvent[]) {
  for (let index = traceEvents.length - 1; index >= 0; index -= 1) {
    const runId = traceEvents[index]?.runId;
    if (runId) {
      return runId;
    }
  }
  return '';
}

function formatStatus(value: string) {
  return STATUS_LABELS[value] ?? value;
}

function formatShortTime(value: string | null | undefined) {
  if (!value) {
    return '未记录';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '未记录';
  }

  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function latestTraceMessage(events: AgentTraceEvent[]) {
  return [...events].reverse().find((event) => event.message)?.message ?? '等待运行事件';
}

function getPanelSummary(runDetail: AgentRunDetail | null, traceEvents: AgentTraceEvent[]) {
  if (runDetail?.summary) {
    return runDetail.summary;
  }

  return latestTraceMessage(traceEvents);
}

function inferStatusFromTrace(events: AgentTraceEvent[]) {
  const latestEventType = events.at(-1)?.eventType ?? '';
  if (latestEventType.includes('failed')) {
    return 'failed';
  }
  if (latestEventType.includes('succeeded')) {
    return 'succeeded';
  }
  if (latestEventType.includes('started') || latestEventType.includes('running')) {
    return 'running';
  }
  return '未加载';
}

function getSkillSummary(runDetail: AgentRunDetail | null, events: AgentTraceEvent[]) {
  if (runDetail?.skillActivity) {
    return {
      skillId: runDetail.skillActivity.skillId || '未记录',
      status: formatStatus(runDetail.skillActivity.status),
    };
  }

  const skillEvent = [...events]
    .reverse()
    .find((event) => event.eventType.startsWith('skill_'));

  return {
    skillId:
      typeof skillEvent?.payload.skillId === 'string'
        ? skillEvent.payload.skillId
        : typeof skillEvent?.payload.skill_id === 'string'
          ? skillEvent.payload.skill_id
          : '未加载',
    status: skillEvent ? formatStatus(inferStatusFromTrace([skillEvent])) : '未加载',
  };
}

export default function RunDetailPanel({ sessionId, traceEvents }: RunDetailPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [runDetail, setRunDetail] = useState<AgentRunDetail | null>(null);
  const [loadedRunKey, setLoadedRunKey] = useState('');
  const [loadingRunKey, setLoadingRunKey] = useState('');
  const [errorState, setErrorState] = useState({ runKey: '', message: '' });
  const activeRunKeyRef = useRef('');
  const latestRunKeyRef = useRef('');

  const runId = useMemo(() => findLatestRunId(traceEvents), [traceEvents]);
  const runKey = sessionId && runId ? `${sessionId}:${runId}` : '';
  latestRunKeyRef.current = runKey;
  const hasRun = Boolean(sessionId && runId);
  const visibleRunDetail = loadedRunKey === runKey ? runDetail : null;
  const isLoading = loadingRunKey === runKey;
  const errorMessage = errorState.runKey === runKey ? errorState.message : '';
  const detailTrace = visibleRunDetail && runDetail ? runDetail.trace : [];
  const detailSteps = visibleRunDetail && runDetail ? runDetail.steps : [];
  const detailToolCalls = visibleRunDetail && runDetail ? runDetail.toolCalls : [];
  const currentTraceEvents = useMemo(
    () => (runId ? traceEvents.filter((event) => event.runId === runId) : []),
    [runId, traceEvents],
  );
  const fallbackTraceEvents = currentTraceEvents.length > 0 ? currentTraceEvents : traceEvents;
  const visibleTraceEvents = visibleRunDetail ? detailTrace : fallbackTraceEvents;
  const skillSummary = getSkillSummary(visibleRunDetail, fallbackTraceEvents);
  const panelSummaryItems = [
    {
      label: '状态',
      value: visibleRunDetail ? formatStatus(visibleRunDetail.status) : inferStatusFromTrace(fallbackTraceEvents),
    },
    { label: '触发', value: visibleRunDetail?.triggerType || '未加载' },
    { label: 'Skill', value: `${skillSummary.skillId} / ${skillSummary.status}` },
    { label: 'Tool Calls', value: String(visibleRunDetail ? detailToolCalls.length : 0) },
    { label: 'Trace Events', value: String(visibleTraceEvents.length) },
  ];
  const summary = getPanelSummary(visibleRunDetail, traceEvents);

  const loadRunDetail = useCallback(async () => {
    const targetSessionId = sessionId;
    const targetRunId = runId;
    const targetRunKey = runKey;
    if (!targetSessionId || !targetRunId || !targetRunKey) {
      return;
    }

    activeRunKeyRef.current = targetRunKey;
    setLoadingRunKey(targetRunKey);
    setErrorState({ runKey: targetRunKey, message: '' });

    try {
      const detail = await getAgentRunDetail(targetSessionId, targetRunId);
      if (activeRunKeyRef.current !== targetRunKey || latestRunKeyRef.current !== targetRunKey) {
        return;
      }
      setRunDetail(detail);
      setLoadedRunKey(targetRunKey);
    } catch (error) {
      if (activeRunKeyRef.current !== targetRunKey || latestRunKeyRef.current !== targetRunKey) {
        return;
      }
      setErrorState({
        runKey: targetRunKey,
        message: error instanceof Error ? error.message : '运行详情加载失败',
      });
    } finally {
      if (activeRunKeyRef.current === targetRunKey && latestRunKeyRef.current === targetRunKey) {
        setLoadingRunKey('');
      }
    }
  }, [runId, runKey, sessionId]);

  useEffect(() => {
    activeRunKeyRef.current = runKey;
    setRunDetail(null);
    setLoadedRunKey('');
    setErrorState({ runKey: '', message: '' });
    setLoadingRunKey('');

    if (isExpanded && hasRun) {
      void loadRunDetail();
    }
  }, [hasRun, isExpanded, loadRunDetail, runKey]);

  function toggleExpanded() {
    const nextExpanded = !isExpanded;
    setIsExpanded(nextExpanded);
  }

  return (
    <section
      aria-label="运行详情"
      className="mx-5 mb-5 rounded-lg border border-border bg-[#fbfcfa] p-4"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">运行详情</p>
          <h2 className="mt-1 text-base font-semibold text-slate-950">
            {runId ? `Run ${runId}` : '等待运行记录'}
          </h2>
          <p className="mt-1 line-clamp-2 text-sm text-slate-600">{summary}</p>
          <dl className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-5">
            {panelSummaryItems.map((item) => (
              <div key={item.label} className="rounded-md bg-slate-50 px-2 py-1.5">
                <dt className="text-slate-500">{item.label}</dt>
                <dd className="mt-0.5 truncate font-medium text-slate-900">{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <button
          type="button"
          onClick={toggleExpanded}
          disabled={!hasRun || isLoading}
          aria-expanded={isExpanded}
          aria-controls="run-detail-panel-body"
          className="inline-flex shrink-0 items-center justify-center rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isExpanded ? '收起运行详情' : '展开运行详情'}
        </button>
      </div>

      {isExpanded ? (
        <div id="run-detail-panel-body" className="mt-4 space-y-4 border-t border-slate-100 pt-4">
          {isLoading ? <p role="status" className="text-sm text-slate-500">正在加载运行详情...</p> : null}
          {errorMessage ? <p role="alert" className="text-sm text-rose-600">{errorMessage}</p> : null}
          {!isLoading && !errorMessage && !visibleRunDetail ? (
            <p className="text-sm text-slate-500">暂无可展示的运行详情。</p>
          ) : null}

          {visibleRunDetail ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-slate-500">状态</p>
                  <p className="mt-1 text-sm font-medium text-slate-900">{formatStatus(visibleRunDetail.status)}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">开始</p>
                  <p className="mt-1 text-sm font-medium text-slate-900">{formatShortTime(visibleRunDetail.startedAt)}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">结束</p>
                  <p className="mt-1 text-sm font-medium text-slate-900">{formatShortTime(visibleRunDetail.finishedAt)}</p>
                </div>
              </div>

              <section className="rounded-md border border-slate-200 p-3">
                <h3 className="text-sm font-semibold text-slate-950">Skill Activity</h3>
                {visibleRunDetail.skillActivity ? (
                  <div className="mt-2 space-y-1 text-sm text-slate-600">
                    <p className="font-medium text-slate-900">{visibleRunDetail.skillActivity.skillId}</p>
                    <p>版本：{visibleRunDetail.skillActivity.skillVersion}</p>
                    <p>状态：{formatStatus(visibleRunDetail.skillActivity.status)}</p>
                    <p>原因：{visibleRunDetail.skillActivity.reason || '未记录'}</p>
                    <p>输入摘要：{visibleRunDetail.skillActivity.inputSummary || '未记录'}</p>
                    <p>输出摘要：{visibleRunDetail.skillActivity.outputSummary || '未记录'}</p>
                    <p>错误信息：{visibleRunDetail.skillActivity.errorMessage || '无'}</p>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">暂无 skill 记录。</p>
                )}
              </section>

              <section className="rounded-md border border-slate-200 p-3">
                <h3 className="text-sm font-semibold text-slate-950">Tool Calls</h3>
                {detailToolCalls.length > 0 ? (
                  <ul className="mt-2 divide-y divide-slate-100">
                    {detailToolCalls.map((toolCall) => (
                      <li key={toolCall.id} className="py-2 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-900">{toolCall.toolId}</span>
                          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                            {formatStatus(toolCall.status)}
                          </span>
                          <span className="text-xs text-slate-500">{toolCall.actorRole}</span>
                        </div>
                        <p className="mt-1 text-slate-600">{toolCall.resultSummary || toolCall.errorMessage || '无结果摘要'}</p>
                        {toolCall.resultRef ? (
                          <p className="mt-1 break-all text-xs text-slate-500">结果引用：{toolCall.resultRef}</p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">暂无 tool call 记录。</p>
                )}
              </section>

              <section className="rounded-md border border-slate-200 p-3">
                <h3 className="text-sm font-semibold text-slate-950">Trace Timeline</h3>
                {detailTrace.length > 0 ? (
                  <ol className="mt-2 space-y-2">
                    {detailTrace.map((event) => (
                      <li key={event.id} className="text-sm text-slate-600">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-900">{event.eventType}</span>
                          <span className="text-xs text-slate-500">#{event.sequence}</span>
                          <span className="text-xs text-slate-500">{event.actorRole}</span>
                          <span className="text-xs text-slate-500">{formatShortTime(event.createdAt)}</span>
                        </div>
                        <p className="mt-1">{event.message ?? '无事件描述'}</p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">暂无 trace 事件。</p>
                )}
              </section>

              <section className="rounded-md border border-slate-200 p-3">
                <h3 className="text-sm font-semibold text-slate-950">Step Snapshot</h3>
                {detailSteps.length > 0 ? (
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {detailSteps.map((step) => (
                      <article key={step.id} className="rounded-md bg-slate-50 p-3 text-sm">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="font-medium text-slate-900">{step.title}</h4>
                          <span className="text-xs text-slate-500">{formatStatus(step.status)}</span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500">进度：{step.progress}%</p>
                        <p className="mt-1 text-slate-600">{step.summary || step.description}</p>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">暂无 step 快照。</p>
                )}
              </section>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
