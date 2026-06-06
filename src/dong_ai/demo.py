"""dong demo — zero-config cross-project graph memory demo.

No API key, no network calls. Creates fake projects in a temp SQLite DB
and queries them exactly like the real graph commands do.
"""

import sqlite3
import os

from dong_ai.display import C


def _cmd_demo() -> None:
    db_path = "/tmp/dong_demo.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS codegraph (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            node_type TEXT,
            node_name TEXT,
            file_path TEXT,
            line_number INTEGER DEFAULT 0,
            signature TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            embedding BLOB DEFAULT NULL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS code_deps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            from_node TEXT,
            to_node TEXT,
            dep_type TEXT,
            created_at TEXT
        );
    """)

    # ── Project A: Config Parser (2 weeks ago) ──
    ts_a = "2026-05-24T10:00:00"
    proj_a = "config-parser"
    nodes_a = [
        (proj_a, "function", "parse_yaml", "parser.py", 10,
         "def parse_yaml(path: str) -> dict", "YAML file parser"),
        (proj_a, "function", "parse_json", "parser.py", 45,
         "def parse_json(path: str) -> dict", "JSON file parser"),
        (proj_a, "function", "parse_toml", "parser.py", 78,
         "def parse_toml(path: str) -> dict", "TOML file parser"),
        (proj_a, "function", "validate_schema", "validator.py", 12,
         "def validate_schema(data: dict, schema: dict) -> bool", "Schema validation"),
        (proj_a, "function", "merge_config", "merger.py", 8,
         "def merge_config(*configs: dict) -> dict", "Deep merge config dicts"),
        (proj_a, "class", "ConfigManager", "manager.py", 5,
         "class ConfigManager", "Central config manager"),
        (proj_a, "function", "load_config", "manager.py", 15,
         "def load_config(path: str) -> dict", "Load and validate config"),
        (proj_a, "function", "watch_directory", "watcher.py", 22,
         "def watch_directory(path: str, callback)", "FS watcher"),
    ]
    for n in nodes_a:
        c.execute(
            "INSERT INTO codegraph (project_id, node_type, node_name, file_path, line_number, signature, detail, created_at) VALUES (?,?,?,?,?,?,?,?)",
            n + (ts_a,))

    deps_a = [
        (proj_a, "ConfigManager", "load_config", "calls"),
        (proj_a, "ConfigManager", "validate_schema", "calls"),
        (proj_a, "load_config", "parse_yaml", "calls"),
        (proj_a, "load_config", "parse_json", "calls"),
        (proj_a, "load_config", "parse_toml", "calls"),
        (proj_a, "load_config", "merge_config", "calls"),
        (proj_a, "watch_directory", "load_config", "calls"),
        (proj_a, "load_config", "validate_schema", "calls"),
    ]
    for d in deps_a:
        c.execute(
            "INSERT INTO code_deps (project_id, from_node, to_node, dep_type, created_at) VALUES (?,?,?,?,?)",
            d + (ts_a,))

    # ── Project B: Data Pipeline (last week) ──
    ts_b = "2026-06-01T14:00:00"
    proj_b = "data-pipeline"
    nodes_b = [
        (proj_b, "function", "parse_csv", "ingest.py", 15,
         "def parse_csv(path: str) -> list[dict]", "CSV parser for data ingestion"),
        (proj_b, "function", "parse_json", "ingest.py", 52,
         "def parse_json(path: str) -> list[dict]", "JSON array parser"),
        (proj_b, "function", "transform", "transform.py", 10,
         "def transform(rows: list[dict], rules: list) -> list[dict]", "Data transformation"),
        (proj_b, "function", "validate_row", "validate.py", 8,
         "def validate_row(row: dict, schema: dict) -> bool", "Row validation"),
        (proj_b, "function", "export_csv", "export.py", 12,
         "def export_csv(data: list[dict], path: str)", "Export to CSV"),
        (proj_b, "function", "export_json", "export.py", 35,
         "def export_json(data: list[dict], path: str)", "Export to JSON"),
        (proj_b, "class", "Pipeline", "pipeline.py", 8,
         "class Pipeline", "ETL pipeline orchestrator"),
        (proj_b, "function", "run_pipeline", "pipeline.py", 28,
         "def run_pipeline(source: str, rules: list) -> list[dict]", "Run full ETL"),
    ]
    for n in nodes_b:
        c.execute(
            "INSERT INTO codegraph (project_id, node_type, node_name, file_path, line_number, signature, detail, created_at) VALUES (?,?,?,?,?,?,?,?)",
            n + (ts_b,))

    deps_b = [
        (proj_b, "Pipeline", "run_pipeline", "calls"),
        (proj_b, "run_pipeline", "parse_csv", "calls"),
        (proj_b, "run_pipeline", "parse_json", "calls"),
        (proj_b, "run_pipeline", "transform", "calls"),
        (proj_b, "run_pipeline", "export_csv", "calls"),
        (proj_b, "transform", "validate_row", "calls"),
        (proj_b, "parse_csv", "validate_row", "calls"),
    ]
    for d in deps_b:
        c.execute(
            "INSERT INTO code_deps (project_id, from_node, to_node, dep_type, created_at) VALUES (?,?,?,?,?)",
            d + (ts_b,))

    conn.commit()

    def _list():
        cur = c.execute("""
            SELECT project_id, COUNT(*) as nc,
                   SUM(CASE WHEN node_type='function' THEN 1 ELSE 0 END) as fn,
                   SUM(CASE WHEN node_type='class' THEN 1 ELSE 0 END) as cl
            FROM codegraph GROUP BY project_id
        """)
        for r in cur.fetchall():
            dc = c.execute(
                "SELECT COUNT(*) FROM code_deps WHERE project_id=?", (r[0],)
            ).fetchone()[0]
            yield {"id": r[0], "nodes": r[1], "functions": r[2] or 0,
                   "classes": r[3] or 0, "deps": dc}

    def _q(query_str, pid=""):
        kw = f"%{query_str}%"
        if pid:
            cur = c.execute(
                "SELECT node_name, node_type, file_path, signature FROM codegraph "
                "WHERE project_id=? AND (node_name LIKE ? OR signature LIKE ?)",
                (pid, kw, kw))
        else:
            cur = c.execute(
                "SELECT node_name, node_type, file_path, signature, project_id "
                "FROM codegraph WHERE node_name LIKE ? OR signature LIKE ?",
                (kw, kw))
        return [dict(r) for r in cur.fetchall()]

    # ════════════════ Render ════════════════

    print()
    title = f"╭─ {C.B}Dong AI — Cross-Project Graph Memory Demo{C.R} "
    print(f"{title}{'─'*(72-len(title))}╮")
    print(f"{C.D}┊  No API key needed. No network calls. Demo data is local.{C.R}")
    print(f"{C.D}┊  This is exactly how dong graph list / view works for real.{C.R}")
    print(f"╰{'─'*72}╯")
    print()

    # Step 1
    print(f"{C.B}Step 1: What does the graph remember?{C.R}")
    print(f"{C.D}    Two projects indexed (not stored as conversation history).{C.R}")
    print()
    projects = list(_list())
    total_nodes = sum(p["nodes"] for p in projects)
    total_deps = sum(p["deps"] for p in projects)
    print(f"  {C.P}Graph Memory:{C.R} {len(projects)} projects, "
          f"{total_nodes} symbols, {total_deps} dependencies")
    print()
    for p in projects:
        desc = {"config-parser": "built 2026-05-24 — YAML/JSON/TOML config system",
                "data-pipeline": "built 2026-06-01 — CSV/JSON ETL pipeline"}
        print(f"    {C.B}{p['id']:<30}{C.R} {p['nodes']:>3} symbols "
              f"({p['functions']} fn, {p['classes']} cls)  {p['deps']} deps")
        print(f"    {'':36}{desc.get(p['id'], '')}")
    print()

    # Step 2
    print(f"{C.B}Step 2: Cross-project search{C.R}")
    print(f"{C.D}    Without graph memory: scroll through conversation history per project.{C.R}")
    print(f"{C.D}    With graph memory: one query across ALL past projects.{C.R}")
    print()
    for term in ["parse_json", "parse_csv", "load_config"]:
        results = _q(term)
        proj_names = set(r.get("project_id", r["file_path"]) for r in results)
        proj_str = ", ".join(sorted(proj_names))
        print(f"    {C.Y}{term:<20}{C.R} {len(results)} match(es) in {proj_str}")
        for r in results:
            pid = r.get("project_id", "")
            print(f"      {r['node_type']:8s} {r['node_name']:<20s} "
                  f"{r['file_path']:<30s} {pid}")
    print()

    # Step 3
    print(f"{C.B}Step 3: Drill into a project — exact signatures{C.R}")
    print(f"{C.D}    Get function signatures, not degraded conversation memory.{C.R}")
    print()
    for pid in ["config-parser", "data-pipeline"]:
        print(f"  {C.P}{pid}{C.R}")
        cur = c.execute(
            "SELECT node_name, node_type, file_path, line_number, signature "
            "FROM codegraph WHERE project_id=? ORDER BY file_path, line_number",
            (pid,))
        for r in cur.fetchall():
            print(f"    {r[1]:8s} {C.B}{r[0]:<20s}{C.R} {r[2]}:{r[3]}")
            if r[4]:
                print(f"    {'':12}{C.D}{r[4][:85]}{C.R}")
        print()

    # Step 4
    print(f"{C.B}Step 4: Impact analysis — who depends on what?{C.R}")
    print(f"{C.D}    Refactoring load_config? Here's every caller, indexed.{C.R}")
    print()
    for target in ["load_config", "parse_json"]:
        callers = c.execute(
            "SELECT from_node, dep_type FROM code_deps "
            "WHERE project_id='config-parser' AND to_node=?", (target,)).fetchall()
        callees = c.execute(
            "SELECT from_node, to_node, dep_type FROM code_deps "
            "WHERE project_id='config-parser' AND from_node=?", (target,)).fetchall()
        print(f"    {C.Y}{target}{C.R}")
        if callers:
            print(f"      Called by ({len(callers)}):")
            for caller, dtype in callers:
                print(f"        {caller}")
        if callees:
            print(f"      Calls ({len(callees)}):")
            for frm, to, dtype in callees:
                print(f"        {to}  [{dtype}]")
        if not callers and not callees:
            print("      (no dependencies)")
        print()

    # Step 5
    print(f"{C.B}Step 5: Resume a project after a week{C.R}")
    print(f"{C.D}    'I built a data pipeline last week, what were the key symbols?'{C.R}")
    print()
    cur = c.execute(
        "SELECT node_name, node_type FROM codegraph WHERE project_id='data-pipeline' "
        "ORDER BY CASE WHEN node_type='class' THEN 0 ELSE 1 END, line_number")
    for r in cur.fetchall():
        icon = {"class": "  class", "function": "  fn   "}.get(r[1], "  ?    ")
        print(f"    {icon} {r[0]}")
    print()

    # Summary box
    print(f"{C.GN}{'┌' + '─'*72 + '┐'}{C.R}")
    print(f"{C.GN}│{C.R}  This is the difference between 'index' and 'remember'.{' ':<34}{C.GN}│{C.R}")
    print(f"{C.GN}│{C.R}  Traditional agents scroll through degraded conversation history.{' ':<25}{C.GN}│{C.R}")
    print(f"{C.GN}│{C.R}  Dong AI queries an index. Clean. Fast. Cross-project.{' ':<32}{C.GN}│{C.R}")
    print(f"{C.GN}│{' ':<72}│{C.R}")
    print(f"{C.GN}│{C.R}  Want to try it for real?{' ':<49}{C.GN}│{C.R}")
    print(f"{C.GN}│{C.R}    pip install dong-ai && dong setup{' ':<41}{C.GN}│{C.R}")
    print(f"{C.GN}│{C.R}    dong make 'anything' (no API key? Ollama is free){' ':<20}{C.GN}│{C.R}")
    print(f"{C.GN}└{'─'*72}┘{C.R}")

    conn.close()
    os.remove(db_path)
