"""
Dong AI — CEO 长期记忆框架 (v2)

基于 Datastore 统一存储，移除所有旧版 SQLite 直连。

三层：
  Soul — 人格文件
  Fact — 事实 KV
  Episode — 摘要
"""

import os, re, time
from pathlib import Path
from datetime import datetime, timezone
from .datastore import Datastore, get_repo


class CEOMemory:
    """CEO 长期记忆"""

    TRIVIAL = {'hi','hello','嗨','你好','test','ok','好的','谢谢','thanks','👍','😂'}

    CONFIG_DEFAULTS = {
        'context_length': '32768', 'max_response': '8192',
        'temperature': '0.7', 'auto_compress_at': '20',
        'keep_recent': '15', 'inject_history': 'true',
        'max_facts': '50', 'mode': 'auto',
        'ceo_context': '64000',
        'ceo_max_tokens': '8192',
        'worker_context': '16000',
        'worker_max_tokens': '4096',
    }

    MODE_PRESETS = {
        "api": {
            "ceo_context": "256000",
            "ceo_max_tokens": "16384",
            "worker_context": "128000",
            "worker_max_tokens": "8192",
            "description": "API 模式，256K 大窗口",
        },
        "local": {
            "ceo_context": "64000",
            "ceo_max_tokens": "8192",
            "worker_context": "64000",
            "worker_max_tokens": "4096",
            "description": "本地 64K",
        },
    }

    def __init__(self):
        self.base_dir = Path.home() / ".dong" / "ceo"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.soul_path = self.base_dir / "soul.md"
        self.ds = Datastore()
        self.mem = get_repo("memory")
        self.sessions = get_repo("session")
        self._last_compress_check = 0

    def _is_trivial(self, text: str) -> bool:
        t = text.strip().lower()
        return t in self.TRIVIAL or len(t) < 3

    # ── Soul ──

    def soul(self) -> str:
        if self.soul_path.exists():
            return self.soul_path.read_text().strip()
        return ""

    def soul_set(self, text: str):
        self.soul_path.write_text(text.strip() + "\n")

    # ── Facts ──

    def get(self, key: str) -> str:
        return self.mem.get(key)

    def set(self, key: str, value: str, category: str = "fact", source: str = "auto"):
        self.mem.set(key, value, category, source)

    def delete(self, key: str):
        self.mem.delete(key)

    def facts(self, category: str = "") -> list:
        return self.mem.list(category)

    # ── Episodes ──

    def compress(self, text: str):
        self.ds.conn.execute(
            "INSERT INTO episodes (summary, token_estimate, created_at) VALUES (?,?,?)",
            (text[:500], len(text)//2, datetime.now(timezone.utc).isoformat()))
        self.ds.conn.commit()

    def episodes(self, limit: int = 5) -> list:
        cur = self.ds.conn.execute(
            "SELECT summary, token_estimate, created_at FROM episodes ORDER BY id DESC LIMIT ?", (limit,))
        return [{"summary": r[0][:200], "tokens": r[1], "time": r[2]} for r in cur.fetchall()]

    # ── Sessions ──

    def session_start(self, sid: str = None) -> str:
        return self.sessions.create(sid)

    def session_save(self, sid: str, role: str, content: str):
        if self._is_trivial(content) and role == 'user':
            return
        self.sessions.save_message(sid, role, content)
        self._auto_compress(sid)

    def _auto_compress(self, sid: str):
        now = time.time()
        if now - self._last_compress_check < 5:
            return
        self._last_compress_check = now
        cfg = self.config_load()
        threshold = int(cfg.get('auto_compress_at', '20'))
        keep = int(cfg.get('keep_recent', '15'))
        c = self.ds.conn
        count = c.execute("SELECT message_count FROM sessions WHERE id=?", (sid,)).fetchone()
        if count and count[0] > threshold:
            old = c.execute(
                "SELECT id, role, content FROM messages WHERE session_id=? ORDER BY id ASC LIMIT ?",
                (sid, max(0, count[0] - keep))).fetchall()
            if old and len(old) > 5:
                non_t = [m for m in old if not self._is_trivial(m[2]) and m[1] != 'system']
                if non_t:
                    summary = f"[{non_t[0][2][:50]}...] → [{non_t[-1][2][:50]}...] ({len(non_t)} 条)"
                    c.execute("INSERT INTO episodes (session_id, summary, token_estimate, created_at) VALUES (?,?,?,?)",
                              (sid, summary, sum(len(m[2]) for m in old)//2, datetime.now(timezone.utc).isoformat()))
                ids = [m[0] for m in old]
                c.execute(f"DELETE FROM messages WHERE id IN ({','.join('?'*len(ids))})", ids)
                c.execute("UPDATE sessions SET message_count = message_count - ?, compressed = compressed + 1 WHERE id=?", (len(ids), sid))
            c.commit()

    def session_list(self, limit=10):
        return self.sessions.list_recent(limit)

    def session_load(self, sid: str) -> dict:
        msgs = self.sessions.get_messages(sid)
        cur = self.ds.conn.execute("SELECT summary FROM episodes WHERE session_id=? ORDER BY id", (sid,))
        summaries = [r[0] for r in cur.fetchall()]
        return {"messages": msgs, "summaries": summaries}

    def session_resume(self) -> str:
        cur = self.ds.conn.execute("SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1").fetchone()
        return cur[0] if cur else ""

    # ── Query ──

    def query(self, q: str, limit: int = 5) -> list:
        results = self.mem.query(q)
        # 搜 lore
        lore = get_repo("lore")
        for r in lore.query(q):
            results.append(r)
        # 搜 sessions
        for r in self.sessions.search(q, limit):
            results.append({"source": "chat", "key": r["session"], "value": r["content"], "category": r["role"]})
        return results[:limit]

    # ── Config ──

    def config_load(self) -> dict:
        import configparser
        cfg = configparser.ConfigParser()
        cfg_path = self.base_dir.parent / "config.ini"

        # 1. 默认值（最低优先级）
        config = dict(self.CONFIG_DEFAULTS)

        # 2. 用户配置文件（读一次获取 mode）
        user_cfg = {}
        if cfg_path.exists():
            try:
                cfg.read(str(cfg_path))
                for section in cfg.sections():
                    for key, val in cfg[section].items():
                        user_cfg[key] = val
            except:
                pass

        # 3. 模式预设（基于用户设置的 mode）
        mode = user_cfg.get("mode", config.get("mode", "auto"))
        resolved = self._resolve_mode(mode)
        if resolved and resolved in self.MODE_PRESETS:
            for k, v in self.MODE_PRESETS[resolved].items():
                if k != "description":
                    config[k] = v

        # 4. 用户配置覆盖（最高优先级）
        for k, v in user_cfg.items():
            config[k] = v

        return config

    def _resolve_mode(self, mode: str) -> str:
        """解析 auto 模式为实际模式"""
        if mode != "auto":
            return mode
        # auto 模式：有 API key 且本地显存 < 16GB → api，否则 local
        try:
            import os
            if os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENAI_API_KEY", ""):
                # 有 API key → 检查显存
                import subprocess
                r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total",
                                   "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=2)
                if r.returncode == 0 and r.stdout.strip():
                    vram = int(r.stdout.strip().split("\n")[0])
                    if vram >= 16000:
                        return "local"  # 显存够跑大模型 → 优先本地
                return "api"  # 有 key 显存不够 → 用 API
        except: pass
        return "local"  # 没有 key → 本地

    def config_set(self, key: str, value: str):
        import configparser
        cfg = configparser.ConfigParser()
        cfg_path = self.base_dir.parent / "config.ini"
        if cfg_path.exists():
            cfg.read(str(cfg_path))
        section = 'model'
        for k, s in {'context_length':'model','provider':'model','temperature':'temperature','auto_compress_at':'session','keep_recent':'session','inject_history':'memory','max_facts':'memory'}.items():
            if k in key: section = s; break
        if section not in cfg: cfg[section] = {}
        cfg[section][key] = str(value)
        with open(str(cfg_path), 'w') as f: cfg.write(f)

    # ── Hardware ──

    def detect_hardware(self) -> dict:
        info = {"gpu_vram_mb": 0, "gpu_type": "none", "total_ram_mb": 0}
        import subprocess
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                info["gpu_vram_mb"] = int(r.stdout.strip().split('\n')[0])
                info["gpu_type"] = "nvidia"
        except: pass
        if info["gpu_vram_mb"] == 0:
            try:
                r = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=3)
                for line in r.stdout.split('\n'):
                    if line.startswith("Mem:"):
                        info["total_ram_mb"] = int(line.split()[1])
                        info["gpu_vram_mb"] = info["total_ram_mb"]
                        info["gpu_type"] = "cpu"
            except: pass
        vram = info["gpu_vram_mb"]
        if vram >= 24000: info["recommended"] = {"model": "Qwen3.6-35B", "context": 65536}
        elif vram >= 12000: info["recommended"] = {"model": "Qwen2.5-14B", "context": 32768}
        elif vram >= 8000: info["recommended"] = {"model": "Qwen2.5-7B", "context": 32768}
        else: info["recommended"] = {"model": "API模式", "context": 32768}
        return info

    # ── Inject ──

    def inject_compact(self) -> str:
        parts = []
        s = self.soul()
        if s: parts.append(f"## CEO 人格\n{s}\n")
        facts = self.mem.list()
        prefs = [f for f in facts if f['category'] in ('preference', 'fact')][:5]
        if prefs:
            lines = ["## 用户信息"]
            for f in prefs: lines.append(f"  {f['key']}: {f['value']}")
            parts.append("\n".join(lines))
        lore_count = get_repo("lore").count()
        idx = []
        if len(facts) > 5: idx.append(f"  {len(facts)} 条记忆")
        if lore_count > 0: idx.append(f"  {lore_count} 条世界观设定")
        if idx:
            parts.append("## 知识库索引\n" + "\n".join(idx))
            parts.append("需要详情用 [TOOL_CALL:memory] action=get key=xxx 查询")
        return "\n\n".join(parts)
