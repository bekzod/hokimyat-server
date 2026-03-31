import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect

import storage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/upload/")
async def upload_audio(file: UploadFile = File(...)):
    """Upload an audio file, store it in MinIO, return metadata."""
    file_id = str(uuid.uuid4())
    ext = (file.filename or "audio.webm").rsplit(".", 1)[-1] if file.filename else "webm"
    key = f"uploads/{file_id}.{ext}"

    data = await file.read()
    content_type = file.content_type or "audio/webm"

    await storage.upload_audio(
        key=key,
        data=data,
        content_type=content_type,
        metadata={
            "original_filename": (file.filename or "unknown")[:200],
            "upload_time": datetime.utcnow().isoformat(),
        },
    )

    return {
        "file_id": file_id,
        "key": key,
        "size": len(data),
        "content_type": content_type,
        "filename": file.filename,
    }


@router.get("/files/")
async def list_files():
    """List all uploaded audio files."""
    files = await storage.list_audio(prefix="uploads/")
    return {"files": files}


@router.get("/files/{file_id}/url")
async def get_file_url(file_id: str):
    """Get a presigned download URL for an audio file."""
    # find the file by prefix match
    files = await storage.list_audio(prefix=f"uploads/{file_id}")
    if not files:
        return {"error": "File not found"}, 404
    url = await storage.get_presigned_url(files[0]["key"])
    return {"url": url, "key": files[0]["key"]}


@router.websocket("/stream")
async def audio_stream(ws: WebSocket):
    """
    WebSocket endpoint for real-time microphone audio streaming.

    Protocol:
    1. Client connects
    2. Server sends {"type": "ready"}
    3. Client sends binary audio chunks (webm/opus)
    4. Client sends {"type": "stop"} text message when done
    5. Server saves assembled audio to MinIO, responds with metadata
    """
    await ws.accept()
    logger.info("WebSocket audio stream connected")

    session_id = str(uuid.uuid4())
    chunks: list[bytes] = []
    total_bytes = 0

    try:
        # signal readiness
        await ws.send_json({"type": "ready", "session_id": session_id})

        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # binary audio data
            if "bytes" in message and message["bytes"]:
                chunk = message["bytes"]
                chunks.append(chunk)
                total_bytes += len(chunk)

                # acknowledge periodically (every ~100KB)
                if total_bytes % (100 * 1024) < len(chunk):
                    await ws.send_json({
                        "type": "ack",
                        "received_bytes": total_bytes,
                    })

            # text control messages
            if "text" in message and message["text"]:
                import json
                try:
                    msg = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "stop":
                    break

        # assemble and save
        if chunks:
            audio_data = b"".join(chunks)
            key = f"streams/{session_id}.webm"

            await storage.upload_audio(
                key=key,
                data=audio_data,
                content_type="audio/webm",
                metadata={
                    "source": "live_stream",
                    "session_id": session_id,
                    "upload_time": datetime.utcnow().isoformat(),
                },
            )

            await ws.send_json({
                "type": "saved",
                "session_id": session_id,
                "key": key,
                "size": len(audio_data),
            })
            logger.info("Stream %s saved: %d bytes", session_id, len(audio_data))
        else:
            await ws.send_json({"type": "empty", "session_id": session_id})

    except WebSocketDisconnect:
        # client disconnected — still try to save partial data
        if chunks:
            audio_data = b"".join(chunks)
            key = f"streams/{session_id}.webm"
            await storage.upload_audio(key=key, data=audio_data, content_type="audio/webm", metadata={"source": "live_stream_partial", "session_id": session_id})
            logger.info("Partial stream %s saved on disconnect: %d bytes", session_id, len(audio_data))
    except Exception:
        logger.exception("WebSocket stream error for session %s", session_id)
        try:
            await ws.send_json({"type": "error", "message": "Server xatosi"})
        except Exception:
            pass
