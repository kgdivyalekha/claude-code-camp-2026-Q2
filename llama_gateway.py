#!/usr/bin/env python3
"""
Gateway to translate Claude API format to Ollama format.
Runs on port 8000 by default.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import json
import uuid
from datetime import datetime

app = FastAPI()

OLLAMA_BASE = "http://localhost:11434"
CLAUDE_MODEL = "llama3.2:3b"   
DEFAULT_MODEL = "llama3.2:3b"   


# ---------------------------------------------------------
# Root route (fixes your 404 when visiting http://localhost:8000)
# ---------------------------------------------------------
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Llama Gateway is running",
        "forwarding_to": OLLAMA_BASE,
        "model": DEFAULT_MODEL
    }


# ---------------------------------------------------------
# Simple /generate endpoint (the one you tried to call)
# ---------------------------------------------------------
@app.post("/generate")
async def generate(payload: dict):
    prompt = payload.get("prompt", "")

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": DEFAULT_MODEL,
                "prompt": prompt,
                "stream": False
            }
        )

    if response.status_code != 200:
        return JSONResponse(
            {"error": f"Ollama error: {response.text}"},
            status_code=response.status_code
        )

    data = response.json()
    return {"response": data.get("response", "")}


# ---------------------------------------------------------
# Claude-compatible endpoint: /v1/messages
# ---------------------------------------------------------
@app.post("/v1/messages")
async def handle_claude_messages(request: Request):
    """Translate Claude API format to Ollama format."""
    try:
        data = await request.json()

        model = data.get("model", DEFAULT_MODEL)
        messages = data.get("messages", [])
        max_tokens = data.get("max_tokens", 1024)

        # Build prompt from Claude-style messages
        prompt = ""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        prompt += block.get("text", "")
            else:
                prompt += content
            prompt += "\n"

        print(f"[DEBUG] Sending to Ollama: model={model}, prompt_len={len(prompt)}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                }
            )

        if response.status_code != 200:
            print(f"[ERROR] Ollama returned {response.status_code}: {response.text}")
            return JSONResponse(
                {"error": f"Ollama error: {response.text}"},
                status_code=response.status_code
            )

        ollama_response = response.json()
        generated_text = ollama_response.get("response", "")

        print(f"[DEBUG] Got response from Ollama: {len(generated_text)} chars")

        # Convert to Claude format
        claude_response = {
            "id": f"msg_{uuid.uuid4().hex[:16]}",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": generated_text
                }
            ],
            "model": model,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": len(prompt.split()),
                "output_tokens": len(generated_text.split())
            }
        }

        return JSONResponse(claude_response)

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "ollama_base": OLLAMA_BASE}


# ---------------------------------------------------------
# Run server
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    print("Starting Llama Gateway on http://localhost:8000")
    print(f"Forwarding to Ollama at {OLLAMA_BASE}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
