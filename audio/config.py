from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MinIO / S3
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    audio_bucket: str = "meeting-audio"

    # Server
    log_level: str = "INFO"

    # Transcription — non-realtime (onnx_asr)
    onnx_asr_model_type: str = "nemo-conformer-tdt"
    onnx_asr_model_path: str = "./models/rnnt"
    onnx_asr_quantization: str = "int8"
    onnx_asr_providers: list[str] = ["CPUExecutionProvider"]

    # Transcription — realtime streaming RNNT
    rnnt_encoder_onnx: str = "./models/encoder-fastconformer_streaming_rnnt.onnx"
    rnnt_decoder_joint_onnx: str = "./models/decoder_joint-fastconformer_streaming_rnnt.onnx"
    rnnt_model_name: str = "bekzod123/FastConformer-Hybrid-Transducer-CTC-BPE-Streaming"
    rnnt_nemo_filename: str = "FastConformer-Hybrid-Transducer-CTC-BPE-Streaming.nemo"
    rnnt_chunk_seconds: float = 1.0
    rnnt_providers: list[str] = ["CPUExecutionProvider"]
    rnnt_max_symbols_per_step: int = 10

    # VAD
    vad_silence_threshold_db: float = -40.0
    vad_silence_seconds: float = 0.8
    vad_preroll_blocks: int = 2

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
