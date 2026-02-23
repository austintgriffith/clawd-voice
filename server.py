#!/usr/bin/env python3
"""
Voice chat server — mic → STT → OpenClaw → smallTTS → audio
"""
import os
import sys
import json
import subprocess
import tempfile
import time
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

OPENCLAW_URL = "http://127.0.0.1:18789/v1/chat/completions"
OPENCLAW_TOKEN = os.environ.get("OPENCLAW_TOKEN", "")
OPENCLAW_MODEL = "openclaw:clawdadsonnet"

# LLM backend config
# Options: "ollama", "openai", "openclaw"
# "openclaw" = routes through the full OpenClaw agent (clawd with memory + tools)
LLM_BACKEND = "openclaw"
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen2.5:7b"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o"
OPENCLAW_CHAT_URL   = os.environ.get("OPENCLAW_URL", "http://127.0.0.1:18789/v1/chat/completions")
OPENCLAW_CHAT_TOKEN = os.environ.get("OPENCLAW_TOKEN", "")
OPENCLAW_CHAT_MODEL = os.environ.get("OPENCLAW_MODEL", "openclaw:clawdadsonnet")

# Used only for ollama/openai backends (openclaw has its own full system prompt)
SYSTEM_PROMPT = """You are clawd, Austin Griffith's personal AI voice assistant.
Austin works at the Ethereum Foundation on Builder Growth — he created scaffold-eth and BuidlGuidl.
Keep ALL responses SHORT — 1-3 sentences max.
You are talking out loud so NEVER use markdown, bullet points, headers, or emoji.
Be conversational, warm, and direct."""

# Injected before every openclaw voice request so it knows to be brief + voice-friendly
VOICE_PREFIX = "[VOICE MODE] Respond in 1-3 short spoken sentences. No markdown, no bullet points, no emoji. Be warm and direct."
SMALLTTS_DIR = os.path.expanduser("~/smalltts")
PORT = 7800

# Conversation history for context
conversation_history = []

def call_llm(user_text: str, backend: str = None, model: str = None, history: list = None) -> str:
    """Send text to LLM, get response. Backend/model/history can be overridden per-request."""
    backend = backend or LLM_BACKEND

    # Use provided per-agent history from frontend, or fall back to server-side history
    if history is not None:
        msgs = history  # already includes the user message
    else:
        conversation_history.append({"role": "user", "content": user_text})
        msgs = conversation_history

    if backend == "openclaw":
        use_model = model or OPENCLAW_CHAT_MODEL
        messages = list(msgs)
        messages[-1] = {"role": "user", "content": f"{VOICE_PREFIX}\n\n{messages[-1]['content']}"}
        payload = json.dumps({"model": use_model, "messages": messages, "stream": False}).encode()
        req = Request(OPENCLAW_CHAT_URL, data=payload, headers={
            "Authorization": f"Bearer {OPENCLAW_CHAT_TOKEN}",
            "Content-Type": "application/json"
        })
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

    elif backend == "openai":
        use_model = model or OPENAI_MODEL
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + msgs
        api_key = os.environ.get("OPENAI_API_KEY", "")
        payload = json.dumps({"model": use_model, "messages": messages, "stream": False, "max_tokens": 150}).encode()
        req = Request(OPENAI_URL, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        })
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

    else:
        # Ollama
        use_model = model or OLLAMA_MODEL
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + msgs
        payload = json.dumps({"model": use_model, "messages": messages, "stream": False}).encode()
        req = Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

    reply = data["choices"][0]["message"]["content"]
    # Only update server-side history if not using frontend-managed history
    if history is None:
        conversation_history.append({"role": "assistant", "content": reply})
    return reply


def clean_for_tts(text: str) -> str:
    """Strip emoji and non-ASCII characters that break espeak."""
    import re
    # Remove emoji and other non-latin unicode
    text = text.encode("ascii", "ignore").decode("ascii")
    # Clean up leftover whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text or "I have a response but could not speak it."


DEFAULT_VOICE = "Samantha"
DEFAULT_RATE = 210  # words per minute (default is 175)

ALLOWED_VOICES = {
    "Eddy (English (US))", "Reed (English (US))", "Rocko (English (US))",
    "Flo (English (US))", "Sandy (English (US))", "Shelley (English (US))",
    "Samantha", "Daniel", "Eddy (English (UK))", "Reed (English (UK))",
    "Karen", "Moira", "Rishi", "Tessa",
}

def synthesize_speech(text: str, voice: str = DEFAULT_VOICE, rate: int = DEFAULT_RATE) -> bytes:
    """Use macOS `say` for near-instant TTS. Returns WAV bytes."""
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name

    result = subprocess.run(
        ["say", "-v", voice, "-r", str(rate), text, "-o", out_path, "--data-format=LEF32@22050"],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        raise RuntimeError(f"say failed: {result.stderr}")

    with open(out_path, "rb") as f:
        wav_bytes = f.read()

    os.unlink(out_path)
    return wav_bytes


def transcribe_whisper(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio using OpenAI Whisper API."""
    import urllib.parse
    
    # Write audio to temp file
    ext = "webm" if "webm" in mime_type else "wav"
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
        f.write(audio_bytes)
        audio_path = f.name
    
    try:
        # Use curl to call Whisper API (avoid multipart encoding complexity)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        result = subprocess.run([
            "curl", "-s",
            "https://api.openai.com/v1/audio/transcriptions",
            "-H", f"Authorization: Bearer {api_key}",
            "-F", f"file=@{audio_path};type={mime_type}",
            "-F", "model=whisper-1",
            "-F", "response_format=text"
        ], capture_output=True, text=True, timeout=30)
        
        return result.stdout.strip()
    finally:
        os.unlink(audio_path)


class VoiceChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_file("index.html", "text/html")
        elif self.path == "/health":
            self.send_json({"status": "ok"})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/chat":
            self.handle_chat()
        elif self.path == "/think":
            self.handle_think()
        elif self.path == "/speak":
            self.handle_speak()
        elif self.path == "/reset":
            self.handle_reset()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Audio-Type")
        self.end_headers()

    def handle_chat(self):
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            if "audio" in content_type or "application/octet-stream" in content_type:
                # Audio input — transcribe first
                audio_type = self.headers.get("X-Audio-Type", content_type)
                print(f"[transcribe] got audio ({len(body)} bytes, {audio_type})")
                user_text = transcribe_whisper(body, audio_type)
                print(f"[transcribe] → '{user_text}'")
                if not user_text:
                    self.send_json({"error": "Could not transcribe audio"}, 400)
                    return
            else:
                # JSON text input
                data = json.loads(body)
                user_text = data.get("text", "").strip()
                if not user_text:
                    self.send_json({"error": "No text provided"}, 400)
                    return

            print(f"[llm] sending: {user_text}")
            t0 = time.time()
            reply_text = call_llm(user_text)
            print(f"[llm] done in {time.time()-t0:.2f}s: {reply_text[:100]}...")

            print(f"[tts] synthesizing...")
            t1 = time.time()
            wav_bytes = synthesize_speech(clean_for_tts(reply_text))
            print(f"[tts] done in {time.time()-t1:.2f}s ({len(wav_bytes)} bytes)")

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_bytes)))
            self.send_header("X-Reply-Text", reply_text[:500].encode("ascii", "replace").decode("ascii"))
            self.send_header("X-User-Text", user_text[:200].encode("ascii", "replace").decode("ascii"))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", "X-Reply-Text, X-User-Text")
            self.end_headers()
            self.wfile.write(wav_bytes)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def handle_think(self):
        """Phase 1: text in → LLM reply text out (fast)."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            user_text = data.get("text", "").strip()
            backend   = data.get("backend", LLM_BACKEND)
            model     = data.get("model", None)
            history   = data.get("history", None)  # per-agent history from frontend
            if not user_text:
                self.send_json({"error": "No text"}, 400)
                return
            t0 = time.time()
            reply_text = call_llm(user_text, backend=backend, model=model, history=history)
            print(f"[llm:{backend}:{model}] {time.time()-t0:.2f}s → {reply_text[:80]}...")
            self.send_json({"reply": reply_text, "user": user_text})
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def handle_speak(self):
        """Phase 2: text in → WAV out (slower)."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            text = data.get("text", "").strip()
            voice = data.get("voice", DEFAULT_VOICE)
            rate = int(data.get("rate", DEFAULT_RATE))
            if not text:
                self.send_json({"error": "No text"}, 400)
                return
            t0 = time.time()
            wav_bytes = synthesize_speech(clean_for_tts(text), voice, rate)
            print(f"[tts] {time.time()-t0:.2f}s voice={voice} rate={rate} ({len(wav_bytes)} bytes)")
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(wav_bytes)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def handle_reset(self):
        global conversation_history
        conversation_history = []
        self.send_json({"status": "reset"})

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, filename, content_type):
        path = Path(__file__).parent / filename
        if not path.exists():
            self.send_error(404)
            return
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def load_openclaw_config():
    """Load API keys and gateway token from ~/.openclaw/openclaw.json into env."""
    global OPENCLAW_CHAT_TOKEN
    try:
        config = json.loads(Path(os.path.expanduser("~/.openclaw/openclaw.json")).read_text())
        vars_ = config.get("env", {}).get("vars", {})
        gw    = config.get("gateway", {})
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            if not os.environ.get(key) and vars_.get(key):
                os.environ[key] = vars_[key]
                print(f"[init] {key} loaded from openclaw config")
        token = gw.get("auth", {}).get("token", "")
        if token and not os.environ.get("OPENCLAW_TOKEN"):
            os.environ["OPENCLAW_TOKEN"] = token
            OPENCLAW_CHAT_TOKEN = token
            print("[init] OPENCLAW_TOKEN loaded from openclaw config")
    except Exception as e:
        print(f"[init] Could not load openclaw config: {e}")


if __name__ == "__main__":
    load_openclaw_config()

    print(f"🎙️  clawd voice → http://127.0.0.1:{PORT}")
    print(f"   backend: {LLM_BACKEND}")
    print(f"   voice:   {DEFAULT_VOICE} @ {DEFAULT_RATE}wpm")

    server = HTTPServer(("127.0.0.1", PORT), VoiceChatHandler)
    server.serve_forever()
