from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class VideoDetectionJob(Base):
    """Persistent state and Cloud Storage references for video detection."""

    __tablename__ = "video_detection_jobs"

    job_id = Column(String(36), primary_key=True)
    user_id = Column(ForeignKey("users.user_id"), nullable=False, index=True)
    lot_slug = Column(String(80), nullable=False)
    camera_id = Column(String(80), nullable=False)
    content_type = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="queued", index=True)
    message = Column(String(255), nullable=False, default="Waiting for a detection worker")
    error = Column(Text, nullable=True)
    frame_number = Column(Integer, nullable=False, default=0)
    total_frames = Column(Integer, nullable=False, default=0)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    frame_available = Column(Boolean, nullable=False, default=False)
    input_object = Column(String(512), nullable=False)
    layout_object = Column(String(512), nullable=False)
    reference_object = Column(String(512), nullable=False)
    frame_object = Column(String(512), nullable=True)
    result_object = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class VideoDetectionSlot(Base):
    """Singleton row used to serialize creation of active video jobs."""

    __tablename__ = "video_detection_slots"

    slot_id = Column(Integer, primary_key=True)
    touched_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
