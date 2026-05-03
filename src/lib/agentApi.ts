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

export interface AgentSession {
  id: string
  status: AgentStatus
  messages: AgentMessage[]
  plan: EditPlan | null
  clips: ClipInfo[]
  events: AgentEvent[]
  videoUrl: string | null
  activeJobId: string | null
  progress: number
  currentStep: string
  error: { message: string; retryableStep?: string | null } | null
}

type RequestOptions = {
  method?: 'GET' | 'POST'
  body?: unknown
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
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

async function readErrorMessage(response: Response): Promise<string> {
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
  return request<AgentSession>('/api/agent/sessions', {
    method: 'POST',
    body: { message },
  })
}

export function sendAgentMessage(sessionId: string, message: string): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return request<AgentSession>(`/api/agent/sessions/${encodedSessionId}/messages`, {
    method: 'POST',
    body: { message },
  })
}

export function confirmAgentSession(sessionId: string): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return request<AgentSession>(`/api/agent/sessions/${encodedSessionId}/confirm`, {
    method: 'POST',
  })
}

export function getAgentSession(sessionId: string): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return request<AgentSession>(`/api/agent/sessions/${encodedSessionId}`)
}

export function getAgentSessionEvents(sessionId: string): Promise<AgentEvent[]> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return request<AgentEvent[]>(`/api/agent/sessions/${encodedSessionId}/events`)
}
