
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
            raise Exception("Vizard API Key missing in environment variables.")

        endpoint = f"{self.BASE_URL}/project/create"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "videoUrl": video_url,
            "projectName": project_name,
            "lang": "en", 
            "preferLength": 30 
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            if response.status_code != 200:
                error_body = response.text
                logger.error(f"Vizard API Error ({response.status_code}): {error_body}")
                raise Exception(f"Vizard API Error: {error_body}")
                
            data = response.json()
            project_id = data.get("data", {}).get("projectId")
            if not project_id:
                raise Exception(f"Vizard response missing projectId. Full Data: {data}")
                
            logger.info(f"Vizard project created: {project_id}")
            return project_id
        except Exception as e:
            logger.error(f"Vizard project creation failed: {e}")
            raise

    def get_clips(self, project_id: str):
        """
        Polls Vizard AI for the generated clips.
        """
        endpoint = f"{self.BASE_URL}/project/clip/list"
        headers = {"api-key": self.api_key}
        params = {"projectId": project_id}

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                logger.error(f"Vizard Get Clips Error ({response.status_code}): {response.text}")
                return []
            
            data = response.json()
            # Vizard status codes: 0 = OK, etc.
            clips_list = data.get("data", {}).get("list", [])
            return clips_list
        except Exception as e:
            logger.error(f"Failed to fetch clips from Vizard: {e}")
            return []
