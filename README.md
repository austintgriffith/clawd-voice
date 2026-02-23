# 🦞 clawd voice

A local voice chat interface for talking to multiple AI agents simultaneously.  
Hold a brain button → speak → release → hear the response.

## Features

- **6 AI brains** with distinct voices — Sonnet, Opus, GPT-4o, 4o-mini, Qwen 7b, Llama 70b
- **Browser-native STT** — Chrome's built-in speech recognition, zero latency
- **macOS `say` TTS** — instant local speech synthesis, distinct voice per model
- **Shared transcript** — switch between models mid-conversation, context follows you
- **LocalStorage persistence** — sessions survive page refresh
- **Multiple contexts** — create new conversations, switch between them

## Setup

### Requirements
- macOS (uses `say` for TTS)
- Python 3.10+
- Chrome (for `webkitSpeechRecognition`)
- [OpenClaw](https://openclaw.ai) gateway running locally (optional — for Sonnet/Opus)
- [Ollama](https://ollama.ai) running locally (optional — for Qwen/Llama)

### Install & run

```bash
# Clone
git clone https://github.com/austingriffith/clawd-voice
cd clawd-voice

# Set env vars (or let it auto-load from ~/.openclaw/openclaw.json)
export OPENAI_API_KEY=sk-...
export OPENCLAW_TOKEN=...   # from openclaw.json > gateway.auth.token
export OPENCLAW_URL=http://127.0.0.1:18789/v1/chat/completions

# Run
python3 server.py
```

Open `http://127.0.0.1:7800` in Chrome.

### Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (for GPT-4o / 4o-mini) | auto-loaded from openclaw config |
| `OPENCLAW_TOKEN` | OpenClaw gateway auth token | auto-loaded from openclaw config |
| `OPENCLAW_URL` | OpenClaw gateway URL | `http://127.0.0.1:18789/v1/chat/completions` |
| `OPENCLAW_MODEL` | Default OpenClaw agent | `openclaw:clawdadsonnet` |

> **Note:** If you have OpenClaw installed, API keys are auto-loaded from `~/.openclaw/openclaw.json` — no `.env` file needed.

## Agents & voices

| Brain | Model | Voice | Speed |
|-------|-------|-------|-------|
| 🏠 Qwen 7b | `qwen2.5:7b` (Ollama) | Rishi | ~0.4s |
| 🚀 4o-mini | `gpt-4o-mini` | Eddy | ~0.3s |
| 🦙 Llama 70b | `llama3.3:latest` (Ollama) | Karen | ~2.5s |
| ⚡ GPT-4o | `gpt-4o` | Daniel | ~0.6s |
| 🦞 Sonnet | `claude-sonnet-4-6` via OpenClaw | Samantha | ~1.5s |
| 🧠 Opus | `claude-opus-4-6` via OpenClaw | Rocko | ~3s |

## How it works

```
voice → Chrome STT (instant) → server /think → LLM → server /speak → macOS say → audio
```

Switching models mid-conversation: each new brain receives a transcript of the prior conversation so it can pick up seamlessly (Option C shared context).

## Files

- `server.py` — Python HTTP server, handles LLM routing + TTS
- `index.html` — Single-page frontend, all JS inline
