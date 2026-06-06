"""
Dong AI — 元认知引擎 (MetacognitionEngine)

三层学习架构，让 AI 公司实现「组织革命」：

  单环 (Single-loop):      做项目 → 复盘 → 下次改进        ✅ ExperienceEngine
  双环 (Double-loop):      复盘复盘本身是否有效              ✅ 本模块
  二重学习 (Deutero):      改进学习方式本身                 ✅ 本模块
  元认知 (Metacognition):  知道自己知道什么、不知道什么       ✅ 本模块

用法:
  from .metacognition import MetacognitionEngine
  meta = MetacognitionEngine(experience_engine, llm)
  
  # 在每次 ExperienceEngine.debrief 之后调用
  meta.meta_debrief(project_type, debrief_path)
  
  # 随时查看组织学习状态
  print(meta.knowledge_map())
"""

import json, os, re, time
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


# ── 数据目录 ──
_META_DIR = Path.home() / ".dong" / "meta"
_META_DIR.mkdir(parents=True, exist_ok=True)

# ── 学习策略注册表 ──
# 不同的复盘/学习方式，可以动态添加
DEFAULT_STRATEGIES = {
    "debrief_full": {
        "name": "完整复盘",
        "description": "用LLM分析项目得失，提取经验教训",
        "applies_to": ["software", "analysis", "audit"],
        "effectiveness": [],
    },
    "debrief_light": {
        "name": "轻量复盘",
        "description": "只用评分和类型生成默认教训",
        "applies_to": ["novel", "game"],
        "effectiveness": [],
    },
    "recall_same_type": {
        "name": "同类型召回",
        "description": "按项目类型匹配历史经验",
        "applies_to": ["all"],
        "effectiveness": [],
    },
    "recall_keyword": {
        "name": "关键词召回",
        "description": "按需求关键词匹配历史经验",
        "applies_to": ["all"],
        "effectiveness": [],
    },
}


@dataclass
class LearningRecord:
    """一次学习行为的完整记录"""
    project_type: str
    strategy: str                     # 使用的学习策略
    debrief_path: str                 # skill 文件路径
    score_before: Optional[float]     # 当前项目评分
    score_after: Optional[float] = None   # 后续项目评分（回填）
    was_recalled: Optional[bool] = None   # 后续项目是否召回了此 skill
    timestamp: float = 0.0


class MetacognitionEngine:
    """元认知引擎 — 双环 + 二重学习 + 组织元认知"""

    def __init__(self, experience_engine=None, llm=None):
        self.ee = experience_engine
        self.llm = llm
        self._records: list[LearningRecord] = []
        self._strategies: dict = dict(DEFAULT_STRATEGIES)
        self._load_state()

    # ═══════════════════════════════════════════════════════════
    # 双环学习: 复盘复盘本身
    # ═══════════════════════════════════════════════════════════

    def meta_debrief(self, project_type: str, debrief_path: str,
                     score: Optional[float] = None,
                     strategy: str = "debrief_full") -> str:
        """双环复盘：记录这次复盘本身的信息，供后续评估"""
        record = LearningRecord(
            project_type=project_type,
            strategy=strategy,
            debrief_path=debrief_path,
            score_before=score,
            timestamp=time.time(),
        )
        self._records.append(record)
        self._save_state()

        # 用 LLM 评估复盘质量（如果有 llm）
        assessment = self._assess_debrief_quality(project_type, debrief_path)

        # 更新策略效果
        self._track_strategy_effectiveness(strategy, project_type)

        return assessment

    def _assess_debrief_quality(self, project_type: str,
                                 debrief_path: str) -> str:
        """评估复盘质量"""
        if not self.llm:
            return ""

        try:
            content = Path(debrief_path).read_text()[:1500]
            resp = self.llm.chat(
                [{"role": "user", "content": (
                    f"评估以下复盘的质量，只输出 JSON：\n\n复盘的 skill:\n{content}\n\n"
                    f"{{\"quality\":0-10,\"actionable\":true/false,\"missing\":\"缺少什么\",\"improvement\":\"怎么改进\"}}"
                )}],
                system="复盘质量评估专家。",
            )
            return resp.text[:300]
        except Exception:
            return ""

    # ═══════════════════════════════════════════════════════════
    # 二重学习: 改进学习方式本身
    # ═══════════════════════════════════════════════════════════

    def track_recall_effectiveness(self, project_type: str,
                                    skill_name: str,
                                    was_helpful: bool) -> None:
        """记录一个 skill 在后续项目中是否真的有帮助"""
        for r in reversed(self._records):
            if r.project_type == project_type and r.was_recalled is None:
                r.was_recalled = was_helpful
                self._save_state()
                break

    def record_followup_score(self, project_type: str, score: float) -> None:
        """记录后续项目的评分（用于判断复盘是否有效）"""
        for r in reversed(self._records):
            if r.project_type == project_type and r.score_after is None:
                r.score_after = score
                self._save_state()
                break

    def evolve_strategy(self) -> Optional[str]:
        """根据历史效果，调整学习策略"""
        if len(self._records) < 3:
            return None

        # 统计各策略效果
        strategy_effect = {}
        for r in self._records:
            if r.strategy not in strategy_effect:
                strategy_effect[r.strategy] = {"count": 0, "improved": 0}
            strategy_effect[r.strategy]["count"] += 1
            if r.score_after and r.score_before:
                if r.score_after > r.score_before:
                    strategy_effect[r.strategy]["improved"] += 1

        # 找最佳策略
        best_strategy = None
        best_rate = 0
        for s, stats in strategy_effect.items():
            if stats["count"] >= 2:
                rate = stats["improved"] / stats["count"]
                if rate > best_rate:
                    best_rate = rate
                    best_strategy = s

        if best_strategy and best_rate > 0.6:
            return f"📈 最佳学习策略: {best_strategy} (改善率 {best_rate:.0%})"

        # 如果现有策略都不好，建议换策略
        if best_rate < 0.3 and self.llm:
            return self._suggest_new_strategy()

        return None

    def _suggest_new_strategy(self) -> str:
        """用 LLM 建议新的学习策略"""
        try:
            recent = self._records[-5:]
            context = "\n".join(
                f"类型:{r.project_type} 策略:{r.strategy} 评分:{r.score_before}→{r.score_after}"
                for r in recent if r.score_after
            )
            resp = self.llm.chat(
                [{"role": "user", "content": (
                    f"以下是我最近的学习记录:\n{context}\n\n"
                    f"当前学习效果不佳，请建议新的复盘/学习策略。直接输出策略描述。"
                )}],
                system="学习策略专家。给出可操作的新策略。",
            )
            return f"💡 建议新策略: {resp.text[:200]}"
        except Exception as e:
            return f"⚠️ 策略建议失败: {e}"

    def _track_strategy_effectiveness(self, strategy: str,
                                       project_type: str) -> None:
        """更新策略效果记录"""
        if strategy in self._strategies:
            self._strategies[strategy]["effectiveness"].append({
                "project_type": project_type,
                "time": time.time(),
            })

    # ═══════════════════════════════════════════════════════════
    # 组织元认知: 知道自己知道什么、不知道什么
    # ═══════════════════════════════════════════════════════════

    def knowledge_map(self) -> str:
        """组织知识地图 — 知道什么、不知道什么、擅长什么"""
        total = len(self._records)
        by_type: dict[str, list[float]] = {}
        improvements = []
        declines = []

        for r in self._records:
            if r.project_type not in by_type:
                by_type[r.project_type] = []
            if r.score_before is not None:
                by_type[r.project_type].append(r.score_before)
            if r.score_before and r.score_after:
                diff = r.score_after - r.score_before
                if diff > 0.5:
                    improvements.append((r.project_type, diff, r.strategy))
                elif diff < -0.5:
                    declines.append((r.project_type, diff, r.strategy))

        # 擅长领域（平均评分最高的）
        strengths = sorted(
            [(t, sum(scores)/len(scores), len(scores))
             for t, scores in by_type.items()],
            key=lambda x: -x[1],
        )

        # 学习策略效果
        strategy_rates = {}
        for r in self._records:
            if r.score_before and r.score_after:
                st = r.strategy
                if st not in strategy_rates:
                    strategy_rates[st] = {"total": 0, "improved": 0}
                strategy_rates[st]["total"] += 1
                if r.score_after > r.score_before:
                    strategy_rates[st]["improved"] += 1

        lines = [
            f"🧠 组织元认知报告",
            f"{'='*50}",
            f"学习总次数: {total}",
            f"",
            f"📊 领域能力:",
        ]

        for t, avg, n in strengths[:5]:
            bar = "█" * int(avg) + "░" * (10 - int(avg))
            lines.append(f"  {t:<15} {bar} {avg:.1f} ({n}次)")

        lines.append(f"\n📈 显著进步 ({len(improvements)} 项):")
        for t, diff, s in improvements[-3:]:
            lines.append(f"  {t:<15} +{diff:.1f} (策略: {s})")

        if declines:
            lines.append(f"\n📉 需要关注 ({len(declines)} 项):")
            for t, diff, s in declines[-3:]:
                lines.append(f"  {t:<15} {diff:.1f} (策略: {s})")

        lines.append(f"\n🔬 学习策略效果:")
        for s, stats in sorted(strategy_rates.items(), key=lambda x: -x[1]["improved"]/x[1]["total"] if x[1]["total"] > 0 else 0):
            rate = stats["improved"] / stats["total"] if stats["total"] > 0 else 0
            bar = "█" * int(rate * 10)
            lines.append(f"  {s:<20} {bar} {stats['improved']}/{stats['total']} ({rate:.0%})")

        # 知识缺口
        known_types = set(by_type.keys())
        all_types = {"software", "novel", "game", "analysis", "audit",
                      "ecommerce", "finance", "marketing"}
        gaps = all_types - known_types
        if gaps:
            lines.append(f"\n❓ 知识缺口 (未涉足的领域):")
            for g in sorted(gaps)[:8]:
                lines.append(f"  · {g}")

        lines.append(f"\n{'='*50}")
        lines.append(f"📋 总结:")
        lines.append(f"  擅长: {strengths[0][0] if strengths else '暂无'}")
        lines.append(f"  需要提升: {declines[0][0] if declines else '暂无'}")
        lines.append(f"  学习策略建议: run dong company evolve")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # 状态持久化
    # ═══════════════════════════════════════════════════════════

    def _save_state(self) -> None:
        state = {
            "records": [
                {
                    "project_type": r.project_type,
                    "strategy": r.strategy,
                    "debrief_path": r.debrief_path,
                    "score_before": r.score_before,
                    "score_after": r.score_after,
                    "was_recalled": r.was_recalled,
                    "timestamp": r.timestamp,
                }
                for r in self._records[-100:]  # 只保留最近100条
            ],
            "strategies": self._strategies,
        }
        (_META_DIR / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2))

    def _load_state(self) -> None:
        path = _META_DIR / "state.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._records = [LearningRecord(**r) for r in data.get("records", [])]
                if "strategies" in data:
                    self._strategies.update(data["strategies"])
            except Exception:
                pass

    def stats(self) -> dict:
        return {
            "total_learning_cycles": len(self._records),
            "strategies_tracked": len(self._strategies),
            "knowledge_gaps": 8,  # estimated
        }
