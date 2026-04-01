# a2a-mqtt

Example multi-agent setup using the **Strands Agent SDK** with **A2A** (Agent-to-Agent) JSON-RPC between processes, **MQTT** for live progress in the UI, and **YAML + environment**-driven model configuration (Amazon Bedrock by default; OpenAI or Ollama optional).

**Repository:** [github.com/AliasgharArabi/a2a-mqtt](https://github.com/AliasgharArabi/a2a-mqtt)

## What runs where

| Component | Entry | Port | Role |
|-----------|--------|------|------|
| Researcher | `python workers/researcher.py` | 9101 | A2A worker — research outline |
| Writer | `python workers/writer.py` | 9102 | A2A worker — article draft |
| Orchestrator | `python orchestrator/agent.py` | 9200 | A2A coordinator; calls researcher & writer |
| Web UI | `npm run dev` | 3000 (`PORT`) | React + Vite; Express dev server; optional MQTT broker on 1883 |

The UI sends **A2A** `message/send` to the orchestrator (`ORCHESTRATOR_A2A_URL`, default `http://127.0.0.1:9200/`).

## Prerequisites

- **Node.js** 18+ (for the UI / dev server)
- **Python** 3.11+
- **Model backend** — default path is **Amazon Bedrock** (AWS credentials / profile and region). For local alternatives, set `STRANDS_MODEL_PROVIDER` to `openai` or `ollama` and configure keys/host as described in [`model_env.py`](model_env.py).

## Setup

**Python**

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Node**

```bash
npm install
```

**Environment**

- Copy [`.env.example`](.env.example) to `.env.local` if you use UI env vars (e.g. `GEMINI_API_KEY`, `APP_URL` for hosted setups).
- Per-agent Bedrock model IDs and `max_tokens` are in [`agents.yaml`](agents.yaml); env vars override them (see comments in `agents.yaml` and `model_env.py`).

## Run locally

Start the three Python A2A servers first, then the UI (four terminals):

```bash
# Terminal 1
source .venv/bin/activate && python workers/researcher.py

# Terminal 2
source .venv/bin/activate && python workers/writer.py

# Terminal 3
source .venv/bin/activate && python orchestrator/agent.py

# Terminal 4
npm run dev
```

Open **http://localhost:3000** (unless `PORT` is set).

### MQTT

The dev server can embed an MQTT broker on **1883** (`UI_MQTT_PORT`). Set `EMBEDDED_MQTT=0` or `false` to use an external broker. `MQTT_ORG` defaults to `demo-org`.

## Project layout (high level)

- `orchestrator/` — orchestrator agent + A2A server + streaming UI patch  
- `workers/` — researcher and writer A2A servers  
- `transport/` — MQTT / progress helpers  
- `src/` — React chat UI  
- `server.ts` — Express + Vite middleware, MQTT, orchestrator proxy  

For deeper stack notes (AWS profile resolution, Ollama/OpenAI), see [`model_env.py`](model_env.py).
