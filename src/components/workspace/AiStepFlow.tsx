'use client';

import { useAgentStore } from '@/stores/useAgentStore';
import styles from './AiStepFlow.module.css';

function clampProgress(value: number) {
  return Math.max(0, Math.min(100, value));
}

export default function AiStepFlow() {
  const session = useAgentStore((state) => state.session);
  const totalProgress = clampProgress(session?.progress ?? 0);
  const currentStep = session?.currentStep || '等待你描述需求';

  return (
    <section className={styles.flow} aria-label="AI 步骤进度">
      <div>
        <span className={styles.eyebrow}>AI STEP FLOW</span>
        <h2>先看进度，再看每一步结果</h2>
      </div>

      <div className={styles.statusPanel}>
        <div className={styles.statusRow}>
          <span>{currentStep}</span>
          <strong>{totalProgress}%</strong>
        </div>
        <div className={styles.progressTrack} aria-label="方案进度">
          <div className={styles.progressBar} style={{ width: `${totalProgress}%` }} />
        </div>
      </div>
    </section>
  );
}
