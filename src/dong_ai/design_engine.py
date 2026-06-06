"""
Dong AI — 设计引擎

从 ceo.py 拆出的独立模块：设计阶段、红蓝辩论、自评分
"""

import re
from .logger import get_logger

log = get_logger("design")


class DesignEngine:
    """设计引擎——负责接收需求、红蓝辩论、输出方案和评分"""
    
    def __init__(self, llm_client, datastore):
        self.llm = llm_client
        self.ds = datastore
    
    def design(self, user_request: str, max_retries: int = 3) -> dict:
        """完整设计流程 + 需求清单拆解"""
        attempt = 0
        last_score = 0
        current_request = user_request
        
        while attempt < max_retries:
            attempt += 1
            log.info("design_attempt", attempt=attempt, request=current_request[:50])
            
            # 事前验尸
            premortem = self.llm.chat([
                {"role": "user", "content": f"需求：{current_request}\n\n假设项目6个月后彻底失败。列出3-5个最可能的原因和预防措施。"}
            ], system="你是风险分析师。简洁明了。", max_tokens=1024, temperature=0.5)
            self.ds.add_decision("premortem", premortem.text)
            
            # 初始设计
            risk_ctx = f"\n\n已识别风险（必须规避）：\n{premortem.text[:500]}"
            design = self.llm.chat([
                {"role": "user", "content": f"需求：{current_request}\n\n输出完整设计方案。{risk_ctx}"}
            ], system="你是资深架构师。", max_tokens=8192, temperature=0.5)
            self.ds.add_decision("design_initial", design.text)
            
            # 红队审查
            red_team = self.llm.chat([
                {"role": "user", "content": f"审查方案：\n{design.text}\n\n按严重程度列出问题，给出改进建议。"}
            ], system="你是红队审查专家。", max_tokens=4096, temperature=0.7)
            self.ds.add_decision("red_team_review", red_team.text)
            
            # 改进
            improved = self.llm.chat([
                {"role": "user", "content": f"原始方案：\n{design.text}\n\n反馈：\n{red_team.text}\n\n改进输出最终版。"}
            ], system="你是资深架构师。吸收反馈，改进方案。", max_tokens=8192, temperature=0.3)
            self.ds.add_decision("design_final", improved.text)
            
            # 评分
            score_str = self.llm.chat([
                {"role": "user", "content": f"给方案打分(1-10)。输出格式：总分: X.X\n\n{improved.text}"}
            ], system="严格的评审委员。8分以上已经很优秀。", max_tokens=200, temperature=0.1)
            
            try:
                score = float(re.search(r'总分[：:]\s*(\d+\.?\d*)', score_str.text).group(1))
            except:
                score = 7.0
            
            log.info("design_scored", attempt=attempt, score=score)
            self.ds.add_decision("self_score", f"评分: {score}", score=score)
            
            if score >= 9:
                requirements = self._extract_requirements(improved.text)
                return {"design": improved.text, "score": score, "requirements": requirements}
            
            last_score = score
            current_request = f"{user_request}\n\n之前评分{score}，请大幅改进。"
        
        requirements = self._extract_requirements(improved.text)
        return {"design": improved.text, "score": last_score, "requirements": requirements}

    def _extract_requirements(self, design_text: str) -> list:
        """从设计方案中提取可验证的需求清单"""
        try:
            resp = self.llm.chat([
                {"role": "user", "content": (
                    f"从以下设计方案中提取5-12条可验证的硬性需求。\n"
                    f"每条需求必须可被自动化测试验证。\n"
                    f"输出 JSON 格式（只输出 JSON 数组，不要其他内容）：\n"
                    f'{{"requirements": [\n'
                    f'  {{"id": "R1", "desc": "支持YAML格式配置文件", "verify": "test_load_yaml()"}},\n'
                    f'  {{"id": "R2", "desc": "文件不存在时返回默认配置", "verify": "test_fallback()"}}\n'
                    f"]}}\n\n设计方案：\n{design_text[:4000]}"
                )}
            ], system="需求分析专家。输出严格JSON。", max_tokens=4096, temperature=0.2)

            json_match = re.search(r'\{.*\}', resp.text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                reqs = data.get("requirements", [])
                # 写入决策记录
                for r in reqs:
                    self.ds.add_decision(f"req_{r['id']}", f"{r['desc']} → {r.get('verify','')}", score=1.0)
                return reqs
        except Exception:
            pass
        return []

    def get_coverage(self, requirements: list, completed_task_ids: list) -> dict:
        """计算需求覆盖率"""
        if not requirements:
            return {"rate": 1.0, "covered": [], "missing": []}
        total = len(requirements)
        import re
        covered = []
        for r in requirements:
            rid = r["id"].lower()
            rdesc = r.get("desc", "")
            # 从需求描述中提取英文关键词（技术术语）
            eng_keywords = set(re.findall(r'[a-zA-Z_]\w{2,}', rdesc))
            # 展开为单个词（load_config → load, config）
            eng_parts = set()
            for kw in eng_keywords:
                for part in kw.lower().split("_"):
                    if len(part) > 2:
                        eng_parts.add(part)
            for tid in completed_task_ids:
                t = tid.lower()
                if rid in t:
                    covered.append(r); break
                if any(p in t for p in eng_parts):
                    covered.append(r); break
        return {
            "rate": len(covered) / max(total, 1),
            "covered": covered,
            "missing": [r for r in requirements if r not in covered],
        }
