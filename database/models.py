import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, LargeBinary, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class JobRecord(Base):
    """Tracks background automation job states, execution steps, and durable progress."""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="PENDING")
    current_step = Column(String(100), nullable=False, default="INITIALIZING")
    manual_intervention_required = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    completed_steps = Column(Text, nullable=False, default="[]")  # JSON list of completed step names
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    credential = relationship("CredentialRecord", back_populates="job", uselist=False, cascade="all, delete-orphan")

class CredentialRecord(Base):
    """
    Stores encrypted credentials ONLY after successful account creation.
    Passwords are encrypted at rest using Fernet authenticated encryption.
    """
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(100), nullable=False, unique=True)
    encrypted_password = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    job = relationship("JobRecord", back_populates="credential")
