"""
Self-improving 'skills' system.

A skill is a small reusable playbook the assistant writes for ITSELF after
finishing a non-trivial task, so next time something similar comes up it can
follow the same successful approach instead of starting from scratch. This is
what makes the assistant self-improving rather than static.

Skills are stored as plain JSON files under data/skills/, so you can read,
hand-edit, or delete any of them at any time.
"""
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional


class SkillLibrary:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir

    def list_skills(self) -> List[Dict]:
        skills = []
        for f in sorted(self.skills_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                data["slug"] = f.stem  # stable id the UI can use to reference/delete this skill
                skills.append(data)
            except json.JSONDecodeError:
                continue
        return skills

    def delete_skill(self, slug: str) -> bool:
        path = self.skills_dir / f"{slug}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def find_matching(self, user_text: str) -> Optional[Dict]:
        text = user_text.lower()
        best, best_score = None, 0
        for skill in self.list_skills():
            score = sum(1 for kw in skill.get("triggers", []) if kw.lower() in text)
            if score > best_score:
                best, best_score = skill, score
        return best

    def save_skill(self, name: str, description: str, triggers: List[str], playbook: str) -> Path:
        slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or f"skill_{int(time.time())}"
        path = self.skills_dir / f"{slug}.json"
        data = {
            "name": name,
            "description": description,
            "triggers": triggers,
            "playbook": playbook,
            "created_ts": time.time(),
        }
        path.write_text(json.dumps(data, indent=2))
        return path

    def create_skill_from_transcript(self, provider, transcript: str) -> Dict:
        """
        Ask the LLM to reflect on a just-completed task and, if it's genuinely
        reusable, distill it into a skill: a name, trigger keywords, and a
        step-by-step playbook the future assistant can follow.
        """
        instruction = (
            "You just finished helping the user with a task. Read the transcript "
            "below and, ONLY IF it represents a reusable multi-step approach worth "
            "remembering, respond with strict JSON: "
            '{"worth_saving": true, "name": "...", "description": "...", '
            '"triggers": ["keyword1", "keyword2"], "playbook": "numbered steps as one string"}. '
            "If it is too trivial or one-off to be worth saving, respond with "
            '{"worth_saving": false}. Respond with JSON only, nothing else, no markdown fences.\n\n'
            f"TRANSCRIPT:\n{transcript}"
        )
        raw = provider.chat([{"role": "user", "content": instruction}], max_tokens=600).strip()
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            return {"worth_saving": False}
        if result.get("worth_saving"):
            self.save_skill(
                result["name"], result["description"], result.get("triggers", []), result["playbook"]
            )
        return result
