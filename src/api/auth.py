import os
import json
import logging
import requests
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from src.database import get_db
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

# Google OAuth config
GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# Facebook OAuth Config
FB_SCOPES = [
    "pages_show_list", 
    "pages_read_engagement", 
    "pages_manage_posts", 
    "instagram_basic", 
    "instagram_content_publish"
]

# ============================================================================
# GOOGLE AUTH
# ============================================================================

@router.get("/google/login")
async def google_login():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google Credentials missing in .env")
        
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "project_id": "biru-bhai-os",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": settings.google_client_secret,
            "redirect_uris": [f"{settings.api_base_url}/auth/google/callback"]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{settings.api_base_url}/auth/google/callback"
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    return RedirectResponse(authorization_url)

@router.get("/google/callback")
async def google_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
        
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "project_id": "biru-bhai-os",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": settings.google_client_secret,
            "redirect_uris": [f"{settings.api_base_url}/auth/google/callback"]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{settings.api_base_url}/auth/google/callback"
    )
    
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    token_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    with open("google_token.json", "w") as f:
        json.dump(token_data, f)
        
    return {"status": "SUCCESS", "message": "Google Calendar linked! Goga Bhai can now manage your events."}

# ============================================================================
# FACEBOOK AUTH
# ============================================================================

@router.get("/facebook/login")
async def facebook_login():
    if not settings.facebook_app_id or not settings.facebook_app_secret:
        raise HTTPException(status_code=500, detail="Facebook Credentials (App ID/Secret) missing in .env")

    redirect_uri = f"{settings.api_base_url}/auth/facebook/callback"
    scope_str = ",".join(FB_SCOPES)
    
    # State should ideally be random string, using 'birubhai_state' for simplicity
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={settings.facebook_app_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state=birubhai_state"
        f"&scope={scope_str}"
    )
    
    return RedirectResponse(auth_url)


@router.get("/facebook/callback")
async def facebook_callback(request: Request):
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    if error:
        return {"status": "ERROR", "message": f"Facebook Login Failed: {error}"}
    if not code:
        return {"status": "ERROR", "message": "No code provided"}

    redirect_uri = f"{settings.api_base_url}/auth/facebook/callback"

    # Exchange Code for Access Token
    token_url = (
        f"https://graph.facebook.com/v18.0/oauth/access_token?"
        f"client_id={settings.facebook_app_id}"
        f"&redirect_uri={redirect_uri}"
        f"&client_secret={settings.facebook_app_secret}"
        f"&code={code}"
    )
    
    try:
        resp = requests.get(token_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("access_token")
        
        if not access_token:
             return {"status": "ERROR", "message": "Failed to retrieve access token"}

        # Exchange for Long-Lived Token (optional but recommended)
        # We'll save the token we got for now.
        
        token_data = {
            "access_token": access_token,
            "token_type": data.get("token_type"),
            "expires_in": data.get("expires_in")
        }
        
        # Save to local file
        with open("facebook_token.json", "w") as f:
            json.dump(token_data, f)
            
        return {"status": "SUCCESS", "message": "Facebook Login Successful! Token saved."}

    except Exception as e:
        logger.error(f"Facebook Auth Error: {e}")
        return {"status": "ERROR", "message": str(e)}
