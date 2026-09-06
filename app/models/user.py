import uuid
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class User(Base):
    __tablename__ = "app_users"
    __table_args__ = {"extend_existing": True}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name            = Column(String, nullable=True)   # nullable in case Supabase table lacks this col
    email           = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)   # nullable to not conflict with Supabase auth schema
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    shares      = relationship("Share", back_populates="owner", foreign_keys="Share.owner_id")
    stars       = relationship("StarredItem", back_populates="user")
    trash_items = relationship("TrashItem", back_populates="user")
    pub_links   = relationship("PublicLink", back_populates="owner")
