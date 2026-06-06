# Dong AI Company — 架构文档

## 系统架构

```
┌────────────────────────────────────────────────────────────┐
│                   用户层                                     │
│  dong chat    dong run    dong serve   第三方 API 客户端     │
└──────────────────────┬─────────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────────┐
│                   编排层                                     │
│  ┌──────────┐  ┌────────────┐  ┌─────────────────────────┐ │
│  │   CEO    │  │ WorkerPool │  │     CLI / TUI / API      │ │
│  │ 协调器   │  │ 工人调度    │  │    命令分发/显示/路由     │ │
│  └────┬─────┘  └──────┬─────┘  └─────────────────────────┘ │
└───────┼───────────────┼────────────────────────────────────┘
        │               │
┌───────▼───────────────▼────────────────────────────────────┐
│                   引擎层                                     │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │ ModelPool  │  │ LLMClient  │  │   DesignEngine       │  │
│  │ 20+Provider │  │ HTTP/SSE   │  │   红蓝辩论/需求挖掘   │  │
│  │ 自动failover│  │ 统一接口   │  │   评分/提取           │  │
│  └────────────┘  └────────────┘  └──────────────────────┘  │
└────────────────────────────────────────────────────────────┘
        │
┌───────▼────────────────────────────────────────────────────┐
│                   存储层                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Memory   │  │ Session  │  │ Project  │  │  Graph    │  │
│  │ Fact KV  │  │ 会话历史  │  │ 决策/模块 │  │ 符号/依赖  │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
└────────────────────────────────────────────────────────────┘
```

## 核心模块 · Core Modules

### CEO (`ceo.py`)
项目全流程协调器。接收用户需求，驱动 DesignEngine → WorkerPool → BoardReview 全流程。

```
CEO.run("开发配置系统")
  │
  ├─ 加载相关技能 → 注入上下文
  ├─ DesignEngine.design() → 红蓝辩论 + 需求清单
  ├─ _make_plan() → 拆模块
  ├─ _split_phases() → 按依赖分组
  │
  ├─ for each phase:
  │   ├─ _execute_phase() → WorkerPool 执行
  │   ├─ _board_review() → 董事会评分
  │   ├─ 需求覆盖率检查 → 未覆盖扣分
  │   └─ 评分 < 6.0 → 🚫 终止
  │
  ├─ _generate_report() → 完整报告
  └─ 清理 checkpoint
```

### WorkerPool (`worker.py`)
动态工人调度引擎。CEO 根据任务用 LLM 生成角色卡，工人并行执行。

```
assign_task(task, design)
  │
  ├─ _get_graph_context() → 查询图记忆注入上下文
  ├─ _generate_workers() → LLM 动态生成员工
  │
  ├─ 并行执行:
  │   ├─ _worker_code_impl → 写代码
  │   ├─ _worker_test_impl → 写测试
  │   ├─ _worker_review_impl → 审查
  │   └─ _worker_general_impl → 通用
  │
  ├─ _cross_review() → 员工互相审查
  ├─ _run_real_tests() → 跑 pytest
  └─ _index_task_output() → 写入图记忆
```

### ModelPool (`model_pool.py`)
Provider 配置发现 + 自动 failover。

```
call(messages)
  │
  ├─ available() → 按 mode 排序 provider
  ├─ 遍历 provider → 创建 LLMClient
  │   ├─ 成功 → 返回结果 + 记录 usage
  │   └─ 失败 → 打印错误 → 下一个
  └─ 全部失败 → raise RuntimeError
```

### 存储 (`datastore.py`)
统一 SQLite 存储层。6 个 Repository：

- **MemoryRepository**: Fact KV，CEOMemory 的持久化
- **SessionRepository**: 会话消息和摘要
- **ProjectRepository**: 设计决策、模块状态、经验教训
- **LoreRepository**: 世界观设定（写作场景）
- **GraphRepository**: 代码符号、依赖关系、需求追溯
- **LogRepository**: 结构化日志

## 数据流

```
用户输入
  │
  ▼
CEO 分析 → 相关技能注入 → DesignEngine(红蓝辩论)
  │
  ▼
设计方案 + 需求清单
  │
  ▼
拆模块 → 按依赖排序 → 分阶段
  │
  ▼
每个阶段:
  ├─ WorkerPool 并行执行
  ├─ 产出文件 → 图记忆索引
  ├─ 交叉审查
  ├─ 真实跑测试
  ├─ 董事会评分
  ├─ 需求覆盖率检查 → 扣分
  └─ 评分≥6.0 → 进入下一阶段
  │
  ▼
最终报告
```

## 图记忆

图记忆不是"存档"，是**运行时上下文引擎**。

```
保存:
  任务完成后 → 文件路径/符号签名/接口/教训 → codegraph + code_deps 表

查询:
  新任务开始前 → 提取任务关键词 → 在 codegraph 表 LIKE 搜索 → 格式化注入 prompt

价值:
  精确签名(load_config(path:str)→dict) 而非模糊描述("做了配置加载")
  依赖关系(YAMLConfig→Config[inherits]) 而非平铺列表
  跨阶段追溯(阶段2的代码 → 阶段3的工人能查到)
```

## 三把锁架构

```
设计锁: 设计方案 → LLM 提取需求清单(R1,R2,R3...)
  │
  ▼
阶段门: 每个阶段完成 → 董事会评分 → 覆盖率检查 → 评分≥6.0?
  │                                            │
  │                            是 ← 放行下一阶段 否 → 🚫 终止
  │
  ▼
追溯锁: 图记忆记录每项需求的满足状态 → CEO 随时可查 "谁覆盖了什么"
```
