import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from app.auth.security import decode_token
from app.config import settings

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.websocket("/ws")
async def dashboard_websocket(websocket: WebSocket, token: str = Query(...)):
    # Authenticate via query param token
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            await websocket.close(code=4001)
            return
    except JWTError:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"dashboard:{tenant_id}")

        async def listen():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"].decode())

        listener_task = asyncio.create_task(listen())

        try:
            while True:
                # Keep connection alive, handle pings from client
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            pass
        finally:
            listener_task.cancel()
            await pubsub.unsubscribe(f"dashboard:{tenant_id}")
            await r.aclose()

    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
