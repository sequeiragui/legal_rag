# ProcessKeeper

**Capture institutional knowledge before it walks out the door.**

ProcessKeeper is an AI-powered tool that interviews team members about their processes and procedures, then automatically generates visual flowcharts and sequential diagrams. When a senior leaves your team, their knowledge stays — documented and visual.

## How it works

1. **Chat** — Describe a process you do. The AI asks smart follow-up questions to capture decision points, edge cases, tools used, and who's involved.
2. **Generate** — Choose between a **flowchart** (with decision branches) or a **sequential diagram** (step-by-step), and the AI extracts a structured graph from the conversation.
3. **Save** — Store the process in your team's library. Download as SVG anytime.

## Quick Start (Docker)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env and add your Anthropic API key

# 2. Build and run
docker-compose up --build -d

# 3. Open
# http://localhost:8000
```

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and add your Anthropic API key

# 3. Run
uvicorn rag:app --reload --port 8000

# 4. Open http://localhost:8000
```

## Deploy to EC2

```bash
# On your EC2 instance:
git clone <your-repo> processkeeper
cd processkeeper
cp .env.example .env
nano .env  # add your ANTHROPIC_API_KEY

docker-compose up --build -d

# The app runs on port 8000
# Make sure your security group allows inbound on 8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve the frontend |
| POST | `/chat` | Send a message in a session |
| POST | `/extract` | Extract a process graph from a session |
| POST | `/save` | Save a process to the library |
| GET | `/processes` | List all saved processes |
| GET | `/processes/{id}` | Get a specific saved process |
| DELETE | `/processes/{id}` | Delete a saved process |

## Tech Stack

- **Backend**: Python, FastAPI
- **AI**: Claude (Anthropic API)
- **Frontend**: Vanilla HTML/CSS/JS (no build step)
- **Storage**: JSON files (no database needed)
- **Deploy**: Docker