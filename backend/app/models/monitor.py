from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base


class Monitor(Base):
    """API monitor model - represents an API endpoint being monitored"""
    __tablename__ = "monitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=False)
    method = Column(String(10), nullable=False, default="GET")
    headers = Column(JSON, nullable=True)
    body = Column(JSON, nullable=True)
    expected_status = Column(Integer, nullable=False, default=200)
    check_interval = Column(Integer, nullable=False, default=5)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    owner = relationship("User", back_populates="monitors")
    checks = relationship("Check", back_populates="monitor", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="monitor", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="monitor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Monitor(id={self.id}, name={self.name}, url={self.url})>"