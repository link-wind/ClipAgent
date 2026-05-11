import { requestJson } from './agentApi'
import type { AgentDiagnostic, AgentErrorInfo, AgentEvent, AgentStep, AgentStepId, ClipInfo } from './agentApi'

export interface AgentTaskSummary {
  id: string
  sessionId: string
  title: string
  status: string
  progress: number
  currentStep: string
  currentStepId: AgentStepId | null
  createdAt: string
  updatedAt: string
}

export interface AgentTaskDetail extends AgentTaskSummary {
  events: AgentEvent[]
  clips: ClipInfo[]
  steps: AgentStep[]
  diagnostic: AgentDiagnostic | null
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

export function getAgentDashboard(): Promise<AgentDashboardSummary> {
  return requestJson<AgentDashboardSummary>('/api/agent/dashboard')
}

export function listAgentTasks(): Promise<AgentTaskSummary[]> {
  return requestJson<AgentTaskSummary[]>('/api/agent/tasks')
}

export function getAgentTask(jobId: string): Promise<AgentTaskDetail> {
  return requestJson<AgentTaskDetail>(`/api/agent/tasks/${encodeURIComponent(jobId)}`)
}
