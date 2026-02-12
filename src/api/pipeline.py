import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import ContentAsset
from src.enums import ContentStatus, PIPELINE_STEP_NAMES
from src.schemas import PipelineStatusResponse, PipelineAdvanceResponse, PipelineStepDetail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


def _build_steps(asset: ContentAsset) -> list[PipelineStepDetail]:
    """Build step details from asset's pipeline_data."""
    pd = asset.pipeline_data or {}
    steps = []
    step_keys = {
        1: 'step_1_fetch',
        2: 'step_2_transcribe',
        3: 'step_3_analyze',
        4: 'step_4_clip',
        5: 'step_5_caption_post',
    }
    for num in range(1, 6):
        key = step_keys[num]
        data = pd.get(key, {})
        status = data.get('status', 'PENDING')

        # Current running step
        if num == asset.pipeline_step and asset.pipeline_step_status == 'RUNNING':
            status = 'RUNNING'
        elif num > asset.pipeline_step:
            status = 'PENDING'

        summary = None
        if status == 'COMPLETED':
            result = data.get('result', {})
            if num == 1:
                summary = f"Title: {result.get('title', '?')}, Duration: {result.get('duration', 0)}s"
            elif num == 2:
                summary = f"{result.get('segments_count', 0)} segments transcribed"
            elif num == 3:
                summary = f"{len(result.get('viral_segments', []))} viral segments found"
            elif num == 4:
                summary = f"{data.get('clips_count', 0)} clips generated"
            elif num == 5:
                summary = f"{data.get('captions_generated', 0)} captions, {data.get('posts_created', 0)} posts"
        elif status == 'POLLING':
            summary = data.get('message', 'Processing...')
        elif status == 'FAILED':
            summary = data.get('error', 'Failed')
        elif status == 'SKIPPED':
            summary = data.get('message', 'Skipped')

        steps.append(PipelineStepDetail(
            step_number=num,
            step_name=PIPELINE_STEP_NAMES[num],
            status=status,
            error_message=data.get('error'),
            result_summary=summary,
        ))
    return steps


@router.get("/{asset_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(asset_id: int, db: Session = Depends(get_db)):
    """Get full pipeline status with all 5 step details."""
    asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = asset.pipeline_step or 0
    return PipelineStatusResponse(
        asset_id=asset.id,
        title=asset.title,
        overall_status=asset.status.value if hasattr(asset.status, 'value') else str(asset.status),
        current_step=current,
        current_step_name=PIPELINE_STEP_NAMES.get(current, "Not Started"),
        steps=_build_steps(asset),
        error_message=asset.error_message,
    )


@router.post("/{asset_id}/advance", response_model=PipelineAdvanceResponse)
async def advance_pipeline(asset_id: int, db: Session = Depends(get_db)):
    """Execute the current pipeline step and advance. Each call runs ONE step."""
    from src.agents.pipeline_executor import PipelineExecutor

    asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    current = asset.pipeline_step or 0
    current_status = asset.pipeline_step_status or "PENDING"

    # Already complete
    if current >= 5 and current_status == "COMPLETED":
        return PipelineAdvanceResponse(
            asset_id=asset_id, step_advanced_to=5,
            step_name="Caption & Post", status="COMPLETED",
            message="Pipeline already complete",
        )

    # Determine which step to execute
    if current_status in ("COMPLETED", "SKIPPED"):
        next_step = current + 1
    elif current_status == "POLLING":
        next_step = current  # re-poll same step
    elif current_status == "FAILED":
        next_step = current  # retry same step
    else:
        next_step = max(current, 1)  # start from step 1 if not started

    if next_step > 5:
        asset.status = ContentStatus.READY
        db.commit()
        return PipelineAdvanceResponse(
            asset_id=asset_id, step_advanced_to=5,
            step_name="Caption & Post", status="COMPLETED",
            message="All steps complete",
        )

    # Update status to RUNNING
    asset.pipeline_step = next_step
    asset.pipeline_step_status = "RUNNING"
    asset.status = ContentStatus.PROCESSING
    db.commit()

    # Execute the step
    executor = PipelineExecutor()
    try:
        result = executor.execute_step(asset_id, next_step, db)
        step_status = result.get('status', 'COMPLETED')

        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        asset.pipeline_step = next_step
        asset.pipeline_step_status = step_status

        if next_step == 5 and step_status == "COMPLETED":
            asset.status = ContentStatus.READY

        db.commit()

        return PipelineAdvanceResponse(
            asset_id=asset_id,
            step_advanced_to=next_step,
            step_name=PIPELINE_STEP_NAMES.get(next_step, "Unknown"),
            status=step_status,
            message=result.get('message', f"Step {next_step} {step_status.lower()}"),
        )

    except Exception as e:
        logger.error(f"Pipeline step {next_step} failed for asset {asset_id}: {e}")
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        asset.pipeline_step = next_step
        asset.pipeline_step_status = "FAILED"
        asset.status = ContentStatus.FAILED
        asset.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
