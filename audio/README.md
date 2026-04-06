# Meeting Audio Service

Audio upload, live streaming, storage, and speech-to-text transcription for meetings.

## Endpoints

All routes are prefixed with `/api/meeting`.

### Storage

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/upload/` | Upload an audio file to MinIO |
| `GET` | `/files/` | List uploaded audio files |
| `GET` | `/files/{file_id}/url` | Get a presigned download URL |
| `WS` | `/stream` | Stream microphone audio (webm/opus) and save to MinIO |

### Transcription

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/transcribe` | Upload an audio file and get the transcript back |
| `WS` | `/transcribe/stream` | Realtime streaming transcription with partial results |

## Transcription

### Non-realtime (`POST /transcribe`)

Upload any audio file (wav, mp3, webm, etc.) and receive the full transcript.

```bash
curl -X POST http://localhost:8100/api/meeting/transcribe \
  -F "file=@recording.wav"
```

Response:

```json
{"text": "transcribed text here"}
```

Uses the `onnx_asr` library under the hood.

### Realtime streaming (`WS /transcribe/stream`)

Stream PCM audio from a microphone and receive partial transcripts in real time.
Uses a FastConformer RNNT model with ONNX Runtime and energy-based VAD.

**Audio format:** PCM-16 little-endian, 16 kHz, mono.

#### Protocol

```
Client connects -> ws://localhost:8100/api/meeting/transcribe/stream

Server -> {"type": "ready", "session_id": "..."}

Client -> binary PCM16 frames (recommended: 100 ms chunks = 3200 bytes)

Server -> {"type": "partial", "text": "salom dun"}
Server -> {"type": "utterance", "text": "salom dunyo", "index": 0}
  (emitted when VAD detects end-of-utterance silence)

Client -> {"type": "stop"}

Server -> {"type": "done", "session_id": "...", "utterances": ["salom dunyo", ...]}
```

#### JavaScript example

```javascript
const ws = new WebSocket("ws://localhost:8100/api/meeting/transcribe/stream");

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === "partial") {
    console.log("partial:", msg.text);
  } else if (msg.type === "utterance") {
    console.log("final:", msg.text);
  } else if (msg.type === "done") {
    console.log("all utterances:", msg.utterances);
  }
};

ws.onopen = () => {
  // Start sending PCM16 audio from getUserMedia + AudioWorklet
  // Convert Float32 samples to Int16 LE before sending
};

// To stop:
ws.send(JSON.stringify({ type: "stop" }));
```

## Configuration

All settings are configurable via environment variables or `.env`.

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `http://minio:9000` | MinIO S3 endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin123` | MinIO secret key |
| `AUDIO_BUCKET` | `meeting-audio` | S3 bucket name |

### Non-realtime transcription (onnx_asr)

| Variable | Default | Description |
|----------|---------|-------------|
| `ONNX_ASR_MODEL_TYPE` | `nemo-conformer-tdt` | Model type for onnx_asr |
| `ONNX_ASR_MODEL_PATH` | `./models/rnnt` | Path to exported model directory |
| `ONNX_ASR_QUANTIZATION` | `int8` | Quantization level |
| `ONNX_ASR_PROVIDERS` | `["CPUExecutionProvider"]` | ONNX Runtime providers |

### Realtime streaming transcription (RNNT)

| Variable | Default | Description |
|----------|---------|-------------|
| `RNNT_ENCODER_ONNX` | `./models/encoder-fastconformer_streaming_rnnt.onnx` | Encoder ONNX model path |
| `RNNT_DECODER_JOINT_ONNX` | `./models/decoder_joint-fastconformer_streaming_rnnt.onnx` | Decoder/joint ONNX model path |
| `RNNT_MODEL_NAME` | `bekzod123/FastConformer-Hybrid-Transducer-CTC-BPE-Streaming` | HuggingFace repo for tokenizer/config |
| `RNNT_NEMO_FILENAME` | `FastConformer-Hybrid-Transducer-CTC-BPE-Streaming.nemo` | `.nemo` archive filename |
| `RNNT_CHUNK_SECONDS` | `1.0` | Audio chunk size for encoder inference |
| `RNNT_PROVIDERS` | `["CPUExecutionProvider"]` | ONNX Runtime providers |
| `RNNT_MAX_SYMBOLS_PER_STEP` | `10` | Max tokens per encoder timestep |

### VAD

| Variable | Default | Description |
|----------|---------|-------------|
| `VAD_SILENCE_THRESHOLD_DB` | `-40.0` | dBFS threshold for speech detection |
| `VAD_SILENCE_SECONDS` | `0.8` | Silence duration to finalize an utterance |
| `VAD_PREROLL_BLOCKS` | `2` | Audio blocks buffered before speech onset |

## Model setup

Place model files under `./models/` (or configure paths via env vars):

```
audio/
  models/
    rnnt/                        # onnx_asr model directory (non-realtime)
    encoder-fastconformer_streaming_rnnt.onnx   # streaming encoder
    decoder_joint-fastconformer_streaming_rnnt.onnx  # streaming decoder/joint
```

The `.nemo` archive for tokenizer and preprocessor config is downloaded automatically
from HuggingFace on first startup (or provide a local `.nemo` path via `RNNT_MODEL_NAME`).

## Running

### Docker (recommended)

```bash
docker compose up audio_server
```

### Local development

```bash
cd audio
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

## Architecture

```
audio/
  api/
    routes.py          # REST + WebSocket endpoints
  transcription/
    vad.py             # Energy-based voice activity detector
    recognizer.py      # RNNT model bundle + per-session streaming state
    service.py         # TranscriptionService (model lifecycle, session factory)
  config.py            # Pydantic settings
  storage.py           # MinIO/S3 upload and retrieval
  main.py              # FastAPI app with startup model loading
```
