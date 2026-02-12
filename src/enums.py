from enum import Enum

class ContentStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"

class ClipStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    POSTED = "POSTED"
    FAILED = "FAILED"


class PostStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    POSTING = "POSTING"
    POSTED = "POSTED"
    FAILED = "FAILED"

class Platform(str, Enum):
    YOUTUBE = "YOUTUBE"
    INSTAGRAM = "INSTAGRAM"
    WHATSAPP = "WHATSAPP"
    LOCAL = "LOCAL"

class ContentType(str, Enum):
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class PipelineStep(int, Enum):
    NOT_STARTED = 0
    FETCH = 1
    TRANSCRIBE = 2
    ANALYZE = 3
    CLIP = 4
    CAPTION_POST = 5


PIPELINE_STEP_NAMES = {
    0: "Not Started",
    1: "Fetch Metadata",
    2: "Transcribe Audio",
    3: "AI Analysis",
    4: "Generate Clips",
    5: "Caption & Post",
}
