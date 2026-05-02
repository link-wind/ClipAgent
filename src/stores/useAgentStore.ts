import { create } from 'zustand'
import type { AgentSession } from '@/lib/agentApi'

interface AgentStore {
  session: AgentSession | null
  isSubmitting: boolean
  setSession: (session: AgentSession | null) => void
  setSubmitting: (isSubmitting: boolean) => void
  reset: () => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  session: null,
  isSubmitting: false,
  setSession: (session) => set({ session }),
  setSubmitting: (isSubmitting) => set({ isSubmitting }),
  reset: () => set({ session: null, isSubmitting: false }),
}))
