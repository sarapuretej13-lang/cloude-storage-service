import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Share(Base):
    __tablename__ = "shares"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    owner_id          = Column(UUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False)
    item_path         = Column(String, nullable=False)
    item_type         = Column(String, nullable=False, default="file")
    shared_with_email = Column(String, nullable=False)
    permission        = Column(String, default="viewer")
    created_at        = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="shares", foreign_keys=[owner_id])


class PublicLink(Base):
    __tablename__ = "public_links"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False)
    token      = Column(String, unique=True, index=True, nullable=False)
    item_path  = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="pub_links", foreign_keys=[user_id])
