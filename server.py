"""Gemini TTS Proxy — translates OpenAI /v1/audio/speech requests to Gemini's generateContent API."""

import asyncio
import base64
import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_DEFAULT_VOICE = os.environ.get("GEMINI_DEFAULT_VOICE", "Kore")
PROXY_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8890"))
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# OpenAI voice name → Gemini voice name
VOICE_MAP = {
    "alloy": "Puck",
    "echo": "Charon",
    "fable": "Achernar",
    "onyx": "Orus",
    "nova": "Kore",
    "shimmer": "Aoede",
}

CONTENT_TYPES = {
    "pcm": "audio/pcm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "flac": "audio/flac",
    "aac": "audio/aac",
}

http_client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=60.0)
    yield
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)


class SpeechRequest(BaseModel):
    model: str = ""
    input: str
    voice: str = ""
    response_format: str = "pcm"
    instructions: Optional[str] = None
    speed: Optional[float] = 1.0


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")

    # Map non-Gemini model names to the configured Gemini TTS model
    model = req.model if req.model.startswith("gemini") else GEMINI_MODEL

    # Map OpenAI voice names to Gemini equivalents; pass through unknown names as-is
    voice = req.voice or GEMINI_DEFAULT_VOICE
    gemini_voice = VOICE_MAP.get(voice.lower(), voice)

    # Build the text: prepend instructions if provided
    if req.instructions:
        text = f"Say the following text {req.instructions}: {req.input}"
    else:
        text = f"Say the following text: {req.input}"

    # Build Gemini request payload
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": gemini_voice}
                }
            },
        },
    }

    url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    headers = {"x-goog-api-key": GEMINI_API_KEY}

    try:
        resp = await http_client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gemini API timed out")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini API unreachable: {exc}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()

    # Extract base64 audio from response — scan parts for inlineData
    audio_b64 = None
    try:
        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                audio_b64 = part["inlineData"]["data"]
                break
    except (KeyError, IndexError):
        pass
    if not audio_b64:
        raise HTTPException(status_code=502, detail="No audio in Gemini response")

    try:
        pcm_bytes = base64.b64decode(audio_b64)
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid audio data from Gemini")

    fmt = req.response_format.lower()

    if fmt == "pcm":
        return Response(content=pcm_bytes, media_type=CONTENT_TYPES["pcm"])

    # Convert PCM to requested format via ffmpeg
    audio_bytes = await _ffmpeg_convert(pcm_bytes, fmt)
    content_type = CONTENT_TYPES.get(fmt, "application/octet-stream")
    return Response(content=audio_bytes, media_type=content_type)


async def _ffmpeg_convert(pcm_bytes: bytes, fmt: str) -> bytes:
    """Convert raw PCM (24kHz, 16-bit, mono) to the target format using ffmpeg."""
    codec_args = {
        "mp3": ["-codec:a", "libmp3lame", "-q:a", "2"],
        "wav": ["-codec:a", "pcm_s16le"],
        "opus": ["-codec:a", "libopus", "-b:a", "64k"],
        "flac": ["-codec:a", "flac"],
        "aac": ["-codec:a", "aac", "-b:a", "128k"],
    }
    args = codec_args.get(fmt)
    if not args:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "pipe:0",
        *args, "-f", fmt, "pipe:1",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=pcm_bytes)

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"ffmpeg error: {stderr.decode()}")

    return stdout


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=PROXY_HOST, port=PROXY_PORT)
