"""Dong AI Company — 多智能体 AI 公司框架

一键安装:
  pip install dong-ai

快速开始:
  dong chat          # 交互式 TUI
  dong run "需求"    # 一键项目执行
  dong serve         # API 服务
  dong detect        # 检测可用模型
"""

from __future__ import annotations

__version__ = "0.2.1"

from .ceo import CEO
from .llm import LLMConfig, LLMResponse, OpenAICompatibleClient, create_client
from .datastore import Datastore, get_repo
from .design_engine import DesignEngine
from .display import print_banner, print_assistant, status_line, box_top, box_bottom, sep
from .tool_executor import ToolExecutor
from .ceo_memory import CEOMemory
from .logger import get_logger
from .model_pool import ModelPool, get_pool, llm_call, PROVIDERS
from .worker import WorkerPool
from .web_search import search, search_formatted

__all__ = [
    "CEO", "WorkerPool", "ModelPool", "DesignEngine",
    "LLMConfig", "LLMResponse", "OpenAICompatibleClient", "create_client",
    "Datastore", "get_repo", "CEOMemory", "ToolExecutor",
    "print_banner", "print_assistant", "status_line", "box_top", "box_bottom", "sep",
    "get_logger", "get_pool", "llm_call", "PROVIDERS",
    "search", "search_formatted",
]
