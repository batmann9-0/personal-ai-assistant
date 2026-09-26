"""
Polished terminal chat interface.

Usage:
    python -m interfaces.cli chat
    python -m interfaces.cli profile
    python -m interfaces.cli remember timezone PKT
    python -m interfaces.cli skills
    python -m interfaces.cli schedule "write me a daily report" --hour 8 --minute 0
"""
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from config import settings, DB_PATH, SKILLS_DIR, JOBS_PATH
from core.memory import Memory
from core.skills import SkillLibrary
from core.agent import Agent
from core.scheduler import TaskScheduler

app = typer.Typer(help="Personal AI Assistant — terminal interface")
console = Console()
SESSION_ID = "cli-default"


def _build_agent() -> Agent:
    return Agent(settings, Memory(DB_PATH), SkillLibrary(SKILLS_DIR))


@app.command()
def chat():
    """Start an interactive chat session in your terminal."""
    agent = _build_agent()
    console.print(Panel.fit(
        f"[bold]Personal AI Assistant[/bold]\nProvider: {settings.provider} | Model: {settings.model}\n"
        "Type 'exit' to quit, or '/learn' to save the last task as a reusable skill.",
        border_style="cyan",
    ))
    while True:
        user_text = console.input("[bold green]you>[/bold green] ")
        if user_text.strip().lower() in ("exit", "quit"):
            break
        if user_text.strip() == "/learn":
            result = agent.learn_skill_from_recent(SESSION_ID)
            if result.get("worth_saving"):
                console.print(f"[cyan]Saved new skill:[/cyan] {result['name']}")
            else:
                console.print("[yellow]Nothing distinct enough to save as a skill yet.[/yellow]")
            continue
        reply = agent.handle_message(SESSION_ID, user_text)
        console.print(Markdown(reply))


@app.command()
def profile():
    """Show what the assistant currently knows about you."""
    agent = _build_agent()
    console.print(Panel(agent.memory.profile_as_text(), title="Your profile"))


@app.command()
def remember(key: str, value: str):
    """Manually teach the assistant a fact, e.g.: remember timezone PKT"""
    agent = _build_agent()
    agent.remember_fact(key, value)
    console.print(f"[green]Saved:[/green] {key} = {value}")


@app.command()
def skills():
    """List all skills the assistant has learned so far."""
    agent = _build_agent()
    saved = agent.skills.list_skills()
    if not saved:
        console.print("[yellow]No skills learned yet — use /learn after a complex task.[/yellow]")
    for s in saved:
        console.print(Panel(s["playbook"], title=f"{s['name']} — {s['description']}"))


@app.command()
def schedule(prompt: str, hour: int = typer.Option(8), minute: int = typer.Option(0)):
    """Schedule a recurring daily task, e.g.: schedule "daily report" --hour 8"""
    agent = _build_agent()
    sched = TaskScheduler(JOBS_PATH, agent, notify=lambda sid, text: console.print(Markdown(text)))
    sched.add_daily_job(SESSION_ID, hour, minute, prompt)
    console.print(f"[green]Scheduled daily at {hour:02d}:{minute:02d}:[/green] {prompt}")
    console.print("[yellow]Note: this only fires while a process is running — deploy the web app "
                   "or a bot 24/7 (see README) for scheduled jobs to actually run.[/yellow]")


if __name__ == "__main__":
    app()
