---
name: dong-ai-company
description: "您的私人AI公司 — 红蓝辩论/动态工人池/图记忆/董事会评分。将 Hermes 升级为完整的 AI 企业治理系统。"
tags: [ai-agent, multi-agent, orchestration, company, governance]
---

# Dong AI Company

将您的 Hermes Agent 升级为一家完整的 AI 企业。

## 前提条件

```bash
pip install dong-ai
dong setup        # 交互式配置
dong serve        # 启动 API 服务（默认 localhost:8648）
```

## 可用工具

### dong_run
在 Dong AI 中一键执行项目，返回完整报告。

**参数:**
- `request` (必填): 项目需求描述

**用法:**
```
[TOOL_CALL:dong_run] request=帮我开发一个配置系统 [/TOOL_CALL]
```

### dong_chat
与 Dong AI CEO 对话，获取设计方案和决策建议。

**参数:**
- `message` (必填): 对话内容

**用法:**
```
[TOOL_CALL:dong_chat] message=这个架构有什么风险？ [/TOOL_CALL]
```

### dong_analyze
用 Dong AI 的图记忆分析项目代码库。

**参数:**
- `path` (必填): 项目路径

**用法:**
```
[TOOL_CALL:dong_analyze] path=/path/to/project [/TOOL_CALL]
```

## 能力说明

Dong AI Company 提供 Hermes 原生不包含的企业级治理能力：

| 能力 | 说明 |
|------|------|
| 红蓝辩论 | 两个 AI 团队针对设计方案辩论，CEO 择优采纳 |
| 动态工人池 | 每项任务从 160+ 角色池中动态招募员工 |
| 图记忆 | 函数签名/依赖关系持久化，跨阶段精确注入 |
| 董事会评分 | 每个阶段 1-10 评分，低于 6.0 不放行 |
| 需求锁 | 设计阶段产出需求清单，逐条核对覆盖率 |
| 20+ Provider | DeepSeek / OpenAI / Claude / Groq / 本地模型自动切换 |
| 双模式 | API 模式 256K 窗口 / 本地模式 64K 窗口 |
| MCP 客户端 | 发现并调用任何 MCP 服务器工具 |
| 定时任务 | 持久化 Cron 调度器 |
| Webhook | 外部事件触发自动审计 |

## 快速集成

```bash
# 1. 安装 Dong AI
pip install dong-ai

# 2. 运行配置向导
dong setup

# 3. 启动 API 服务（Hermes 通过 API 调用 Dong AI）
dong serve --port 8648

# 4. 在 Hermes 中使用上述工具调用 Dong AI
```

## 学习资源

- GitHub: https://github.com/Dong04-123/Dong-AI-Company
- PyPI: https://pypi.org/project/dong-ai/
- 文档: `dong --help`
