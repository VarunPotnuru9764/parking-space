from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def record_event(
    db: Session,
    request: Request,
    event_type: str,
    description: str,
    actor_user_id: int | None = None,
    email: str | None = None,
    success: bool = True,
) -> None:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500] or None
    db.add(AuditEvent(
        actor_user_id=actor_user_id,
        event_type=event_type,
        description=description[:500],
        success=success,
        email=email,
        client_ip=client_ip,
        user_agent=user_agent,
    ))
