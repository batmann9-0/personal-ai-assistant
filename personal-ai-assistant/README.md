# Personal AI Assistant

A self-improving personal assistant that:

- **Remembers you across sessions** — every conversation is saved, and it keeps a running *profile* of facts it learns about you.
- **Writes its own skills** — after a complex task, tell it `/learn` and it distills what it just did into a reusable playbook for next time.
- **Is model-agnostic** — switch between Anthropic, OpenAI, or any model on OpenRouter by changing three lines in `.env`. No code changes.
- **Follows you everywhere** — the same agent is reachable from a terminal CLI, Telegram, Discord, or a web app.
- **Runs automated tasks** — schedule things like "send me a daily report at 8am."
- **Has a real web UI** — a four-page app (Chat / Profile / Skills / Schedule) at `/`, not just a JSON API: markdown-rendered replies, a typing indicator, empty/loading/error states, and delete confirmations for skills and scheduled tasks.

## How it's built

```
config.py               # all settings, loaded from .env
core/
  providers.py           # Anthropic / OpenAI / OpenRouter — swap with one env var
  memory.py               # SQLite: conversation history + long-term "who you are" profile
  skills.py                # self-written, reusable task playbooks (data/skills/*.json)
  agent.py                  # orchestrates provider + memory + skills for every interface
  scheduler.py               # cron-style recurring tasks, persisted to data/jobs.json
interfaces/
  cli.py                  # terminal chat (Typer + rich)
  telegram_bot.py          # Telegram gateway
  discord_bot.py            # Discord gateway
  web/server.py               # FastAPI JSON API + simple chat page — your "live web app"
data/                     # created automatically: memory.sqlite3, skills/, jobs.json
```

Every interface builds the same `Agent` from the same `Memory`/`SkillLibrary`, so a fact you teach it in Telegram is remembered when you open the web app later (as long as they share the same `data/` folder).

## 1. Local setup

Requires Python 3.10+.

```bash
cd personal-ai-assistant
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```ini
LLM_PROVIDER=anthropic        # or: openai / openrouter
LLM_MODEL=claude-sonnet-4-6   # any model name your provider/OpenRouter supports
LLM_API_KEY=sk-...
```

That's the entire "switch LLMs" mechanism — change `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY`, restart, done. OpenRouter is useful if you want to try many models (Llama, Gemini, Mistral, etc.) with one key: set `LLM_PROVIDER=openrouter` and `LLM_MODEL` to whatever OpenRouter calls it, e.g. `openrouter/anthropic/claude-sonnet-4.6`.

## 2. Talk to it from the terminal

```bash
python -m interfaces.cli chat
```

Other handy commands:

```bash
python -m interfaces.cli profile                 # see what it's learned about you
python -m interfaces.cli remember timezone PKT    # manually teach it a fact
python -m interfaces.cli skills                   # list self-written skills
python -m interfaces.cli schedule "daily report" --hour 8 --minute 0
```

Inside a chat session, type `/learn` right after finishing something non-trivial — it will decide whether the approach is worth saving as a skill, and if so, write it to `data/skills/`.

## 3. Connect Telegram / Discord

**Telegram:** message `@BotFather` → `/newbot` → paste the token into `TELEGRAM_BOT_TOKEN` in `.env`, then:
```bash
python -m interfaces.telegram_bot
```

**Discord:** create an app + bot at the [Discord Developer Portal](https://discord.com/developers/applications), enable "Message Content Intent", paste the token into `DISCORD_BOT_TOKEN`, invite the bot to your server, then:
```bash
python -m interfaces.discord_bot
```

Both run continuously and share the same `data/` memory as the CLI and web app.

## 4. Scheduling automated tasks

`core/scheduler.py` stores jobs in `data/jobs.json` and re-registers them whenever a process starts. Add a job from the CLI, the web API (`POST /api/schedule`), or in code — e.g. a daily report delivered by whichever gateway is running:

```bash
python -m interfaces.cli schedule "Summarize my day and suggest 3 priorities for tomorrow" --hour 20 --minute 0
```

Important: a scheduled job only fires while **some** process is alive to run it. For it to reliably fire every day, deploy the web app (or a bot) 24/7 — see below.

---

## 5. Running it 24/7 on a cheap cloud server

Any $4–6/month VPS works (Hetzner CX22, DigitalOcean Basic Droplet, Oracle free tier, Vultr, etc.), Ubuntu 22.04+.

### Option A — Docker (recommended, simplest to keep alive)

```bash
# on the server, after installing Docker + Docker Compose
git clone <your-repo-or-scp-the-folder> personal-ai-assistant
cd personal-ai-assistant
cp .env.example .env && nano .env     # fill in your keys

docker compose up -d web                      # always-on web app + API
docker compose --profile telegram up -d       # optional: also run the Telegram bot
docker compose --profile discord up -d        # optional: also run the Discord bot
```

`data/` is mounted as a volume, so memory and skills persist across restarts/redeploys.

### Option B — plain systemd (no Docker)

```bash
sudo apt update && sudo apt install -y python3-venv
git clone <your-repo> /opt/assistant && cd /opt/assistant
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
```

Create `/etc/systemd/system/assistant-web.service`:

```ini
[Unit]
Description=Personal AI Assistant - Web
After=network.target

[Service]
WorkingDirectory=/opt/assistant
ExecStart=/opt/assistant/.venv/bin/uvicorn interfaces.web.server:app --host 0.0.0.0 --port 8000
Restart=always
EnvironmentFile=/opt/assistant/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now assistant-web
# same pattern for interfaces.telegram_bot / interfaces.discord_bot as separate services
```

---

## 6. Making it a live web app (public URL + HTTPS)

The FastAPI app in `interfaces/web/server.py` already IS a web app — the steps below just put it on a real domain safely.

**Fastest path — a PaaS (no server admin at all):**
Push this folder to a GitHub repo, then deploy on **Railway**, **Render**, or **Fly.io**:
- Point it at the `Dockerfile` (all three support "deploy from Dockerfile").
- Set the same environment variables from `.env` in the platform's dashboard.
- Attach a persistent volume mounted at `/app/data` (Railway/Fly both support volumes) so memory isn't wiped on redeploy.
- The platform gives you a public HTTPS URL immediately — done.

**Full control — your own VPS + domain:**

1. Point your domain's DNS `A` record at the server's IP.
2. Run the app on port 8000 (Docker or systemd, above).
3. Install Nginx as a reverse proxy:

```nginx
# /etc/nginx/sites-available/assistant
server {
    server_name assistant.yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/assistant /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d assistant.yourdomain.com     # free HTTPS cert, auto-renews
```

Your assistant is now live at `https://assistant.yourdomain.com`, reachable from any browser or phone, while the CLI/Telegram/Discord gateways keep working against the same memory on the same box.

**Note on security:** the web app has no login by default — anyone with the URL can chat as "you" and see the chat UI (though not your raw memory file). Before sharing the URL, add basic auth in Nginx (`auth_basic`) or a simple API-key check in `server.py` if it won't stay private.

---

## Extending it

- **Add a provider:** implement a new `LLMProvider` subclass in `core/providers.py` and register it in `get_provider()`.
- **Change what counts as "worth learning":** edit the instruction prompt in `SkillLibrary.create_skill_from_transcript`.
- **Smarter memory search:** `Memory.search()` is deliberately simple (keyword match) so it has zero extra dependencies; swap in an embeddings-based vector search there if you want semantic recall.
- **More gateways:** copy the pattern in `interfaces/telegram_bot.py` — every gateway just needs to call `agent.handle_message(session_id, text)` and send back the reply.

## A note on where this was built

This project was generated in a sandboxed Linux environment, then packaged as a zip. Extract it into your own project folder (e.g. `Task managment app/personal-ai-assistant`) and follow the setup steps above from there.
