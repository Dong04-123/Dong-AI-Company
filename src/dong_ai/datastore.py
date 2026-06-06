"""
Dong AI — 统一持久化层

解决原架构三大问题：
  1. 三个 SQLite 文件各自为政 → 统一到一个 Datastore
  2. 每方法建连拆连 → 连接池/单连接
  3. 无类型无接口 → Repository 模式 + 类型提示

用法:
  from datastore import Datastore
  ds = Datastore()
  repo = ds.memory()
  repo.set("key", "value")

表架构自动初始化，连接复用。
"""

import sqlite3, json, time, os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


class Datastore:
    """统一数据存储——管理所有 SQLite 文件和连接"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        self.base_dir = Path.home() / ".dong"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # 持久化连接
        self._conn = sqlite3.connect(str(self.base_dir / "dong.db"), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()
    
    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY, value TEXT NOT NULL,
                category TEXT DEFAULT 'fact', source TEXT DEFAULT 'manual',
                created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT, summary TEXT NOT NULL,
                token_estimate INTEGER DEFAULT 0,
                trivial INTEGER DEFAULT 0, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, title TEXT,
                message_count INTEGER DEFAULT 0,
                token_count INTEGER DEFAULT 0,
                compressed INTEGER DEFAULT 0,
                created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase TEXT NOT NULL, content TEXT NOT NULL,
                score REAL DEFAULT 0, timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS modules (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                quality_score REAL DEFAULT 0,
                test_count INTEGER DEFAULT 0, test_pass INTEGER DEFAULT 0,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS interfaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id TEXT NOT NULL, name TEXT NOT NULL,
                signature TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL, detail TEXT NOT NULL,
                severity TEXT DEFAULT 'info', module_id TEXT,
                timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT, chapter_introduced INTEGER DEFAULT 0,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS codegraph (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                node_name TEXT NOT NULL,
                file_path TEXT,
                line_number INTEGER DEFAULT 0,
                signature TEXT,
                detail TEXT,
                embedding BLOB,
                source TEXT DEFAULT 'auto',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS code_deps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                dep_type TEXT DEFAULT 'import',
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_codegraph_project ON codegraph(project_id);
            CREATE INDEX IF NOT EXISTS idx_codegraph_node ON codegraph(node_name);
            CREATE INDEX IF NOT EXISTS idx_codedeps_from ON code_deps(from_node);
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT, logger TEXT, level TEXT,
                event TEXT, data TEXT, created_at TEXT
            );
        """)
        self._conn.commit()
    
    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn
    
    def close(self):
        self._conn.close()
        Datastore._instance = None


# ── Repository 模式 ──

class MemoryRepository:
    """记忆存储"""
    
    def __init__(self, ds: Datastore):
        self.c = ds.conn
    
    def get(self, key: str) -> str:
        cur = self.c.execute("SELECT value FROM facts WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else ""
    
    def set(self, key: str, value: str, category: str = "fact", source: str = "auto"):
        now = datetime.now(timezone.utc).isoformat()
        self.c.execute(
            "INSERT OR REPLACE INTO facts (key, value, category, source, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (key, value, category, source, now, now))
        self.c.commit()
    
    def delete(self, key: str):
        self.c.execute("DELETE FROM facts WHERE key=?", (key,))
        self.c.commit()
    
    def list(self, category: str = "") -> list:
        if category:
            cur = self.c.execute("SELECT key, value, category, source FROM facts WHERE category=? ORDER BY key", (category,))
        else:
            cur = self.c.execute("SELECT key, value, category, source FROM facts ORDER BY category, key")
        return [{"key": r[0], "value": r[1], "category": r[2], "source": r[3]} for r in cur.fetchall()]
    
    def query(self, q: str) -> list:
        kw = f"%{q}%"
        cur = self.c.execute(
            "SELECT key, value, category, source FROM facts WHERE key LIKE ? OR value LIKE ? LIMIT 10",
            (kw, kw))
        return [{"key": r[0], "value": r[1], "category": r[2], "source": r[3]} for r in cur.fetchall()]


class SessionRepository:
    """会话存储"""
    
    def __init__(self, ds: Datastore):
        self.c = ds.conn
    
    def create(self, sid: str = None) -> str:
        import uuid
        sid = sid or f"s{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()
        self.c.execute("INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                       (sid, f"会话 {sid[-8:]}", now, now))
        self.c.commit()
        return sid
    
    def save_message(self, sid: str, role: str, content: str):
        now = datetime.now(timezone.utc).isoformat()
        self.c.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                       (sid, role, content[:2000], now))
        self.c.execute("UPDATE sessions SET message_count = message_count + 1, updated_at = ? WHERE id=?",
                       (now, sid))
        self.c.commit()
    
    def get_messages(self, sid: str) -> list:
        cur = self.c.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id", (sid,))
        return [{"role": r[0], "content": r[1]} for r in cur.fetchall()]
    
    def list_recent(self, limit: int = 10) -> list:
        cur = self.c.execute(
            "SELECT id, title, message_count, created_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,))
        return [{"id": r[0], "title": r[1], "msgs": r[2], "time": r[3][:19]} for r in cur.fetchall()]
    
    def search(self, q: str, limit: int = 10) -> list:
        kw = f"%{q}%"
        cur = self.c.execute(
            "SELECT session_id, role, content, created_at FROM messages WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
            (kw, limit))
        return [{"session": r[0][-12:], "role": r[1], "content": r[2][:200], "time": r[3]} for r in cur.fetchall()]


class ProjectRepository:
    """项目图谱存储"""
    
    def __init__(self, ds: Datastore):
        self.c = ds.conn
    
    def add_decision(self, phase: str, content: str, score: float = 0):
        self.c.execute("INSERT INTO decisions (phase, content, score, timestamp) VALUES (?,?,?,?)",
                       (phase, content, score, datetime.now(timezone.utc).isoformat()))
        self.c.commit()
    
    def get_decisions(self, limit: int = 20) -> list:
        cur = self.c.execute("SELECT phase, content, score FROM decisions ORDER BY id DESC LIMIT ?", (limit,))
        return [{"phase": r[0], "content": r[1][:100], "score": r[2]} for r in cur.fetchall()]
    
    def query(self, q: str) -> list:
        kw = f"%{q}%"
        results = []
        queries = [
            ("decisions", "phase, content", "phase LIKE ? OR content LIKE ?"),
            ("lessons", "pattern, detail", "pattern LIKE ? OR detail LIKE ?"),
            ("modules", "name, status", "name LIKE ? OR status LIKE ?"),
        ]
        for table, fields, where in queries:
            cur = self.c.execute(
                f"SELECT '{table}' as src, {fields} FROM {table} WHERE {where} LIMIT 5",
                (kw, kw),
            )
            for r in cur.fetchall():
                results.append({"source": r[0], "key": r[1], "value": r[2][:200]})
        return results


class LoreRepository:
    """世界观存储"""
    
    def __init__(self, ds: Datastore):
        self.c = ds.conn
    
    def add(self, category: str, name: str, description: str, chapter: int = 0):
        self.c.execute("INSERT INTO lore (category, name, description, chapter_introduced, created_at) VALUES (?,?,?,?,?)",
                       (category, name, description, chapter, datetime.now(timezone.utc).isoformat()))
        self.c.commit()
    
    def query(self, q: str) -> list:
        kw = f"%{q}%"
        cur = self.c.execute(
            "SELECT category, name, description FROM lore WHERE name LIKE ? OR description LIKE ? LIMIT 10",
            (kw, kw))
        return [{"source": "lore", "category": r[0], "key": r[1], "value": r[2]} for r in cur.fetchall()]
    
    def count(self) -> int:
        return self.c.execute("SELECT COUNT(*) FROM lore").fetchone()[0]


class GraphRepository:
    """代码图存储 — 符号索引 + 依赖关系"""

    def __init__(self, ds: Datastore):
        self.c = ds.conn

    def add_node(self, project_id: str, node_type: str, node_name: str,
                 file_path: str = "", line_number: int = 0,
                 signature: str = "", detail: str = ""):
        text_idx = f"{node_name} {signature} {detail} {file_path}"
        emb = self._embed(text_idx)
        self.c.execute(
            "INSERT INTO codegraph (project_id, node_type, node_name, file_path, line_number, signature, detail, embedding, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (project_id, node_type, node_name, file_path, line_number, signature, detail,
             emb,
             datetime.now(timezone.utc).isoformat()))
        self.c.commit()

    def add_dep(self, project_id: str, from_node: str, to_node: str, dep_type: str = "import"):
        self.c.execute(
            "INSERT INTO code_deps (project_id, from_node, to_node, dep_type, created_at) VALUES (?,?,?,?,?)",
            (project_id, from_node, to_node, dep_type,
             datetime.now(timezone.utc).isoformat()))
        self.c.commit()

    # ── 嵌入向量（语义搜索）──

    def _embed(self, text: str) -> bytes:
        """调用本地嵌入模型，返回 pickle 格式的向量"""
        if not text.strip():
            return b""
        try:
            import urllib.request, json, pickle, struct
            payload = json.dumps({"model": "nomic-embed-text", "prompt": text[:512]}).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/embeddings",
                data=payload, headers={"Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                vec = data.get("embedding", [])
                return struct.pack(f"{len(vec)}f", *vec) if vec else b""
        except Exception:
            return b""

    def _cosine_sim(self, a: bytes, b: bytes) -> float:
        import struct
        if not a or not b or len(a) != len(b):
            return 0.0
        va = list(struct.unpack(f"{len(a)//4}f", a))
        vb = list(struct.unpack(f"{len(b)//4}f", b))
        dot = sum(x * y for x, y in zip(va, vb))
        na = sum(x * x for x in va) ** 0.5
        nb = sum(x * x for x in vb) ** 0.5
        return dot / (na * nb) if na > 0 and nb > 0 else 0.0

    # ── 图遍历 ──

    def traverse(self, project_id: str, node_name: str, depth: int = 1) -> list:
        """从节点出发沿依赖链遍历，返回所有相关节点"""
        related = set()
        related.add(node_name)
        current = {node_name}
        levels = [{node_name}]
        for d in range(depth):
            if not current:
                break
            placeholders = ",".join("?" for _ in current)
            cur = self.c.execute(
                f"SELECT from_node, to_node FROM code_deps WHERE project_id=? AND (from_node IN ({placeholders}) OR to_node IN ({placeholders}))",
                (project_id, *current, *current))
            found = set()
            for r in cur.fetchall():
                found.add(r[0])
                found.add(r[1])
            current = found - related
            related.update(current)
            if current:
                levels.append(current)
        related.discard(node_name)

        result = []
        seen = set()
        for level_idx, level in enumerate(levels[1:], 1):
            if not level:
                continue
            placeholders = ",".join("?" for _ in level)
            cur = self.c.execute(
                f"SELECT node_name, node_type, file_path, signature FROM codegraph WHERE project_id=? AND node_name IN ({placeholders}) LIMIT 20",
                (project_id, *level))
            for r in cur.fetchall():
                if r[0] not in seen:
                    seen.add(r[0])
                    node = {"name": r[0], "type": r[2], "file": r[2], "signature": r[3], "depth": level_idx}
                    result.append(node)

        # 计算影响分
        direct = sum(1 for n in result if n.get("depth") == 1)
        indirect = sum(1 for n in result if n.get("depth", 0) > 1)
        total = len(result)
        risk = min(100, direct * 25 + indirect * 10) if total > 0 else 0

        return {"nodes": result, "direct": direct, "indirect": indirect, "total": total, "risk": risk}

    # ── 查询 ──

    def get_project_nodes(self, project_id: str, node_type: str = "") -> list:
        if node_type:
            cur = self.c.execute(
                "SELECT * FROM codegraph WHERE project_id=? AND node_type=? ORDER BY file_path, line_number",
                (project_id, node_type))
        else:
            cur = self.c.execute(
                "SELECT * FROM codegraph WHERE project_id=? ORDER BY file_path, line_number",
                (project_id,))
        return [dict(r) for r in cur.fetchall()]

    def query(self, q: str, project_id: str = "") -> list:
        """关键词 + 语义混合搜索"""
        kw = f"%{q}%"
        results = {}
        # 1. 关键词搜索（精确匹配）
        if project_id:
            cur = self.c.execute(
                "SELECT id, node_name, node_type, file_path, signature, embedding FROM codegraph WHERE project_id=? AND (node_name LIKE ? OR signature LIKE ? OR detail LIKE ?) LIMIT 15",
                (project_id, kw, kw, kw))
        else:
            cur = self.c.execute(
                "SELECT id, node_name, node_type, file_path, signature, embedding FROM codegraph WHERE node_name LIKE ? OR signature LIKE ? OR detail LIKE ? LIMIT 15",
                (kw, kw, kw))
        for r in cur.fetchall():
            results[r[0]] = {"name": r[1], "type": r[2], "file": r[3], "signature": r[4], "score": 1.0, "emb": r[5]}

        # 2. 语义搜索（向量相似度，仅当嵌入模型可用）
        q_emb = self._embed(q)
        if q_emb:
            cur2 = self.c.execute(
                "SELECT id, node_name, node_type, file_path, signature, embedding FROM codegraph WHERE embedding IS NOT NULL AND embedding != '' ORDER BY id DESC LIMIT 50",
                () if project_id else ())
            for r in cur2.fetchall():
                if r[0] in results:
                    continue
                sim = self._cosine_sim(q_emb, r[5] or b"")
                if sim > 0.5:
                    results[r[0]] = {"name": r[1], "type": r[2], "file": r[3], "signature": r[4], "score": sim}

        return [v for v in sorted(results.values(), key=lambda x: -x["score"])[:10]]

    def get_deps(self, project_id: str, node_name: str = "") -> list:
        if node_name:
            cur = self.c.execute(
                "SELECT * FROM code_deps WHERE project_id=? AND from_node=?",
                (project_id, node_name))
        else:
            cur = self.c.execute(
                "SELECT * FROM code_deps WHERE project_id=?",
                (project_id,))
        return [dict(r) for r in cur.fetchall()]

    def query(self, q: str, project_id: str = "") -> list:
        kw = f"%{q}%"
        if project_id:
            cur = self.c.execute(
                "SELECT node_name, node_type, file_path, signature FROM codegraph WHERE project_id=? AND (node_name LIKE ? OR signature LIKE ?) LIMIT 10",
                (project_id, kw, kw))
        else:
            cur = self.c.execute(
                "SELECT node_name, node_type, file_path, signature FROM codegraph WHERE node_name LIKE ? OR signature LIKE ? LIMIT 10",
                (kw, kw))
        return [{"name": r[0], "type": r[1], "file": r[2], "signature": r[3]} for r in cur.fetchall()]

    def format_context(self, project_id: str, keywords: list = None) -> str:
        parts = []
        nodes = self.get_project_nodes(project_id)
        if nodes:
            fn_count = sum(1 for n in nodes if n["node_type"] == "function")
            cls_count = sum(1 for n in nodes if n["node_type"] == "class")
            parts.append(f"📊 项目代码库: {len(nodes)} 符号 ({fn_count} 函数, {cls_count} 类)")
            if keywords:
                for kw in keywords:
                    matches = self.query(kw, project_id)
                    if matches:
                        parts.append(f"\n🔍 与「{kw}」相关的符号:")
                        for m in matches[:5]:
                            parts.append(f"  · {m['name']} ({m['type']}) in {m['file']}: {m.get('signature','')[:80]}")
                        # 图遍历：自动查找相关依赖
                        for m in matches[:3]:
                            trav = self.traverse(project_id, m["name"], depth=1)
                            if trav["nodes"]:
                                parts.append(f"  └─ 影响面 ({trav['total']} 个, 风险 {trav['risk']}%):")
                                for r in trav["nodes"][:5]:
                                    parts.append(f"      {r['name']} ({r['type']})")
        deps = self.get_deps(project_id)
        if deps:
            parts.append(f"\n🔗 依赖关系: {len(deps)} 条")
            for d in deps[:10]:
                parts.append(f"  {d['from_node']} → {d['to_node']} [{d['dep_type']}]")
        return "\n".join(parts) if parts else ""

    def list_projects(self) -> list:
        cur = self.c.execute(
            "SELECT project_id, COUNT(*) as node_count, "
            "SUM(CASE WHEN node_type='function' THEN 1 ELSE 0 END) as fn_count, "
            "SUM(CASE WHEN node_type='class' THEN 1 ELSE 0 END) as cls_count "
            "FROM codegraph GROUP BY project_id ORDER BY node_count DESC LIMIT 50")
        projects = []
        for r in cur.fetchall():
            dc = self.c.execute("SELECT COUNT(*) FROM code_deps WHERE project_id=?", (r[0],))
            projects.append({"id": r[0], "nodes": r[1], "functions": r[2] or 0,
                             "classes": r[3] or 0, "deps": dc.fetchone()[0]})
        return projects

    def merge_project(self, from_id: str, to_id: str) -> int:
        self.c.execute("UPDATE codegraph SET project_id=? WHERE project_id=?", (to_id, from_id))
        self.c.execute("UPDATE code_deps SET project_id=? WHERE project_id=?", (to_id, from_id))
        self.c.commit()
        return self.c.execute("SELECT COUNT(*) FROM codegraph WHERE project_id=?", (to_id,)).fetchone()[0]


# ── 工厂 ──

_repo_cache = {}

def get_repo(name: str):
    """获取 Repository 实例（带缓存）"""
    if name not in _repo_cache:
        ds = Datastore()
        repos = {
            "memory": MemoryRepository,
            "session": SessionRepository,
            "project": ProjectRepository,
            "lore": LoreRepository,
            "graph": GraphRepository,
        }
        cls = repos.get(name)
        if cls:
            _repo_cache[name] = cls(ds)
    return _repo_cache.get(name)
