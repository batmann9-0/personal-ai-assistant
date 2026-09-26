"""
Simple persistent task scheduler — e.g. "send me a daily report at 8am".

Jobs are stored in data/jobs.json so they survive restarts. Whichever process
is running (web server, or a bot) loads and re-registers them on startup, so
as long as ONE of your deployed processes is always on, scheduled jobs fire.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class TaskScheduler:
    def __init__(self, jobs_path: Path, agent, notify: Callable[[str, str], None]):
        """
        agent: the Agent instance used to actually generate the report/task output.
        notify(session_id, text): delivers the result — e.g. sends a Telegram/
        Discord message, or (for the web app) appends it to a log the page polls.
        """
        self.jobs_path = jobs_path
        self.agent = agent
        self.notify = notify
        self.scheduler = BackgroundScheduler()
        self._jobs: List[Dict] = self._load_jobs()

    def _load_jobs(self) -> List[Dict]:
        if self.jobs_path.exists():
            jobs = json.loads(self.jobs_path.read_text())
            for job in jobs:
                job.setdefault("id", str(uuid.uuid4()))  # backfill ids for older job files
            return jobs
        return []

    def _save_jobs(self):
        self.jobs_path.write_text(json.dumps(self._jobs, indent=2))

    def add_daily_job(self, session_id: str, hour: int, minute: int, prompt: str, name: str = "") -> Dict:
        job = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "hour": hour,
            "minute": minute,
            "prompt": prompt,
            "name": name or prompt[:40],
        }
        self._jobs.append(job)
        self._save_jobs()
        self._register(job)
        return job

    def remove_job(self, job_id: str) -> bool:
        match = next((j for j in self._jobs if j["id"] == job_id), None)
        if not match:
            return False
        self._jobs = [j for j in self._jobs if j["id"] != job_id]
        self._save_jobs()
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass  # job may not have been registered yet in this process
        return True

    def _register(self, job: Dict):
        def run():
            reply = self.agent.handle_message(job["session_id"], job["prompt"])
            self.notify(job["session_id"], reply)

        self.scheduler.add_job(
            run,
            CronTrigger(hour=job["hour"], minute=job["minute"]),
            id=job["id"],
            replace_existing=True,
        )

    def start(self):
        for job in self._jobs:
            self._register(job)
        self.scheduler.start()

    def list_jobs(self) -> List[Dict]:
        return self._jobs
