from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import deferred
from sqlalchemy.sql import func

from app.database import Base


class DetectionJob(Base):
    """Temporary input and result state shared by the API and Cloud Run Job."""

    __tablename__ = "layout_detection_jobs"

    job_id = Column(String(36), primary_key=True)
    user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    lot_slug = Column(String(80), nullable=False)
    camera_id = Column(String(80), nullable=False)
    content_type = Column(String(64), nullable=False)
    image_data = deferred(Column(LONGBLOB, nullable=True))
    status = Column(String(20), nullable=False, default="queued", index=True)
    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    completion_logged = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
