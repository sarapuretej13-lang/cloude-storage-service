import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class StarredItem(Base):
    __tablename__ = "starred_items"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False)
    item_path  = Column(String, nullable=False)
    item_type  = Column(String, nullable=False)
    item_name  = Column(String, nullable=False)
    starred_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="stars")
