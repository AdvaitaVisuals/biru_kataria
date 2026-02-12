"""
Pydantic Schemas — Request/Response contracts for the API

Clean separation: Models = DB, Schemas = API interface
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# CONTENT ASSET SCHEMAS
# ============================================================

class AssetUploadResponse(BaseModel):
    """Response after uploading a content asset."""
    id: int
    title: str
    status: str
    file_path: str
    message: str = "Asset uploaded successfully"

    class Config:
        from_attributes = True


class AssetStatusResponse(BaseModel):
    """Full status of a content asset with its clips."""
    id: int
    title: str
    status: str
    error_message: Optional[str] = None
    source_type: Optional[str] = None
    content_type: Optional[str] = None
    meta_data: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    clips: list = Field(default_factory=list)

    class Config:
        from_attributes = True


class ProcessResponse(BaseModel):
    """Response after triggering processing."""
    asset_id: int
    task_id: str
    status: str = "PROCESSING"
    message: str = "Processing started in background"


# ============================================================
# CLIP SCHEMAS
# ============================================================

class ClipResponse(BaseModel):
    """A single clip's data."""
    id: int
    asset_id: int
    start_time: float
    end_time: float
    duration: float
    status: str
    error_message: Optional[str] = None
    transcription: Optional[str] = None
    virality_score: float = 0.0
    hook_strength: float = 0.0
    emotion_tags: Optional[list] = None
    file_path: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================
# GENERAL SCHEMAS
# ============================================================

class YouTubeUploadRequest(BaseModel):
    """Request to process a YouTube video."""
    url: str
    title: Optional[str] = None

class StrategyResponse(BaseModel):
    """Response from the Strategy Brain."""
    asset_id: int
    decisions: list = Field(default_factory=list)
    message: str = "Strategy analyzed"

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.2.0"
    phase: str = "Phase 2 & 3: Intelligence + Strategy"

class ErrorResponse(BaseModel):
    detail: str
