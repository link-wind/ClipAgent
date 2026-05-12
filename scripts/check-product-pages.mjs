import { readFile } from 'node:fs/promises';
import path from 'node:path';

const repoRoot = process.cwd();

async function readText(relativePath) {
  const filePath = path.join(repoRoot, relativePath);
  return readFile(filePath, 'utf8');
}

async function readFirstAvailable(relativePaths) {
  const missingPaths = [];

  for (const relativePath of relativePaths) {
    try {
      return await readText(relativePath);
    } catch (error) {
      if (error?.code !== 'ENOENT') {
        throw error;
      }
      missingPaths.push(relativePath);
    }
  }

  throw new Error(`未找到可用文件，已检查: ${missingPaths.join(', ')}`);
}

function readDashboardHtml() {
  return readFirstAvailable([
    '.next/server/app/page.html',
    '.next/server/app/index.html',
  ]);
}

function assertIncludes(html, needle, message) {
  if (!html.includes(needle)) {
    throw new Error(message);
  }
}

function assertExcludes(html, needle, message) {
  if (html.includes(needle)) {
    throw new Error(message);
  }
}

async function main() {
  const dashboardHtml = await readDashboardHtml();
  assertIncludes(dashboardHtml, 'ClipForge', 'dashboard 页面缺少产品标题');
  assertIncludes(
    dashboardHtml,
    '对话式短视频制作工作台，把创意 brief 推进成可执行方案、任务流程和最终产出。',
    'dashboard 页面缺少产品定位文案',
  );
  assertIncludes(dashboardHtml, '运行概况', 'dashboard 页面缺少运行概况区块');
  assertIncludes(dashboardHtml, '关键指标', 'dashboard 页面缺少关键指标区块');
  assertIncludes(dashboardHtml, '运行证明', 'dashboard 页面缺少运行证明区块');
  assertIncludes(dashboardHtml, '最近工作', 'dashboard 页面缺少最近工作区块');
  assertExcludes(dashboardHtml, 'Dashboard Home', 'dashboard 页面仍保留旧首页标题');

  const workspaceHtml = await readText('.next/server/app/workspace.html');
  assertIncludes(workspaceHtml, '步骤 1：理解原始需求', 'workspace 页面缺少后端步骤 1 标题');
  assertIncludes(workspaceHtml, '步骤 2：提炼目标与限制', 'workspace 页面缺少后端步骤 2 标题');
  assertIncludes(workspaceHtml, '步骤 3：生成多个方案方向', 'workspace 页面缺少后端步骤 3 标题');
  assertIncludes(workspaceHtml, '步骤 4：输出最终执行方案', 'workspace 页面缺少后端步骤 4 标题');
  assertIncludes(workspaceHtml, '方案方向', 'workspace 页面缺少方案方向区块标题');
  assertIncludes(workspaceHtml, '等待后端返回方案方向。', 'workspace 页面缺少方案方向空态文案');
  assertIncludes(workspaceHtml, '确认方案并生成任务', 'workspace 页面缺少确认方案主动作');
  assertIncludes(workspaceHtml, '方案工作区', 'workspace 页面缺少主工作区 aria 标签');
  assertIncludes(workspaceHtml, '描述你想完成的视频', 'workspace 页面缺少空态标题');
  assertIncludes(workspaceHtml, '底部输入区用于继续补充信息', 'workspace 页面缺少输入区说明');

  const tasksHtml = await readText('.next/server/app/tasks.html');
  assertIncludes(tasksHtml, '任务控制台', 'tasks 页面缺少控制台标题');
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '搜索任务', 'tasks 页面缺少搜索输入');
  assertIncludes(tasksHtml, '可管理任务列表', 'tasks 页面缺少 B1 列表标题');
  assertIncludes(tasksHtml, '查看已选', 'tasks 页面缺少 B1 已选操作入口');
  assertIncludes(tasksHtml, '列表 + 弹窗详情', 'tasks 页面缺少 B1 布局说明');
  assertIncludes(tasksHtml, '批量操作将在后续阶段开放', 'tasks 页面缺少诚实的批量操作提示');
  assertIncludes(tasksHtml, '失败优先关注', 'tasks 页面缺少运营摘要标签');
  assertIncludes(tasksHtml, '结果直达', 'tasks 页面缺少结果摘要标签');

  const settingsHtml = await readText('.next/server/app/settings.html');
  assertIncludes(settingsHtml, '运行设置', 'settings 页面缺少运行设置标题');
  assertIncludes(settingsHtml, 'AI 配置', 'settings 页面缺少 AI 配置分组');
  assertIncludes(settingsHtml, '素材源配置', 'settings 页面缺少素材源配置分组');
  assertIncludes(settingsHtml, 'YouTube 高级配置', 'settings 页面缺少 YouTube 高级配置分组');
  assertIncludes(settingsHtml, '基础设施配置', 'settings 页面缺少基础设施配置分组');
  assertIncludes(settingsHtml, '保存修改', 'settings 页面缺少保存操作');
  assertIncludes(settingsHtml, '放弃修改', 'settings 页面缺少放弃操作');

  const tasksConceptIndexHtml = await readText('.next/server/app/tasks/concepts.html');
  assertIncludes(tasksConceptIndexHtml, '任务页三种静态参考方案', 'tasks concepts 索引页缺少页面标题');
  assertIncludes(tasksConceptIndexHtml, 'B1 列表 + 弹窗详情', 'tasks concepts 索引页缺少 B1 入口');
  assertIncludes(tasksConceptIndexHtml, 'B2 列表 + 右侧详情面板', 'tasks concepts 索引页缺少 B2 入口');
  assertIncludes(tasksConceptIndexHtml, 'B3 独立详情页', 'tasks concepts 索引页缺少 B3 入口');

  const b1Html = await readText('.next/server/app/tasks/concepts/b1.html');
  assertIncludes(b1Html, '列表 + 弹窗详情', 'B1 concept 页面缺少布局标题');
  assertIncludes(b1Html, 'Modal 任务详情', 'B1 concept 页面缺少弹窗详情标题');

  const b2Html = await readText('.next/server/app/tasks/concepts/b2.html');
  assertIncludes(b2Html, '列表 + 右侧详情面板', 'B2 concept 页面缺少布局标题');
  assertIncludes(b2Html, '任务控制台', 'B2 concept 页面缺少控制台说明');

  const b3Html = await readText('.next/server/app/tasks/concepts/b3.html');
  assertIncludes(b3Html, '独立详情页', 'B3 concept 页面缺少布局标题');
  assertIncludes(b3Html, '返回任务列表', 'B3 concept 页面缺少返回列表入口');

  console.log('product page checks passed');
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
