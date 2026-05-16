import { create } from 'zustand'
import type { AgentEvent, AgentSession, AgentTraceEvent } from '@/lib/agentApi'

interface AgentStore {
  session: AgentSession | null
  activeSessionId: string | null
  events: AgentEvent[]
  traceEvents: AgentTraceEvent[]
  lastTraceSequence: number
  isSubmitting: boolean
  setSession: (session: AgentSession | null) => void
  setActiveSessionId: (sessionId: string | null) => void
  setEvents: (events: AgentEvent[]) => void
  appendTraceEvent: (event: AgentTraceEvent) => void
  resetTrace: () => void
  setSubmitting: (isSubmitting: boolean) => void
  reset: () => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  session: null,
  activeSessionId: null,
  events: [],
  traceEvents: [],
  lastTraceSequence: 0,
  isSubmitting: false,
  setSession: (session) =>
    set((state) => {
      const isSameSession = state.session?.id === session?.id

      return {
        session,
        activeSessionId: session?.id ?? null,
        events: session?.events ?? [],
        traceEvents: isSameSession ? state.traceEvents : [],
        lastTraceSequence: isSameSession ? state.lastTraceSequence : 0,
      }
    }),
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setEvents: (events) =>
    set((state) => ({
      events,
      session: state.session ? { ...state.session, events } : state.session,
    })),
  appendTraceEvent: (event) =>
    set((state) => {
      if (event.sequence <= state.lastTraceSequence) {
        return state
      }

      return {
        traceEvents: [...state.traceEvents, event],
        lastTraceSequence: event.sequence,
      }
    }),
  resetTrace: () => set({ traceEvents: [], lastTraceSequence: 0 }),
  setSubmitting: (isSubmitting) => set({ isSubmitting }),
  reset: () =>
    set({
      session: null,
      activeSessionId: null,
      events: [],
      traceEvents: [],
      lastTraceSequence: 0,
      isSubmitting: false,
    }),
}))
