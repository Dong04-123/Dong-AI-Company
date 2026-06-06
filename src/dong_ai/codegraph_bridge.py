"""
CodeGraph 桥接 v2 — 用 tree-sitter-analyzer CLI 查询代码结构

CEO 通过这个模块做符号级代码理解。
使用 CLI 接口避免 async API 的复杂性。
"""
from __future__ import annotations

import json
import subprocess
import shlex
from pathlib import Path


class CodeGraphBridge:
    def __init__(self, workspace: str = ".") -> None:
        self.workspace = str(Path(workspace).resolve())
        # 自动查找可用 Python
        import sys as _sys
        self._venv_python = _sys.executable

    def _run_tsa(self, *args: str) -> dict:
        """运行 tree-sitter-analyzer CLI"""
        cmd = [self._venv_python, "-m", "tree_sitter_analyzer"] + list(args)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=self.workspace
            )
            output = result.stdout or result.stderr
            # 尝试解析 JSON
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"text": output[:2000], "raw": output[:500]}
        except subprocess.TimeoutExpired:
            return {"error": "分析超时"}
        except FileNotFoundError:
            return {"error": "tree-sitter-analyzer 未安装"}
        except Exception as e:
            return {"error": str(e)}

    def analyze_file(self, filepath: str) -> dict:
        """分析单个文件：结构、符号、函数"""
        return self._run_tsa("--structure", filepath)

    def get_outline(self, filepath: str) -> list:
        """获取文件大纲"""
        result = self.analyze_file(filepath)
        if "error" in result:
            return [result]
        symbols = result.get("symbols", result.get("functions", result.get("classes", [])))
        if not symbols and "text" in result:
            return [{"name": "文件结构", "detail": result["text"][:500]}]
        return symbols

    def get_summary(self, filepath: str) -> str:
        """获取文件摘要"""
        result = self._run_tsa("--summary", filepath)
        if "error" in result:
            return f"[CodeGraph] {result['error']}"
        if "text" in result:
            return f"[CodeGraph] 文件摘要:\n{result['text'][:1000]}"
        return f"[CodeGraph] 分析了 {filepath}"

    def format_for_llm(self, query_type: str, **kwargs) -> str:
        """把 CodeGraph 结果格式化成 LLM 友好的文本"""
        if query_type == "outline":
            result = self.get_outline(kwargs.get("file", ""))
            parts = [f"📄 {kwargs.get('file', '')}"]
            for r in result[:15]:
                if "error" in r:
                    return f"[CodeGraph] {r['error']}"
                parts.append(f"  · {r.get('name', r.get('kind', '?'))} 行{r.get('line', '?')}")
            return "\n".join(parts)

        elif query_type == "summary":
            return self.get_summary(kwargs.get("file", ""))

        return "[CodeGraph] 未知查询类型"
