'use client';

import { FormEvent, useState } from 'react';
import { confirmAgentSession, createAgentSession, sendAgentMessage } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';
import Button from '@/components/common/Button';
import styles from './AgentChat.module.css';

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function toUserError(error: unknown, resetSession: () => void) {
  const message = error instanceof Error ? error.message : '请求失败，请稍后重试。';
  if (message.includes('Session not found')) {
    resetSession();
    return '会话已失效，可能是后端刚刚重启了。请重新发送需求生成新方案。';
  }
  return message;
}

export default function AgentChat() {
  const session = useAgentStore((state) => state.session);
  const isSubmitting = useAgentStore((state) => state.isSubmitting);
  const setSession = useAgentStore((state) => state.setSession);
  const setSubmitting = useAgentStore((state) => state.setSubmitting);
  const [message, setMessage] = useState('');
  const [errorText, setErrorText] = useState('');

  const trimmedMessage = message.trim();
  const canSend = Boolean(trimmedMessage) && !isSubmitting;
  const canConfirm = session?.status === 'plan_ready' && !isSubmitting;

  const submitMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSend) {
      return;
    }

    setSubmitting(true);
    setErrorText('');

    try {
      const nextSession = session
        ? await sendAgentMessage(session.id, trimmedMessage)
        : await createAgentSession(trimmedMessage);
      setSession(nextSession);
      setMessage('');
    } catch (error) {
      setErrorText(toUserError(error, () => setSession(null)));
    } finally {
      setSubmitting(false);
    }
  };

  const confirmPlan = async () => {
    if (!session || !canConfirm) {
      return;
    }

    setSubmitting(true);
    setErrorText('');

    try {
      setSession(await confirmAgentSession(session.id));
    } catch (error) {
      setErrorText(toUserError(error, () => setSession(null)));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.chat}>
      <div className={styles.messages}>
        {!session ? (
          <div className={styles.empty}>
            <h2>描述你想生成的视频</h2>
            <p>告诉 Agent 主题、风格、时长和素材偏好，它会先生成剪辑计划。</p>
          </div>
        ) : (
          session.messages.map((item) => (
            <article
              key={item.id}
              className={`${styles.message} ${item.role === 'user' ? styles.userMessage : styles.agentMessage}`}
            >
              <div className={styles.messageMeta}>
                <span>{item.role === 'user' ? '你' : 'Agent'}</span>
                <time dateTime={item.createdAt}>{formatTime(item.createdAt)}</time>
              </div>
              <p>{item.content}</p>
            </article>
          ))
        )}
      </div>

      {errorText ? <div className={styles.error}>{errorText}</div> : null}

      <form className={styles.composer} onSubmit={submitMessage}>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="输入需求或补充说明"
          rows={4}
          disabled={isSubmitting}
        />
        <div className={styles.actions}>
          <Button type="button" variant="secondary" onClick={confirmPlan} disabled={!canConfirm}>
            确认并开始
          </Button>
          <Button type="submit" disabled={!canSend}>
            {isSubmitting ? '处理中' : '发送'}
          </Button>
        </div>
      </form>
    </div>
  );
}
