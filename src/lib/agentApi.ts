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

export interface AgentSession {
  id: string
  status: AgentStatus
  messages: AgentMessage[]
  plan: EditPlan | null
  clips: ClipInfo[]
  events: AgentEvent[]
  steps: AgentStep[]
  videoUrl: string | null
  activeJobId: string | null
  progress: number
  currentStep: string
  error: AgentErrorInfo | null
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

export function getAgentSession(sessionId: string): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentSession>(`/api/agent/sessions/${encodedSessionId}`)
}

export function getAgentSessionEvents(sessionId: string): Promise<AgentEvent[]> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentEvent[]>(`/api/agent/sessions/${encodedSessionId}/events`)
}
