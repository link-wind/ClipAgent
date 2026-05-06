import ProductShell from '@/components/layout/ProductShell'
import { ConceptShell, TaskConceptRouteDetailPage } from '@/components/tasks/concepts/TaskConceptPrimitives'
import { defaultTaskConceptId, taskConceptDetailById, taskConceptSummaries } from '@/components/tasks/concepts/mockTaskConceptData'

export default function TaskConceptB3Page() {
  return (
    <ProductShell>
      <ConceptShell
        variant="B3"
        title="独立详情页"
        description="这版把任务详情提升成独立页面模型。列表和详情拆成两个主视图，更利于后续叠加完整日志、更多动作和更重的产物区。"
      >
        <TaskConceptRouteDetailPage tasks={taskConceptSummaries} initialTask={taskConceptDetailById[defaultTaskConceptId]} />
      </ConceptShell>
    </ProductShell>
  )
}
