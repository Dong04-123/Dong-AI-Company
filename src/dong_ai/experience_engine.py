"""
Dong AI — 经验引擎 (ExperienceEngine)

让 CEO "越做越会做"的核心模块。
不是模型变聪明了，是提示词变聪明了。

流程:
  项目完成 → debrief()  → 分析得失 → 写入 skill
  新项目   → recall()   → 搜索图记忆 → 注入提示词

经验以 SKILL.md 格式存储，条件标签匹配。
"""

import json, os, re, time, hashlib
from pathlib import Path
from typing import Optional


_LESSONS_DIR = Path.home() / ".dong" / "lessons"
_LESSONS_DIR.mkdir(parents=True, exist_ok=True)


class ExperienceEngine:
    """经验引擎 — 复盘、固化、召回"""

    def __init__(self, llm=None):
        self.llm = llm

    # ═══════════════════════════════════════════════════════════
    # 复盘 → 技能固化
    # ═══════════════════════════════════════════════════════════

    def debrief(self, project_type: str, user_request: str, design: str,
                phases: list, scores: list[float], report_text: str,
                requirements: list = None) -> str:
        """项目完成后复盘，生成经验技能文件"""
        if not scores:
            scores = [0.0]
        avg_score = sum(scores) / len(scores)

        # 用 LLM 分析经验（如果有）
        lessons = self._analyze_lessons(
            project_type, user_request, design, phases, scores, report_text
        ) if self.llm else self._default_lessons(project_type, scores)

        # 提取标签
        tags = self._extract_tags(project_type, user_request, design)

        # 写入 skill 文件
        skill_name = f"lessons-{project_type}-{int(time.time())}"
        content = self._format_skill(
            skill_name, tags, project_type, user_request,
            avg_score, lessons, requirements
        )
        path = _LESSONS_DIR / f"{skill_name}.md"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _analyze_lessons(self, project_type: str, user_request: str,
                         design: str, phases: list, scores: list[float],
                         report_text: str) -> list[dict]:
        """用 LLM 分析项目经验"""
        prompt = (
            f"分析以下项目的经验教训，输出 JSON 数组:\n"
            f"项目类型: {project_type}\n"
            f"需求: {user_request[:300]}\n"
            f"设计摘要: {design[:300]}\n"
            f"阶段数: {len(phases)}\n"
            f"评分数: {scores}\n"
            f"最终报告: {report_text[:500]}\n\n"
            f'输出 JSON: [{{"type":"经验/教训","content":"...","tag":"适用标签"}}] 最多6条'
        )
        try:
            resp = self.llm.chat([{"role": "user", "content": prompt}],
                                 system="项目复盘专家。只输出 JSON 数组。")
            json_match = re.search(r'\[.*?\]', resp.text, re.DOTALL)
            if json_match:
                items = json.loads(json_match.group())
                if isinstance(items, list):
                    return items
        except Exception:
            pass
        return self._default_lessons(project_type, scores)

    def _default_lessons(self, project_type: str, scores: list[float]) -> list[dict]:
        """兜底经验（无 LLM 时使用）"""
        lessons = [
            {"type": "经验", "content": f"完成 {project_type} 类型项目",
             "tag": project_type},
        ]
        if scores and min(scores) < 6.0:
            lessons.append({
                "type": "教训",
                "content": "有阶段评分低于 6.0，注意需求完整度",
                "tag": "quality",
            })
        return lessons

    def _extract_tags(self, project_type: str, user_request: str,
                      design: str) -> list[str]:
        """从项目和需求中提取匹配标签"""
        tags = [project_type, "lessons"]
        # 从需求中提取关键技术词
        tech_keywords = re.findall(r'[a-zA-Z_]\w{2,}', user_request + " " + design)
        common = {'the', 'and', 'for', 'with', 'from', 'that', 'this',
                  'build', 'create', 'make', 'using', 'based', 'project',
                  'system', 'should', 'will', 'need', 'have', 'been', 'also',
                  'api', 'web', 'app', 'tool', 'data', 'file', 'test',
                  'code', 'user', 'new', 'set', 'use', 'way', 'well'}
        tech_tags = [w.lower() for w in tech_keywords
                     if len(w) >= 3 and w.lower() not in common]
        tags.extend(sorted(set(tech_tags))[:6])
        return tags

    def _format_skill(self, name: str, tags: list[str], project_type: str,
                      user_request: str, avg_score: float,
                      lessons: list[dict],
                      requirements: list = None) -> str:
        """格式化为 SKILL.md"""
        req_text = ""
        if requirements:
            req_text = "\n".join(f"  - [{r['id']}] {r['desc'][:80]}"
                                 for r in requirements[:8])

        lessons_text = "\n".join(
            f"- **{l['type']}**: {l['content']}"
            + (f" `#{l['tag']}`" if l.get('tag') and l['tag'] != project_type else "")
            for l in lessons
        )

        return (
            "---\n"
            f"name: {name}\n"
            f"tags: [{', '.join(tags)}]\n"
            f"created: {time.strftime('%Y-%m-%d')}\n"
            "---\n"
            "\n"
            f"## 项目复盘\n"
            f"类型: {project_type}\n"
            f"评分: {avg_score:.1f}\n"
            f"需求: {user_request[:100]}\n"
            "\n"
            f"## 经验\n"
            f"{lessons_text}\n"
            "\n"
            + (f"## 需求清单\n{req_text}\n" if req_text else "")
        )

    # ═══════════════════════════════════════════════════════════
    # 经验召回
    # ═══════════════════════════════════════════════════════════

    def recall(self, user_request: str, project_type: str = None) -> str:
        """新项目启动前召回相关经验，返回注入文本"""
        lessons = self._find_relevant(user_request, project_type)
        if not lessons:
            return ""

        parts = ["\n## 📚 历史经验"]
        for lesson in lessons:
            avg = lesson.get("avg_score", "?")
            parts.append(f"\n### {lesson['project_type']}项目 ({lesson['date']}) 评分{avg}")
            parts.append(lesson["content"][:300])
        return "\n".join(parts)

    def _find_relevant(self, user_request: str,
                       project_type: str = None) -> list[dict]:
        """搜索相关经验文件"""
        results = []
        request_lower = user_request.lower()

        for f in sorted(_LESSONS_DIR.glob("*.md"), reverse=True):
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue

            # 提取元数据
            meta = self._parse_skill_meta(text)
            if not meta:
                continue

            # 评分匹配
            relevance = 0

            # 同类型项目 → 高相关
            if project_type and meta.get("type") == project_type:
                relevance += 5

            # 标签匹配
            tags = meta.get("tags", [])
            for kw in re.findall(r'[a-zA-Z_]\w{2,}', user_request):
                kw = kw.lower()
                if kw in tags:
                    relevance += 2

            # 需求关键词匹配
            req_text = meta.get("request", "")
            req_kws = re.findall(r'[a-zA-Z_]\w{2,}', req_text.lower())
            overlap = len(set(re.findall(r'[a-zA-Z_]\w{2,}', request_lower))
                          & set(req_kws))
            relevance += overlap * 0.5

            if relevance >= 2 or (len(request_lower.split()) <= 3 and relevance >= 1):
                results.append({
                    "project_type": meta.get("type", "?"),
                    "date": meta.get("date", "?"),
                    "avg_score": meta.get("score", "?"),
                    "content": text[:500],
                    "relevance": relevance,
                })

        # 按相关性排序，取最近 3 条
        results.sort(key=lambda x: -x["relevance"])
        return results[:3]

    def _parse_skill_meta(self, text: str) -> dict:
        """从 SKILL.md 提取元数据"""
        meta = {}
        in_frontmatter = False
        for line in text.split("\n"):
            if line.strip() == "---" and not in_frontmatter:
                in_frontmatter = True
                continue
            elif line.strip() == "---" and in_frontmatter:
                in_frontmatter = False
                continue
            if in_frontmatter:
                if line.startswith("tags:"):
                    tags_str = line.split(":", 1)[1].strip()
                    meta["tags"] = re.findall(r'\w+', tags_str)
                elif line.startswith("created:"):
                    meta["date"] = line.split(":", 1)[1].strip()
            else:
                if line.startswith("类型:"):
                    meta["type"] = line.split(":", 1)[1].strip()
                elif line.startswith("评分:"):
                    try:
                        meta["score"] = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith("需求:"):
                    meta["request"] = line.split(":", 1)[1].strip()
        return meta

    # ═══════════════════════════════════════════════════════════
    # 统计
    # ═══════════════════════════════════════════════════════════

    def project_stats(self) -> dict:
        """项目执行统计"""
        files = list(_LESSONS_DIR.glob("*.md"))
        types = {}
        scores = []
        for f in files:
            meta = self._parse_skill_meta(f.read_text())
            t = meta.get("type", "?")
            types[t] = types.get(t, 0) + 1
            if meta.get("score"):
                scores.append(meta["score"])
        return {
            "total_projects": len(files),
            "by_type": types,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "total_lessons": sum(1 for f in files if "lessons-" in f.name),
        }
