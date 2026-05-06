export interface TaskConceptStep {
  id: string
  title: string
  description: string
  status: string
  progress: number
  summary: string
  error?: {
    message: string
  } | null
}

export interface TaskConceptEvent {
  id: string
  eventType: string
  step: string
  message: string
  createdAt: string
}

export interface TaskConceptClip {
  sceneId: number
  sourceUrl: string
  publicUrl: string
  caption: string
  duration: number
  sourceDuration: number
}

export interface TaskConceptDetail {
  id: string
  sessionId: string
  title: string
  status: string
  progress: number
  currentStep: string
  currentStepId: string
  createdAt: string
  updatedAt: string
  videoUrl: string | null
  error: {
    message: string
  } | null
  steps: TaskConceptStep[]
  events: TaskConceptEvent[]
  clips: TaskConceptClip[]
}

export interface TaskConceptSummary {
  id: string
  sessionId: string
  title: string
  status: string
  progress: number
  currentStep: string
  currentStepId: string
  updatedAt: string
}

export const taskConceptDetails: TaskConceptDetail[] = [
  {
    id: '97383060-838b-43c9-800c-162e6d69f86a',
    sessionId: '939b4573-187a-406e-9a64-220b8edc1b26',
    title: '智能剪辑短片',
    status: 'succeeded',
    progress: 100,
    currentStep: '完成',
    currentStepId: 'render_video',
    createdAt: '2026-05-06T11:10:44.484624',
    updatedAt: '2026-05-06T11:10:51.355605',
    videoUrl: '/output/939b4573-187a-406e-9a64-220b8edc1b26.mp4',
    error: null,
    steps: [
      {
        id: 'create_task',
        title: '创建执行任务',
        description: '将确认后的方案投递到后端执行队列。',
        status: 'succeeded',
        progress: 100,
        summary: '任务成功进入独立队列 clipforge-agent-ws-hardening。',
      },
      {
        id: 'search_assets',
        title: '搜索素材',
        description: '按镜头关键词搜索可用公开视频素材。',
        status: 'succeeded',
        progress: 100,
        summary: '4 个场景均命中 Pexels 候选素材，并跳过了不必要的 YouTube fallback 搜索。',
      },
      {
        id: 'prepare_assets',
        title: '准备素材',
        description: '下载素材、修正裁剪窗口并整理渲染输入。',
        status: 'succeeded',
        progress: 100,
        summary: '4 段素材下载成功，已写入 clips 和 trim 元数据。',
      },
      {
        id: 'render_video',
        title: '渲染视频',
        description: '合成字幕、混音并输出 MP4。',
        status: 'succeeded',
        progress: 100,
        summary: '渲染完成，产出可播放 MP4。',
      },
    ],
    events: [
      {
        id: 'event-queued',
        eventType: 'job_queued',
        step: 'queued',
        message: '任务已入队，等待执行',
        createdAt: '2026-05-06T11:10:44.487655',
      },
      {
        id: 'event-start',
        eventType: 'job_started',
        step: 'searching',
        message: '任务开始执行',
        createdAt: '2026-05-06T11:10:44.665025',
      },
      {
        id: 'event-clips',
        eventType: 'clips_ready',
        step: 'downloading',
        message: '素材已准备完成，共 4 段',
        createdAt: '2026-05-06T11:10:46.903004',
      },
      {
        id: 'event-render',
        eventType: 'render_started',
        step: 'rendering',
        message: '开始合成视频',
        createdAt: '2026-05-06T11:10:46.924282',
      },
      {
        id: 'event-done',
        eventType: 'job_succeeded',
        step: 'done',
        message: '视频已经生成，可以预览或下载。',
        createdAt: '2026-05-06T11:10:51.357486',
      },
    ],
    clips: [
      {
        sceneId: 1,
        sourceUrl: 'https://www.pexels.com/video/amman-city-at-night-18138680/',
        publicUrl: '/downloads/939b4573-187a-406e-9a64-220b8edc1b26_1_pexels_1.mp4',
        caption: '开场建立氛围',
        duration: 6,
        sourceDuration: 14,
      },
      {
        sceneId: 2,
        sourceUrl: 'https://www.pexels.com/video/modern-ui-design-on-digital-tablet-37116270/',
        publicUrl: '/downloads/939b4573-187a-406e-9a64-220b8edc1b26_2_pexels_1.mp4',
        caption: '展示核心功能或主题',
        duration: 8,
        sourceDuration: 14,
      },
      {
        sceneId: 3,
        sourceUrl: 'https://www.pexels.com/video/colleagues-having-a-meeting-7967232/',
        publicUrl: '/downloads/939b4573-187a-406e-9a64-220b8edc1b26_3_pexels_1.mp4',
        caption: '呈现真实使用场景',
        duration: 10,
        sourceDuration: 8,
      },
      {
        sceneId: 4,
        sourceUrl: 'https://www.pexels.com/video/capturing-creative-coming-soon-content-with-smartphone-35576671/',
        publicUrl: '/downloads/939b4573-187a-406e-9a64-220b8edc1b26_4_pexels_1.mp4',
        caption: '收束到品牌和行动号召',
        duration: 6,
        sourceDuration: 7,
      },
    ],
  },
  {
    id: '621f20cc-4323-4a31-8509-98b7492293c4',
    sessionId: '2bc81ffd-b60f-4f68-9c56-e00e2870b636',
    title: '智能剪辑短片',
    status: 'failed',
    progress: 35,
    currentStep: '正在搜索素材',
    currentStepId: 'search_assets',
    createdAt: '2026-05-06T11:04:12.046378',
    updatedAt: '2026-05-06T11:09:33.563000',
    videoUrl: null,
    error: {
      message: 'youtube: 素材搜索失败：ERROR: Unable to download API page: [Errno 54] Connection reset by peer',
    },
    steps: [
      {
        id: 'create_task',
        title: '创建执行任务',
        description: '将确认后的方案投递到后端执行队列。',
        status: 'succeeded',
        progress: 100,
        summary: '任务已成功排入后端队列。',
      },
      {
        id: 'search_assets',
        title: '搜索素材',
        description: '按镜头关键词搜索可用公开视频素材。',
        status: 'failed',
        progress: 50,
        summary: 'Pexels 未被有效利用，fallback 到 YouTube 后卡在反爬超时。',
        error: {
          message: 'youtube:search timed out after 3 retries',
        },
      },
      {
        id: 'prepare_assets',
        title: '准备素材',
        description: '下载素材、修正裁剪窗口并整理渲染输入。',
        status: 'pending',
        progress: 0,
        summary: '等待素材搜索完成。',
      },
      {
        id: 'render_video',
        title: '渲染视频',
        description: '合成字幕、混音并输出 MP4。',
        status: 'pending',
        progress: 0,
        summary: '等待素材准备完成。',
      },
    ],
    events: [
      {
        id: 'event-queued-2',
        eventType: 'job_queued',
        step: 'queued',
        message: '任务已入队，等待执行',
        createdAt: '2026-05-06T11:04:12.051134',
      },
      {
        id: 'event-start-2',
        eventType: 'job_started',
        step: 'searching',
        message: '任务开始执行',
        createdAt: '2026-05-06T11:04:12.245481',
      },
      {
        id: 'event-fail-2',
        eventType: 'job_failed',
        step: 'searching',
        message: 'YouTube 搜索多次超时，任务停止在 search_assets。',
        createdAt: '2026-05-06T11:09:33.563000',
      },
    ],
    clips: [],
  },
  {
    id: 'job-queued-001',
    sessionId: 'session-queued-001',
    title: '新品发布预热视频',
    status: 'running',
    progress: 62,
    currentStep: '正在准备素材',
    currentStepId: 'prepare_assets',
    createdAt: '2026-05-06T13:20:11.000000',
    updatedAt: '2026-05-06T13:22:18.000000',
    videoUrl: null,
    error: null,
    steps: [
      {
        id: 'create_task',
        title: '创建执行任务',
        description: '创建并投递执行任务。',
        status: 'succeeded',
        progress: 100,
        summary: '任务已成功创建。',
      },
      {
        id: 'search_assets',
        title: '搜索素材',
        description: '搜索候选视频素材。',
        status: 'succeeded',
        progress: 100,
        summary: '检索到 9 个候选，已挑选 4 段进入下载。',
      },
      {
        id: 'prepare_assets',
        title: '准备素材',
        description: '下载、裁剪与整理素材。',
        status: 'running',
        progress: 62,
        summary: '正在下载第 3 段镜头，进度稳定。',
      },
      {
        id: 'render_video',
        title: '渲染视频',
        description: '生成最终 MP4。',
        status: 'pending',
        progress: 0,
        summary: '等待素材准备完成。',
      },
    ],
    events: [
      {
        id: 'event-queued-3',
        eventType: 'job_started',
        step: 'searching',
        message: '任务开始执行',
        createdAt: '2026-05-06T13:20:12.000000',
      },
      {
        id: 'event-search-3',
        eventType: 'clips_ready',
        step: 'downloading',
        message: '已完成候选素材挑选',
        createdAt: '2026-05-06T13:21:00.000000',
      },
      {
        id: 'event-prepare-3',
        eventType: 'asset_downloading',
        step: 'downloading',
        message: '正在下载 scene 3',
        createdAt: '2026-05-06T13:22:18.000000',
      },
    ],
    clips: [
      {
        sceneId: 1,
        sourceUrl: 'https://www.pexels.com/video/sample-1/',
        publicUrl: '/downloads/sample-1.mp4',
        caption: '开场动效',
        duration: 5,
        sourceDuration: 9,
      },
      {
        sceneId: 2,
        sourceUrl: 'https://www.pexels.com/video/sample-2/',
        publicUrl: '/downloads/sample-2.mp4',
        caption: '产品特写',
        duration: 7,
        sourceDuration: 12,
      },
    ],
  },
]

export const defaultTaskConceptId = taskConceptDetails[0].id

export const taskConceptSummaries: TaskConceptSummary[] = taskConceptDetails.map((task) => ({
  id: task.id,
  sessionId: task.sessionId,
  title: task.title,
  status: task.status,
  progress: task.progress,
  currentStep: task.currentStep,
  currentStepId: task.currentStepId,
  updatedAt: task.updatedAt,
}))

export const taskConceptDetailById = Object.fromEntries(taskConceptDetails.map((task) => [task.id, task]))
