# 🌊 clawd voice

A local voice chat interface for talking to multiple AI agents with distinct voices.  
Hold a brain button (or keyboard key) → speak → release → hear the response instantly.

**Repo:** [github.com/clawdbotatg/clawd-voice](https://github.com/clawdbotatg/clawd-voice)

## Features

- **7 AI brains** with distinct voices — Sonnet, Opus, GPT-4o, DeepSeek R1, Qwen3-Coder, Qwen 7b + clawd+ super-context
- **Keyboard PTT** — hold `X C V B N M` or `Space` to activate each brain
- **Browser Web Speech API TTS** — fires on the first 2 words, zero network latency
- **Instant interruption** — hold any key mid-speech to cut off and re-record
- **Sentence-streaming** — TTS fires per sentence as the LLM generates, not after
- **🌊 clawd+ super-context brain** — pulls live nerve cord log, priorities, MEMORY.md, and recent git commits before every query
- **Sonnet + Opus have real tool access** — browser, exec, nerve cord messaging via OpenClaw
- **Shared transcript** — switch between models mid-conversation, context follows you
- **LocalStorage persistence** — sessions survive page refresh, multiple contexts supported
- **NO_REPLY scrubbing** — strips agent control tokens before display or speech
- **Voice-only UI** — no text input, no clutter, just brains and a chat log

## Setup

### Requirements
- macOS
- Python 3.10+
- Chrome (for `webkitSpeechRecognition` + Web Speech TTS)
- [OpenClaw](https://openclaw.ai) gateway running locally (for Sonnet/Opus/clawd+)
- [Ollama](https://ollama.ai) running locally (for Qwen/DeepSeek/Qwen3-Coder)

### Install & run

```bash
git clone https://github.com/clawdbotatg/clawd-voice
cd clawd-voice

# Keys auto-load from ~/.openclaw/openclaw.json if you have OpenClaw installed
# Or set manually:
export OPENAI_API_KEY=sk-...
export OPENCLAW_TOKEN=...
export OPENCLAW_URL=http://127.0.0.1:18789/v1/chat/completions

python3 server.py
```

Open `http://127.0.0.1:7800` in Chrome.

## Keyboard shortcuts

| Key | Brain | Voice |
|-----|-------|-------|
| `X` | 🏠 Qwen 7b (local, fast) | Rishi |
| `C` | 🧠 DeepSeek R1 70b (local, smart) | Eddy |
| `V` | 🧑‍💻 Qwen3-Coder (local, beefy) | Karen |
| `B` | ⚡ GPT-4o | Daniel |
| `N` | 🦞 Sonnet (clawd, full memory + tools) | Samantha |
| `M` | 🧠 Opus (clawd, deepest thinker + tools) | Rocko |
| `Space` | 🌊 clawd+ (super-context, live data) | Samantha |

Hold to record → release to send. Press again mid-speech to interrupt.

## Agents

### Raw models (no tools)
- **Qwen 7b** — fastest local, great for quick questions
- **DeepSeek R1 70b** — chain-of-thought reasoning, slow but thorough
- **Qwen3-Coder** — 51GB local beast, coding-focused
- **GPT-4o** — fast cloud, smart, no memory

### OpenClaw agents (full tool access ✅)
- **🦞 Sonnet** — Claude Sonnet via OpenClaw with Austin's full memory, can use browser/exec/nerve cord
- **🧠 Opus** — Claude Opus via OpenClaw, same tools, deeper reasoning
- **🌊 clawd+** — Sonnet with live context injected: today's nerve cord log, priorities, MEMORY.md, recent git commits

## How it works

```
Hold key → Chrome STT (instant local) → server → LLM stream → Web Speech TTS (fires on word 2)
```

### TTS pipeline
- Web Speech API speaks inline — zero server round-trip
- Fires after first 2 words arrive in the stream
- Subsequent sentences queue and play in order
- Any keypress cancels ongoing speech immediately

### clawd+ context assembly
Before every query, `/stream-clawd` fetches:
1. `MEMORY.md` — Austin's full memory and mission context
2. `TOOLS.md` — nerve cord usage, priorities API
3. Nerve cord log (today's activity)
4. Current priorities from nerve cord
5. Recent git commits from active repos

### NO_REPLY scrubbing
OpenClaw agents sometimes append `NO_REPLY` as a control token. The server scrubs it across token boundaries before emitting to the frontend, and the frontend has a secondary scrub layer.

## Files

- `server.py` — Python HTTP server: LLM routing, context assembly, SSE streaming, TTS
- `index.html` — Single-page frontend: Web Speech STT/TTS, streaming bubbles, keyboard PTT

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (GPT-4o) | auto-loaded from openclaw config |
| `OPENCLAW_TOKEN` | OpenClaw gateway auth token | auto-loaded from openclaw config |
| `OPENCLAW_URL` | OpenClaw gateway URL | `http://127.0.0.1:18789/v1/chat/completions` |
| `OPENCLAW_MODEL` | Default OpenClaw agent model | `openclaw:clawdadsonnet` |

> Keys auto-load from `~/.openclaw/openclaw.json` if OpenClaw is installed — no `.env` needed.
