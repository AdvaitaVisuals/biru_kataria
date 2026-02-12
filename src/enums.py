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
