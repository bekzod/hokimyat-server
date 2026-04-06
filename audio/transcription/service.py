import asyncio
import logging
import tempfile
from pathlib import Path

import numpy as np

from .recognizer import RNNTModelBundle, StreamingRecognizerState, SAMPLE_RATE
from .vad import EnergyVoiceGate

logger = logging.getLogger(__name__)

_service: "TranscriptionService | None" = None


def init_service(settings) -> "TranscriptionService":
    global _service
    _service = TranscriptionService(settings)
    return _service


def get_service() -> "TranscriptionService":
    if _service is None:
        raise RuntimeError(
            "TranscriptionService not initialized. Call init_service() at startup."
        )
    return _service


class StreamingSession:
    """Per-WebSocket streaming transcription session with VAD + RNNT."""

    def __init__(
        self,
        model: RNNTModelBundle,
        *,
        chunk_seconds: float = 1.0,
        vad_threshold_db: float = -40.0,
        vad_silence_seconds: float = 0.8,
        vad_preroll_blocks: int = 2,
    ):
        self.recognizer = StreamingRecognizerState(model)
        self.vad = EnergyVoiceGate(
            threshold_db=vad_threshold_db,
            silence_seconds=vad_silence_seconds,
            sample_rate=SAMPLE_RATE,
            preroll_blocks=vad_preroll_blocks,
        )
        self.chunk_samples_target = int(SAMPLE_RATE * chunk_seconds)
        self.buffered = np.empty(0, dtype=np.float32)
        self.utterances: list[str] = []

    def process_audio(self, pcm_float32: np.ndarray) -> list[dict]:
        """Process a block of float32 PCM audio.

        Returns a list of events:
          {"type": "partial", "text": "..."}
          {"type": "utterance", "text": "...", "index": N}
        """
        events: list[dict] = []
        emitted_blocks, should_finalize = self.vad.process(pcm_float32)

        for block in emitted_blocks:
            self.buffered = np.concatenate([self.buffered, block])
            events.extend(self._process_buffer(force=False))

        if should_finalize:
            events.extend(self._finalize_utterance())

        return events

    def finalize(self) -> list[dict]:
        """Flush remaining audio and finalize the last utterance."""
        if len(self.buffered) > 0 or self.recognizer.tokens:
            return self._finalize_utterance()
        return []

    def _process_buffer(self, force: bool = False) -> list[dict]:
        events: list[dict] = []
        while len(self.buffered) >= self.chunk_samples_target or (
            force and len(self.buffered) > 0
        ):
            chunk_size = min(self.chunk_samples_target, len(self.buffered))
            chunk = self.buffered[:chunk_size]
            self.buffered = self.buffered[chunk_size:]
            text = self.recognizer.transcribe_chunk(chunk)
            if text:
                events.append({"type": "partial", "text": text})
        return events

    def _finalize_utterance(self) -> list[dict]:
        events = self._process_buffer(force=True)
        text = self.recognizer.current_text()
        self.buffered = np.empty(0, dtype=np.float32)
        self.recognizer.reset()
        self.vad.reset()
        if text:
            self.utterances.append(text)
            events.append(
                {"type": "utterance", "text": text, "index": len(self.utterances) - 1}
            )
        return events


class TranscriptionService:
    """Manages model lifecycle and provides both file and streaming transcription."""

    def __init__(self, settings):
        self.settings = settings
        self._rnnt_model: RNNTModelBundle | None = None
        self._onnx_asr_model = None

    def load_streaming_model(self) -> None:
        logger.info("Loading streaming RNNT model...")
        self._rnnt_model = RNNTModelBundle(
            encoder_onnx_path=self.settings.rnnt_encoder_onnx,
            decoder_joint_onnx_path=self.settings.rnnt_decoder_joint_onnx,
            model_name=self.settings.rnnt_model_name,
            nemo_filename=self.settings.rnnt_nemo_filename,
            providers=self.settings.rnnt_providers,
            max_symbols_per_step=self.settings.rnnt_max_symbols_per_step,
        )
        logger.info(
            "Streaming RNNT model loaded (providers=%s)",
            self._rnnt_model.encoder.get_providers(),
        )

    @property
    def streaming_ready(self) -> bool:
        return self._rnnt_model is not None

    def _get_onnx_asr_model(self):
        if self._onnx_asr_model is None:
            import onnx_asr

            self._onnx_asr_model = onnx_asr.load_model(
                self.settings.onnx_asr_model_type,
                path=self.settings.onnx_asr_model_path,
                quantization=self.settings.onnx_asr_quantization,
                providers=self.settings.onnx_asr_providers,
            )
            logger.info("onnx_asr model loaded for file transcription")
        return self._onnx_asr_model

    async def transcribe_file(self, audio_data: bytes, filename: str) -> dict:
        """Transcribe an uploaded audio file using onnx_asr."""
        model = self._get_onnx_asr_model()
        suffix = Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(audio_data)
            tmp.flush()
            result = await asyncio.to_thread(model.recognize, tmp.name)
        return {"text": str(result)}

    def create_streaming_session(self) -> StreamingSession:
        if self._rnnt_model is None:
            raise RuntimeError(
                "Streaming model not loaded. Call load_streaming_model() first."
            )
        return StreamingSession(
            self._rnnt_model,
            chunk_seconds=self.settings.rnnt_chunk_seconds,
            vad_threshold_db=self.settings.vad_silence_threshold_db,
            vad_silence_seconds=self.settings.vad_silence_seconds,
            vad_preroll_blocks=self.settings.vad_preroll_blocks,
        )
