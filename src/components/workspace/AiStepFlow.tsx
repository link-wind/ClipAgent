'use client';

import { useEffect, useMemo, useState } from 'react';
import { useAgentStore } from '@/stores/useAgentStore';
import type { AgentStep, AgentStatus } from '@/lib/agentApi';
import styles from './AiStepFlow.module.css';

const STEP_ORDER = [
  { key: 'understand_request', label: '理解需求', summary: '我先读取你的 brief，确认主题、目标和表达重点。' },
  { key: 'extract_requirements', label: '提炼约束', summary: '我会整理时长、风格、镜头重点和执行限制。' },
  { key: 'generate_options', label: '生成方向', summary: '我正在生成更适合当前 brief 的方案方向与检索词。' },
  { key: 'finalize_plan', label: '确认方案', summary: '我会把最终可执行方案收束成可以直接确认的版本。' },
  { key: 'create_task', label: '创建任务', summary: '方案确认后，我会立即创建执行任务并交给 worker。' },
  { key: 'search_assets', label: '搜索素材', summary: '我正在按当前方案搜索候选素材并筛掉无关结果。' },
  { key: 'prepare_assets', label: '准备素材', summary: '我会下载、裁剪并整理这次渲染需要的素材。' },
  { key: 'render_video', label: '渲染视频', summary: '我正在合成字幕、混音并输出最终视频。' },
] as const;

type StepKey = (typeof STEP_ORDER)[number]['key'];

type ConversationalStepCard = {
  key: StepKey;
  label: string;
  statusText: string;
  message: string;
  progress: number;
  isComplete: boolean;
  isActive: boolean;
  isFailed: boolean;
  isVisible: boolean;
  isPlaceholder: boolean;
};

function clampProgress(value: number) {
  return Math.max(0, Math.min(100, value));
}

function getProgressIncrement(currentProgress: number) {
  if (currentProgress < 18) {
    return 6;
  }
  if (currentProgress < 44) {
    return 4;
  }
  if (currentProgress < 78) {
    return 2;
  }
  return 1;
}

function getDisplayedCardProgress(card: ConversationalStepCard, currentProgress: number) {
  const targetProgress = clampProgress(card.progress);
  if (currentProgress >= targetProgress) {
    return targetProgress;
  }

  return clampProgress(Math.min(targetProgress, currentProgress + getProgressIncrement(currentProgress)));
}

function getDisplayProgressStyle(progress: number) {
  const normalized = clampProgress(progress) / 100;
  const opacity = 0.58 + normalized * 0.42;
  const brightness = 0.88 + normalized * 0.24;
  const saturate = 0.82 + normalized * 0.38;

  return {
    width: `${clampProgress(progress)}%`,
    opacity,
    filter: `brightness(${brightness}) saturate(${saturate})`,
  };
}

function getStepIndexByStatus(step: AgentStep | undefined) {
  const hasStarted = step?.status !== 'pending' && step?.status !== 'skipped';
  if (!step || !hasStarted) {
    return -1;
  }
  return STEP_ORDER.findIndex((item) => item.key === step.id);
}

function getRevealTargetCount(steps: AgentStep[] | undefined, status: AgentStatus | undefined) {
  const failedIndex = steps?.reduce((matchedIndex, step) => {
    if (step.status !== 'failed') {
      return matchedIndex;
    }
    return Math.max(matchedIndex, getStepIndexByStatus(step));
  }, -1) ?? -1;

  if (failedIndex >= 0) {
    return failedIndex + 1;
  }

  const runningIndex = steps?.reduce((matchedIndex, step) => {
    if (step.status !== 'running') {
      return matchedIndex;
    }
    return Math.max(matchedIndex, getStepIndexByStatus(step));
  }, -1) ?? -1;

  if (runningIndex >= 0) {
    return runningIndex + 1;
  }

  const succeededCount = steps?.filter((step) => step.status === 'succeeded').length ?? 0;
  if (status === 'done') {
    return Math.max(1, succeededCount);
  }

  if (succeededCount > 0) {
    return Math.min(STEP_ORDER.length, succeededCount);
  }

  return 1;
}

function getCurrentStepKey(steps: AgentStep[] | undefined, status: AgentStatus | undefined): StepKey | null {
  const failedStep = steps?.find((step) => step.status === 'failed');
  if (failedStep) {
    return failedStep.id as StepKey;
  }

  const runningStep = steps?.find((step) => step.status === 'running');
  if (runningStep) {
    return runningStep.id as StepKey;
  }

  const lastSucceededIndex = STEP_ORDER.reduce((lastIndex, step, index) => {
    const matched = steps?.find((item) => item.id === step.key);
    return matched?.status === 'succeeded' ? index : lastIndex;
  }, -1);

  if (status === 'done' && lastSucceededIndex >= 0) {
    return STEP_ORDER[lastSucceededIndex].key;
  }

  if (lastSucceededIndex >= 0 && lastSucceededIndex + 1 < STEP_ORDER.length) {
    return STEP_ORDER[lastSucceededIndex + 1].key;
  }

  return null;
}

function getStepProgress(step: AgentStep | undefined, card: { isComplete: boolean; isActive: boolean; isPlaceholder: boolean }, totalProgress: number) {
  if (card.isPlaceholder) {
    return 0;
  }
  if (card.isComplete) {
    return 100;
  }
  if (card.isActive) {
    return clampProgress(step?.progress ?? totalProgress);
  }
  return 0;
}

function buildStepMessage(
  card: { label: string; isComplete: boolean; isActive: boolean; isFailed: boolean; isPlaceholder: boolean },
  step: AgentStep | undefined,
) {
  if (card.isPlaceholder) {
    return '下一张卡片会在当前步骤完成后出现。';
  }
  if (card.isFailed) {
    return step?.error?.message || `我在${card.label}这一步遇到了问题，正在等你决定下一步。`;
  }
  if (card.isActive) {
    return step?.summary || step?.description || `我正在处理${card.label}，很快会把结果同步给你。`;
  }
  if (card.isComplete) {
    return step?.summary || `我已经完成${card.label}，当前结果已经沉淀好了。`;
  }
  return `我会按顺序推进${card.label}。`;
}

function buildConversationalStepCards(steps: AgentStep[] | undefined, status: AgentStatus | undefined, progress: number) {
  const totalProgress = clampProgress(progress);
  const currentStepKey = getCurrentStepKey(steps, status);
  const activeStepIndex = currentStepKey ? STEP_ORDER.findIndex((step) => step.key === currentStepKey) : -1;

  return STEP_ORDER.map((stepMeta, index) => {
    const step = steps?.find((item) => item.id === stepMeta.key);
    const isFailed = step?.status === 'failed';
    const isComplete = step?.status === 'succeeded' || (status === 'done' && index <= activeStepIndex);
    const isActive = !isFailed && (step?.status === 'running' || (stepMeta.key === currentStepKey && !isComplete));

    const card = {
      key: stepMeta.key,
      label: stepMeta.label,
      statusText: isFailed ? '失败' : isComplete ? '已完成' : isActive ? '进行中' : '等待中',
      message: '',
      progress: 0,
      isComplete,
      isActive,
      isFailed,
      isVisible: true,
      isPlaceholder: false,
    };

    card.progress = getStepProgress(step, card, totalProgress);
    card.message = buildStepMessage(card, step);
    return card;
  }) as ConversationalStepCard[];
}

export default function AiStepFlow() {
  const session = useAgentStore((state) => state.session);
  const hasUserMessage = Boolean(session?.messages?.some((message) => message.role === 'user' && message.content.trim()));
  const totalProgress = clampProgress(session?.progress ?? 0);
  const currentStep = session?.currentStep || '等待你描述需求';
  const cards = useMemo(
    () => buildConversationalStepCards(session?.steps, session?.status, totalProgress),
    [session?.progress, session?.status, session?.steps, totalProgress]
  );
  const [displayedTotalProgress, setDisplayedTotalProgress] = useState(hasUserMessage ? totalProgress : 0);
  const [revealedCount, setRevealedCount] = useState(() => (hasUserMessage ? getRevealTargetCount(session?.steps, session?.status) : 0));
  const [displayedCards, setDisplayedCards] = useState<ConversationalStepCard[]>(() =>
    cards.slice(0, hasUserMessage ? getRevealTargetCount(session?.steps, session?.status) : 0)
  );
  const revealTargetCount = useMemo(
    () => {
      if (!hasUserMessage) {
        return 0;
      }
      return getRevealTargetCount(session?.steps, session?.status);
    },
    [hasUserMessage, session?.status, session?.steps]
  );

  useEffect(() => {
    if (!hasUserMessage) {
      setDisplayedTotalProgress(0);
      return;
    }

    const intervalId = window.setInterval(() => {
      setDisplayedTotalProgress((currentValue) => {
        const targetProgress =
          session?.status === 'done' ? 100 : session?.status === 'failed' ? Math.min(99, Math.max(totalProgress, 96)) : 99;

        if (currentValue >= targetProgress) {
          return targetProgress;
        }

        return clampProgress(Math.min(targetProgress, currentValue + getProgressIncrement(currentValue)));
      });
    }, 380);

    return () => window.clearInterval(intervalId);
  }, [hasUserMessage, session?.status, totalProgress]);

  useEffect(() => {
    if (!hasUserMessage) {
      setRevealedCount(0);
      return;
    }

    if (revealedCount === revealTargetCount) {
      return;
    }

    if (revealTargetCount < revealedCount) {
      setRevealedCount(revealTargetCount);
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setRevealedCount((currentCount) => {
        if (currentCount >= revealTargetCount) {
          return currentCount;
        }
        return currentCount + 1;
      });
    }, 500);

    return () => window.clearTimeout(timeoutId);
  }, [hasUserMessage, revealTargetCount, revealedCount]);

  useEffect(() => {
    if (!hasUserMessage) {
      setDisplayedCards([]);
      return;
    }

    const normalizedCards = cards.map((card) => ({ ...card, isPlaceholder: false }));
    const revealedCards = cards.slice(0, revealedCount);
    const visibleCards = normalizedCards.slice(0, revealedCount).map((card, index) => ({
      ...card,
      isPlaceholder: revealedCards[index]?.isPlaceholder ?? false,
    }));

    setDisplayedCards((previousCards) =>
      visibleCards.map((card) => {
        const previous = previousCards.find((item) => item.key === card.key);
        return previous
          ? { ...card, progress: previous.progress }
          : { ...card, progress: 0 };
      })
    );
  }, [cards, hasUserMessage, revealedCount]);

  useEffect(() => {
    if (!hasUserMessage) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setDisplayedCards((previousCards) =>
        previousCards.map((card) => {
          const targetCard = cards.find((item) => item.key === card.key) ?? card;
          return { ...targetCard, progress: getDisplayedCardProgress(targetCard, card.progress) };
        })
      );
    }, 320);

    return () => window.clearInterval(intervalId);
  }, [cards, hasUserMessage, session?.status]);

  return (
    <section className={styles.flow} aria-label="AI 步骤进度">
      <div>
        <span className={styles.eyebrow}>AI STEP FLOW</span>
        <h2>先看进度，再看每一步结果</h2>
      </div>

      <div className={styles.statusPanel}>
        <div className={styles.statusRow}>
          <span>{currentStep}</span>
          <strong>{displayedTotalProgress}%</strong>
        </div>
        <div className={styles.progressTrack} aria-label="方案进度">
          <div className={styles.progressBar} style={getDisplayProgressStyle(displayedTotalProgress)} />
        </div>
      </div>

      <ol className={styles.steps} aria-label="步骤卡片">
        {displayedCards.map((card) => (
          <li
            key={card.key}
            className={[
              styles.step,
              card.isComplete ? styles.stepComplete : '',
              card.isActive ? styles.stepActive : '',
              card.isFailed ? styles.stepFailed : '',
              card.isPlaceholder ? styles.stepPlaceholder : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <div className={styles.stepMark} aria-hidden="true">
              <span />
            </div>
            <div className={styles.stepBody}>
              <div className={styles.stepTitleRow}>
                <h3>{card.label}</h3>
                <span>{card.statusText}</span>
              </div>
              <p>{card.message}</p>
              <div className={styles.stepProgress}>
                <div className={styles.stepProgressMeta}>
                  <span>步骤进度</span>
                  <span>{card.progress}%</span>
                </div>
                <div className={styles.stepProgressTrack}>
                  <div className={styles.stepProgressBar} style={getDisplayProgressStyle(card.progress)} />
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
