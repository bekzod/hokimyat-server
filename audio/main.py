import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from api.routes import router
from transcription.service import init_service

settings = get_settings()
logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


def create_app() -> FastAPI:
    application = FastAPI(
        title="Meeting Audio Service",
        description="Audio upload, streaming, storage, and transcription for meetings",
        version="2.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router, prefix="/api/meeting")

    @application.on_event("startup")
    async def _load_transcription_models():
        service = init_service(settings)
        try:
            service.load_streaming_model()
        except Exception:
            logger.warning(
                "Streaming RNNT model could not be loaded — "
                "realtime transcription will be unavailable. "
                "Check RNNT_ENCODER_ONNX / RNNT_DECODER_JOINT_ONNX paths.",
                exc_info=True,
            )

    return application


app = create_app()
