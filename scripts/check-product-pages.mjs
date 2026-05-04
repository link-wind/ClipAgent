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
  assertIncludes(workspaceHtml, '方案方向', 'workspace 页面缺少方案方向区块');
  assertIncludes(workspaceHtml, '最终执行方案', 'workspace 页面缺少最终执行方案区块');
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
