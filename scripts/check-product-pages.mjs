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
  assertIncludes(tasksHtml, '当前阶段', 'tasks 页面缺少当前阶段列');
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '批量操作', 'tasks 页面缺少批量操作入口');
  assertExcludes(tasksHtml, 'Modal 任务详情', 'tasks 页面仍保留常驻详情说明区');

  console.log('product page checks passed');
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
