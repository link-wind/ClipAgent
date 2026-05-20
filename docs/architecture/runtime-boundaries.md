# Runtime Boundaries

## 目标

当前运行时边界的目标是把 agent 运行链路固定在 `app / runtime / domain / infrastructure / compat` 五层内，避免新的实现继续堆回 legacy service 目录，同时为后续 RAG、skill、MCP 扩展预留稳定落点。

## 边界职责

### `backend/app`

- 承载面向用例的应用服务与编排入口。
- 负责 session、planning、execution、knowledge、skills、tools 等业务流程。
- 可以组合 domain contract、runtime contract、repository 和 infrastructure adapter。
- 不负责 HTTP、Celery、数据库模型定义或第三方 SDK 细节。

### `backend/runtime`

- 承载 agent runtime 级别的协作协议与组合件。
- 当前包括 `AgentRuntime`、`ContextEngine`、`SkillEngine`、`ToolGateway`、`TraceRecorder`。
- 负责把 app service 组织成运行时入口，但不承载具体业务规则和 provider 实现。
- 可以依赖 `backend.app` 暴露的服务、`backend.domain` 契约，以及最小必要的 trace / context contract。

### `backend/domain`

- 承载稳定业务契约、值对象和跨流程共享的数据结构。
- 关注“是什么”，不关注“怎么调接口”“怎么落库”。
- 不依赖 app、runtime、infrastructure、compat。

### `backend/infrastructure`

- 承载外部系统适配器和实现细节。
- 包括 AI、config、media、tools、vector 等目录。
- 负责数据库外部依赖、LLM / 媒体 / MCP / 向量检索等接入实现。
- 可以依赖 domain contract，但不反向驱动 app 和 runtime 的业务编排。

### `backend/compat`

- 只保留必须继续兼容的收口层。
- 这里的职责是托住历史调用面，而不是承载新实现。
- frozen compat surface 当前为 0；如未来确需新增 compat 入口，必须先更新 architecture 文档和 guard，再引入最小范围白名单。

## 允许依赖方向

推荐依赖方向如下：

`api / workers -> app -> domain`

`runtime -> app + domain`

`app -> domain + infrastructure`

`infrastructure -> domain`

`compat -> app | runtime | infrastructure`

额外约束：

- `domain` 不能反向依赖其它层。
- `app` 不直接依赖 HTTP route、Celery task entrypoint 或历史兼容入口。
- `runtime` 负责组合，不应变成新的业务实现堆积层。
- `infrastructure` 不回流业务编排到上层。
- `compat` 不新增推荐实现目录，只做临时兼容收口。

## 后续扩展推荐落点

### RAG

- 业务入口放在 `backend/app/knowledge`。
- 检索与知识契约放在 `backend/domain/knowledge`。
- 向量索引、存储、embedding、外部知识源适配器放在 `backend/infrastructure/vector` 或相邻 infrastructure 子目录。
- runtime 只消费整理后的 context contract，不直接持有检索实现。

### Skill

- skill contract 与选择结果放在 `backend/domain/skills`。
- registry、selection、planner 侧编排放在 `backend/app/skills`。
- 内置 skill handler 放在 `backend/skills/builtin`，作为被 app / runtime 调用的能力包。
- `SkillEngine` 继续作为 runtime 级协调入口，不承载具体 skill 定义。

### MCP / Tool

- tool contract 放在 `backend/domain/tools`。
- 调度、权限、registry 放在 `backend/app/tools`。
- 本地工具适配器、MCP client / adapter 放在 `backend/infrastructure/tools`。
- `ToolGateway` 只负责 runtime 侧调用门面，不直接实现具体 MCP 协议细节。

## 长期 guard 关注点

- architecture tests 持续校验 zero compat baseline。
- 非 architecture tests 不应重新依赖 legacy service import path。
- 新能力扩展优先落在既有五层边界内，只有确有兼容压力时才经过 `compat` 收口。
