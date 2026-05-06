import ProductShell from '@/components/layout/ProductShell'
import { ConceptIndexCard, ConceptShell } from '@/components/tasks/concepts/TaskConceptPrimitives'

export default function TaskConceptIndexPage() {
  return (
    <ProductShell>
      <ConceptShell
        variant="Index"
        title="任务页三种静态参考方案"
        description="这三个页面都使用同一套 mock 任务数据，只用来比较信息结构、视觉密度和任务排查效率，不接真实 API。"
      >
        <section className="grid gap-4 lg:grid-cols-3">
          <ConceptIndexCard
            href="/tasks/concepts/b1"
            title="B1 列表 + 弹窗详情"
            description="保留当前任务列表页节奏，把详情做成更成熟的弹窗结构。"
            notes={['改动最小', '迁移成本低', '频繁排查时会反复开合弹窗']}
          />
          <ConceptIndexCard
            href="/tasks/concepts/b2"
            title="B2 列表 + 右侧详情面板"
            description="把 /tasks 做成真正的任务控制台，左边扫列表，右边常驻看详情。"
            notes={['最适合联调排查', '列表和详情可同时看', '桌面端体验最好']}
          />
          <ConceptIndexCard
            href="/tasks/concepts/b3"
            title="B3 独立详情页"
            description="把详情提升为单独页面，给任务日志、产物、重试操作留更大的成长空间。"
            notes={['扩展性最好', '路由更清晰', '这一阶段范围会稍大']}
          />
        </section>
      </ConceptShell>
    </ProductShell>
  )
}
