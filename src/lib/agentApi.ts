export type AgentStatus =
  | 'idle'
  | 'queued'
  | 'planning'
  | 'plan_ready'
  | 'searching'
  | 'downloading'
  | 'rendering'
  | 'done'
  | 'failed'

export interface AgentMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: string
}

export interface PlanScene {
  id: number
  description: string
  keywords: string[]
  duration: number
  searchQuery: string
}

export interface EditPlan {
  title: string
  targetDuration: number
  style: string
  scenes: PlanScene[]
}

export interface ClipInfo {
  sceneId: number
  sourceUrl: string
  localPath: string
  publicUrl: string
  sourceDuration: number
  trimStart: number
  trimDuration: number
  caption: string
  startTime: number
  duration: number
}

export interface AgentEvent {
  id: string
  eventType: string
  step: string | null
  progress: number | null
  message: string | null
  payload: Record<string, unknown>
  createdAt: string
}

export interface AgentTraceEvent {
  id: string
  sessionId: string
  runId: string | null
  stepId: string | null
  jobId: string | null
  eventType: string
  level: string
  message: string | null
  payload: Record<string, unknown>
  sequence: number
  actorRole: string
  createdAt: string
}

export type AgentTraceStreamStatus = 'running' | 'succeeded' | 'failed'

export interface AgentTraceStreamPayload {
  phase: string
  status: AgentTraceStreamStatus
  progress: number
  label: string
  message: string
}

export interface AgentErrorInfo {
  message: string
  retryableStep?: string | null
}

export type AgentStepId =
  | 'understand_request'
  | 'extract_requirements'
  | 'generate_options'
  | 'finalize_plan'
  | 'create_task'
  | 'search_assets'
  | 'prepare_assets'
  | 'render_video'

export type AgentStepStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'

export interface AgentStepError {
  message: string
  retryable: boolean
  retryableStep?: AgentStepId | null
}

export interface AgentStep {
  id: AgentStepId
  title: string
  description: string
  status: AgentStepStatus
  progress: number
  summary: string
  result: Record<string, unknown> | null
  error: AgentStepError | null
  startedAt: string | null
  finishedAt: string | null
}

export type AgentDiagnosticSeverity = 'info' | 'warning' | 'error'

export interface AgentDiagnostic {
  phase: 'planning' | 'search_assets' | 'prepare_assets' | 'render_video' | 'unknown'
  category: 'no_inventory' | 'provider_blocked' | 'download_failed' | 'render_failed' | 'planning_failed' | 'unknown'
  title: string
  message: string
  primaryProvider: string | null
  failedSceneIds: number[]
  providerDiagnostics: Record<string, unknown>[]
  sceneDiagnostics: Record<string, unknown>[]
  retryStrategyHint: string | null
  repairPrompt: string
  severity: AgentDiagnosticSeverity
}

export type GroundingStatus = 'pending_search' | 'needs_confirmation' | 'confirmed'

export interface AgentGroundingCandidate {
  id: string
  title: string
  imageUrl: string
  sourceUrl: string
  previewUrl: string
  sourceType: string
  provider: string
  providerLabel: string
  isOfficial: boolean
  confidence: number
  summary: string
  diagnostics: Record<string, unknown>
  productName: string
  audience: string
  styleHint: string
  featureHints: string[]
}

export interface AgentGroundingSummary {
  status: GroundingStatus
  productName: string
  audience: string
  styleHint: string
  featureHints: string[]
  searchQueries: string[]
  candidates: AgentGroundingCandidate[]
  selectedCandidateIds: string[]
}

export interface AgentSession {
  id: string
  status: AgentStatus
  messages: AgentMessage[]
  plan: EditPlan | null
  currentPlanVersion: number | null
  clips: ClipInfo[]
  events: AgentEvent[]
  steps: AgentStep[]
  videoUrl: string | null
  activeJobId: string | null
  progress: number
  currentStep: string
  grounding: AgentGroundingSummary | null
  error: AgentErrorInfo | null
  diagnostic: AgentDiagnostic | null
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: unknown
}

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export async function readErrorMessage(response: Response): Promise<string> {
  const fallback = `请求失败：${response.status} ${response.statusText}`

  try {
    const data = (await response.json()) as { detail?: unknown; error?: unknown; message?: unknown }
    const detail = data.detail ?? data.error ?? data.message

    if (typeof detail === 'string' && detail.trim()) {
      return `${fallback} - ${detail}`
    }

    if (detail !== undefined && detail !== null) {
      return `${fallback} - ${JSON.stringify(detail)}`
    }
  } catch {
    // 响应体可能不是 JSON，使用状态码信息即可。
  }

  return fallback
}

export function createAgentSession(message: string): Promise<AgentSession> {
  return requestJson<AgentSession>('/api/agent/sessions', {
    method: 'POST',
    body: { message },
  })
}

export function sendAgentMessage(sessionId: string, message: string): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentSession>(`/api/agent/sessions/${encodedSessionId}/messages`, {
    method: 'POST',
    body: { message },
  })
}

export function confirmAgentSession(sessionId: string): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentSession>(`/api/agent/sessions/${encodedSessionId}/confirm`, {
    method: 'POST',
  })
}

export function confirmGroundingCandidates(sessionId: string, candidateIds: string[]): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentSession>(`/api/agent/sessions/${encodedSessionId}/grounding/confirm`, {
    method: 'POST',
    body: { candidateIds },
  })
}

export function getAgentSession(sessionId: string): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentSession>(`/api/agent/sessions/${encodedSessionId}`)
}

export function getAgentSessionEvents(sessionId: string): Promise<AgentEvent[]> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentEvent[]>(`/api/agent/sessions/${encodedSessionId}/events`)
}

export interface AgentTraceSubscriptionHandlers {
  onEvent?: (event: AgentTraceEvent) => void
  onHeartbeat?: (payload: Record<string, unknown>) => void
  onClosed?: (payload: Record<string, unknown>) => void
  onError?: (error: Event) => void
}

export interface AgentTraceSubscription {
  close: () => void
}

const TRACE_EVENT_TYPES = [
  'run_started',
  'run_succeeded',
  'run_failed',
  'step_started',
  'step_progress',
  'step_succeeded',
  'step_failed',
  'job_queued',
  'job_started',
  'job_succeeded',
  'job_failed',
  'tool_call_recorded',
  'rag_retrieval_started',
  'rag_retrieval_succeeded',
  'rag_retrieval_failed',
  'skill_selected',
  'skill_invoked',
  'skill_run_started',
  'skill_run_succeeded',
  'skill_run_failed',
  'mcp_tool_call_started',
  'mcp_tool_call_succeeded',
  'mcp_tool_call_failed',
]

const TERMINAL_TRACE_EVENTS = new Set(['run_succeeded', 'run_failed', 'job_succeeded', 'job_failed'])

export function isTerminalTraceEvent(eventType: string): boolean {
  return TERMINAL_TRACE_EVENTS.has(eventType)
}

function isTraceStreamStatus(value: unknown): value is AgentTraceStreamStatus {
  return value === 'running' || value === 'succeeded' || value === 'failed'
}

export function extractTraceStreamPayload(event: AgentTraceEvent): AgentTraceStreamPayload | null {
  const stream = event.payload.stream
  if (!stream || typeof stream !== 'object') {
    return null
  }

  const payload = stream as Record<string, unknown>
  if (
    typeof payload.phase !== 'string' ||
    !isTraceStreamStatus(payload.status) ||
    typeof payload.progress !== 'number' ||
    typeof payload.label !== 'string' ||
    typeof payload.message !== 'string'
  ) {
    return null
  }

  return {
    phase: payload.phase,
    status: payload.status,
    progress: Math.max(0, Math.min(1, payload.progress)),
    label: payload.label,
    message: payload.message,
  }
}

function parseSseJson<T>(event: MessageEvent<string>): T | null {
  try {
    return JSON.parse(event.data) as T
  } catch {
    return null
  }
}

export function subscribeAgentSessionTrace(
  sessionId: string,
  handlers: AgentTraceSubscriptionHandlers,
  afterSequence = 0
): AgentTraceSubscription {
  const encodedSessionId = encodeURIComponent(sessionId)
  const source = new EventSource(
    `/api/agent/sessions/${encodedSessionId}/stream?afterSequence=${Math.max(0, afterSequence)}`
  )

  const handleTraceEvent = (event: MessageEvent<string>) => {
    const payload = parseSseJson<AgentTraceEvent>(event)
    if (payload) {
      handlers.onEvent?.(payload)
    }
  }

  TRACE_EVENT_TYPES.forEach((eventType) => {
    source.addEventListener(eventType, handleTraceEvent as EventListener)
  })

  source.addEventListener('heartbeat', (event) => {
    const payload = parseSseJson<Record<string, unknown>>(event as MessageEvent<string>)
    if (payload) {
      handlers.onHeartbeat?.(payload)
    }
  })

  source.addEventListener('stream_closed', (event) => {
    const payload = parseSseJson<Record<string, unknown>>(event as MessageEvent<string>)
    if (payload) {
      handlers.onClosed?.(payload)
    }
    source.close()
  })

  source.addEventListener('stream_error', (event) => {
    handlers.onError?.(event)
    source.close()
  })

  source.onerror = (event) => {
    handlers.onError?.(event)
    source.close()
  }

  return {
    close: () => source.close(),
  }
}
