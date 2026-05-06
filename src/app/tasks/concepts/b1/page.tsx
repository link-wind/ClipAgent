import ProductShell from '@/components/layout/ProductShell'
import { ConceptShell, TaskConceptModalPage } from '@/components/tasks/concepts/TaskConceptPrimitives'
import { defaultTaskConceptId, taskConceptDetailById, taskConceptSummaries } from '@/components/tasks/concepts/mockTaskConceptData'

export default function TaskConceptB1Page() {
  return (
    <ProductShell>
      <ConceptShell
        variant="B1"
        title="列表 + 弹窗详情"
        description="这版延续现有 /tasks 的主形态，把任务列表保留在页面主层，详情收进一个更完整、更像工作流工具的弹窗。"
      >
        <TaskConceptModalPage tasks={taskConceptSummaries} initialTask={taskConceptDetailById[defaultTaskConceptId]} />
      </ConceptShell>
    </ProductShell>
  )
}
