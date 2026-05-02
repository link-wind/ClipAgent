'use client';

import { useAgentStore } from '@/stores/useAgentStore';
import styles from './ResultPanel.module.css';

export default function ResultPanel() {
  const session = useAgentStore((state) => state.session);
  const videoUrl = session?.videoUrl;

  return (
    <section className={styles.panel}>
      <div className={styles.heading}>
        <h2>结果</h2>
        {videoUrl ? <span>已生成</span> : null}
      </div>

      {session?.error ? <p className={styles.error}>{session.error.message}</p> : null}

      {!videoUrl ? (
        <p className={styles.empty}>视频生成完成后会在这里预览和下载。</p>
      ) : (
        <div className={styles.result}>
          <video src={videoUrl} controls preload="metadata" />
          <div className={styles.actions}>
            <a href={videoUrl} target="_blank" rel="noreferrer">
              打开视频
            </a>
            <a href={videoUrl} download>
              下载
            </a>
          </div>
        </div>
      )}
    </section>
  );
}
