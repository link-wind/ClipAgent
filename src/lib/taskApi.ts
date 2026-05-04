import type { AgentErrorInfo, AgentEvent, AgentStatus, ClipInfo } from './agentApi'

export interface AgentTaskSummary {
  id: string
  sessionId: string
  title: string
  status: AgentStatus
  progress: number
  currentStep: string
  createdAt: string
  updatedAt: string
}

export interface AgentTaskDetail extends AgentTaskSummary {
  events: AgentEvent[]
  clips: ClipInfo[]
  error: AgentErrorInfo | null
  videoUrl: string | null
}

export interface AgentDashboardSummary {
  totalSessions: number
  activeTasks: number
  completedTasks: number
  failedTasks: number
  recentTasks: AgentTaskSummary[]
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
    },
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

export function getAgentDashboard(): Promise<AgentDashboardSummary> {
  return request<AgentDashboardSummary>('/api/agent/dashboard')
}

export function listAgentTasks(): Promise<AgentTaskSummary[]> {
  return request<AgentTaskSummary[]>('/api/agent/tasks')
}

export function getAgentTask(jobId: string): Promise<AgentTaskDetail> {
  return request<AgentTaskDetail>(`/api/agent/tasks/${encodeURIComponent(jobId)}`)
}
