import { create } from 'zustand'
import type { AgentEvent, AgentSession } from '@/lib/agentApi'

interface AgentStore {
  session: AgentSession | null
  activeSessionId: string | null
  events: AgentEvent[]
  isSubmitting: boolean
  setSession: (session: AgentSession | null) => void
  setActiveSessionId: (sessionId: string | null) => void
  setEvents: (events: AgentEvent[]) => void
  setSubmitting: (isSubmitting: boolean) => void
  reset: () => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  session: null,
  activeSessionId: null,
  events: [],
  isSubmitting: false,
  setSession: (session) =>
    set({
      session,
      activeSessionId: session?.id ?? null,
      events: session?.events ?? [],
    }),
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setEvents: (events) =>
    set((state) => ({
      events,
      session: state.session ? { ...state.session, events } : state.session,
    })),
  setSubmitting: (isSubmitting) => set({ isSubmitting }),
  reset: () => set({ session: null, activeSessionId: null, events: [], isSubmitting: false }),
}))
