from datetime import datetime
from typing import List

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.session import Base
import enum

class JobStatus(enum.Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    PREPROCESSING = "PREPROCESSING"
    SEPARATING_VOCALS = "SEPARATING_VOCALS"
    DETECTING_LANGUAGE = "DETECTING_LANGUAGE"
    TRANSCRIBING = "TRANSCRIBING"
    POST_PROCESSING = "POST_PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

TERMINAL_STATUSES = (JobStatus.COMPLETED.value, JobStatus.FAILED.value)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    jobs = relationship("TranscriptionJob", back_populates="user", cascade="all, delete-orphan")

class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    client_id = Column(String(64), index=True, nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(64), nullable=False)
    file_type = Column(String(10), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    requested_language = Column(String(10), nullable=False)
    detected_language = Column(String(10), nullable=True)
    status = Column(String(32), index=True, nullable=False)
    transcription_progress = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    warning = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), index=True, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="jobs")
    segments = relationship("TranscriptionSegment", back_populates="job", cascade="all, delete-orphan")
    result = relationship("TranscriptionResult", back_populates="job", uselist=False, cascade="all, delete-orphan")

class TranscriptionSegment(Base):
    __tablename__ = "transcription_segments"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), ForeignKey("transcription_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False)

    job = relationship("TranscriptionJob", back_populates="segments")

class TranscriptionResult(Base):
    __tablename__ = "transcription_results"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), ForeignKey("transcription_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_text = Column(Text, nullable=False)
    model_name = Column(String(64), nullable=False)
    device = Column(String(16), nullable=True)
    processing_time = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    job = relationship("TranscriptionJob", back_populates="result")
