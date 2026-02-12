
import os
import logging
from PIL import Image, ImageDraw, ImageFont
import cv2

logger = logging.getLogger(__name__)

class FramePowerAgent:
    """
    Agent #3: Responsible for extracting high-impact frames and 
    generating posters with text overlays.
    """
    
    def __init__(self, font_path="arial.ttf"):
        # We try to use a bold system font
        self.font_path = font_path

    def create_viral_poster(self, frame_path: str, text: str, output_path: str):
        """
        Takes a frame and adds bold text overlay.
        """
        try:
            img = Image.open(frame_path)
            draw = ImageDraw.Draw(img)
            width, height = img.size
            
            # Position text at the bottom third
            try:
                font = ImageFont.truetype(self.font_path, size=int(height * 0.08))
            except:
                font = ImageFont.load_default()

            # Text Shadow/Outline for visibility
            text_pos = (width // 10, height - (height // 3))
            
            # Draw shadow
            draw.text((text_pos[0]+5, text_pos[1]+5), text, font=font, fill="black")
            # Draw primary text (Yellow is very popular in Haryanvi thumbnails)
            draw.text(text_pos, text, font=font, fill="#FFD700")

            img.save(output_path, quality=95)
            logger.info(f"Poster created: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Poster generation failed: {e}")
            return None
