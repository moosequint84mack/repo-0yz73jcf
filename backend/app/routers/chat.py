"""Internal chat: REST history + WebSocket realtime (user-to-user and user-to-support)."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..auth import _JWT_SECRET, get_current_user
from ..config import settings
from ..db import SessionLocal, get_db
from ..models_db import ChatMessage, User
from ..schemas import ChatMessageOut, ConversationPreview, SendMessageRequest, UserOut

logger = logging.getLogger("screener.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ConnectionManager:
    """Tracks live WebSocket connections per user id for message fan-out."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._connections.pop(user_id, None)

    async def send_to(self, user_id: int, payload: dict) -> None:
        for ws in list(self._connections.get(user_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - drop broken sockets
                await self.disconnect(user_id, ws)


manager = ConnectionManager()


def _persist_message(db: Session, sender_id: int, recipient_id: int, body: str) -> ChatMessage:
    msg = ChatMessage(sender_id=sender_id, recipient_id=recipient_id, body=body.strip())
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/contacts", response_model=list[ConversationPreview])
def contacts(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ConversationPreview]:
    """All other users with last-message preview and unread count.

    Regular users always see super-users first (technical support).
    """
    others = list(db.scalars(select(User).where(User.id != user.id, User.is_active.is_(True))))
    previews: list[ConversationPreview] = []
    for other in others:
        last = db.scalar(
            select(ChatMessage)
            .where(
                or_(
                    and_(
                        ChatMessage.sender_id == user.id, ChatMessage.recipient_id == other.id
                    ),
                    and_(
                        ChatMessage.sender_id == other.id, ChatMessage.recipient_id == user.id
                    ),
                )
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        unread = (
            db.scalar(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.sender_id == other.id,
                    ChatMessage.recipient_id == user.id,
                    ChatMessage.read_at.is_(None),
                )
            )
            or 0
        )
        previews.append(
            ConversationPreview(
                user=UserOut.model_validate(other),
                last_message=ChatMessageOut.model_validate(last) if last else None,
                unread=int(unread),
            )
        )
    # Support (super-users) first, then by most recent activity.
    previews.sort(
        key=lambda p: (
            not p.user.role == "superuser",
            -(p.last_message.created_at.timestamp() if p.last_message else 0),
        )
    )
    return previews


@router.get("/messages/{other_id}", response_model=list[ChatMessageOut])
def history(
    other_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ChatMessage]:
    msgs = list(
        db.scalars(
            select(ChatMessage)
            .where(
                or_(
                    and_(ChatMessage.sender_id == user.id, ChatMessage.recipient_id == other_id),
                    and_(ChatMessage.sender_id == other_id, ChatMessage.recipient_id == user.id),
                )
            )
            .order_by(ChatMessage.created_at.asc())
        )
    )
    # Mark inbound messages read.
    now = dt.datetime.now(dt.timezone.utc)
    for m in msgs:
        if m.recipient_id == user.id and m.read_at is None:
            m.read_at = now
    db.commit()
    return msgs


@router.post("/messages", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    req: SendMessageRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ChatMessage:
    recipient = db.get(User, req.recipient_id)
    if recipient is None or not recipient.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")
    msg = _persist_message(db, user.id, recipient.id, req.body)
    payload = ChatMessageOut.model_validate(msg).model_dump(mode="json")
    await manager.send_to(recipient.id, {"type": "message", "data": payload})
    return msg


def _user_from_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[settings.jwt_algorithm])
        return int(payload.get("sub", 0)) or None
    except (jwt.PyJWTError, ValueError):
        return None


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, token: str = "") -> None:
    """Realtime channel. Authenticate with ?token=<jwt>; send {recipient_id, body}."""
    user_id = _user_from_token(token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            recipient_id = int(data.get("recipient_id", 0))
            body = str(data.get("body", "")).strip()
            if not recipient_id or not body:
                continue
            with SessionLocal() as db:
                recipient = db.get(User, recipient_id)
                if recipient is None or not recipient.is_active:
                    continue
                msg = _persist_message(db, user_id, recipient_id, body)
                payload = ChatMessageOut.model_validate(msg).model_dump(mode="json")
            await manager.send_to(recipient_id, {"type": "message", "data": payload})
            await manager.send_to(user_id, {"type": "message", "data": payload})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
