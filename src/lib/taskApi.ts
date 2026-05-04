import type { AgentEvent, ClipInfo } from './agentApi'

export interface AgentTaskSummary {
  id: string
  sessionId: string
  title: string
  status: string
  progress: number
  currentStep: string
  createdAt: string
  updatedAt: string
}

export interface AgentTaskDetail extends AgentTaskSummary {
  events: AgentEvent[]
  clips: ClipInfo[]
  error: { message: string; retryableStep?: string | null } | null
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
    throw new Error(`请求失败：${response.status} ${response.statusText}`)
  }

  return response.json() as Promise<T>
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
