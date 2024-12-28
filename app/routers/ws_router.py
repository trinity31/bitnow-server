from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.stream_service import stream_service
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/price")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await stream_service.add_client(websocket)

    try:
        while True:
            # 클라이언트의 연결 상태 확인을 위한 대기
            try:
                # text 메시지만 받도록 수정
                await websocket.receive_text()
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        await stream_service.remove_client(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await stream_service.remove_client(websocket)
