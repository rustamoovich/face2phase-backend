"""
Service for processing media files: generating thumbnails, extracting PDF previews, etc.
"""
import io
import fitz  # PyMuPDF
from PIL import Image
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class MediaProcessingService:
    """Service for processing images, videos, and documents"""
    
    # Thumbnail sizes
    SMALL_SIZE = (300, 300)  # For feed/grid
    MEDIUM_SIZE = (800, 800)  # For viewing
    
    # Quality settings
    JPEG_QUALITY = 85
    PDF_DPI = 150
    
    @staticmethod
    def create_image_thumbnails(image_data: bytes) -> Tuple[bytes, bytes]:
        """
        Create small and medium thumbnails from image data
        
        Args:
            image_data: Original image bytes
            
        Returns:
            Tuple of (small_thumbnail_bytes, medium_thumbnail_bytes)
        """
        try:
            # Open original image
            img = Image.open(io.BytesIO(image_data))
            
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create small thumbnail
            small_img = img.copy()
            small_img.thumbnail(MediaProcessingService.SMALL_SIZE, Image.Resampling.LANCZOS)
            small_buffer = io.BytesIO()
            small_img.save(small_buffer, format='JPEG', quality=MediaProcessingService.JPEG_QUALITY, optimize=True)
            small_thumbnail = small_buffer.getvalue()
            
            # Create medium thumbnail
            medium_img = img.copy()
            medium_img.thumbnail(MediaProcessingService.MEDIUM_SIZE, Image.Resampling.LANCZOS)
            medium_buffer = io.BytesIO()
            medium_img.save(medium_buffer, format='JPEG', quality=MediaProcessingService.JPEG_QUALITY, optimize=True)
            medium_thumbnail = medium_buffer.getvalue()
            
            logger.info(f"Created thumbnails: small={len(small_thumbnail)} bytes, medium={len(medium_thumbnail)} bytes")
            
            return small_thumbnail, medium_thumbnail
            
        except Exception as e:
            logger.error(f"Error creating image thumbnails: {e}")
            raise
    
    @staticmethod
    def extract_pdf_first_page(pdf_data: bytes) -> bytes:
        """
        Extract first page of PDF as JPEG image
        
        Args:
            pdf_data: PDF file bytes
            
        Returns:
            JPEG bytes of first page
        """
        try:
            # Open PDF
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            
            if pdf_document.page_count == 0:
                raise ValueError("PDF has no pages")
            
            # Get first page
            first_page = pdf_document[0]
            
            # Render page to image
            mat = fitz.Matrix(MediaProcessingService.PDF_DPI / 72, MediaProcessingService.PDF_DPI / 72)
            pix = first_page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Save as JPEG
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=MediaProcessingService.JPEG_QUALITY, optimize=True)
            preview_bytes = buffer.getvalue()
            
            pdf_document.close()
            
            logger.info(f"Extracted PDF first page: {len(preview_bytes)} bytes")
            
            return preview_bytes
            
        except Exception as e:
            logger.error(f"Error extracting PDF first page: {e}")
            raise
    
    @staticmethod
    def create_video_poster(video_path: str) -> Optional[bytes]:
        """
        Extract first frame from video as poster image
        (Placeholder for future implementation with ffmpeg or similar)
        
        Args:
            video_path: Path to video file
            
        Returns:
            JPEG bytes of first frame or None
        """
        # TODO: Implement video poster extraction using ffmpeg-python or opencv
        logger.warning("Video poster extraction not yet implemented")
        return None
    
    @staticmethod
    def get_storage_path(event_id: str, media_type: str, category: str, filename: str) -> str:
        """
        Generate R2 storage path according to the structure:
        events/{event_id}/{media_type}/{category}/{filename}
        
        Args:
            event_id: UUID of the event
            media_type: photos/videos/documents/assets
            category: original/thumbnails/posters/previews/files
            filename: File name with extension
            
        Returns:
            Full R2 path
        """
        return f"events/{event_id}/{media_type}/{category}/{filename}"
    
    @staticmethod
    def detect_media_type(content_type: str, filename: str) -> Tuple[str, str]:
        """
        Detect media type and file type from content type and filename
        
        Args:
            content_type: MIME type
            filename: Original filename
            
        Returns:
            Tuple of (media_type, file_type)
            media_type: photos/videos/documents
            file_type: jpg/png/mp4/pdf/etc
        """
        content_type = content_type.lower()
        filename = filename.lower()
        
        # Images
        if content_type.startswith('image/'):
            if content_type == 'image/jpeg' or filename.endswith(('.jpg', '.jpeg')):
                return 'photos', 'jpg'
            elif content_type == 'image/png' or filename.endswith('.png'):
                return 'photos', 'png'
            elif content_type == 'image/gif' or filename.endswith('.gif'):
                return 'photos', 'gif'
            elif content_type == 'image/webp' or filename.endswith('.webp'):
                return 'photos', 'webp'
            else:
                return 'photos', 'jpg'  # Default to jpg
        
        # Videos
        elif content_type.startswith('video/'):
            if content_type == 'video/mp4' or filename.endswith('.mp4'):
                return 'videos', 'mp4'
            elif content_type == 'video/quicktime' or filename.endswith('.mov'):
                return 'videos', 'mov'
            elif content_type == 'video/x-msvideo' or filename.endswith('.avi'):
                return 'videos', 'avi'
            else:
                return 'videos', 'mp4'  # Default to mp4
        
        # Documents
        elif content_type == 'application/pdf' or filename.endswith('.pdf'):
            return 'documents', 'pdf'
        
        else:
            # Default fallback
            return 'photos', 'jpg'
