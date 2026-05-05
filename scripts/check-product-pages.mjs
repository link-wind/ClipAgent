const baseUrl = process.env.CHECK_BASE_URL ?? 'http://127.0.0.1:3000';

async function fetchHtml(path) {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}: ${response.status} ${response.statusText}`);
  }
  return response.text();
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
  const workspaceHtml = await fetchHtml('/workspace');
  assertIncludes(workspaceHtml, '步骤 1：理解原始需求', 'workspace 页面缺少后端步骤 1 标题');
  assertIncludes(workspaceHtml, '步骤 2：提炼目标与限制', 'workspace 页面缺少后端步骤 2 标题');
  assertIncludes(workspaceHtml, '步骤 3：生成多个方案方向', 'workspace 页面缺少后端步骤 3 标题');
  assertIncludes(workspaceHtml, '步骤 4：输出最终执行方案', 'workspace 页面缺少后端步骤 4 标题');
  assertIncludes(workspaceHtml, '确认方案并生成任务', 'workspace 页面缺少确认方案主动作');

  const tasksHtml = await fetchHtml('/tasks');
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '批量操作', 'tasks 页面缺少批量操作入口');
  assertExcludes(tasksHtml, 'Modal 任务详情', 'tasks 页面仍保留常驻详情说明区');

  console.log('product page checks passed');
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
