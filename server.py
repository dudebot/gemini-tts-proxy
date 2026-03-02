"""Gemini TTS Proxy — translates OpenAI /v1/audio/speech requests to Gemini's generateContent API."""

import asyncio
import base64
import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
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


class SpeechRequest(BaseModel):
    model: str = "gemini-2.5-flash-tts"
    input: str
    voice: str = "Kore"
    response_format: str = "pcm"
    instructions: Optional[str] = None
    speed: Optional[float] = 1.0


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")

    # Map OpenAI voice names to Gemini equivalents; pass through unknown names as-is
    gemini_voice = VOICE_MAP.get(req.voice.lower(), req.voice)

    # Build the text: prepend instructions if provided
    text = f"{req.instructions}: {req.input}" if req.instructions else req.input

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

    url = f"{GEMINI_BASE_URL}/{req.model}:generateContent?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()

    # Extract base64 audio from response
    try:
        inline_data = data["candidates"][0]["content"]["parts"][0]["inlineData"]
        audio_b64 = inline_data["data"]
    except (KeyError, IndexError) as exc:
        raise HTTPException(status_code=502, detail=f"Unexpected Gemini response: {exc}")

    pcm_bytes = base64.b64decode(audio_b64)

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

    uvicorn.run(app, host="0.0.0.0", port=8890)
