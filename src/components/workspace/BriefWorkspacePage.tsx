'use client';

import ProductShell from '@/components/layout/ProductShell';
import AgentChat from '@/components/agent/AgentChat';
import AiStepFlow from './AiStepFlow';
import styles from './BriefWorkspacePage.module.css';

export default function BriefWorkspacePage() {
  return (
    <ProductShell>
      <div className={styles.page}>
        <header className={styles.header}>
          <nav className={styles.crumb} aria-label="面包屑">
            <span>ClipForge</span>
            <span aria-hidden="true">/</span>
            <span>方案沟通</span>
          </nav>

          <div className={styles.titleRow}>
            <div className={styles.titleCopy}>
              <h1>从需求到执行方案</h1>
              <p>
                先把目标讲清楚，再由 AI 逐步提炼成可执行方案、步骤进度和后续确认点。
              </p>
            </div>

            <div className={styles.status} aria-label="当前状态">
              <span>状态</span>
              <strong>等待确认</strong>
            </div>
          </div>
        </header>

        <main className={styles.workspace} aria-label="方案工作区">
          <section className={styles.chatPanel} aria-label="需求对话">
            <AgentChat />
          </section>
          <section className={styles.flowPanel} aria-label="步骤进度">
            <AiStepFlow />
          </section>
        </main>
      </div>
    </ProductShell>
  );
}
