import type { AgentSession } from '@/lib/agentApi';

export function resolveSessionVideoUrl(session: AgentSession | null | undefined) {
  return (
    session?.videoUrl ||
    session?.clips.find((clip) => clip.publicUrl.includes('/output/'))?.publicUrl ||
    null
  );
}
