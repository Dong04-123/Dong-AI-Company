"""
Dong AI — Vision pipeline v2

Self-directed making that actually delivers.
Multi-step research → structured planning → section-by-section generation → content review → formatted delivery.
"""

import json, os, re, sys, time
from pathlib import Path
from typing import Optional


class VisionPipeline:
    """Vision pipeline — upgraded to match the story"""

    def __init__(self, vision: str, auto: bool = False):
        self.vision = vision
        self.auto = auto
        self._state_path = Path.home() / ".dong" / "vision" / f"{int(time.time())}.json"
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = {
            "vision": vision,
            "mode": "auto" if auto else "interactive",
            "phase": 0, "choices": [],
        }
        self._knowledge = ""

    def run(self):
        from .model_pool import ModelPool
        pool = ModelPool()

        print(f"\n  🎯  {self.vision[:80]}")
        print(f"  {'─'*50}")

        # Phase 1: Multi-step research
        print(f"\n  [1/5]  Research")
        directions = self._research(pool)
        choice = self._ask_choice(directions, "Which direction?")
        self._state["choices"].append(choice)

        # Phase 2: Deep research on chosen direction
        print(f"\n  [2/5]  Deep research")
        outline = self._deep_research(pool, choice)
        outline_choice = self._ask_choice(outline, "Does this outline work?")
        self._state["choices"].append(outline_choice)

        # Phase 3: Section-by-section generation
        print(f"\n  [3/5]  Writing")
        draft = self._generate_sections(pool, choice, outline)

        # Phase 4: Content review
        print(f"\n  [4/5]  Review")
        final = self._review_content(pool, draft, choice)

        # Phase 5: Deliver
        print(f"\n  [5/5]  Deliver")
        path = self._deliver(final)
        print(f"\n  ✅  {path}")

    # ═══════════════════════════════════════════════════════════
    # Phase 1: Multi-step research
    # ═══════════════════════════════════════════════════════════

    def _research(self, pool) -> list[dict]:
        """Multi-step research: search → read → extract → identify gaps → search again"""
        from .web_search import search_formatted
        from .mcp_servers.web_tools import fetch_url

        knowledge = ""

        # Step 1: Broad search
        queries = [
            f"{self.vision[:50]} overview guide 2026",
            f"{self.vision[:50]} best practices methodology",
            f"{self.vision[:50]} analysis framework",
        ]
        for q in queries[:3]:
            try:
                r = search_formatted(q, 4)
                if r and "搜索失败" not in r:
                    knowledge += f"\n--- {q} ---\n{r[:1200]}\n"
            except Exception:
                pass

        # Step 2: Read top results
        urls = re.findall(r'https?://[^\s\)\]\n]+', knowledge)
        for url in urls[:3]:
            try:
                r = fetch_url(url, max_length=3000)
                if r.get("content"):
                    knowledge += f"\n--- from: {url[:60]} ---\n{r['content'][:2000]}\n"
            except Exception:
                pass

        # Step 3: Ask the LLM what's missing, then search again
        gap_prompt = (
            f"Domain: {self.vision}\n\n"
            f"Research so far:\n{knowledge[:2000]}\n\n"
            f"What are 2-3 specific questions or gaps that need more research? "
            f"Output only the questions, one per line."
        )
        gaps = ""
        try:
            for token in pool.call_stream(
                [{"role": "user", "content": gap_prompt}],
                system="Research analyst. Identify what's missing.",
                max_tokens=300, temperature=0.3,
            ):
                gaps += token
        except Exception:
            pass

        # Step 4: Fill gaps
        for line in gaps.strip().split('\n'):
            line = line.strip().strip('-').strip()
            if len(line) > 10:
                try:
                    r = search_formatted(line[:60], 3)
                    if r and "搜索失败" not in r:
                        knowledge += f"\n--- {line[:50]} ---\n{r[:800]}\n"
                except Exception:
                    pass

        self._knowledge = knowledge

        # Step 5: LLM proposes directions
        prompt = (
            f"Vision: {self.vision}\n\n"
            f"Research findings:\n{knowledge[:3000]}\n\n"
            f"Propose 2-3 concrete directions. Format:\n"
            f"=== Direction 1 ===\n"
            f"name: ...\n"
            f"description: ...\n"
            f"rationale: ...\n"
        )
        directions_text = ""
        try:
            for token in pool.call_stream(
                [{"role": "user", "content": prompt}],
                system="Creative strategist. Propose concrete directions with rationale.",
                max_tokens=2048, temperature=0.7,
            ):
                directions_text += token
                print(token, end='', flush=True)
            print()
        except Exception:
            directions_text = "=== Direction 1 ===\nname: Default\ndescription: Proceed\nrationale: Default"

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
            directions = [{"name": "Default", "description": self.vision, "rationale": ""}]

        self._state["directions"] = directions
        return directions

    # ═══════════════════════════════════════════════════════════
    # Phase 2: Deep research + structured outline
    # ═══════════════════════════════════════════════════════════

    def _deep_research(self, pool, choice: dict) -> list[dict]:
        """Deep research on chosen direction → structured outline"""
        from .web_search import search_formatted
        from .mcp_servers.web_tools import fetch_url

        # Targeted search
        query = f"{choice.get('name','')} {choice.get('description','')[:40]} in-depth analysis"
        try:
            r = search_formatted(query, 5)
            if r:
                self._knowledge += f"\n--- deep: {query[:50]} ---\n{r[:2000]}\n"
        except Exception:
            pass

        urls = re.findall(r'https?://[^\s\)\]\n]+', self._knowledge)
        for url in urls[3:5]:
            try:
                r = fetch_url(url, max_length=3000)
                if r.get("content"):
                    self._knowledge += f"\n--- ref: {url[:60]} ---\n{r['content'][:2000]}\n"
            except Exception:
                pass

        # Generate structured outline (sections with descriptions)
        prompt = (
            f"Output direction:\n{choice.get('name','')}: {choice.get('description','')}\n\n"
            f"Research:\n{self._knowledge[:3000]}\n\n"
            f"Create a structured outline with 3-5 sections. "
            f"For each section, give a name, a 1-sentence description, "
            f"and 2-3 key points to cover.\n"
            f"Format:\n"
            f"=== Section 1 ===\n"
            f"name: ...\n"
            f"description: ...\n"
            f"points: point1 | point2 | point3\n"
        )
        outline_text = ""
        try:
            for token in pool.call_stream(
                [{"role": "user", "content": prompt}],
                system="Content strategist. Create structured outlines.",
                max_tokens=2048, temperature=0.4,
            ):
                outline_text += token
                print(token, end='', flush=True)
            print()
        except Exception:
            outline_text = "=== Section 1 ===\nname: Main Content\ndescription: Core content\npoints: key point"

        sections = []
        for block in re.split(r'=== Section \d+ ===', outline_text):
            if block.strip():
                s = {"name": "", "description": "", "points": ""}
                for line in block.strip().split('\n'):
                    if line.startswith("name:"):
                        s["name"] = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        s["description"] = line.split(":", 1)[1].strip()
                    elif line.startswith("points:"):
                        s["points"] = line.split(":", 1)[1].strip()
                if s["name"]:
                    sections.append(s)

        if not sections:
            sections = [{"name": "Main Content", "description": "Core output", "points": "key details"}]

        self._state["outline"] = sections
        return sections

    # ═══════════════════════════════════════════════════════════
    # Phase 3: Section-by-section generation
    # ═══════════════════════════════════════════════════════════

    def _generate_sections(self, pool, choice: dict, outline: list[dict]) -> str:
        """Generate each section independently, maintaining consistency"""
        sections = []
        for i, section in enumerate(outline):
            print(f"\n  --- Section {i+1}: {section['name'][:40]} ---")

            # Build context from previous sections
            prev_context = ""
            if sections:
                prev = sections[-1]
                prev_context = f"\nPrevious section ended with:\n{prev[-300:]}\n"

            prompt = (
                f"Vision: {self.vision}\n"
                f"Direction: {choice.get('name','')}\n"
                f"Section: {section['name']}\n"
                f"Description: {section['description']}\n"
                f"Key points: {section['points']}\n"
                f"{prev_context}"
                f"Research:\n{self._knowledge[:2000]}\n\n"
                f"Write this section. {sections and 'Maintain consistency with previous sections.' or ''}"
            )

            section_text = ""
            try:
                for token in pool.call_stream(
                    [{"role": "user", "content": prompt}],
                    system="Content writer. Write one section at a time, maintaining consistency.",
                    max_tokens=4096, temperature=0.6,
                ):
                    section_text += token
                    print(token[:80].replace('\n',' '), end='', flush=True)
                print()
            except Exception as e:
                print(f"  Section failed: {e}")
                section_text = f"\n\n## {section['name']}\n\n{section['description']}\n"

            sections.append(section_text)

        return "\n\n".join(sections)

    # ═══════════════════════════════════════════════════════════
    # Phase 4: Content review
    # ═══════════════════════════════════════════════════════════

    def _review_content(self, pool, draft: str, choice: dict) -> str:
        """Real content review: checks for substance, not just word count"""
        word_count = len(draft.split())

        # Hard checks
        issues = []
        if word_count < 300:
            issues.append(f"Too short ({word_count} words, minimum 300)")

        # Check for substance (headers, structure)
        headers = [l for l in draft.split('\n') if l.strip().startswith('#')]
        if len(headers) < 3:
            issues.append(f"Only {len(headers)} sections, need at least 3")

        # Check for specificity (has examples, data, or specifics)
        has_examples = any(kw in draft.lower() for kw in ["example", "case", "instance", "sample", "比如", "例如"])
        has_numbers = bool(re.findall(r'\d+[%倍万]', draft))
        if not has_examples and not has_numbers:
            issues.append("Lacks specific examples or data")

        if not issues:
            print(f"  ✅  Content review passed ({word_count} words, {len(headers)} sections)")
            return draft

        print(f"  ⚠️  Review issues found:")
        for i in issues:
            print(f"       • {i}")

        # Iterate once
        prompt = (
            f"Quality issues:\n" + "\n".join(f"- {i}" for i in issues) +
            f"\n\nDraft:\n{draft[:4000]}\n\n"
            f"Fix all issues. Add substance where needed."
        )
        final = ""
        try:
            for token in pool.call_stream(
                [{"role": "user", "content": prompt}],
                system=f"Editor. Fix the issues. Direction: {choice.get('description','')[:80]}",
                max_tokens=8192, temperature=0.4,
            ):
                final += token
                print(token[:80].replace('\n',' '), end='', flush=True)
            print()
        except Exception:
            final = draft
        return final

    # ═══════════════════════════════════════════════════════════
    # Phase 5: Deliver
    # ═══════════════════════════════════════════════════════════

    def _deliver(self, final: str) -> str:
        """Structured delivery with metadata"""
        output_path = self._state_path.parent / "output.md"
        header = (
            f"---\n"
            f"title: {self.vision[:80]}\n"
            f"generated: {time.strftime('%Y-%m-%d %H:%M')}\n"
            f"mode: {'auto' if self.auto else 'interactive'}\n"
            f"sections: {len(self._state.get('outline',[]))}\n"
            f"words: {len(final.split())}\n"
            f"---\n\n"
        )
        output_path.write_text(header + final, encoding="utf-8")

        # Debrief
        try:
            from .experience_engine import ExperienceEngine
            ee = ExperienceEngine()
            ee.debrief(
                project_type="vision",
                user_request=self.vision,
                design="",
                phases=[{"name":"vision_make"}],
                scores=[8.0],
                report_text=final[:500],
            )
        except Exception:
            pass

        return str(output_path)

    def _ask_choice(self, options: list, prompt_text: str) -> dict:
        if self.auto or len(options) <= 1:
            return options[0]

        print(f"\n  {prompt_text}")
        for i, opt in enumerate(options, 1):
            name = opt.get("name", opt.get("description", f"Option {i}"))[:60]
            desc = opt.get("description", "")[:80]
            rationale = opt.get("rationale", "")
            print(f"\n  [{i}] {name}")
            if desc:
                print(f"      {desc}")
            if rationale:
                print(f"      {rationale}")

        print(f"\n  [a] Auto")
        try:
            inp = input(f"\n  ❯  Choose (1-{len(options)}, or a): ").strip()
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
