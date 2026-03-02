# Gemini TTS Proxy

Translates OpenAI-compatible `/v1/audio/speech` requests to Google's Gemini TTS API, enabling VoiceMode to use Gemini 2.5 Flash TTS with natural language voice style control via `tts_instructions`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Gemini API key
```

## Usage

```bash
python server.py
```

The proxy loads config from `.env` and listens on `http://127.0.0.1:8890` by default.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Your Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-preview-tts` | Gemini TTS model to use |
| `GEMINI_DEFAULT_VOICE` | `Kore` | Default voice when none specified |
| `PROXY_HOST` | `127.0.0.1` | Host to bind to |
| `PROXY_PORT` | `8890` | Port to listen on |

## Test

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
  -d '{"input":"Hello world","voice":"Sulafat","response_format":"pcm","instructions":"Speak in a warm, seductive whisper"}' \
  --output test.pcm
```

## VoiceMode Configuration

Add to `~/.voicemode/voicemode.env`:

```bash
VOICEMODE_TTS_BASE_URLS=http://127.0.0.1:8890/v1,http://127.0.0.1:8880/v1
```

This prioritizes Gemini TTS (via proxy) with Kokoro as fallback.

Then in Claude Code, use `tts_instructions` to control voice style:

```
converse(message="Hello", tts_instructions="Speak seductively")
```

## Voice Mapping

OpenAI voice names are automatically mapped to Gemini equivalents. You can also use any Gemini voice name directly (30 voices available).

| OpenAI | Gemini | Character |
|--------|--------|-----------|
| alloy | Puck | Upbeat |
| echo | Charon | Informative |
| fable | Achernar | Soft |
| onyx | Orus | Firm |
| nova | Kore | Firm |
| shimmer | Aoede | Breezy |

Non-Gemini model names (e.g. `tts-1`) are automatically mapped to the configured `GEMINI_MODEL`.

## Audio Formats

- `pcm` — Raw 24kHz 16-bit mono (default, no conversion needed)
- `mp3`, `wav`, `opus`, `flac`, `aac` — Converted via ffmpeg (must be installed)

## Gemini Docs

- [Speech generation (TTS) guide](https://ai.google.dev/gemini-api/docs/speech-generation) — API format, voice list, and multi-speaker setup
- [Available models](https://ai.google.dev/gemini-api/docs/models) — model names and capabilities
- [Get started with TTS (Colab)](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Get_started_TTS.ipynb) — interactive examples
