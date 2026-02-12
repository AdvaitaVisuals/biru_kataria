
import logging
import requests
import time
from src.config import settings

logger = logging.getLogger(__name__)

class VizardAgent:
    """
    Agent responsible for interacting with Vizard AI API for professional video clipping.
    """
    BASE_URL = "https://elb-api.vizard.ai/hvizard-server-front/open-api/v1"

    def __init__(self):
        self.api_key = settings.vizard_api_key

    def create_project(self, video_url: str, project_name: str = "Viral Clip"):
        """
        Submits a video URL to Vizard AI for automated clipping.
        """
        if not self.api_key:
            logger.error("Vizard API Key missing")
            return None

        endpoint = f"{self.BASE_URL}/project/create"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "videoUrl": video_url,
            "projectName": project_name,
            "lang": "en", # Vizard auto-detects, but 'en' or 'hi' can be tipped
            "preferLength": 30 # Seconds
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Expecting something like {"data": {"projectId": "..."}}
            project_id = data.get("data", {}).get("projectId")
            logger.info(f"Vizard project created: {project_id}")
            return project_id
        except Exception as e:
            logger.error(f"Vizard project creation failed: {e}")
            return None

    def get_clips(self, project_id: str):
        """
        Polls Vizard AI for the generated clips.
        """
        endpoint = f"{self.BASE_URL}/project/clip/list"
        headers = {"api-key": self.api_key}
        params = {"projectId": project_id}

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Returns a list of viral clips with scores and URLs
            return data.get("data", {}).get("list", [])
        except Exception as e:
            logger.error(f"Failed to fetch clips from Vizard: {e}")
            return []
