'use client';

import { useAgentStore } from '@/stores/useAgentStore';
import styles from './PlanPanel.module.css';

export default function PlanPanel() {
  const plan = useAgentStore((state) => state.session?.plan);

  return (
    <section className={styles.panel}>
      <div className={styles.heading}>
        <h2>剪辑计划</h2>
        {plan ? <span>{plan.scenes.length} 个场景</span> : null}
      </div>

      {!plan ? (
        <p className={styles.empty}>计划生成后会显示标题、风格、时长和场景拆分。</p>
      ) : (
        <>
          <dl className={styles.summary}>
            <div>
              <dt>标题</dt>
              <dd>{plan.title}</dd>
            </div>
            <div>
              <dt>风格</dt>
              <dd>{plan.style}</dd>
            </div>
            <div>
              <dt>目标时长</dt>
              <dd>{plan.targetDuration} 秒</dd>
            </div>
          </dl>

          <div className={styles.scenes}>
            {plan.scenes.map((scene) => (
              <article key={scene.id} className={styles.scene}>
                <div className={styles.sceneHeader}>
                  <h3>场景 {scene.id}</h3>
                  <span>{scene.duration} 秒</span>
                </div>
                <p>{scene.description}</p>
                <div className={styles.meta}>
                  <span>关键词：{scene.keywords.join('、') || '无'}</span>
                  <span>搜索：{scene.searchQuery || '无'}</span>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
