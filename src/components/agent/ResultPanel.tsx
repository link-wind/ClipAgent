'use client';

import { useAgentStore } from '@/stores/useAgentStore';
import styles from './ResultPanel.module.css';
import { resolveSessionVideoUrl } from './sessionMedia';

function formatSeconds(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return `${value.toFixed(1)}s`;
}

export default function ResultPanel() {
  const session = useAgentStore((state) => state.session);
  const videoUrl = resolveSessionVideoUrl(session);

  return (
    <section className={styles.panel}>
      <div className={styles.heading}>
        <h2>结果</h2>
        {videoUrl ? <span>{session?.activeJobId ? '已生成' : '已恢复'}</span> : null}
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

          {session?.clips.length ? (
            <div className={styles.clipListSection}>
              <div className={styles.clipListHeader}>
                <h3>片段明细</h3>
                <span>{session.clips.length} 段</span>
              </div>
              <ul className={styles.clipList}>
                {session.clips.map((clip) => (
                  <li key={`${clip.sceneId}-${clip.localPath}`} className={styles.clipItem}>
                    <div className={styles.clipTitleRow}>
                      <strong>{clip.caption || `场景 ${clip.sceneId}`}</strong>
                      <span>{formatSeconds(clip.duration)}</span>
                    </div>
                    <dl className={styles.clipMeta}>
                      <div>
                        <dt>片段时长</dt>
                        <dd>{formatSeconds(clip.duration)}</dd>
                      </div>
                      <div>
                        <dt>原始时长</dt>
                        <dd>{formatSeconds(clip.sourceDuration)}</dd>
                      </div>
                      <div>
                        <dt>截取起点</dt>
                        <dd>{formatSeconds(clip.trimStart)}</dd>
                      </div>
                      <div>
                        <dt>截取时长</dt>
                        <dd>{formatSeconds(clip.trimDuration)}</dd>
                      </div>
                    </dl>
                    {clip.sourceUrl ? (
                      <a className={styles.sourceLink} href={clip.sourceUrl} target="_blank" rel="noreferrer">
                        素材来源
                      </a>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
