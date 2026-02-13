import os
import time
import logging
import requests
from src.config import settings

logger = logging.getLogger(__name__)


class AutoPoster:
    """Auto-posting agent for GOGA BHAI. Handles posting clips to Instagram Reels and YouTube Shorts."""

    def __init__(self):
        """Initialize with settings from src.config."""
        self.instagram_access_token = settings.instagram_access_token
        self.instagram_user_id = settings.instagram_business_account_id
        self.youtube_client_id = settings.youtube_client_id
        self.youtube_client_secret = settings.youtube_client_secret
        self.youtube_refresh_token = settings.youtube_refresh_token
        self.request_timeout = 30
        logger.info("AutoPoster initialized with configuration from settings")

    def post_to_instagram_reels(self, video_url: str, caption: str) -> dict:
        """
        Post a clip to Instagram Reels.

        Args:
            video_url: URL of the video to upload
            caption: Caption text for the reel

        Returns:
            dict: {"post_id": str, "platform": "INSTAGRAM", "status": "POSTED"} on success
                  {"status": "SKIPPED", "message": "..."} if credentials missing
                  {"status": "ERROR", "message": "..."} on failure
        """
        if not self.instagram_access_token or not self.instagram_user_id:
            logger.warning("Instagram credentials not configured, skipping Instagram post")
            return {
                "status": "SKIPPED",
                "message": "Instagram credentials not configured"
            }

        try:
            logger.info(f"Starting Instagram Reels upload for video: {video_url}")

            # Step 1: Create media object
            media_endpoint = f"https://graph.facebook.com/v18.0/{self.instagram_user_id}/media"
            media_payload = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": self.instagram_access_token
            }

            logger.debug(f"Creating media object at {media_endpoint}")
            media_response = requests.post(
                media_endpoint,
                json=media_payload,
                timeout=self.request_timeout
            )
            media_response.raise_for_status()
            media_data = media_response.json()

            if "id" not in media_data:
                error_msg = f"Failed to create Instagram media object: {media_data}"
                logger.error(error_msg)
                return {"status": "ERROR", "message": error_msg}

            creation_id = media_data["id"]
            logger.info(f"Media object created with ID: {creation_id}")

            # Step 2: Poll for processing status (max 30 polls, 2 seconds each)
            max_polls = 30
            poll_interval = 2
            status_endpoint = f"https://graph.facebook.com/v18.0/{creation_id}"

            for poll_count in range(max_polls):
                logger.debug(f"Polling status (attempt {poll_count + 1}/{max_polls})")
                time.sleep(poll_interval)

                status_response = requests.get(
                    status_endpoint,
                    params={
                        "fields": "status_code",
                        "access_token": self.instagram_access_token
                    },
                    timeout=self.request_timeout
                )
                status_response.raise_for_status()
                status_data = status_response.json()
                status_code = status_data.get("status_code")

                logger.debug(f"Current status code: {status_code}")

                if status_code == "FINISHED":
                    logger.info(f"Media processing finished after {(poll_count + 1) * poll_interval} seconds")
                    break
            else:
                # Polling timed out
                error_msg = f"Media processing did not complete within {max_polls * poll_interval} seconds"
                logger.error(error_msg)
                return {"status": "ERROR", "message": error_msg}

            # Step 3: Publish the media
            publish_endpoint = f"https://graph.facebook.com/v18.0/{self.instagram_user_id}/media_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": self.instagram_access_token
            }

            logger.debug(f"Publishing media at {publish_endpoint}")
            publish_response = requests.post(
                publish_endpoint,
                json=publish_payload,
                timeout=self.request_timeout
            )
            publish_response.raise_for_status()
            publish_data = publish_response.json()

            post_id = publish_data.get("id")
            if not post_id:
                error_msg = f"Failed to publish Instagram media: {publish_data}"
                logger.error(error_msg)
                return {"status": "ERROR", "message": error_msg}

            logger.info(f"Successfully posted to Instagram Reels with post_id: {post_id}")
            return {
                "post_id": post_id,
                "platform": "INSTAGRAM",
                "status": "POSTED"
            }

        except requests.exceptions.Timeout as e:
            error_msg = f"Instagram API timeout: {str(e)}"
            logger.error(error_msg)
            return {"status": "ERROR", "message": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Instagram API request failed: {str(e)}"
            logger.error(error_msg)
            return {"status": "ERROR", "message": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error posting to Instagram: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": "ERROR", "message": error_msg}

    def post_to_youtube_shorts(self, video_url: str, title: str, description: str, tags: list = None) -> dict:
        """
        Post a clip to YouTube Shorts.

        Args:
            video_url: URL of the video to upload
            title: Title of the YouTube Short
            description: Description of the YouTube Short
            tags: Optional list of tags/keywords

        Returns:
            dict: {"video_id": str, "platform": "YOUTUBE", "status": "POSTED"} on success
                  {"status": "SKIPPED", "message": "..."} if credentials missing
                  {"status": "ERROR", "message": "..."} on failure
        """
        if not self.youtube_refresh_token or not self.youtube_client_id or not self.youtube_client_secret:
            logger.warning("YouTube credentials not configured, skipping YouTube post")
            return {
                "status": "SKIPPED",
                "message": "YouTube credentials not configured"
            }

        temp_file_path = None
        try:
            logger.info(f"Starting YouTube Shorts upload for video: {video_url}")

            # Step 1: Refresh OAuth2 token
            logger.debug("Refreshing YouTube OAuth2 token")
            access_token = self._refresh_youtube_token()
            if not access_token:
                error_msg = "Failed to refresh YouTube access token"
                logger.error(error_msg)
                return {"status": "ERROR", "message": error_msg}

            # Step 2: Download video from video_url to /tmp
            logger.debug(f"Downloading video from {video_url}")
            temp_file_path = self._download_video(video_url)
            if not temp_file_path or not os.path.exists(temp_file_path):
                error_msg = "Failed to download video file"
                logger.error(error_msg)
                return {"status": "ERROR", "message": error_msg}

            # Step 3: Add "#Shorts" to title
            youtube_title = f"{title} #Shorts"
            if tags is None:
                tags = []
            tags.append("Shorts")

            # Step 4: Initiate resumable upload
            logger.debug("Initiating resumable upload")
            upload_url = self._initiate_resumable_upload(access_token, youtube_title, description, tags)
            if not upload_url:
                error_msg = "Failed to initiate resumable upload"
                logger.error(error_msg)
                return {"status": "ERROR", "message": error_msg}

            # Step 5: Upload video bytes
            logger.debug(f"Uploading video to {upload_url}")
            video_id = self._upload_video_bytes(upload_url, temp_file_path, access_token)
            if not video_id:
                error_msg = "Failed to upload video bytes"
                logger.error(error_msg)
                return {"status": "ERROR", "message": error_msg}

            logger.info(f"Successfully posted to YouTube Shorts with video_id: {video_id}")
            return {
                "video_id": video_id,
                "platform": "YOUTUBE",
                "status": "POSTED"
            }

        except Exception as e:
            error_msg = f"Unexpected error posting to YouTube: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": "ERROR", "message": error_msg}
        finally:
            # Step 6: Clean up /tmp file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    logger.debug(f"Cleaning up temporary file: {temp_file_path}")
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_file_path}: {str(e)}")

    def _refresh_youtube_token(self) -> str:
        """
        Refresh YouTube OAuth2 access token.

        Returns:
            str: The new access_token on success, empty string on failure
        """
        try:
            token_endpoint = "https://oauth2.googleapis.com/token"
            payload = {
                "client_id": self.youtube_client_id,
                "client_secret": self.youtube_client_secret,
                "refresh_token": self.youtube_refresh_token,
                "grant_type": "refresh_token"
            }

            logger.debug(f"Requesting new access token from {token_endpoint}")
            response = requests.post(
                token_endpoint,
                data=payload,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            token_data = response.json()

            access_token = token_data.get("access_token")
            if not access_token:
                logger.error(f"No access_token in response: {token_data}")
                return ""

            logger.debug("YouTube access token refreshed successfully")
            return access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh YouTube token: {str(e)}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error refreshing YouTube token: {str(e)}", exc_info=True)
            return ""

    def _download_video(self, video_url: str) -> str:
        """
        Download video from URL to /tmp directory.

        Args:
            video_url: URL of the video to download

        Returns:
            str: Path to the downloaded file on success, empty string on failure
        """
        try:
            logger.debug(f"Downloading video from {video_url}")
            response = requests.get(video_url, timeout=self.request_timeout, stream=True)
            response.raise_for_status()

            # Determine file extension from Content-Type header
            content_type = response.headers.get("content-type", "video/mp4")
            file_extension = "mp4"
            if "webm" in content_type:
                file_extension = "webm"
            elif "quicktime" in content_type:
                file_extension = "mov"

            # Create temp file
            temp_file_path = os.path.join(
                "/tmp" if os.name != "nt" else os.environ.get("TEMP", "C:\\temp"),
                f"biru_bhai_video_{int(time.time())}.{file_extension}"
            )

            # Write video bytes to temp file
            with open(temp_file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size = os.path.getsize(temp_file_path)
            logger.info(f"Video downloaded successfully to {temp_file_path} ({file_size} bytes)")
            return temp_file_path

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download video: {str(e)}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error downloading video: {str(e)}", exc_info=True)
            return ""

    def _initiate_resumable_upload(self, access_token: str, title: str, description: str, tags: list) -> str:
        """
        Initiate a resumable upload session with YouTube.

        Args:
            access_token: YouTube API access token
            title: Video title
            description: Video description
            tags: List of tags

        Returns:
            str: Resumable upload URL on success, empty string on failure
        """
        try:
            upload_endpoint = "https://www.googleapis.com/upload/youtube/v3/videos"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Goog-Upload-Protocol": "resumable"
            }
            params = {
                "uploadType": "resumable",
                "part": "snippet,status"
            }
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": "22"  # Category ID 22 is for "Shorts"
                },
                "status": {
                    "privacyStatus": "public"
                }
            }

            logger.debug(f"Initiating resumable upload to {upload_endpoint}")
            response = requests.post(
                upload_endpoint,
                headers=headers,
                params=params,
                json=body,
                timeout=self.request_timeout
            )
            response.raise_for_status()

            upload_url = response.headers.get("Location")
            if not upload_url:
                logger.error("No Location header in resumable upload response")
                return ""

            logger.debug(f"Resumable upload session initiated: {upload_url}")
            return upload_url

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to initiate resumable upload: {str(e)}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error initiating resumable upload: {str(e)}", exc_info=True)
            return ""

    def _upload_video_bytes(self, upload_url: str, file_path: str, access_token: str) -> str:
        """
        Upload video bytes to the resumable upload URL.

        Args:
            upload_url: The resumable upload URL
            file_path: Path to the video file
            access_token: YouTube API access token

        Returns:
            str: Video ID on success, empty string on failure
        """
        try:
            file_size = os.path.getsize(file_path)
            logger.debug(f"Uploading video file ({file_size} bytes) to {upload_url}")

            with open(file_path, "rb") as f:
                headers = {
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file_size)
                }
                response = requests.put(
                    upload_url,
                    data=f,
                    headers=headers,
                    timeout=self.request_timeout * 2  # Longer timeout for large uploads
                )
                response.raise_for_status()

            # Parse response to get video ID
            response_data = response.json()
            video_id = response_data.get("id")
            if not video_id:
                logger.error(f"No video ID in upload response: {response_data}")
                return ""

            logger.info(f"Video uploaded successfully with ID: {video_id}")
            return video_id

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload video bytes: {str(e)}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error uploading video bytes: {str(e)}", exc_info=True)
            return ""

    def post_to_instagram_photo(self, image_url: str, caption: str) -> dict:
        """
        Post a photo to Instagram Feed.
        """
        if not self.instagram_access_token or not self.instagram_user_id:
            return {"status": "SKIPPED", "message": "Instagram credentials missing"}

        try:
            logger.info(f"Starting Instagram Photo upload: {image_url}")
            # Step 1: Create Container
            url = f"https://graph.facebook.com/v18.0/{self.instagram_user_id}/media"
            payload = {
                "image_url": image_url,
                "caption": caption,
                "access_token": self.instagram_access_token
            }
            res = requests.post(url, json=payload, timeout=30)
            res.raise_for_status()
            creation_id = res.json().get("id")

            # Step 2: Publish
            if not creation_id: return {"status": "ERROR", "message": "No creation ID"}
            
            # Instagram requires waiting for media to be 'READY' usually only for video, but safer to check or just publish for image.
            # Images are usually ready immediately.
            
            pub_url = f"https://graph.facebook.com/v18.0/{self.instagram_user_id}/media_publish"
            pub_payload = {"creation_id": creation_id, "access_token": self.instagram_access_token}
            pub_res = requests.post(pub_url, json=pub_payload, timeout=30)
            pub_res.raise_for_status()
            
            return {"post_id": pub_res.json().get("id"), "platform": "INSTAGRAM", "status": "POSTED"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def post_to_facebook_photo(self, image_url: str, caption: str) -> dict:
        """
        Post a photo to Facebook Page. Supports local file path or URL.
        """
        fb_token = settings.facebook_access_token or self.instagram_access_token
        target_id = settings.facebook_page_id
        
        if not fb_token: return {"status": "SKIPPED", "message": "No FB Token"}
        if not target_id: return {"status": "SKIPPED", "message": "No FB Page ID"}
        
        url = f"https://graph.facebook.com/v18.0/{target_id}/photos"
        try:
            params = {
                "caption": caption,
                "access_token": fb_token
            }
            
            if os.path.exists(image_url):
                # Upload local file
                logger.info(f"Uploading local photo to FB: {image_url}")
                with open(image_url, 'rb') as f:
                    # 'source' is the field for file upload
                    res = requests.post(url, data=params, files={'source': f}, timeout=60)
            else:
                # Use URL
                logger.info(f"Posting photo URL to FB: {image_url}")
                params["url"] = image_url
                res = requests.post(url, params=params, timeout=45)

            res.raise_for_status()
            return {"post_id": res.json().get("id"), "platform": "FACEBOOK", "status": "POSTED"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def post_image(self, image_url: str, platforms: list, caption: str) -> list:
        """
        Post an image to multiple platforms.
        """
        results = []
        logger.info(f"Starting multi-platform image post to: {', '.join(platforms)}")

        for platform in platforms:
            p_upper = platform.upper()
            if p_upper == "INSTAGRAM":
                res = self.post_to_instagram_photo(image_url, caption)
            elif p_upper == "FACEBOOK":
                res = self.post_to_facebook_photo(image_url, caption)
            else:
                res = {"status": "SKIPPED", "message": f"Platform {platform} not supported for images"}
            
            if 'platform' not in res: res['platform'] = p_upper
            results.append(res)
        
        return results

    def post_to_facebook_video(self, video_url: str, caption: str) -> dict:
        """
        Post a clip to Facebook Video/Reels.
        Note: Requires Page Access Token with 'pages_manage_posts' permission.
        """
        # Use specific Facebook token if available, else fallback to IG token
        fb_token = settings.facebook_access_token or self.instagram_access_token
        if not fb_token:
            return {"status": "SKIPPED", "message": "Facebook/Meta credentials missing"}

        # Use Configured Page ID
        target_id = settings.facebook_page_id
        if not target_id:
             logger.warning("Facebook Page ID missing in settings. Simulating post.")
             return {"post_id": "simulated_fb_id_123", "platform": "FACEBOOK", "status": "SKIPPED", "message": "FACEBOOK_PAGE_ID missing"}
        
        endpoint = f"https://graph.facebook.com/v18.0/{target_id}/videos"
        try:
            logger.info(f"Posting to Facebook Page: {target_id}")
            payload = {
                "file_url": video_url,
                "description": caption,
                "access_token": fb_token
            }
            
            # Real API Request
            resp = requests.post(endpoint, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Facebook post successful: {data.get('id')}")
            return {"post_id": data.get("id"), "platform": "FACEBOOK", "status": "POSTED"}

        except Exception as e:
            logger.error(f"Facebook Post Failed: {e}")
            return {"status": "ERROR", "message": f"Facebook Post Failed: {e}"}

    def post_clip(self, video_url: str, platforms: list, captions: dict = None, title: str = None) -> list:
        """
        Post a clip to multiple platforms with specific captions.
        """
        results = []
        if captions is None: captions = {}
        
        # Fallback values
        defaults = {
            'ig': captions.get('ig') or title or "New Video",
            'yt': captions.get('yt') or title or "New Video",
            'fb': captions.get('fb') or captions.get('ig') or "Check this out!"
        }

        logger.info(f"Starting multi-platform post to: {', '.join(platforms)}")

        for platform in platforms:
            p_upper = platform.upper()
            logger.debug(f"Processing platform: {p_upper}")

            if p_upper == "INSTAGRAM":
                res = self.post_to_instagram_reels(video_url, defaults['ig'])
            elif p_upper == "YOUTUBE":
                res = self.post_to_youtube_shorts(video_url, defaults['yt'], defaults['yt'])
            elif p_upper == "FACEBOOK":
                res = self.post_to_facebook_video(video_url, defaults['fb'])
            else:
                logger.warning(f"Unknown platform: {platform}")
                res = {"status": "SKIPPED", "message": "Unknown platform"}
            
            if 'platform' not in res: res['platform'] = p_upper
            results.append(res)

        logger.info(f"Multi-platform post completed with {len(results)} results")
        return results
