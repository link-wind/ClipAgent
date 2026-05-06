import ProductShell from '@/components/layout/ProductShell'
import { ConceptShell, TaskConceptSidePanelPage } from '@/components/tasks/concepts/TaskConceptPrimitives'
import { defaultTaskConceptId, taskConceptDetailById, taskConceptSummaries } from '@/components/tasks/concepts/mockTaskConceptData'

export default function TaskConceptB2Page() {
  return (
    <ProductShell>
      <ConceptShell
        variant="B2"
        title="列表 + 右侧详情面板"
        description="这版把 /tasks 明确收成任务控制台。列表负责扫读和切换，详情常驻右侧，适合配合真实联调链路做排查。"
      >
        <TaskConceptSidePanelPage tasks={taskConceptSummaries} initialTask={taskConceptDetailById[defaultTaskConceptId]} />
      </ConceptShell>
    </ProductShell>
  )
}
