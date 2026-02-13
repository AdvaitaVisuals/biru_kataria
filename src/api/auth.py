
import os
import json
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from src.database import get_db
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/google", tags=["Auth"])

# Google OAuth config
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

@router.get("/login")
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
        scopes=SCOPES,
        redirect_uri=f"{settings.api_base_url}/auth/google/callback"
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    return RedirectResponse(authorization_url)

@router.get("/callback")
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
        scopes=SCOPES,
        redirect_uri=f"{settings.api_base_url}/auth/google/callback"
    )
    
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # In a real app, we save this to a database or encrypted storage
    # For now, we'll store it in a local file as a "token.json" (Vercel has limited persistence, so DB is better)
    token_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    # TODO: Save to a secure place. For now, we log that it was successful.
    logger.info("Google OAuth Token generated successfully")
    
    # Save to a temporary location for the agent to use
    with open("google_token.json", "w") as f:
        json.dump(token_data, f)
        
    return {"status": "SUCCESS", "message": "Google Calendar linked! Biru Bhai can now manage your events."}
