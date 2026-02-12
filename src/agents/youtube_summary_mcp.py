
import httpx
import asyncio
import json
import logging
import os
from fastmcp import FastMCP

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rapidapi_youtube_summary_v1")

# Initialize FastMCP
mcp = FastMCP("rapidapi_youtube_summary_v1")

# RapidAPI Configuration
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "65cf49e56cmsh966f0396dbbdc45p176547jsnaa1e6cd52a44")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "youtube-video-summarizer1.p.rapidapi.com")

# OpenAI Key for the API (Internal to the summarizer)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

async def call_summarizer_api(video_url: str) -> str:
    """Helper function to call the RapidAPI YouTube Summarizer."""
    url = f"https://{RAPIDAPI_HOST}/v1/youtube/summarizeVideoWithToken"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "openai-api-key": OPENAI_API_KEY
    }
    params = {"videoURL": video_url}
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Summarizing video: {video_url}")
            resp = await client.get(url, headers=headers, params=params, timeout=120)
            
            if resp.status_code == 200:
                # The response is usually the markdown summary directly
                return resp.text
            else:
                logger.error(f"API Error: {resp.status_code} - {resp.text}")
                return f"Error from YouTube Summarizer API ({resp.status_code}): {resp.text}"
                
        except Exception as e:
            logger.exception("Technical error during API call")
            return f"Technical Error connecting to RapidAPI: {str(e)}"

@mcp.tool()
async def rapidapi_youtube_summary_cache_v1(video_url: str) -> str:
    """
    Return the video summary of a given YouTube video that has already been summarized.
    The summary is provided in markdown format.
    """
    return await call_summarizer_api(video_url)

@mcp.tool()
async def rapidapi_youtube_summary_token_v1(video_url: str) -> str:
    """
    Summarize a YouTube video using a token/url.
    Returns the summary in markdown format.
    """
    return await call_summarizer_api(video_url)

if __name__ == "__main__":
    mcp.run()
