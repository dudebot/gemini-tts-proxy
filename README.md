# Gemini TTS Proxy

A tiny FastAPI server that accepts OpenAI-compatible `POST /v1/audio/speech` requests and fulfills them with Google's Gemini TTS (`generateContent` with audio response modality). Anything that already speaks the OpenAI text-to-speech API — VoiceMode, custom scripts, other tooling — can use Gemini voices without changing its client code, and gains natural-language voice style control ("speak in a warm whisper") via the `instructions` field, which Gemini honors but OpenAI-compatible local engines typically don't.

The whole proxy is one file, `server.py` (~175 lines). It translates the request, calls Gemini, extracts the returned PCM audio, and optionally converts it to other formats with ffmpeg.

## Requirements

- Python 3.10+
- A [Gemini API key](https://ai.google.dev/gemini-api/docs/api-key)
- `ffmpeg` on PATH — only needed for non-`pcm` response formats

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Gemini API key
```

## Run

```bash
python server.py
```

Config is loaded from `.env` (or real environment variables). By default the proxy binds to `http://127.0.0.1:8890`.

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Your Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-preview-tts` | Gemini TTS model to use |
| `GEMINI_DEFAULT_VOICE` | `Kore` | Voice used when the request doesn't specify one |
| `PROXY_HOST` | `127.0.0.1` | Host to bind to |
| `PROXY_PORT` | `8890` | Port to listen on |

The proxy itself has **no authentication** — it holds your Gemini key server-side and accepts any request it can reach. Keep it bound to localhost (the default) unless you put it behind something that handles auth.

## API

`POST /v1/audio/speech` with a JSON body:

| Field | Default | Behavior |
|---|---|---|
| `input` | (required) | Text to speak |
| `voice` | `GEMINI_DEFAULT_VOICE` | Gemini voice name, or an OpenAI voice name (mapped, see below) |
| `response_format` | `pcm` | `pcm`, `wav`, `mp3`, `opus`, `flac`, `aac` |
| `instructions` | — | Natural-language style direction, prepended to the TTS prompt |
| `model` | `GEMINI_MODEL` | Names starting with `gemini` pass through; anything else (e.g. `tts-1`) maps to the configured model |
| `speed` | `1.0` | Accepted for OpenAI compatibility; not currently applied |

The response body is the audio itself with the matching `Content-Type`.

### Examples

```bash
# Basic TTS
curl -X POST http://localhost:8890/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello world","voice":"Kore","response_format":"pcm"}' \
  --output test.pcm

# Play it
ffplay -f s16le -ar 24000 -ac 1 test.pcm

# With voice style instructions
curl -X POST http://localhost:8890/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello world","voice":"Sulafat","response_format":"mp3","instructions":"Speak in a warm, gentle whisper"}' \
  --output test.mp3
```

## Voice mapping

Any Gemini voice name works directly (30 voices available — see the [voice list](https://ai.google.dev/gemini-api/docs/speech-generation)). The six OpenAI voice names are mapped to Gemini equivalents:

| OpenAI | Gemini | Character |
|--------|--------|-----------|
| alloy | Puck | Upbeat |
| echo | Charon | Informative |
| fable | Achernar | Soft |
| onyx | Orus | Firm |
| nova | Kore | Firm |
| shimmer | Aoede | Breezy |

Unknown voice names pass through to Gemini as-is.

## Audio formats

Gemini returns raw PCM (24kHz, 16-bit, mono). The proxy serves that directly for `response_format: "pcm"` — zero conversion overhead — and pipes it through ffmpeg for `wav`, `mp3`, `opus`, `flac`, and `aac`.

## VoiceMode integration

Add the proxy to `~/.voicemode/voicemode.env`:

```bash
VOICEMODE_TTS_BASE_URLS=http://127.0.0.1:8890/v1,http://127.0.0.1:8880/v1
```

This prioritizes Gemini TTS via the proxy, with a local engine (e.g. Kokoro on 8880) as fallback. Voice style then flows through `tts_instructions`:

```
converse(message="Hello", tts_instructions="Speak softly")
```

## Status

Stable. It's a small single-purpose utility that does one translation job; it hasn't needed changes since it was built (March 2026).

## Gemini docs

- [Speech generation (TTS) guide](https://ai.google.dev/gemini-api/docs/speech-generation) — API format, voice list, multi-speaker setup
- [Available models](https://ai.google.dev/gemini-api/docs/models) — model names and capabilities
- [Get started with TTS (Colab)](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Get_started_TTS.ipynb) — interactive examples
