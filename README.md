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
# Load API key
export GEMINI_API_KEY=your-key-here

# Start proxy
python server.py
```

The proxy listens on `http://0.0.0.0:8890`.

## Test

```bash
# Basic TTS
curl -X POST http://localhost:8890/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash-tts","input":"Hello world","voice":"Kore","response_format":"pcm"}' \
  --output test.pcm

# Play it
ffplay -f s16le -ar 24000 -ac 1 test.pcm

# With voice style instructions
curl -X POST http://localhost:8890/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash-tts","input":"Hello world","voice":"Kore","response_format":"pcm","instructions":"Speak in a warm, seductive whisper"}' \
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

OpenAI voice names are automatically mapped to Gemini equivalents. You can also use any Gemini voice name directly.

| OpenAI | Gemini | Character |
|--------|--------|-----------|
| alloy | Puck | Upbeat, energetic |
| echo | Charon | Informative, clear |
| fable | Achernar | Soft, gentle |
| onyx | Orus | Firm, decisive |
| nova | Kore | Firm, confident |
| shimmer | Aoede | Breezy, natural |

Gemini supports ~30 voices total — pass any valid name directly.

## Audio Formats

- `pcm` — Raw 24kHz 16-bit mono (default, no conversion needed)
- `mp3`, `wav`, `opus`, `flac`, `aac` — Converted via ffmpeg (must be installed)
