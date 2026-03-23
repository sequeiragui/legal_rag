import os
import json
import uuid
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="ProcessKeeper")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ─── Models ───

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ExtractRequest(BaseModel):
    session_id: str
    graph_type: str = "flowchart"  # "flowchart" or "sequential"

class SaveProcessRequest(BaseModel):
    session_id: str
    title: str
    graph_type: str = "flowchart"

# ─── Session storage (in-memory + file persistence) ───

sessions: dict = {}

def get_session(session_id: str) -> dict:
    if session_id not in sessions:
        sessions[session_id] = {
            "id": session_id,
            "messages": [],
            "created": time.time()
        }
    return sessions[session_id]

# ─── System prompts ───

INTERVIEW_SYSTEM = """You are ProcessKeeper, an AI designed to capture institutional knowledge by documenting processes and procedures from experienced team members.

Your goal: Have a natural conversation to understand a process someone does, then help structure it into a clear, complete procedure.

How to behave:
- Start by asking what process they'd like to document
- Listen to their description and ask smart follow-up questions when needed
- Probe for: decision points (if X then Y), edge cases, tools/systems used, who is involved, timing/frequency
- Ask about what could go wrong and how they handle it
- When you feel the process is well-captured, tell them you have enough to generate a graph
- Keep it conversational and friendly — like a colleague taking notes

IMPORTANT: Keep your responses concise (2-4 sentences typically). Don't overwhelm with questions — one or two at a time. Be natural.

Do NOT generate the graph yourself. Just have the conversation. The graph extraction happens separately."""

EXTRACT_FLOWCHART_SYSTEM = """You are a process analyst. Given a conversation where someone described a procedure, extract it into a structured flowchart.

Return ONLY valid JSON (no markdown fences) with this structure:
{
  "title": "Process name",
  "summary": "One-line description",
  "nodes": [
    {
      "id": "1",
      "label": "Short step description",
      "type": "start|step|decision|end",
      "details": "Longer explanation if needed"
    }
  ],
  "edges": [
    {
      "from": "1",
      "to": "2",
      "label": ""
    }
  ]
}

Rules:
- "start" node: always the first node
- "end" node(s): terminal states
- "decision" nodes: have exactly 2 outgoing edges, one labeled "Yes" and one "No"
- "step" nodes: regular process steps
- Keep labels SHORT (5-8 words max)
- Use details field for longer explanations
- Capture ALL steps, decisions, and edge cases mentioned
- IDs should be simple numbers as strings: "1", "2", "3", etc."""

EXTRACT_SEQUENTIAL_SYSTEM = """You are a process analyst. Given a conversation where someone described a procedure, extract it into a sequential process diagram.

Return ONLY valid JSON (no markdown fences) with this structure:
{
  "title": "Process name",
  "summary": "One-line description",
  "nodes": [
    {
      "id": "1",
      "label": "Short step description",
      "type": "step",
      "details": "Longer explanation if needed",
      "phase": "Phase/stage name (optional)"
    }
  ],
  "edges": [
    {
      "from": "1",
      "to": "2",
      "label": ""
    }
  ]
}

Rules:
- Linear sequence of steps, no branching
- If there are decision points, fold them into the step details
- Group steps into phases if natural groupings exist
- Keep labels SHORT (5-8 words max)
- IDs should be simple numbers as strings: "1", "2", "3", etc."""

# ─── Routes ───

@app.get("/")
async def root():
    return FileResponse("static/folio.html")

@app.post("/chat")
async def chat(req: ChatRequest):
    session = get_session(req.session_id)
    session["messages"].append({"role": "user", "content": req.message})

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=INTERVIEW_SYSTEM,
        messages=session["messages"]
    )

    assistant_text = response.content[0].text
    session["messages"].append({"role": "assistant", "content": assistant_text})

    return {"reply": assistant_text, "message_count": len(session["messages"])}

@app.post("/extract")
async def extract_graph(req: ExtractRequest):
    session = get_session(req.session_id)
    if len(session["messages"]) < 2:
        raise HTTPException(400, "Not enough conversation to extract a process")

    conversation_text = "\n".join(
        f"{'Senior' if m['role'] == 'user' else 'Interviewer'}: {m['content']}"
        for m in session["messages"]
    )

    system = EXTRACT_FLOWCHART_SYSTEM if req.graph_type == "flowchart" else EXTRACT_SEQUENTIAL_SYSTEM

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Here is the conversation:\n\n{conversation_text}\n\nExtract the process into the required JSON format."
        }]
    )

    raw = response.content[0].text.strip()
    # Clean markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        graph_data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(500, "Failed to parse graph structure from AI response")

    graph_data["graph_type"] = req.graph_type
    return graph_data

@app.post("/save")
async def save_process(req: SaveProcessRequest):
    session = get_session(req.session_id)
    if len(session["messages"]) < 2:
        raise HTTPException(400, "Not enough conversation")

    # Extract the graph
    conversation_text = "\n".join(
        f"{'Senior' if m['role'] == 'user' else 'Interviewer'}: {m['content']}"
        for m in session["messages"]
    )

    system = EXTRACT_FLOWCHART_SYSTEM if req.graph_type == "flowchart" else EXTRACT_SEQUENTIAL_SYSTEM

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Here is the conversation:\n\n{conversation_text}\n\nExtract the process into the required JSON format."
        }]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    graph_data = json.loads(raw)
    graph_data["graph_type"] = req.graph_type

    process = {
        "id": str(uuid.uuid4())[:8],
        "title": req.title,
        "graph": graph_data,
        "conversation": session["messages"],
        "created": time.time()
    }

    filepath = DATA_DIR / f"{process['id']}.json"
    filepath.write_text(json.dumps(process, indent=2))

    return {"id": process["id"], "title": process["title"]}

@app.get("/processes")
async def list_processes():
    processes = []
    for f in DATA_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            processes.append({
                "id": data["id"],
                "title": data["title"],
                "created": data["created"],
                "node_count": len(data["graph"].get("nodes", [])),
                "graph_type": data["graph"].get("graph_type", "flowchart")
            })
        except Exception:
            continue
    processes.sort(key=lambda x: x["created"], reverse=True)
    return {"processes": processes}

@app.get("/processes/{process_id}")
async def get_process(process_id: str):
    filepath = DATA_DIR / f"{process_id}.json"
    if not filepath.exists():
        raise HTTPException(404, "Process not found")
    return json.loads(filepath.read_text())

@app.delete("/processes/{process_id}")
async def delete_process(process_id: str):
    filepath = DATA_DIR / f"{process_id}.json"
    if filepath.exists():
        filepath.unlink()
    return {"deleted": True}

app.mount("/static", StaticFiles(directory="static"), name="static")