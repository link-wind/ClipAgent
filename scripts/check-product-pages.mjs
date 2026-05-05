import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

const repoRoot = process.cwd();

async function readText(relativePath) {
  const filePath = path.join(repoRoot, relativePath);
  return readFile(filePath, 'utf8');
}

async function readWorkspaceBundleText() {
  const bundleDir = path.join(repoRoot, '.next/static/chunks/app/workspace');
  const entries = await readdir(bundleDir, { withFileTypes: true });
  const bundleFiles = entries.filter((entry) => entry.isFile() && entry.name.endsWith('.js')).map((entry) => entry.name);
  const texts = await Promise.all(bundleFiles.map((fileName) => readText(path.join('.next/static/chunks/app/workspace', fileName))));
  return texts.join('\n');
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
  const workspaceHtml = await readText('.next/server/app/workspace.html');
  assertIncludes(workspaceHtml, '步骤 1：理解原始需求', 'workspace 页面缺少后端步骤 1 标题');
  assertIncludes(workspaceHtml, '步骤 2：提炼目标与限制', 'workspace 页面缺少后端步骤 2 标题');
  assertIncludes(workspaceHtml, '步骤 3：生成多个方案方向', 'workspace 页面缺少后端步骤 3 标题');
  assertIncludes(workspaceHtml, '步骤 4：输出最终执行方案', 'workspace 页面缺少后端步骤 4 标题');
  assertIncludes(workspaceHtml, '确认方案并生成任务', 'workspace 页面缺少确认方案主动作');
  const workspaceBundleText = await readWorkspaceBundleText();

  assertIncludes(workspaceBundleText, '后端返回的方案方向卡片', 'workspace bundle 缺少后端方案方向展示文案');
  assertIncludes(workspaceBundleText, '检索方向：', 'workspace bundle 缺少后端方案方向检索字段');
  assertIncludes(workspaceBundleText, '关键词：', 'workspace bundle 缺少后端方案方向关键词字段');
  assertIncludes(workspaceBundleText, 'optionPreviewCard', 'workspace bundle 缺少方案方向卡片结构');

  const tasksHtml = await readText('.next/server/app/tasks.html');
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '批量操作', 'tasks 页面缺少批量操作入口');
  assertExcludes(tasksHtml, 'Modal 任务详情', 'tasks 页面仍保留常驻详情说明区');

  console.log('product page checks passed');
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
