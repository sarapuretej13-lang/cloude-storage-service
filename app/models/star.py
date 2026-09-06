from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Star(Base):
    __tablename__ = "stars"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_path  = Column(String, nullable=False)
    item_type  = Column(String, nullable=False)   # file | folder
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="stars")


class TrashItem(Base):
    __tablename__ = "trash_items"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_path      = Column(String, nullable=False)   # original path
    item_name      = Column(String, nullable=False)
    item_type      = Column(String, nullable=False)   # file | folder
    trashed_at     = Column(DateTime, default=datetime.utcnow)
