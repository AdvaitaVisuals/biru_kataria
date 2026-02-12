from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, JSON, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base
from src.enums import ContentStatus, ClipStatus, PostStatus, Platform, ContentType

# ============================================================
# BIRU_BHAI: Single Creator OS — No Artist Table, No Multi-User
# Every table has: status, created_at, updated_at, error_message
# ============================================================

class ContentAsset(Base):
    """Raw source material — videos/audio uploaded by the creator."""
    __tablename__ = "content_assets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    source_url = Column(String)  # YouTube URL or Local Path
    source_type = Column(SQLEnum(Platform), default=Platform.LOCAL)
    content_type = Column(SQLEnum(ContentType), default=ContentType.VIDEO)
    file_path = Column(String, nullable=True)  # Local path after download

    status = Column(SQLEnum(ContentStatus), default=ContentStatus.PENDING, index=True)
    error_message = Column(Text, nullable=True)  # Why it failed (if it did)
    meta_data = Column(JSON, default={})  # Duration, FPS, Resolution

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    clips = relationship("Clip", back_populates="asset")


class Clip(Base):
    """Derived short clip cut from a ContentAsset."""
    __tablename__ = "clips"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("content_assets.id"))

    start_time = Column(Float)
    end_time = Column(Float)
    duration = Column(Float)

    file_path = Column(String, nullable=True)
    s3_url = Column(String, nullable=True)

    status = Column(SQLEnum(ClipStatus), default=ClipStatus.PENDING, index=True)
    error_message = Column(Text, nullable=True)

    # Intelligence Data
    transcription = Column(Text, nullable=True)
    virality_score = Column(Float, default=0.0)
    hook_strength = Column(Float, default=0.0)
    emotion_tags = Column(JSON, default=[])

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    asset = relationship("ContentAsset", back_populates="clips")
    posts = relationship("Post", back_populates="clip")


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String)
    message = Column(Text)
    response = Column(Text, nullable=True)
    status = Column(String, default="RECEIVED") # RECEIVED, SENT, FAILED
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class Post(Base):
    """A scheduled or completed social media post for a clip."""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    clip_id = Column(Integer, ForeignKey("clips.id"))
    platform = Column(SQLEnum(Platform))

    scheduled_time = Column(DateTime(timezone=True), index=True)
    posted_time = Column(DateTime(timezone=True), nullable=True)

    performance_metrics = Column(JSON, default={})  # Views, Likes, Shares

    status = Column(SQLEnum(PostStatus), default=PostStatus.SCHEDULED, index=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    clip = relationship("Clip", back_populates="posts")


class StrategyDecision(Base):
    """Log of every decision the Strategy Brain makes — full auditability."""
    __tablename__ = "strategy_decisions"

    id = Column(Integer, primary_key=True, index=True)
    context = Column(JSON)       # What data was used to make the decision
    decision = Column(JSON)      # The decision output
    agent_name = Column(String)  # Which agent made the decision

    status = Column(String, default="EXECUTED", index=True)  # EXECUTED, OVERRIDDEN, FAILED
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
