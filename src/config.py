import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "BIRU_BHAI"
    environment: str = "development"
    database_url: str = "sqlite:///./biru_bhai.db"

    @property
    def get_database_url(self) -> str:
        if self.database_url and self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql://", 1)
        
        # Fallback for Vercel (Read-only OS)
        if os.environ.get("VERCEL"):
            # Put SQLite in /tmp if not using Postgres
            if not self.database_url or "sqlite" in self.database_url:
                return "sqlite:////tmp/biru_bhai.db"
        
        return self.database_url or "sqlite:///biru_bhai.db"

    @property
    def api_base_url(self) -> str:
        # Default to Vercel URL or local
        if os.environ.get("VERCEL_URL"):
            return f"https://{os.environ.get('VERCEL_URL')}"
        return "https://biru-kataria.vercel.app"
    # Credentials from .env
    openai_api_key: str = ""
    whatsapp_token: str = ""
    phone_id: str = ""
    verify_token: str = "bot"
    admin_number: str = ""
    vizard_api_key: str = ""

    # Auto-Posting
    instagram_access_token: str = ""
    instagram_business_account_id: str = ""
    facebook_page_id: str = ""  # New for FB Page Posting
    facebook_access_token: str = "" # Specific Token for FB Page
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""

    # Task Queue
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # Media paths & Tools
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    class Config:
        env_file = ".env"
        # Map .env keys to field names if necessary, 
        # but pydantic matches case-insensitively and handles underscores.
        # However, to be extra safe and avoid 'extra_forbidden' issues, 
        # we can explicitly allow extras or list everything.
        extra = "ignore" 
        fields = {
            'admin_number': {'env': ['ADMIN_NUMBER', 'Phone_Number']},
            'whatsapp_token': {'env': ['WHATSAPP_TOKEN', 'WhatsApp_Token']},
            'openai_api_key': {'env': ['OPENAI_API_KEY', 'Gemini_API']} # Mapping to OpenAI as fallback
        }

settings = Settings()
