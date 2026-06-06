#!/usr/bin/env python3
"""
Example 2: Graph memory — cross-project persistence.

Shows how graph memory remembers symbols and dependencies
across multiple project runs.

Run:
  python3 examples/02_graph_memory.py
"""

from dong_ai.datastore import get_repo


def main():
    print("╭─ Dong AI — Graph Memory Demo ───────────────────╮")
    print("┊")

    gr = get_repo("graph")

    # Simulate indexing project 1
    gr.add_node("proj1", "function", "parse_csv", "parser.py", 10,
                signature="def parse_csv(path: str) -> list[dict]")
    gr.add_node("proj1", "function", "validate_row", "parser.py", 35,
                signature="def validate_row(row: dict) -> bool")
    gr.add_node("proj1", "class", "CSVHandler", "handler.py", 5,
                signature="class CSVHandler")
    gr.add_dep("proj1", "CSVHandler", "parse_csv", "calls")

    # Simulate indexing project 2
    gr.add_node("proj2", "function", "load_config", "config.py", 3,
                signature="def load_config(path: str) -> dict")
    gr.add_node("proj2", "function", "parse_csv", "utils.py", 12,
                signature="def parse_csv(path: str) -> list")
    gr.add_dep("proj2", "load_config", "parse_csv", "calls")

    print("┊  📦 Project 1:")
    nodes1 = gr.get_project_nodes("proj1")
    deps1 = gr.get_deps("proj1")
    for n in nodes1:
        print(f"┊    {n['node_type']:8s} {n['node_name']:<20s} {n['file_path']}")
    print(f"┊    {len(deps1)} dependencies")

    print("┊")
    print("┊  📦 Project 2:")
    nodes2 = gr.get_project_nodes("proj2")
    for n in nodes2:
        print(f"┊    {n['node_type']:8s} {n['node_name']:<20s} {n['file_path']}")

    # Cross-project search
    print("┊")
    results = gr.query("parse_csv")
    print(f"┊  🔍 Cross-project search 'parse_csv': {len(results)} matches")
    hit_projects = set(r["project_id"] for r in results)
    print(f"┊     Found in: {', '.join(hit_projects)}")

    # Context for LLM
    print("┊")
    ctx = gr.format_context("proj1", ["csv", "parse"])
    print(f"┊  📋 LLM context block ({len(ctx)} chars):")
    for line in ctx.split("\n")[:5]:
        print(f"┊    {line}")

    print("╰──────────────────────────────────────────────────╯")


if __name__ == "__main__":
    main()
