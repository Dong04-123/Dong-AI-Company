#!/usr/bin/env python3
"""
Example 3: Experience Engine — learn from past projects.

Shows how Dong AI debriefs a project, saves lessons,
and recalls them for future work.

Run:
  python3 examples/03_experience_engine.py
"""

from dong_ai.experience_engine import ExperienceEngine
from dong_ai.datastore import get_repo


def main():
    print("╭─ Dong AI — Experience Engine Demo ──────────────╮")
    print("┊")

    eng = ExperienceEngine(llm=None)  # no LLM = uses default lessons

    # Simulate completing 3 projects
    projects = [
        ("software", "Build a CLI tool with Python argparse", 8.5),
        ("software", "Create a Django REST API backend", 7.0),
        ("analysis", "Analyze Q2 market data and produce report", 9.0),
    ]

    for i, (ptype, req, score) in enumerate(projects, 1):
        path = eng.debrief(
            project_type=ptype,
            user_request=req,
            design=f"## Design for project {i}",
            phases=[{"name": "design"}, {"name": "code"}, {"name": "test"}],
            scores=[score],
            report_text=f"Project {i} completed. Key findings: implemented successfully.",
        )
        print(f"┊  ✅ Project {i}: {ptype} — lesson saved")
        print(f"┊     {path.split('/')[-1]}")

    # Now recall — simulate a new request
    print("┊")
    new_request = "Build a CLI data processing tool"
    ctx = eng.recall(new_request, project_type="software")
    if ctx:
        print(f"┊  📖 Recalling past experience for:")
        print(f"┊     \"{new_request}\"")
        print("┊")
        for line in ctx.split("\n")[:8]:
            print(f"┊  {line}")
    else:
        print("┊  No relevant past experience found")

    # Stats
    print("┊")
    stats = eng.project_stats()
    print(f"┊  📊 Stats: {stats['total_projects']} projects, "
          f"{stats['avg_score']} avg score")
    print(f"┊     Types: {stats['by_type']}")

    print("╰──────────────────────────────────────────────────╯")


if __name__ == "__main__":
    main()
