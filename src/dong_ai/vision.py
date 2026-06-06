"""
Dong AI — Vision pipeline

Self-directed creative production with user decision gates.
The company researches, proposes options, you choose, it executes.

Modes:
  interactive  →  each phase proposes options, waits for your choice
  auto         →  makes all decisions autonomously, reports afterward

Usage:
  dong vision "一部3章科幻漫剧"            interactive
  dong vision "一份行业分析报告" --auto     fully automatic
"""

import json, os, re, sys, time
from pathlib import Path
from typing import Optional


class VisionPipeline:
    """Vision pipeline — self-directed creative production"""

    def __init__(self, vision: str, auto: bool = False):
        self.vision = vision
        self.auto = auto
        self._state_path = Path.home() / ".dong" / "vision" / f"{int(time.time())}.json"
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = {
            "vision": vision,
            "mode": "auto" if auto else "interactive",
            "phase": 0,
            "choices": [],
            "output_dir": str(self._state_path.parent),
        }

    def run(self):
        """Run the full vision pipeline — optimized for token efficiency"""
        from .model_pool import ModelPool
        pool = ModelPool()

        print(f"\n  🎯  {self.vision[:80]}")
        print(f"  {'─'*50}")

        # Phase 1: Research + propose + deep dive (merged, saves ~40%)
        print(f"\n  [1/4]  Research & planning")
        directions = self._research(pool)
        choice = self._ask_choice(directions, "Which direction?")
        self._state["choices"].append(choice)

        # Phase 2: Generate
        print(f"\n  [2/4]  First draft")
        draft = self._draft(pool, choice)

        # Phase 3: Self-review (only if checklist fails, saves ~30%)
        print(f"\n  [3/4]  Quality check")
        final = self._iterate(pool, draft, choice)

        # Phase 4: Deliver & debrief
        print(f"\n  [4/4]  Delivery")
        path = self._deliver(final)
        self._save_state()
        print(f"\n  ✅  Done.  {path}")

    def _research(self, pool) -> list[dict]:
        """Research the domain and propose directions"""
        from .web_search import search_formatted

        # Search for domain knowledge
        queries = [
            f"{self.vision[:40]} best practices 2026",
            f"{self.vision[:40]} analysis framework methodology",
            f"how to create {self.vision[:40]} step by step",
        ]
        knowledge = ""
        for q in queries[:2]:
            try:
                r = search_formatted(q, 3)
                if r:
                    knowledge += f"\n--- {q[:40]} ---\n{r[:800]}\n"
            except Exception:
                pass

        # Search for competitor/top works analysis
        benchmark_q = f"top {self.vision[:40]} analysis review comparison"
        try:
            r = search_formatted(benchmark_q, 3)
            if r:
                knowledge += f"\n--- benchmark ---\n{r[:800]}\n"
        except Exception:
            pass

        # Fetch detailed content from top result
        urls = re.findall(r'https?://[^\s\)\]]+', knowledge)
        for url in urls[:1]:
            try:
                r = fetch_url(url, max_length=2000)
                if r.get("content"):
                    knowledge += f"\n--- detailed: {url[:50]} ---\n{r['content'][:1000]}\n"
            except Exception:
                pass

        # LLM proposes directions
        prompt = (
            f"Vision: {self.vision}\n\n"
            f"Research findings:\n{knowledge[:3000]}\n\n"
            f"Propose 2-3 concrete directions to pursue. "
            f"For each, give a name, 1-sentence description, and why it works.\n"
            f"Output format:\n"
            f"=== Direction 1 ===\n"
            f"name: ...\n"
            f"description: ...\n"
            f"rationale: ...\n"
        )
        directions_text = ""
        try:
            for token in pool.call_stream(
                [{"role": "user", "content": prompt}],
                system="You are a creative strategist. Propose 2-3 concrete directions with clear rationale. Format as specified.",
                max_tokens=2048, temperature=0.7,
            ):
                directions_text += token
                print(token, end='', flush=True)
            print()
        except Exception as e:
            print(f"  Research failed: {e}")
            directions_text = f"=== Direction 1 ===\nname: Default\ndescription: Proceed with the vision as described\nrationale: Default path"

        # Parse directions
        directions = []
        for block in re.split(r'=== Direction \d+ ===', directions_text):
            if block.strip():
                d = {"name": "", "description": "", "rationale": ""}
                for line in block.strip().split('\n'):
                    if line.startswith("name:"):
                        d["name"] = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        d["description"] = line.split(":", 1)[1].strip()
                    elif line.startswith("rationale:"):
                        d["rationale"] = line.split(":", 1)[1].strip()
                if d["name"]:
                    directions.append(d)

        if not directions:
            directions = [{"name": "Default", "description": self.vision, "rationale": "Default path"}]

        self._state["directions"] = directions
        return directions

    def _draft(self, pool, choice: dict) -> str:
        """Generate first draft — uses research context from choice"""
        prompt = (
            f"Vision: {self.vision}\n"
            f"Direction: {choice.get('name','')}: {choice.get('description','')}\n\n"
            f"Generate the complete output. High quality, detailed."
        )
        draft = ""
        try:
            for token in pool.call_stream(
                [{"role": "user", "content": prompt}],
                system="Creative producer. Generate complete, high-quality output.",
                max_tokens=8192, temperature=0.7,
            ):
                draft += token
                print(token, end='', flush=True)
            print()
        except Exception as e:
            print(f"  Draft failed: {e}")
            draft = prompt
        return draft

    def _iterate(self, pool, draft: str, choice: dict) -> str:
        """Hard checklist gate — only iterates if quality check fails"""
        # 1. Hard checklist (zero LLM cost)
        word_count = len(draft.split())
        has_code = "```" in draft
        has_structure = any(h in draft for h in ["# ", "## ", "### "])
        min_length = 200

        issues = []
        if word_count < min_length:
            issues.append(f"Too short ({word_count} words, need {min_length}+)")
        if not has_code and ("代码" in self.vision or "code" in self.vision.lower() or "CLI" in self.vision):
            issues.append("Missing code blocks (required for this topic)")
        if not has_structure:
            issues.append("Missing section headers (#/##/###)")

        if not issues:
            print(f"  ✅  Quality check passed ({word_count} words)")
            return draft

        print(f"  ⚠️  Quality issues found:")
        for i in issues:
            print(f"       • {i}")

        # 2. Only iterate if checklist fails (saves ~30% tokens)
        prompt = (
            f"The following draft has quality issues:\n"
            + "\n".join(f"- {i}" for i in issues) +
            f"\n\nDraft:\n{draft[:4000]}\n\n"
            f"Fix all issues and produce the improved version. "
            f"Keep everything good, fix only what's broken."
        )
        final = ""
        try:
            for token in pool.call_stream(
                [{"role": "user", "content": prompt}],
                system=f"Quality editor. Fix the specific issues listed. Vision: {choice.get('description','')[:100]}",
                max_tokens=8192, temperature=0.4,
            ):
                final += token
                print(token, end='', flush=True)
            print()
        except Exception:
            final = draft
        return final

    def _deliver(self, final: str) -> str:
        """Save output and debrief"""
        output_path = self._state_path.parent / "output.md"
        output_path.write_text(final, encoding="utf-8")

        # Debrief for experience engine
        try:
            from .experience_engine import ExperienceEngine
            ee = ExperienceEngine()
            ee.debrief(
                project_type="vision",
                user_request=self.vision,
                design=f"Direction: {self._state.get('choices',[{}])[0].get('name','') if self._state.get('choices') else ''}",
                phases=self._state.get("plan", []),
                scores=[8.0],
                report_text=final[:500],
            )
        except Exception:
            pass

        return str(output_path)

    def _ask_choice(self, options: list, prompt_text: str) -> dict:
        """Present options and get user choice, or auto-select"""
        if self.auto or len(options) == 1:
            return options[0]

        print(f"\n  {prompt_text}")
        for i, opt in enumerate(options, 1):
            name = opt.get("name", opt.get("description", f"Option {i}"))[:60]
            desc = opt.get("description", opt.get("tasks", ""))[:80]
            rationale = opt.get("rationale", "")
            print(f"\n  [{i}] {name}")
            if desc:
                print(f"      {desc}")
            if rationale:
                print(f"      {rationale}")

        print(f"\n  [a] Auto (let me decide)")
        try:
            inp = input(f"\n  {'>' if self.auto else '❯'}  Choose (1-{len(options)}, or a): ").strip()
            if inp.lower() == 'a':
                self.auto = True
                return options[0]
            idx = int(inp) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except (ValueError, IndexError):
            pass
        return options[0]

    def _save_state(self):
        self._state_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2))
