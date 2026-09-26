"""
Web gateway — turns the assistant into a live web app / JSON API you can host
anywhere. See README.md for how to put this on a real domain with HTTPS.

Run locally:
    uvicorn interfaces.web.server:app --host 0.0.0.0 --port 8000 --reload
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings, DB_PATH, SKILLS_DIR, JOBS_PATH
from core.memory import Memory
from core.skills import SkillLibrary
from core.agent import Agent
from core.scheduler import TaskScheduler

app = FastAPI(title="Personal AI Assistant")
agent = Agent(settings, Memory(DB_PATH), SkillLibrary(SKILLS_DIR))

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_report_log: list = []  # holds outputs from scheduled jobs, e.g. daily reports


def notify(session_id: str, text: str):
    _report_log.append({"session_id": session_id, "text": text})


scheduler = TaskScheduler(JOBS_PATH, agent, notify)
scheduler.start()


class ChatRequest(BaseModel):
    session_id: str = "web-default"
    message: str


class ScheduleRequest(BaseModel):
    session_id: str = "web-default"
    hour: int
    minute: int = 0
    prompt: str
    name: str = ""


class FactRequest(BaseModel):
    key: str
    value: str


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Message can't be empty.")
    reply = agent.handle_message(req.session_id, req.message)
    return {"reply": reply}


@app.post("/api/learn")
def learn(session_id: str = "web-default"):
    return agent.learn_skill_from_recent(session_id)


@app.get("/api/profile")
def profile():
    return agent.memory.get_profile()


@app.post("/api/remember")
def remember(req: FactRequest):
    if not req.key.strip():
        raise HTTPException(400, "Fact needs a name.")
    agent.remember_fact(req.key.strip(), req.value.strip())
    return {"ok": True}


@app.get("/api/skills")
def list_skills():
    return agent.skills.list_skills()


@app.delete("/api/skills/{slug}")
def delete_skill(slug: str):
    if not agent.skills.delete_skill(slug):
        raise HTTPException(404, "Skill not found.")
    return {"ok": True}


@app.get("/api/schedule")
def list_schedule():
    return scheduler.list_jobs()


@app.post("/api/schedule")
def create_schedule(req: ScheduleRequest):
    if not (0 <= req.hour <= 23 and 0 <= req.minute <= 59):
        raise HTTPException(400, "Time must be a valid 24-hour hour/minute.")
    if not req.prompt.strip():
        raise HTTPException(400, "Task needs a description.")
    return scheduler.add_daily_job(req.session_id, req.hour, req.minute, req.prompt, req.name)


@app.delete("/api/schedule/{job_id}")
def delete_schedule(job_id: str):
    if not scheduler.remove_job(job_id):
        raise HTTPException(404, "Scheduled task not found.")
    return {"ok": True}


@app.get("/api/reports")
def reports():
    """Latest outputs from scheduled jobs (e.g. daily reports); the web UI polls this."""
    return _report_log[-50:]


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": settings.provider, "model": settings.model}
