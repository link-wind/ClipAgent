# ClipForge Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 ClipForge Phase 1 核心架构：Next.js Web 应用，支持素材搜索、时间线剪辑、FFmpeg.wasm 本地渲染输出。

**Architecture:** Next.js 14 App Router + React + Zustand + @dnd-kit + @ffmpeg/ffmpeg。前端全量客户端渲染，服务端只做 SSR 页面壳。素材搜索走 localAdapter 假适配器读取本地 JSON fixture。视频编码完全在浏览器端通过 FFmpeg.wasm 完成。

**Tech Stack:** Next.js 14+, React 18, Zustand, @dnd-kit/core, @dnd-kit/sortable, @ffmpeg/ffmpeg@0.12.x, @ffmpeg/util, lucide-react, CSS Modules

---

## File Structure

```
src/
  app/
    layout.tsx              # 根 layout，引入全局样式
    page.tsx                # 主页面入口
    globals.css             # CSS Variables、reset、全局样式
  components/
    layout/
      AppShell.tsx          # 根容器，CSS Grid 三栏 + 底部预览
      Header.tsx           # 顶栏，项目名 + 渲染按钮
      MaterialsPanel.tsx    # 左侧素材库面板
      TimelinePanel.tsx    # 中间时间线区域
      InspectorPanel.tsx    # 右侧属性检查器
      PreviewBar.tsx       # 底部预览播放器
    materials/
      SearchBox.tsx        # 搜索输入框
      MaterialCard.tsx     # 单个素材卡片
      MaterialList.tsx     # 搜索结果列表
    timeline/
      TimelineTrack.tsx    # 单个轨道容器
      TimelineClip.tsx     # 轨道内视频片段
      Playhead.tsx         # 播放头指示线
    inspector/
      InspectorEmpty.tsx   # 无选中时占位
      ClipProperties.tsx   # 选中片段属性编辑
      TimecodeInput.tsx    # 时间码输入框
    preview/
      VideoPlayer.tsx      # 预览播放器
      PlaybackControls.tsx # 播放控制按钮组
      TimecodeDisplay.tsx  # 时间码显示
    common/
      RenderModal.tsx      # 渲染进度/完成模态框
      Button.tsx           # 通用按钮
      IconButton.tsx       # 图标按钮
  stores/
    useTimelineStore.ts    # 时间线状态（clips + selectedClipIndex + playheadTime）
    useMaterialsStore.ts   # 素材库状态（searchQuery + results + isLoading）
  adapters/
    materials/
      localAdapter.ts      # 本地 fixture 适配器实现
      types.ts             # 素材适配器统一接口类型
  lib/
    ffmpeg.ts              # FFmpeg.wasm 封装
    timecode.ts            # 时间码解析/格式化
public/
  fixtures/
    thumbnails/
      .gitkeep
    .gitkeep
fixtures/
  videos.json             # 素材元数据 JSON
docs/
  superpowers/
    plans/
      2026-05-02-clipforge-phase1-plan.md  # 本文件
```

---

## Task 1: 初始化 Next.js 项目并配置基础依赖

**Files:**
- Create: `package.json`
- Create: `next.config.js`
- Create: `tsconfig.json`
- Create: `src/app/layout.tsx`
- Create: `src/app/page.tsx`
- Create: `src/app/globals.css`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "clipforge",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "zustand": "^4.5.4",
    "@dnd-kit/core": "^6.1.0",
    "@dnd-kit/sortable": "^8.0.0",
    "@dnd-kit/utilities": "^3.2.2",
    "@ffmpeg/ffmpeg": "^0.12.10",
    "@ffmpeg/util": "^0.12.1",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "typescript": "^5.5.3",
    "@types/node": "^20.14.12",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "eslint": "^8.57.0",
    "eslint-config-next": "14.2.5"
  }
}
```

- [ ] **Step 2: 创建 next.config.js**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
          { key: 'Cross-Origin-Embedder-Policy', value: 'require-corp' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
```

> **Note:** FFmpeg.wasm 需要 COOP/COEP headers 才能在浏览器中运行。

- [ ] **Step 3: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: 创建 src/app/globals.css**

```css
:root {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-surface: #0f3460;
  --accent: #00d4ff;
  --accent-alt: #e94560;
  --text-primary: #eaeaea;
  --text-secondary: #a0a0a0;
  --border: #2a2a4a;
  --radius-sm: 4px;
  --radius-md: 8px;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  overflow: hidden;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}
::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}
```

- [ ] **Step 5: 创建 src/app/layout.tsx**

```tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ClipForge',
  description: 'AI-powered video clip editing',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: 创建 src/app/page.tsx**

```tsx
export default function HomePage() {
  return <main style={{ padding: '20px' }}>ClipForge Phase 1 - scaffold</main>;
}
```

- [ ] **Step 7: 安装依赖**

Run: `npm install`
Expected: 所有依赖安装完成，无 error

---

## Task 2: 创建 fixture 数据和 public 目录结构

**Files:**
- Create: `fixtures/videos.json`
- Create: `public/fixtures/thumbnails/.gitkeep`
- Create: `public/fixtures/.gitkeep`

- [ ] **Step 1: 创建 fixtures/videos.json**

```json
[
  {
    "id": "vid_001",
    "title": "城市黄昏车流",
    "description": "傍晚城市街道，车流穿梭，霓虹初上",
    "duration": 45,
    "tags": ["城市", "黄昏", "车流", "夜景"],
    "thumbnailUrl": "/fixtures/thumbnails/vid_001.jpg",
    "videoUrl": "/fixtures/vid_001.mp4"
  },
  {
    "id": "vid_002",
    "title": "海边日落",
    "description": "金色夕阳沉入海平面",
    "duration": 30,
    "tags": ["海边", "日落", "自然", "风景"],
    "thumbnailUrl": "/fixtures/thumbnails/vid_002.jpg",
    "videoUrl": "/fixtures/vid_002.mp4"
  },
  {
    "id": "vid_003",
    "title": "竹林风声",
    "description": "阳光穿过竹林，微风轻拂",
    "duration": 60,
    "tags": ["竹林", "自然", "风", "冥想"],
    "thumbnailUrl": "/fixtures/thumbnails/vid_003.jpg",
    "videoUrl": "/fixtures/vid_003.mp4"
  },
  {
    "id": "vid_004",
    "title": "咖啡拉花特写",
    "description": "手工咖啡拉花过程特写",
    "duration": 20,
    "tags": ["咖啡", "美食", "特写", "手工艺"],
    "thumbnailUrl": "/fixtures/thumbnails/vid_004.jpg",
    "videoUrl": "/fixtures/vid_004.mp4"
  },
  {
    "id": "vid_005",
    "title": "雪山航拍",
    "description": "无人机航拍雪山峰峦",
    "duration": 90,
    "tags": ["雪山", "航拍", "自然", "风景"],
    "thumbnailUrl": "/fixtures/thumbnails/vid_005.jpg",
    "videoUrl": "/fixtures/vid_005.mp4"
  }
]
```

- [ ] **Step 2: 创建目录占位文件**

Run: `mkdir -p public/fixtures/thumbnails && touch public/fixtures/thumbnails/.gitkeep && touch public/fixtures/.gitkeep`
Expected: 目录结构创建完成

---

## Task 3: 素材适配器类型和 localAdapter 实现

**Files:**
- Create: `src/adapters/materials/types.ts`
- Create: `src/adapters/materials/localAdapter.ts`

- [ ] **Step 1: 创建 src/adapters/materials/types.ts**

```typescript
export interface VideoMaterial {
  id: string;
  title: string;
  description: string;
  duration: number;       // 秒
  tags: string[];
  thumbnailUrl: string;
  videoUrl: string;
}

export interface MaterialsAdapter {
  search(query: string): Promise<VideoMaterial[]>;
  getById(id: string): Promise<VideoMaterial | null>;
}
```

- [ ] **Step 2: 创建 src/adapters/materials/localAdapter.ts**

```typescript
import type { MaterialsAdapter, VideoMaterial } from './types';
import videos from '../../../../fixtures/videos.json';

const allMaterials: VideoMaterial[] = videos as VideoMaterial[];

export const localAdapter: MaterialsAdapter = {
  async search(query: string): Promise<VideoMaterial[]> {
    if (!query.trim()) return [];
    const lowerQuery = query.toLowerCase();
    return allMaterials.filter((m) => {
      const titleMatch = m.title.toLowerCase().includes(lowerQuery);
      const tagMatch = m.tags.some((t) => t.toLowerCase().includes(lowerQuery));
      return titleMatch || tagMatch;
    });
  },

  async getById(id: string): Promise<VideoMaterial | null> {
    return allMaterials.find((m) => m.id === id) ?? null;
  },
};
```

---

## Task 4: Zustand Stores 实现

**Files:**
- Create: `src/stores/useMaterialsStore.ts`
- Create: `src/stores/useTimelineStore.ts`

- [ ] **Step 1: 创建 src/stores/useMaterialsStore.ts**

```typescript
import { create } from 'zustand';
import { localAdapter } from '@/adapters/materials/localAdapter';
import type { VideoMaterial } from '@/adapters/materials/types';

interface MaterialsStore {
  searchQuery: string;
  results: VideoMaterial[];
  isLoading: boolean;
  setSearchQuery: (q: string) => void;
  performSearch: (q: string) => Promise<void>;
  clearResults: () => void;
}

export const useMaterialsStore = create<MaterialsStore>((set) => ({
  searchQuery: '',
  results: [],
  isLoading: false,

  setSearchQuery: (q) => set({ searchQuery: q }),

  performSearch: async (q) => {
    set({ isLoading: true });
    const results = await localAdapter.search(q);
    set({ results, isLoading: false });
  },

  clearResults: () => set({ results: [] }),
}));
```

- [ ] **Step 2: 创建 src/stores/useTimelineStore.ts**

```typescript
import { create } from 'zustand';

export interface TimelineClip {
  materialId: string;
  inPoint: number;    // 秒
  outPoint: number;   // 秒
}

interface TimelineStore {
  clips: TimelineClip[];
  selectedClipIndex: number | null;
  playheadTime: number;

  addClip: (materialId: string) => void;
  removeClip: (index: number) => void;
  reorderClips: (fromIndex: number, toIndex: number) => void;
  setClipInOut: (index: number, inPoint: number, outPoint: number) => void;
  selectClip: (index: number | null) => void;
  setPlayheadTime: (time: number) => void;
}

export const useTimelineStore = create<TimelineStore>((set) => ({
  clips: [],
  selectedClipIndex: null,
  playheadTime: 0,

  addClip: (materialId) =>
    set((state) => ({
      clips: [...state.clips, { materialId, inPoint: 0, outPoint: 0 }],
    })),

  removeClip: (index) =>
    set((state) => {
      const newClips = state.clips.filter((_, i) => i !== index);
      return {
        clips: newClips,
        selectedClipIndex:
          state.selectedClipIndex === index
            ? null
            : state.selectedClipIndex !== null && state.selectedClipIndex > index
            ? state.selectedClipIndex - 1
            : state.selectedClipIndex,
      };
    }),

  reorderClips: (fromIndex, toIndex) =>
    set((state) => {
      const newClips = [...state.clips];
      const [moved] = newClips.splice(fromIndex, 1);
      newClips.splice(toIndex, 0, moved);
      return { clips: newClips };
    }),

  setClipInOut: (index, inPoint, outPoint) =>
    set((state) => ({
      clips: state.clips.map((c, i) =>
        i === index ? { ...c, inPoint, outPoint } : c
      ),
    })),

  selectClip: (index) => set({ selectedClipIndex: index }),

  setPlayheadTime: (time) => set({ playheadTime: time }),
}));
```

---

## Task 5: 通用组件（Button / IconButton）

**Files:**
- Create: `src/components/common/Button.tsx`
- Create: `src/components/common/Button.module.css`
- Create: `src/components/common/IconButton.tsx`
- Create: `src/components/common/IconButton.module.css`

- [ ] **Step 1: 创建 src/components/common/Button.tsx**

```tsx
import React from 'react';
import styles from './Button.module.css';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
}

export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`${styles.btn} ${styles[variant]} ${styles[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 2: 创建 src/components/common/Button.module.css**

```css
.btn {
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  transition: background 150ms ease, opacity 150ms ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.primary {
  background: var(--accent);
  color: #000;
}
.primary:hover:not(:disabled) {
  background: #33ddff;
}

.secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
}
.secondary:hover:not(:disabled) {
  background: var(--border);
}

.danger {
  background: var(--accent-alt);
  color: #fff;
}
.danger:hover:not(:disabled) {
  background: #ff5a7a;
}

.sm { padding: 4px 10px; font-size: 12px; }
.md { padding: 8px 16px; font-size: 14px; }
.lg { padding: 12px 24px; font-size: 16px; }
```

- [ ] **Step 3: 创建 src/components/common/IconButton.tsx**

```tsx
import React from 'react';
import styles from './IconButton.module.css';

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'danger';
}

export default function IconButton({
  size = 'md',
  variant = 'default',
  className = '',
  children,
  ...rest
}: IconButtonProps) {
  return (
    <button
      className={`${styles.iconBtn} ${styles[size]} ${styles[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 4: 创建 src/components/common/IconButton.module.css**

```css
.iconBtn {
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 150ms ease;
  background: transparent;
  color: var(--text-secondary);
  padding: 0;
}
.iconBtn:hover:not(:disabled) {
  background: var(--bg-surface);
  color: var(--text-primary);
}
.iconBtn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.iconBtn.danger:hover:not(:disabled) {
  background: var(--accent-alt);
  color: #fff;
}
.sm { width: 24px; height: 24px; }
.md { width: 32px; height: 32px; }
.lg { width: 40px; height: 40px; }
```

---

## Task 6: AppShell 和 Header 布局组件

**Files:**
- Create: `src/components/layout/AppShell.tsx`
- Create: `src/components/layout/AppShell.module.css`
- Create: `src/components/layout/Header.tsx`
- Create: `src/components/layout/Header.module.css`

- [ ] **Step 1: 创建 src/components/layout/AppShell.tsx**

```tsx
import React from 'react';
import styles from './AppShell.module.css';
import Header from './Header';
import MaterialsPanel from './MaterialsPanel';
import TimelinePanel from './TimelinePanel';
import InspectorPanel from './InspectorPanel';
import PreviewBar from './PreviewBar';

export default function AppShell() {
  return (
    <div className={styles.shell}>
      <Header />
      <div className={styles.workspace}>
        <MaterialsPanel />
        <TimelinePanel />
        <InspectorPanel />
      </div>
      <PreviewBar />
    </div>
  );
}
```

- [ ] **Step 2: 创建 src/components/layout/AppShell.module.css**

```css
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-primary);
}

.workspace {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 8px;
  padding: 8px;
}
```

- [ ] **Step 3: 创建 src/components/layout/Header.tsx**

```tsx
'use client';
import React from 'react';
import styles from './Header.module.css';
import Button from '@/components/common/Button';
import { Film, Download } from 'lucide-react';

interface HeaderProps {
  onRender?: () => void;
  isRendering?: boolean;
}

export default function Header({ onRender, isRendering }: HeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <Film size={20} className={styles.logo} />
        <span className={styles.title}>ClipForge</span>
        <span className={styles.badge}>Phase 1</span>
      </div>
      <div className={styles.actions}>
        <Button
          variant="primary"
          size="md"
          onClick={onRender}
          disabled={isRendering}
        >
          <Download size={14} />
          {isRendering ? '渲染中…' : '渲染视频'}
        </Button>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: 创建 src/components/layout/Header.module.css**

```css
.header {
  height: 56px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo {
  color: var(--accent);
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.badge {
  font-size: 10px;
  background: var(--accent);
  color: #000;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 600;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
```

---

## Task 7: MaterialsPanel + SearchBox + MaterialCard + MaterialList

**Files:**
- Create: `src/components/layout/MaterialsPanel.tsx`
- Create: `src/components/layout/MaterialsPanel.module.css`
- Create: `src/components/materials/SearchBox.tsx`
- Create: `src/components/materials/SearchBox.module.css`
- Create: `src/components/materials/MaterialCard.tsx`
- Create: `src/components/materials/MaterialCard.module.css`
- Create: `src/components/materials/MaterialList.tsx`
- Create: `src/components/materials/MaterialList.module.css`

- [ ] **Step 1: 创建 src/components/materials/SearchBox.tsx**

```tsx
'use client';
import React, { useCallback } from 'react';
import styles from './SearchBox.module.css';
import { Search } from 'lucide-react';
import { useMaterialsStore } from '@/stores/useMaterialsStore';

export default function SearchBox() {
  const { searchQuery, setSearchQuery, performSearch } = useMaterialsStore();

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchQuery(e.target.value);
    },
    [setSearchQuery]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        performSearch(searchQuery);
      }
    },
    [searchQuery, performSearch]
  );

  return (
    <div className={styles.wrap}>
      <Search size={14} className={styles.icon} />
      <input
        type="text"
        className={styles.input}
        placeholder="搜索素材（标题/标签）…"
        value={searchQuery}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />
    </div>
  );
}
```

- [ ] **Step 2: 创建 src/components/materials/SearchBox.module.css**

```css
.wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.icon {
  position: absolute;
  left: 8px;
  color: var(--text-secondary);
  pointer-events: none;
}
.input {
  width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 13px;
  padding: 6px 8px 6px 28px;
  outline: none;
  transition: border-color 150ms;
}
.input::placeholder {
  color: var(--text-secondary);
}
.input:focus {
  border-color: var(--accent);
}
```

- [ ] **Step 3: 创建 src/components/materials/MaterialCard.tsx**

```tsx
'use client';
import React from 'react';
import styles from './MaterialCard.module.css';
import type { VideoMaterial } from '@/adapters/materials/types';
import { Clock, Tag } from 'lucide-react';

interface MaterialCardProps {
  material: VideoMaterial;
  onAdd: (id: string) => void;
}

function formatDuration(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

export default function MaterialCard({ material, onAdd }: MaterialCardProps) {
  return (
    <div
      className={styles.card}
      onClick={() => onAdd(material.id)}
      title={`添加 "${material.title}" 到时间线`}
    >
      <div className={styles.thumb}>
        <img src={material.thumbnailUrl} alt={material.title} />
      </div>
      <div className={styles.info}>
        <div className={styles.title}>{material.title}</div>
        <div className={styles.meta}>
          <span className={styles.metaItem}>
            <Clock size={10} />
            {formatDuration(material.duration)}
          </span>
          <span className={styles.metaItem}>
            <Tag size={10} />
            {material.tags.slice(0, 2).join(', ')}
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 创建 src/components/materials/MaterialCard.module.css**

```css
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 150ms, transform 150ms;
}
.card:hover {
  border-color: var(--accent);
  transform: scale(1.02);
}
.thumb {
  width: 100%;
  aspect-ratio: 16/9;
  background: var(--bg-secondary);
  overflow: hidden;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.info {
  padding: 8px;
}
.title {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta {
  display: flex;
  gap: 8px;
}
.metaItem {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--text-secondary);
}
```

- [ ] **Step 5: 创建 src/components/materials/MaterialList.tsx**

```tsx
'use client';
import React from 'react';
import styles from './MaterialList.module.css';
import MaterialCard from './MaterialCard';
import { useMaterialsStore } from '@/stores/useMaterialsStore';
import { useTimelineStore } from '@/stores/useTimelineStore';
import { localAdapter } from '@/adapters/materials/localAdapter';

export default function MaterialList() {
  const { results, isLoading } = useMaterialsStore();
  const { addClip } = useTimelineStore();

  const handleAdd = async (id: string) => {
    const mat = await localAdapter.getById(id);
    if (!mat) return;
    addClip(id);
    const idx = useTimelineStore.getState().clips.length - 1;
    if (idx >= 0) {
      useTimelineStore.getState().setClipInOut(idx, 0, mat.duration);
    }
  };

  if (isLoading) {
    return <div className={styles.empty}>搜索中…</div>;
  }

  if (results.length === 0) {
    return <div className={styles.empty}>输入关键词搜索素材</div>;
  }

  return (
    <div className={styles.list}>
      {results.map((m) => (
        <MaterialCard key={m.id} material={m} onAdd={handleAdd} />
      ))}
    </div>
  );
}
```

- [ ] **Step 6: 创建 src/components/materials/MaterialList.module.css**

```css
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding-right: 4px;
}
.empty {
  color: var(--text-secondary);
  font-size: 12px;
  text-align: center;
  padding: 20px 0;
}
```

- [ ] **Step 7: 创建 src/components/layout/MaterialsPanel.tsx**

```tsx
'use client';
import React from 'react';
import styles from './MaterialsPanel.module.css';
import SearchBox from '@/components/materials/SearchBox';
import MaterialList from '@/components/materials/MaterialList';

export default function MaterialsPanel() {
  return (
    <aside className={styles.panel}>
      <div className={styles.search}>
        <SearchBox />
      </div>
      <div className={styles.results}>
        <MaterialList />
      </div>
    </aside>
  );
}
```

- [ ] **Step 8: 创建 src/components/layout/MaterialsPanel.module.css**

```css
.panel {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.search {
  padding: 8px;
  border-bottom: 1px solid var(--border);
}
.results {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
```

---

## Task 8: TimelinePanel + TimelineTrack + TimelineClip + Playhead

**Files:**
- Create: `src/components/layout/TimelinePanel.tsx`
- Create: `src/components/layout/TimelinePanel.module.css`
- Create: `src/components/timeline/TimelineTrack.tsx`
- Create: `src/components/timeline/TimelineTrack.module.css`
- Create: `src/components/timeline/TimelineClip.tsx`
- Create: `src/components/timeline/TimelineClip.module.css`
- Create: `src/components/timeline/Playhead.tsx`
- Create: `src/components/timeline/Playhead.module.css`

- [ ] **Step 1: 创建 src/components/timeline/TimelineClip.tsx**

```tsx
'use client';
import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import styles from './TimelineClip.module.css';
import IconButton from '@/components/common/IconButton';
import { X } from 'lucide-react';
import { useTimelineStore } from '@/stores/useTimelineStore';

interface TimelineClipProps {
  index: number;
  materialId: string;
  inPoint: number;
  outPoint: number;
  totalDuration: number;
}

function formatTC(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${h}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

export default function TimelineClip({
  index,
  materialId,
  inPoint,
  outPoint,
  totalDuration,
}: TimelineClipProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: `${index}` });
  const { selectedClipIndex, selectClip, removeClip } = useTimelineStore();

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const clipDuration = outPoint - inPoint;
  const widthPercent = totalDuration > 0 ? (clipDuration / totalDuration) * 100 : 0;
  const isSelected = selectedClipIndex === index;

  return (
    <div
      ref={setNodeRef}
      style={{ ...style, width: `${Math.max(widthPercent, 10)}%` }}
      className={`${styles.clip} ${isDragging ? styles.dragging : ''} ${isSelected ? styles.selected : ''}`}
      onClick={() => selectClip(index)}
      {...attributes}
      {...listeners}
    >
      <div className={styles.label}>{materialId}</div>
      <span className={styles.time}>
        {formatTC(inPoint)} – {formatTC(outPoint)}
      </span>
      <IconButton
        size="sm"
        variant="danger"
        className={styles.removeBtn}
        onClick={(e) => {
          e.stopPropagation();
          removeClip(index);
        }}
      >
        <X size={10} />
      </IconButton>
    </div>
  );
}
```

- [ ] **Step 2: 创建 src/components/timeline/TimelineClip.module.css**

```css
.clip {
  position: relative;
  height: 48px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 24px 0 8px;
  cursor: grab;
  transition: border-color 150ms, box-shadow 150ms;
  flex-shrink: 0;
}
.clip:hover {
  border-color: var(--accent);
}
.clip.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}
.clip.dragging {
  opacity: 0.5;
  cursor: grabbing;
}
.label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.time {
  font-size: 10px;
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', monospace;
}
.removeBtn {
  position: absolute;
  top: 2px;
  right: 2px;
}
```

- [ ] **Step 3: 创建 src/components/timeline/Playhead.tsx**

```tsx
'use client';
import React from 'react';
import styles from './Playhead.module.css';

interface PlayheadProps {
  positionPercent: number;
}

export default function Playhead({ positionPercent }: PlayheadProps) {
  return (
    <div
      className={styles.playhead}
      style={{ left: `${positionPercent}%` }}
    >
      <div className={styles.head} />
      <div className={styles.line} />
    </div>
  );
}
```

- [ ] **Step 4: 创建 src/components/timeline/Playhead.module.css**

```css
.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 10;
  pointer-events: none;
  transform: translateX(-50%);
}
.head {
  width: 10px;
  height: 10px;
  background: var(--accent);
  border-radius: 2px 2px 0 0;
  margin: 0 auto;
}
.line {
  width: 2px;
  height: calc(100% - 10px);
  background: var(--accent);
  margin: 0 auto;
}
```

- [ ] **Step 5: 创建 src/components/timeline/TimelineTrack.tsx**

```tsx
'use client';
import React, { useMemo } from 'react';
import {
  SortableContext,
  horizontalListSortingStrategy,
} from '@dnd-kit/sortable';
import styles from './TimelineTrack.module.css';
import TimelineClip from './TimelineClip';
import Playhead from './Playhead';
import { useTimelineStore } from '@/stores/useTimelineStore';

export default function TimelineTrack() {
  const { clips, playheadTime } = useTimelineStore();

  const totalDuration = useMemo(() => {
    return clips.reduce((sum, clip) => sum + (clip.outPoint - clip.inPoint), 0);
  }, [clips]);

  const playheadPercent =
    totalDuration > 0 ? (playheadTime / totalDuration) * 100 : 0;

  return (
    <div className={styles.track}>
      <SortableContext
        items={clips.map((_, i) => `${i}`)}
        strategy={horizontalListSortingStrategy}
      >
        {clips.length === 0 ? (
          <div className={styles.empty}>将素材拖入时间线开始剪辑</div>
        ) : (
          <div className={styles.clips}>
            {clips.map((clip, i) => (
              <TimelineClip
                key={`${i}`}
                index={i}
                materialId={clip.materialId}
                inPoint={clip.inPoint}
                outPoint={clip.outPoint}
                totalDuration={totalDuration}
              />
            ))}
          </div>
        )}
      </SortableContext>
      {clips.length > 0 && (
        <Playhead positionPercent={playheadPercent} />
      )}
    </div>
  );
}
```

- [ ] **Step 6: 创建 src/components/timeline/TimelineTrack.module.css**

```css
.track {
  position: relative;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  min-height: 80px;
  padding: 8px;
  overflow-x: auto;
  flex: 1;
}
.clips {
  display: flex;
  gap: 4px;
  align-items: center;
  min-height: 48px;
}
.empty {
  color: var(--text-secondary);
  font-size: 12px;
  text-align: center;
  padding: 20px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
}
```

- [ ] **Step 7: 创建 src/components/layout/TimelinePanel.tsx**

```tsx
'use client';
import React from 'react';
import styles from './TimelinePanel.module.css';
import TimelineTrack from '@/components/timeline/TimelineTrack';
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { useTimelineStore } from '@/stores/useTimelineStore';

export default function TimelinePanel() {
  const { reorderClips } = useTimelineStore();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const fromIndex = parseInt(active.id as string, 10);
    const toIndex = parseInt(over.id as string, 10);
    reorderClips(fromIndex, toIndex);
  };

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label}>时间线</span>
        <span className={styles.hint}>拖拽排序 · 点击选中 · × 删除</span>
      </div>
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <TimelineTrack />
      </DndContext>
    </section>
  );
}
```

- [ ] **Step 8: 创建 src/components/layout/TimelinePanel.module.css**

```css
.panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}
.label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.hint {
  font-size: 10px;
  color: var(--text-secondary);
}
```

---

## Task 9: InspectorPanel + ClipProperties + TimecodeInput

**Files:**
- Create: `src/components/layout/InspectorPanel.tsx`
- Create: `src/components/layout/InspectorPanel.module.css`
- Create: `src/components/inspector/InspectorEmpty.tsx`
- Create: `src/components/inspector/ClipProperties.tsx`
- Create: `src/components/inspector/ClipProperties.module.css`
- Create: `src/components/inspector/TimecodeInput.tsx`
- Create: `src/components/inspector/TimecodeInput.module.css`

- [ ] **Step 1: 创建 src/components/inspector/TimecodeInput.tsx**

```tsx
'use client';
import React, { useCallback, useState } from 'react';
import styles from './TimecodeInput.module.css';

interface TimecodeInputProps {
  value: number;
  onChange: (seconds: number) => void;
  max?: number;
  label: string;
}

function parseTC(str: string): number | null {
  const parts = str.split(':').map(Number);
  if (parts.some(isNaN)) return null;
  if (parts.length === 3) {
    const [h, m, s] = parts;
    return h * 3600 + m * 60 + s;
  }
  if (parts.length === 2) {
    const [m, s] = parts;
    return m * 60 + s;
  }
  return null;
}

function formatTC(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${h}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

export default function TimecodeInput({
  value,
  onChange,
  max,
  label,
}: TimecodeInputProps) {
  const [displayValue, setDisplayValue] = useState(formatTC(value));
  const [error, setError] = useState(false);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setDisplayValue(e.target.value);
      const parsed = parseTC(e.target.value);
      if (parsed === null) {
        setError(true);
        return;
      }
      if (max !== undefined && parsed > max) {
        setError(true);
        return;
      }
      setError(false);
      onChange(parsed);
    },
    [onChange, max]
  );

  return (
    <div className={styles.field}>
      <label className={styles.label}>{label}</label>
      <input
        type="text"
        className={`${styles.input} ${error ? styles.error : ''}`}
        value={displayValue}
        onChange={handleChange}
        placeholder="HH:MM:SS"
      />
    </div>
  );
}
```

- [ ] **Step 2: 创建 src/components/inspector/TimecodeInput.module.css**

```css
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.label {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
}
.input {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  padding: 6px 8px;
  outline: none;
  transition: border-color 150ms;
}
.input:focus {
  border-color: var(--accent);
}
.input.error {
  border-color: var(--accent-alt);
  color: var(--accent-alt);
}
```

- [ ] **Step 3: 创建 src/components/inspector/ClipProperties.tsx**

```tsx
'use client';
import React, { useMemo } from 'react';
import styles from './ClipProperties.module.css';
import TimecodeInput from './TimecodeInput';
import { useTimelineStore } from '@/stores/useTimelineStore';
import { localAdapter } from '@/adapters/materials/localAdapter';
import type { VideoMaterial } from '@/adapters/materials/types';

export default function ClipProperties() {
  const { clips, selectedClipIndex, setClipInOut } = useTimelineStore();

  if (selectedClipIndex === null) return null;

  const clip = clips[selectedClipIndex];

  const material = useMemo<VideoMaterial | null>(() => {
    return localAdapter.getById(clip.materialId) as unknown as VideoMaterial;
  }, [clip.materialId]);

  if (!material) return null;

  const clipDuration = clip.outPoint - clip.inPoint;

  return (
    <div className={styles.props}>
      <div className={styles.section}>
        <div className={styles.field}>
          <span className={styles.fieldLabel}>素材名称</span>
          <span className={styles.fieldValue}>{material.title}</span>
        </div>
        <div className={styles.field}>
          <span className={styles.fieldLabel}>原始时长</span>
          <span className={styles.fieldValue}>{material.duration}s</span>
        </div>
        <div className={styles.field}>
          <span className={styles.fieldLabel}>剪辑时长</span>
          <span className={`${styles.fieldValue} ${styles.accent}`}>{clipDuration}s</span>
        </div>
      </div>

      <div className={styles.divider} />

      <div className={styles.section}>
        <TimecodeInput
          label="入点"
          value={clip.inPoint}
          onChange={(v) => setClipInOut(selectedClipIndex, v, clip.outPoint)}
          max={clip.outPoint - 1}
        />
        <TimecodeInput
          label="出点"
          value={clip.outPoint}
          onChange={(v) => setClipInOut(selectedClipIndex, clip.inPoint, v)}
          max={material.duration}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 创建 src/components/inspector/ClipProperties.module.css**

```css
.props {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.divider {
  height: 1px;
  background: var(--border);
}
.field {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.fieldLabel {
  font-size: 12px;
  color: var(--text-secondary);
}
.fieldValue {
  font-size: 12px;
  color: var(--text-primary);
  font-weight: 500;
}
.fieldValue.accent {
  color: var(--accent);
}
```

- [ ] **Step 5: 创建 src/components/inspector/InspectorEmpty.tsx**

```tsx
'use client';
import React from 'react';

export default function InspectorEmpty() {
  return (
    <div style={{ color: 'var(--text-secondary)', fontSize: '12px', textAlign: 'center', padding: '20px' }}>
      选择时间线中的一个片段以编辑属性
    </div>
  );
}
```

- [ ] **Step 6: 创建 src/components/layout/InspectorPanel.tsx**

```tsx
'use client';
import React from 'react';
import styles from './InspectorPanel.module.css';
import InspectorEmpty from '@/components/inspector/InspectorEmpty';
import ClipProperties from '@/components/inspector/ClipProperties';
import { useTimelineStore } from '@/stores/useTimelineStore';

export default function InspectorPanel() {
  const { selectedClipIndex } = useTimelineStore();

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label}>属性</span>
      </div>
      <div className={styles.content}>
        {selectedClipIndex === null ? (
          <InspectorEmpty />
        ) : (
          <ClipProperties />
        )}
      </div>
    </aside>
  );
}
```

- [ ] **Step 7: 创建 src/components/layout/InspectorPanel.module.css**

```css
.panel {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.header {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
```

---

## Task 10: PreviewBar + VideoPlayer + PlaybackControls + TimecodeDisplay

**Files:**
- Create: `src/components/layout/PreviewBar.tsx`
- Create: `src/components/layout/PreviewBar.module.css`
- Create: `src/components/preview/VideoPlayer.tsx`
- Create: `src/components/preview/VideoPlayer.module.css`
- Create: `src/components/preview/PlaybackControls.tsx`
- Create: `src/components/preview/PlaybackControls.module.css`
- Create: `src/components/preview/TimecodeDisplay.tsx`
- Create: `src/components/preview/TimecodeDisplay.module.css`

- [ ] **Step 1: 创建 src/components/preview/TimecodeDisplay.tsx**

```tsx
'use client';
import React from 'react';
import styles from './TimecodeDisplay.module.css';

interface TimecodeDisplayProps {
  seconds: number;
}

function formatTC(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${h}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

export default function TimecodeDisplay({ seconds }: TimecodeDisplayProps) {
  return <span className={styles.tc}>{formatTC(seconds)}</span>;
}
```

- [ ] **Step 2: 创建 src/components/preview/TimecodeDisplay.module.css**

```css
.tc {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 70px;
}
```

- [ ] **Step 3: 创建 src/components/preview/PlaybackControls.tsx**

```tsx
'use client';
import React from 'react';
import styles from './PlaybackControls.module.css';
import IconButton from '@/components/common/IconButton';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';

interface PlaybackControlsProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  onSkipBack: () => void;
  onSkipForward: () => void;
}

export default function PlaybackControls({
  isPlaying,
  onPlayPause,
  onSkipBack,
  onSkipForward,
}: PlaybackControlsProps) {
  return (
    <div className={styles.controls}>
      <IconButton size="md" onClick={onSkipBack} title="后退5秒">
        <SkipBack size={16} />
      </IconButton>
      <IconButton size="lg" onClick={onPlayPause}>
        {isPlaying ? <Pause size={18} /> : <Play size={18} />}
      </IconButton>
      <IconButton size="md" onClick={onSkipForward} title="前进5秒">
        <SkipForward size={16} />
      </IconButton>
    </div>
  );
}
```

- [ ] **Step 4: 创建 src/components/preview/PlaybackControls.module.css**

```css
.controls {
  display: flex;
  align-items: center;
  gap: 4px;
}
```

- [ ] **Step 5: 创建 src/components/preview/VideoPlayer.tsx**

```tsx
'use client';
import React, { useRef, useState, useEffect, useCallback } from 'react';
import styles from './VideoPlayer.module.css';
import PlaybackControls from './PlaybackControls';
import TimecodeDisplay from './TimecodeDisplay';
import { useTimelineStore } from '@/stores/useTimelineStore';

export default function VideoPlayer() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const { clips, playheadTime, setPlayheadTime } = useTimelineStore();
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  const totalDuration = clips.reduce((sum, c) => sum + (c.outPoint - c.inPoint), 0);

  useEffect(() => {
    if (!videoRef.current || clips.length === 0) return;
    let accTime = 0;
    for (const clip of clips) {
      const clipDur = clip.outPoint - clip.inPoint;
      if (playheadTime < accTime + clipDur) {
        const clipLocalTime = playheadTime - accTime + clip.inPoint;
        videoRef.current.currentTime = clipLocalTime;
        return;
      }
      accTime += clipDur;
    }
  }, [playheadTime, clips]);

  const handlePlayPause = useCallback(() => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current) return;
    setCurrentTime(videoRef.current.currentTime);
  }, []);

  const handleSkipBack = useCallback(() => {
    setPlayheadTime(Math.max(0, playheadTime - 5));
  }, [playheadTime, setPlayheadTime]);

  const handleSkipForward = useCallback(() => {
    setPlayheadTime(Math.min(totalDuration, playheadTime + 5));
  }, [playheadTime, totalDuration, setPlayheadTime]);

  const firstClip = clips[0];

  if (clips.length === 0) {
    return (
      <div className={styles.player}>
        <div className={styles.placeholder}>在时间线中添加片段后可以预览</div>
      </div>
    );
  }

  return (
    <div className={styles.player}>
      <video
        ref={videoRef}
        className={styles.video}
        src={firstClip ? `/fixtures/${firstClip.materialId}.mp4` : undefined}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setIsPlaying(false)}
      />
      <div className={styles.controls}>
        <PlaybackControls
          isPlaying={isPlaying}
          onPlayPause={handlePlayPause}
          onSkipBack={handleSkipBack}
          onSkipForward={handleSkipForward}
        />
        <TimecodeDisplay seconds={currentTime} />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: 创建 src/components/preview/VideoPlayer.module.css**

```css
.player {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #000;
  border-radius: var(--radius-md);
  overflow: hidden;
}
.video {
  flex: 1;
  width: 100%;
  object-fit: contain;
}
.controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px;
  background: var(--bg-secondary);
}
.placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
}
```

- [ ] **Step 7: 创建 src/components/layout/PreviewBar.tsx**

```tsx
'use client';
import React from 'react';
import styles from './PreviewBar.module.css';
import VideoPlayer from '@/components/preview/VideoPlayer';

export default function PreviewBar() {
  return (
    <footer className={styles.bar}>
      <VideoPlayer />
    </footer>
  );
}
```

- [ ] **Step 8: 创建 src/components/layout/PreviewBar.module.css**

```css
.bar {
  height: 240px;
  flex-shrink: 0;
  padding: 8px;
  border-top: 1px solid var(--border);
}
```

---

## Task 11: RenderModal + FFmpeg 封装 + 渲染流程

**Files:**
- Create: `src/components/common/RenderModal.tsx`
- Create: `src/components/common/RenderModal.module.css`
- Create: `src/lib/ffmpeg.ts`
- Create: `src/lib/timecode.ts`

- [ ] **Step 1: 创建 src/lib/timecode.ts**

```typescript
export function parseTimecode(str: string): number | null {
  const parts = str.split(':').map(Number);
  if (parts.some(isNaN)) return null;
  if (parts.length === 3) {
    const [h, m, s] = parts;
    return h * 3600 + m * 60 + s;
  }
  if (parts.length === 2) {
    const [m, s] = parts;
    return m * 60 + s;
  }
  return null;
}

export function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}
```

- [ ] **Step 2: 创建 src/lib/ffmpeg.ts**

```typescript
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { toBlobURL, fetchFile } from '@ffmpeg/util';

let ffmpeg: FFmpeg | null = null;

export async function getFFmpeg(): Promise<FFmpeg> {
  if (ffmpeg && ffmpeg.loaded) return ffmpeg;

  ffmpeg = new FFmpeg();

  ffmpeg.on('progress', ({ progress }) => {
    // global progress tracking can be added here
  });

  const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm';
  await ffmpeg.load({
    coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
    wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
  });

  return ffmpeg;
}

export async function renderTimeline(
  clips: Array<{ materialId: string; inPoint: number; outPoint: number }>,
  onProgress?: (percent: number, label: string) => void
): Promise<Blob> {
  const ff = await getFFmpeg();

  const total = clips.length;
  const tempFiles: string[] = [];

  for (let i = 0; i < clips.length; i++) {
    const clip = clips[i];
    onProgress?.(Math.round((i / total) * 80), `裁剪片段 ${clip.materialId}`);
    const videoURL = `/fixtures/${clip.materialId}.mp4`;
    const inputData = await fetchFile(videoURL);
    const inputName = `input_${i}.mp4`;
    await ff.writeFile(inputName, inputData);

    const outputName = `cut_${i}.mp4`;
    const ss = clip.inPoint.toFixed(3);
    const to = clip.outPoint.toFixed(3);
    await ff.exec(['-i', inputName, '-ss', ss, '-to', to, '-c', 'copy', outputName]);
    tempFiles.push(outputName);

    await ff.deleteFile(inputName);
  }

  onProgress?.(85, '合并片段…');

  const concatList = tempFiles.map((f) => `file '${f}'`).join('\n');
  await ff.writeFile('list.txt', concatList);
  await ff.exec(['-f', 'concat', '-i', 'list.txt', '-c', 'copy', 'output.mp4']);

  onProgress?.(95, '生成最终文件…');
  const data = await ff.readFile('output.mp4');

  for (const f of tempFiles) {
    await ff.deleteFile(f);
  }
  await ff.deleteFile('list.txt');
  await ff.deleteFile('output.mp4');

  return new Blob([data], { type: 'video/mp4' });
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 3: 创建 src/components/common/RenderModal.tsx**

```tsx
'use client';
import React, { useState, useCallback } from 'react';
import styles from './RenderModal.module.css';
import Button from './Button';
import { X, CheckCircle, AlertCircle } from 'lucide-react';

interface RenderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRender: () => Promise<void>;
}

type RenderState = 'idle' | 'rendering' | 'success' | 'error';

export default function RenderModal({ isOpen, onClose, onRender }: RenderModalProps) {
  const [state, setState] = useState<RenderState>('idle');
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleRender = useCallback(async () => {
    setState('rendering');
    setProgress(0);
    setErrorMsg('');
    try {
      await onRender();
      setState('success');
      setProgress(100);
    } catch (err) {
      setState('error');
      setErrorMsg(err instanceof Error ? err.message : '渲染失败');
    }
  }, [onRender]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <span className={styles.title}>
            {state === 'idle' && '渲染设置'}
            {state === 'rendering' && '渲染中…'}
            {state === 'success' && '渲染完成'}
            {state === 'error' && '渲染失败'}
          </span>
          <Button variant="secondary" size="sm" onClick={onClose}>
            <X size={14} />
          </Button>
        </div>

        <div className={styles.body}>
          {state === 'idle' && (
            <>
              <p className={styles.desc}>视频将以 MP4 格式在浏览器中编码，完成后自动下载。</p>
              <Button variant="primary" onClick={handleRender}>开始渲染</Button>
            </>
          )}

          {state === 'rendering' && (
            <>
              <div className={styles.progressBar}>
                <div className={styles.progressFill} style={{ width: `${progress}%` }} />
              </div>
              <div className={styles.progressInfo}>
                <span>{progress}%</span>
                <span>{progressLabel}</span>
              </div>
            </>
          )}

          {state === 'success' && (
            <div className={styles.result}>
              <CheckCircle size={40} className={styles.successIcon} />
              <p>视频渲染完成！</p>
              <Button variant="primary" onClick={onClose}>完成</Button>
            </div>
          )}

          {state === 'error' && (
            <div className={styles.result}>
              <AlertCircle size={40} className={styles.errorIcon} />
              <p>{errorMsg}</p>
              <Button variant="secondary" onClick={handleRender}>重试</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 创建 src/components/common/RenderModal.module.css**

```css
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  width: 400px;
  max-width: 90vw;
  overflow: hidden;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.body {
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}
.desc {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
}
.progressBar {
  width: 100%;
  height: 8px;
  background: var(--bg-surface);
  border-radius: 4px;
  overflow: hidden;
}
.progressFill {
  height: 100%;
  background: var(--accent);
  transition: width 200ms ease;
}
.progressInfo {
  width: 100%;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}
.result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.result p {
  font-size: 14px;
  color: var(--text-primary);
}
.successIcon {
  color: var(--accent);
}
.errorIcon {
  color: var(--accent-alt);
}
```

---

## Task 12: 集成到 page.tsx 并修复所有 TypeScript 错误

**Files:**
- Modify: `src/app/page.tsx` (replace scaffold with AppShell)

- [ ] **Step 1: 修改 src/app/page.tsx**

```tsx
import AppShell from '@/components/layout/AppShell';

export default function HomePage() {
  return <AppShell />;
}
```

- [ ] **Step 2: 运行 TypeScript 检查**

Run: `npx tsc --noEmit`
Expected: 无 error（允许未使用变量的 warning）

- [ ] **Step 3: 启动开发服务器验证**

Run: `npm run dev`
Expected: 页面加载正常，控制台无 Error 级别错误

---

## Task 13: 添加入门文档（README）

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# ClipForge Phase 1

AI 视频剪辑助手 Phase 1 — 验证核心架构：素材搜索 → 时间线组织 → 视频渲染。

## 技术栈

- **Next.js 14** (App Router, SSR)
- **React 18** + TypeScript
- **Zustand** (状态管理)
- **@dnd-kit** (拖拽排序)
- **@ffmpeg/ffmpeg** (浏览器端视频编码)

## 快速开始

\`\`\`bash
npm install
npm run dev
\`\`\`

打开 http://localhost:3000

## Phase 1 功能

- [x] 本地 JSON fixture 素材搜索（关键词匹配 title + tags）
- [x] 时间线单轨道编辑（添加、删除、拖拽排序片段）
- [x] 入点/出点编辑（属性检查器）
- [x] 视频预览（播放头 seek + 播放控制）
- [x] FFmpeg.wasm 渲染输出（.mp4 格式，浏览器端编码）
- [x] 深色剪辑界面风格

## Fixture 视频

Phase 1 使用本地 \`public/fixtures/\` 目录下的 .mp4 文件。需要自行准备短时长示例视频。

1. 下载视频到 \`public/fixtures/vid_001.mp4\` 等
2. 更新 \`fixtures/videos.json\` 中的元数据
3. 视频缩略图放到 \`public/fixtures/thumbnails/\`

## 后续计划

- Phase 2: 真实平台素材爬取（YouTube/B站/Pexels）
- Phase 3: 多轨道 + 转场 + 特效
- Phase 4: 音频混音
- Phase 5: 项目保存/加载
```

---

## Implementation Order

1. Task 1: 初始化 Next.js 项目
2. Task 2: Fixture 数据结构
3. Task 3: 素材适配器
4. Task 4: Zustand Stores
5. Task 5: 通用 UI 组件
6. Task 6: AppShell + Header
7. Task 7: MaterialsPanel + Search + Card + List
8. Task 8: TimelinePanel + Track + Clip + Playhead
9. Task 9: InspectorPanel + ClipProperties + TimecodeInput
10. Task 10: PreviewBar + VideoPlayer + PlaybackControls
11. Task 11: RenderModal + FFmpeg 封装 + 渲染流程
12. Task 12: 集成 + TypeScript 修复
13. Task 13: README

---

## Spec Coverage Checklist

- [x] 本地 JSON fixture 素材搜索 — Task 3, Task 7
- [x] 时间线单轨道编辑（添加、删除、排序）— Task 4, Task 8
- [x] 入点/出点编辑 — Task 4, Task 9
- [x] 视频预览 + 播放控制 — Task 10
- [x] FFmpeg.wasm 渲染输出 — Task 11
- [x] 深色剪辑界面风格 — Task 1 (globals.css), 各个 CSS Modules
- [x] 目录结构符合经典 MVC — Task 1 文件结构
- [x] 技术栈匹配（Next.js + React + Zustand + dnd-kit + FFmpeg.wasm）— Task 1
- [x] Zustand Store 设计 — Task 4
- [x] 素材适配器接口 — Task 3
- [x] Fixture videos.json 数据 — Task 2
