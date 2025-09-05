from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from pydantic import BaseModel
import yt_dlp
import os
import logging
import shutil
from fastapi.responses import FileResponse
import uuid
import subprocess
import secrets
import time
from datetime import datetime
import pkg_resources
import sys
import asyncio
from fastapi import BackgroundTasks
import logging.handlers
from contextlib import asynccontextmanager

# Import Instagram configuration
try:
    from modules.const import InstagramConfig
except ImportError:
    # Fallback configuration if import fails
    class InstagramConfig:
        MAX_RETRIES = 6
        RETRY_DELAY_BASE = 2
        RETRY_BACKOFF_MULTIPLIER = 2.0
        MAX_RETRY_DELAY = 30
        RETRY_ERROR_PATTERNS = [
            'extraction', 'unavailable', 'private', 'login required', 'cookie',
            'network', 'timeout', 'connection', '403', '429', '502', '503', '504'
        ]
        USER_AGENTS = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Instagram 123.0.0.21.114 (iPhone12,1; iOS 14_2; en_US; en-US; scale=2.00; 828x1792; 239485664) AppleWebKit/420+'
        ]

# Enhanced logging
import logging.handlers

# Create logs directory if it doesn't exist
LOGS_DIR = "/var/log"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "ytdl_service.log")

# Configure logging
logger = logging.getLogger("ytdl_service")
logger.setLevel(logging.INFO)

# Create formatters
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# File handler with rotation
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Prevent propagation to root logger
logger.propagate = False

# Configuration
DOWNLOADS_DIR = "/opt/ytdl_service/downloads"
API_KEY_FILE = "/opt/ytdl_service/api_key.txt"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Add configuration for update check and cleanup
YTDLP_UPDATE_INTERVAL = 24 * 60 * 60  # 24 hours in seconds
CLEANUP_INTERVAL = 60 * 60  # 1 hour in seconds
FILE_MAX_AGE = 24 * 60 * 60  # 24 hours in seconds

last_update_check = 0
last_update_status = None
last_cleanup_time = 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(periodic_tasks())
    logger.info("Background tasks started")
    yield
    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Background tasks cancelled")

app = FastAPI(lifespan=lifespan)

# Handle API key
def get_api_key():
    if not os.path.exists(API_KEY_FILE):
        try:
            api_key = secrets.token_urlsafe(32)
            with open(API_KEY_FILE, "w") as f:
                f.write(api_key)
            logger.info(f"Generated new API key file: {API_KEY_FILE}")
            return api_key
        except IOError as e:
            logger.error(f"Error writing API key file {API_KEY_FILE}: {e}")
            logger.warning("Failed to write API key file, using temporary key.")
            return secrets.token_urlsafe(32)
    else:
        try:
            with open(API_KEY_FILE, "r") as f:
                return f.read().strip()
        except IOError as e:
            logger.error(f"Error reading API key file {API_KEY_FILE}: {e}")
            logger.warning("Failed to read API key file, using temporary key.")
            return secrets.token_urlsafe(32)

API_KEY = get_api_key()
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header != API_KEY:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
    return api_key_header

class DownloadRequest(BaseModel):
    url: str
    format: str = 'best[ext=mp4]/best'
    subtitles: bool = False
    audio_only: bool = False
    max_height: int = 1080

def check_and_update_ytdlp():
    """Check if yt-dlp is up to date and update if necessary"""
    try:
        # Get current version
        current_version = yt_dlp.version.__version__
        
        # Get latest version from PyPI
        latest_version = subprocess.check_output(
            [sys.executable, "-m", "pip", "index", "versions", "yt-dlp"],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Parse the output to get the latest version
        latest_version = latest_version.split("LATEST: ")[1].split("\n")[0].strip()
        
        if latest_version > current_version:
            logger.info(f"Updating yt-dlp from {current_version} to {latest_version}")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("yt-dlp updated successfully")
            return True, latest_version
        
        return False, current_version
        
    except Exception as e:
        logger.error(f"Error checking/updating yt-dlp: {str(e)}")
        return False, current_version if 'current_version' in locals() else "unknown"

async def cleanup_old_files():
    """Clean up files older than FILE_MAX_AGE"""
    global last_cleanup_time
    current_time = time.time()
    
    if current_time - last_cleanup_time < CLEANUP_INTERVAL:
        return
    
    logger.info("Running periodic cleanup of old files...")
    deleted_count = 0
    saved_space = 0
    
    try:
        for filename in os.listdir(DOWNLOADS_DIR):
            file_path = os.path.join(DOWNLOADS_DIR, filename)
            if os.path.isfile(file_path):
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > FILE_MAX_AGE:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        saved_space += file_size
                        logger.info(f"Cleaned up old file: {filename} (age: {round(file_age/3600, 1)} hours)")
                except Exception as e:
                    logger.warning(f"Error cleaning up file {filename}: {e}")
        
        logger.info(f"Cleanup completed: {deleted_count} files deleted, {round(saved_space/(1024*1024), 2)} MB saved")
        last_cleanup_time = current_time
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

async def periodic_tasks():
    """Background task to periodically check for updates and cleanup"""
    global last_update_check, last_update_status
    
    while True:
        try:
            current_time = time.time()
            
            # Check for yt-dlp updates
            if current_time - last_update_check >= YTDLP_UPDATE_INTERVAL:
                logger.info("Running periodic yt-dlp update check")
                was_updated, version = check_and_update_ytdlp()
                last_update_check = current_time
                last_update_status = {
                    "was_updated": was_updated,
                    "version": version,
                    "timestamp": datetime.now().isoformat()
                }
                logger.info(f"yt-dlp update check completed: {last_update_status}")
            
            # Run cleanup
            await cleanup_old_files()
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in periodic tasks: {str(e)}")
            await asyncio.sleep(300)  # Wait 5 minutes before retrying on error

@app.get("/health")
async def health_check():
    # Public endpoint, no API key required
    try:
        # Check for ffmpeg
        ffmpeg_available = subprocess.run(
            ["which", "ffmpeg"],
            capture_output=True
        ).returncode == 0
        
        # Check for required directory permissions
        write_permission = os.access(DOWNLOADS_DIR, os.W_OK)
        read_permission = os.access(DOWNLOADS_DIR, os.R_OK)
        
        # Get current yt-dlp version without checking for updates
        current_version = yt_dlp.version.__version__
        
        return {
            "status": "healthy",
            "ffmpeg_available": ffmpeg_available,
            "yt_dlp_version": current_version,
            "last_update_check": datetime.fromtimestamp(last_update_check).isoformat() if last_update_check else None,
            "last_update_status": last_update_status,
            "downloads_dir": DOWNLOADS_DIR,
            "downloads_dir_writeable": write_permission,
            "downloads_dir_readable": read_permission,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def get_video_info(file_path):
    """Get video information using ffprobe"""
    try:
        ffprobe_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if video_stream:
                width = video_stream.get('width', 0)
                height = video_stream.get('height', 0)
                codec = video_stream.get('codec_name', 'unknown')
                logger.info(f"Video info: {width}x{height}, codec: {codec}")
                return {
                    'width': width,
                    'height': height,
                    'codec': codec,
                    'quality_score': height if height else 0
                }
                
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
    
    return {'width': 0, 'height': 0, 'codec': 'unknown', 'quality_score': 0}

def find_downloaded_file(download_id):
    """Find the downloaded file with the given ID"""
    try:
        if not os.path.exists(DOWNLOADS_DIR):
            logger.error(f"Downloads directory doesn't exist: {DOWNLOADS_DIR}")
            return None
        
        files_in_dir = os.listdir(DOWNLOADS_DIR)
        logger.info(f"Looking for files with prefix '{download_id}' in {len(files_in_dir)} files")
        
        # Look for files with our download_id
        matching_files = []
        for fname in files_in_dir:
            if fname.startswith(download_id):
                fpath = os.path.join(DOWNLOADS_DIR, fname)
                if os.path.isfile(fpath):
                    size = os.path.getsize(fpath)
                    if size > 0:
                        matching_files.append((fpath, size, fname))
                        logger.info(f"Found matching file: {fname} ({size} bytes)")
        
        if matching_files:
            # Sort by file size (largest first) to get the main video file
            matching_files.sort(key=lambda x: x[1], reverse=True)
            best_file = matching_files[0][0]
            logger.info(f"Selected best file: {os.path.basename(best_file)} ({matching_files[0][1]} bytes)")
            return best_file
        
        logger.error(f"No matching files found for download_id: {download_id}")
        logger.info(f"Available files: {[f for f in files_in_dir if os.path.isfile(os.path.join(DOWNLOADS_DIR, f))]}")
        return None
        
    except Exception as e:
        logger.error(f"Error finding downloaded file: {e}")
        return None

def cleanup_files(prefix):
    """Clean up all files with the given prefix"""
    try:
        if not os.path.exists(DOWNLOADS_DIR):
            logger.error(f"Downloads directory doesn't exist: {DOWNLOADS_DIR}")
            return
        
        for item in os.listdir(DOWNLOADS_DIR):
            if item.startswith(prefix):
                item_path = os.path.join(DOWNLOADS_DIR, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        logger.info(f"Cleaned up file: {item}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        logger.info(f"Cleaned up directory: {item}")
                except Exception as e:
                    logger.warning(f"Failed to clean up item {item}: {e}")
                    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def download_youtube_video(request: DownloadRequest, download_id: str, output_template: str):
    """Enhanced YouTube download with working strategies"""
    
    # Detect YouTube Shorts, Clips, and regular videos
    is_youtube_shorts = "youtube.com/shorts" in request.url
    is_youtube_clips = "youtube.com/clip" in request.url
    is_youtube = any(x in request.url for x in ["youtube.com", "youtu.be"])
    
    if not is_youtube:
        return None  # Not YouTube, use regular download
    
    logger.info(f"🎬 YouTube download detected: {request.url}")
    logger.info(f"   Type: {'Shorts' if is_youtube_shorts else 'Clips' if is_youtube_clips else 'Regular'}")
    
    # Define working strategies based on bot testing
    strategies = [
        {
            'name': 'Android client (proven working)',
            'opts': {
                'format': '18/22/best[ext=mp4]/best',
                'outtmpl': output_template,
                'restrictfilenames': True,
                'retries': 2,
                'fragment_retries': 2,
                'socket_timeout': 30,
                'ignoreerrors': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'quiet': False,
                'no_warnings': False,
                'http_headers': {
                    'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android']
                    }
                },
                'postprocessors': []  # No post-processing for reliability
            }
        },
        {
            'name': 'iOS client fallback',
            'opts': {
                'format': 'bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]/18/22/best',
                'outtmpl': output_template,
                'restrictfilenames': True,
                'retries': 2,
                'fragment_retries': 2,
                'socket_timeout': 30,
                'ignoreerrors': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'quiet': False,
                'no_warnings': False,
                'http_headers': {
                    'User-Agent': 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)'
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['ios']
                    }
                },
                'postprocessors': []
            }
        },
        {
            'name': 'Web client with headers',
            'opts': {
                'format': '18/22/best[ext=mp4]/best',
                'outtmpl': output_template,
                'restrictfilenames': True,
                'retries': 2,
                'fragment_retries': 2,
                'socket_timeout': 30,
                'ignoreerrors': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'quiet': False,
                'no_warnings': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.youtube.com/'
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web']
                    }
                },
                'postprocessors': []
            }
        }
    ]
    
    # Try each strategy
    for i, strategy in enumerate(strategies, 1):
        logger.info(f"📋 Trying YouTube strategy {i}/{len(strategies)}: {strategy['name']}")
        
        try:
            with yt_dlp.YoutubeDL(strategy['opts']) as ydl:
                info = ydl.extract_info(request.url, download=True)
                
                if info:
                    logger.info(f"✅ YouTube strategy '{strategy['name']}' succeeded!")
                    
                    # Wait for file system
                    time.sleep(2)
                    
                    # Find downloaded file
                    downloaded_file = find_downloaded_file(download_id)
                    if downloaded_file:
                        video_info = get_video_info(downloaded_file)
                        logger.info(f"YouTube download successful: {os.path.basename(downloaded_file)} - {video_info['width']}x{video_info['height']}")
                        
                        return {
                            "success": True,
                            "file_path": os.path.basename(downloaded_file),
                            "download_url": f"/files/{os.path.basename(downloaded_file)}",
                            "title": info.get('title', 'YouTube Video'),
                            "url": request.url,
                            "description": info.get('description', ''),
                            "tags": info.get('tags', []),
                            "duration": info.get('duration'),
                            "uploader": info.get('uploader'),
                            "file_size_bytes": os.path.getsize(downloaded_file),
                            "file_size_mb": round(os.path.getsize(downloaded_file) / (1024 * 1024), 2),
                            "video_info": video_info,
                            "quality": f"{video_info['width']}x{video_info['height']}" if video_info['width'] > 0 else "Audio only",
                            "strategy_used": strategy['name']
                        }
                    else:
                        logger.error(f"Downloaded file not found for strategy: {strategy['name']}")
                        
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"❌ YouTube strategy '{strategy['name']}' failed: {str(e)}")
            cleanup_files(download_id)
        except Exception as e:
            logger.error(f"❌ YouTube strategy '{strategy['name']}' error: {str(e)}")
            cleanup_files(download_id)
    
        # All strategies failed
        logger.error(f"❌ All Instagram strategies failed for: {request.url}")
        logger.error("This is likely due to Instagram's anti-bot measures requiring authentication")
        logger.error("Common issues: CSRF token missing, rate limiting, login requirements, or service outages")

        # Provide specific guidance based on error patterns
        error_suggestions = []
        if "instagramez.com" in request.url:
            error_suggestions.append("Try using direct Instagram URLs instead of instagramez.com")

        # Check for common error patterns in the last error message
        last_error_msg = str(error_msg).lower() if error_msg else ""
        if last_error_msg:
            if "csrf" in last_error_msg or "login" in last_error_msg:
                error_suggestions.append("Instagram requires authentication - consider using valid cookies")
            if "rate" in last_error_msg:
                error_suggestions.append("Rate limited - wait a few minutes before retrying")
            if "500" in last_error_msg or "internal server" in last_error_msg:
                error_suggestions.append("Service may be experiencing issues - try again later")

        # Ensure variables are defined for error reporting
        if 'instagram_strategies' not in locals():
            instagram_strategies = []

        if not error_suggestions:
            error_suggestions.append("Try obtaining valid Instagram cookies or use a different download method")

        return {
            "success": False,
            "error": "All Instagram download strategies failed. Instagram may require authentication or has updated their anti-bot measures.",
            "error_type": "all_strategies_failed",
            "suggestions": error_suggestions,
            "strategies_attempted": len(instagram_strategies) + 1,  # +1 for embed attempt
            "last_error": last_error_msg[:200] if last_error_msg else "Unknown error"
        }

@app.post("/download")
async def download_video(request: DownloadRequest,
                        background_tasks: BackgroundTasks,
                        api_key: str = Depends(verify_api_key)):
    
    download_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOADS_DIR, f'{download_id}.%(ext)s')
    
    # Clean up any existing files with this ID
    cleanup_files(download_id)
    
    # Check if it's YouTube and use specialized handler
    is_youtube = any(x in request.url for x in ["youtube.com", "youtu.be"])
    
    if is_youtube:
        logger.info(f"🎯 YouTube URL detected, using specialized handler: {request.url}")
        result = download_youtube_video(request, download_id, output_template)
        if result:
            return result
        # If YouTube handler fails, fall through to regular handler
        logger.warning("YouTube handler failed, trying regular handler")
    
    # Instagram detection - expanded patterns including instagramez redirects
    is_instagram = any(x in request.url for x in [
        "instagram.com/p/", "instagram.com/reel/", "instagram.com/tv/",
        "instagram.com/stories/", "instagram.com/reels/", "instagram.com/explore/",
        "www.instagram.com/p/", "www.instagram.com/reel/", "www.instagram.com/tv/",
        "www.instagram.com/stories/", "www.instagram.com/reels/",
        "instagramez.com/reel/", "instagramez.com/p/", "instagramez.com/tv/"
    ])

    # Convert instagramez.com URLs to direct Instagram URLs for better compatibility
    if "instagramez.com" in request.url:
        original_url = request.url
        request.url = request.url.replace("instagramez.com", "www.instagram.com")
        logger.info(f"🔄 Converted instagramez URL to direct Instagram: {original_url} -> {request.url}")

    if is_instagram:
        logger.info(f"📸 Instagram download attempt: {request.url}")

        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

        # Initialize variables for error handling
        error_msg = ""
        instagram_strategies = []

        # Define Instagram-specific retry strategies using configuration
        # Define Instagram-specific retry strategies using configuration
        # These strategies simulate clicking "X" to close login popup
        instagram_strategies = [
            {
                'name': 'Instagram Mobile API (bypass popup)',
                'user_agent': InstagramConfig.USER_AGENTS[2],
                'headers': {
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'X-IG-App-ID': '936619743392459',
                    'X-IG-WWW-Claim': '0',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-Instagram-AJAX': '1',
                    'X-CSRFToken': 'missing',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'X-IG-App-Startup-Country': 'US',
                },
                'extractor_args': {
                    'instagram': {
                        'api_hostname': 'i.instagram.com',
                        'api_version': 'v1'
                    }
                }
            },
            {
                'name': 'Embed Endpoint (popup bypass)',
                'user_agent': InstagramConfig.USER_AGENTS[0],
                'headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'cross-site',
                    'Cache-Control': 'max-age=0',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                'extractor_args': {
                    'instagram': {
                        'api_hostname': 'www.instagram.com',
                        'api_version': 'v1'
                    }
                }
            },
            {
                'name': 'Direct Media API (no popup)',
                'user_agent': InstagramConfig.USER_AGENTS[1],
                'headers': {
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Range': 'bytes=0-',
                    'Cache-Control': 'no-cache',
                    'Referer': 'https://www.instagram.com/',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-Instagram-AJAX': '1',
                },
                'extractor_args': {
                    'instagram': {
                        'api_hostname': 'www.instagram.com',
                        'api_version': 'v1'
                    }
                }
            },
            {
                'name': 'Legacy Mobile (popup resistant)',
                'user_agent': InstagramConfig.USER_AGENTS[3],
                'headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-Instagram-AJAX': '1',
                },
                'extractor_args': {
                    'instagram': {
                        'api_hostname': 'i.instagram.com',
                        'api_version': 'v1'
                    }
                }
            },
            {
                'name': 'Anonymous Browser (stealth mode)',
                'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                'extractor_args': {
                    'instagram': {
                        'api_hostname': 'www.instagram.com',
                        'api_version': 'v1'
                    }
                }
            },
            {
                'name': 'Instagram GraphQL API (advanced)',
                'user_agent': InstagramConfig.USER_AGENTS[2],
                'headers': {
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'X-IG-App-ID': '936619743392459',
                    'X-IG-WWW-Claim': '0',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-Instagram-AJAX': '1',
                    'X-CSRFToken': 'missing',
                    'X-IG-WWW-Claim': 'hmac.AR0PlJC1Fi2YV2NJjIg6hcCgcYcX_OYJ9X9Q9Vj2QgE1',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'X-ASBD-ID': '198387',
                    'X-FB-Friendly-Name': 'PolarisPostActionLoadPostQueryQuery',
                },
                'extractor_args': {
                    'instagram': {
                        'api_hostname': 'www.instagram.com',
                        'api_version': 'v1'
                    }
                }
            }
        ]

        # Try each strategy
        for strategy_idx, strategy in enumerate(instagram_strategies):
            logger.info(f"📋 Trying Instagram strategy {strategy_idx + 1}/{len(instagram_strategies)}: {strategy['name']}")

            # For the first strategy, try to pre-dismiss any login popup
            if strategy_idx == 0:
                try:
                    logger.info("🔄 Attempting to pre-dismiss login popup...")
                    # Make a quick request to potentially trigger and dismiss the popup
                    pre_opts = {
                        'format': 'best[height<=240]',  # Very low quality to be quick
                        'outtmpl': '/tmp/pre_dismiss_%(id)s.%(ext)s',
                        'quiet': True,
                        'no_warnings': True,
                        'socket_timeout': 10,
                        'retries': 0,
                        'http_headers': strategy['headers'],
                        'extractor_args': strategy['extractor_args']
                    }

                    if os.path.exists(cookies_path):
                        pre_opts['cookiefile'] = cookies_path

                    with yt_dlp.YoutubeDL(pre_opts) as pre_ydl:
                        try:
                            pre_ydl.extract_info(request.url, download=False)
                        except:
                            pass  # Expected to fail, just trying to trigger popup dismissal

                    # Clean up any pre-download files
                    import glob
                    for f in glob.glob('/tmp/pre_dismiss_*'):
                        try:
                            os.remove(f)
                        except:
                            pass

                    logger.info("✅ Pre-dismiss attempt completed")
                    time.sleep(0.5)  # Brief pause before main download

                except Exception as e:
                    logger.warning(f"⚠️ Pre-dismiss attempt failed: {str(e)}")

            ydl_opts = {
                'format': request.format or 'bestvideo+bestaudio/best',
                'outtmpl': output_template,
                'restrictfilenames': True,
                'retries': 2,  # Reduced per-strategy retries since we have multiple strategies
                'fragment_retries': 2,
                'socket_timeout': 45,
                'concurrent_fragment_downloads': 1,  # Reduced to avoid rate limiting
                'max_downloads': 1,
                'http_chunk_size': 5242880,  # Smaller chunks for better compatibility
                'quiet': False,
                'no_warnings': False,
                'verbose': True,
                'progress_hooks': [
                    lambda d: logger.info(f"[Instagram] Download progress: {d.get('_percent_str', 'N/A')} - {d.get('filename', 'N/A')}")
                    if d['status'] == 'downloading'
                    else logger.info(f"[Instagram] Download status: {d['status']}")
                ],
                'ignoreerrors': False,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'sleep_interval': 1,  # Add small delay between requests
                'max_sleep_interval': 3,
                'http_headers': {
                    'User-Agent': strategy['user_agent'],
                    **strategy['headers']
                },
                **strategy.get('extractor_args', {
                    'instagram': {
                        'api_hostname': 'i.instagram.com',
                        'api_version': 'v1'
                    }
                })
            }

            # Use cookies if available
            if os.path.exists(cookies_path):
                ydl_opts['cookiefile'] = cookies_path
                logger.info(f"Using Instagram cookies from {cookies_path}")
            else:
                logger.warning("No cookies.txt found for Instagram. Some videos may require login.")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(request.url, download=True)

                    if not info:
                        logger.warning(f"Strategy '{strategy['name']}' failed to extract info, trying next strategy")
                        cleanup_files(download_id)
                        continue

                    time.sleep(2)
                    downloaded_file = find_downloaded_file(download_id)

                    if not downloaded_file:
                        logger.warning(f"Strategy '{strategy['name']}' failed to find downloaded file, trying next strategy")
                        cleanup_files(download_id)
                        continue

                    video_info = get_video_info(downloaded_file)
                    logger.info(f"Instagram download successful with strategy '{strategy['name']}': {os.path.basename(downloaded_file)} - {video_info['width']}x{video_info['height']}")

                    return {
                        "success": True,
                        "file_path": os.path.basename(downloaded_file),
                        "download_url": f"/files/{os.path.basename(downloaded_file)}",
                        "title": info.get('title', 'Instagram Video') if info else 'Instagram Video',
                        "url": request.url,
                        "description": info.get('description', '') if info else '',
                        "tags": info.get('tags', []) if info else [],
                        "duration": info.get('duration') if info else None,
                        "uploader": info.get('uploader') if info else None,
                        "file_size_bytes": os.path.getsize(downloaded_file),
                        "file_size_mb": round(os.path.getsize(downloaded_file) / (1024 * 1024), 2),
                        "video_info": video_info,
                        "quality": f"{video_info['width']}x{video_info['height']}" if video_info['width'] > 0 else "Audio only",
                        "strategy_used": strategy['name']
                    }

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.warning(f"[Instagram] Strategy '{strategy['name']}' failed: {error_msg}")

                # Enhanced error detection for Instagram-specific issues
                instagram_error_patterns = [
                    # Login/popup related errors
                    'login', 'sign in', 'authentication', 'popup', 'modal', 'challenge',
                    'verification', 'captcha', 'bot detection', 'suspicious activity',
                    'csrf token', 'no csrf token', 'locked behind login',
                    # Content access errors
                    'private', 'unavailable', 'not found', 'removed', 'deleted',
                    'content is not available', 'requested content is not available',
                    # Network/rate limiting
                    'rate limit', 'too many requests', 'blocked', 'forbidden', 'access denied',
                    'rate-limit reached', 'rate limit reached',
                    # API specific errors
                    'api', 'endpoint', 'invalid response', 'parsing', 'json',
                    'unable to extract shared data', 'unable to extract additional data',
                    'general metadata extraction failed', 'main webpage is locked',
                    # Service errors
                    'internal server error', '500', '502', '503', '504',
                    # Generic retry patterns
                    'extraction', 'unavailable', 'network', 'timeout', 'connection',
                    '403', '429', 'temporary', 'retry', 'please report this issue'
                ]

                # Check if this is a recoverable error that should try next strategy
                if any(keyword in error_msg.lower() for keyword in instagram_error_patterns):
                    logger.info(f"Recoverable Instagram error detected, trying next strategy: {error_msg[:100]}...")
                    cleanup_files(download_id)
                    # Add a small delay before trying next strategy
                    time.sleep(1)
                    continue
                else:
                    # Non-recoverable error, fail immediately
                    logger.error(f"Non-recoverable Instagram error: {error_msg}")
                    cleanup_files(download_id)
                    return {
                        "success": False,
                        "error": f"Instagram download failed: {error_msg}",
                        "error_type": "download_error",
                        "strategy_used": strategy['name']
                    }

            except Exception as e:
                logger.warning(f"[Instagram] Strategy '{strategy['name']}' exception: {str(e)}")
                cleanup_files(download_id)
                # Continue to next strategy for any exception
                continue

        # All strategies failed - try embed endpoint as last resort
        logger.warning("🔄 All primary strategies failed, trying embed endpoint...")
        try:
            embed_url = request.url.replace('instagram.com/p/', 'instagram.com/p/').replace('instagram.com/reel/', 'instagram.com/reel/')
            if 'instagram.com' in embed_url:
                embed_opts = {
                    'format': request.format or 'bestvideo+bestaudio/best',
                    'outtmpl': output_template,
                    'quiet': False,
                    'no_warnings': False,
                    'socket_timeout': 30,
                    'retries': 1,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (compatible; embed)',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://www.instagram.com/embed/',
                    }
                }

                with yt_dlp.YoutubeDL(embed_opts) as embed_ydl:
                    embed_info = embed_ydl.extract_info(embed_url, download=True)

                    if embed_info:
                        time.sleep(1)
                        downloaded_file = find_downloaded_file(download_id)

                        if downloaded_file:
                            video_info = get_video_info(downloaded_file)
                            logger.info(f"✅ Instagram embed download successful: {os.path.basename(downloaded_file)}")

                            return {
                                "success": True,
                                "file_path": os.path.basename(downloaded_file),
                                "download_url": f"/files/{os.path.basename(downloaded_file)}",
                                "title": embed_info.get('title', 'Instagram Video'),
                                "url": request.url,
                                "description": embed_info.get('description', ''),
                                "tags": embed_info.get('tags', []),
                                "duration": embed_info.get('duration'),
                                "uploader": embed_info.get('uploader'),
                                "file_size_bytes": os.path.getsize(downloaded_file),
                                "file_size_mb": round(os.path.getsize(downloaded_file) / (1024 * 1024), 2),
                                "video_info": video_info,
                                "quality": f"{video_info['width']}x{video_info['height']}" if video_info['width'] > 0 else "Audio only",
                                "strategy_used": "embed_endpoint"
                            }

        except Exception as embed_error:
            logger.warning(f"⚠️ Embed endpoint also failed: {str(embed_error)}")

        # All strategies including embed failed
        logger.error(f"❌ All Instagram strategies including embed failed for: {request.url}")
        logger.error("This is likely due to Instagram's anti-bot measures requiring authentication")
        logger.error("Consider obtaining valid Instagram cookies for better success rates")

        return {
            "success": False,
            "error": "All Instagram download strategies failed including embed endpoint. Instagram may require authentication or has updated their anti-bot measures.",
            "error_type": "all_strategies_failed",
            "suggestion": "Try obtaining valid Instagram cookies or use a different download method",
            "strategies_attempted": len(instagram_strategies) + 1  # +1 for embed attempt
        }
    
    # For other platforms, use simplified approach
    try:
        logger.info(f"🌐 Starting regular download for URL: {request.url}")
        
        # Simplified format for non-YouTube platforms
        format_string = request.format or 'best[ext=mp4]/best'
        
        ydl_opts = {
            'format': format_string,
            'outtmpl': output_template,
            'restrictfilenames': True,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 60,
            'ignoreerrors': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'quiet': False,
            'no_warnings': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            'postprocessors': []  # Minimal post-processing
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=True)
            
            if not info:
                raise Exception("Failed to extract video information")
            
            time.sleep(2)
            downloaded_file = find_downloaded_file(download_id)
            
            if not downloaded_file:
                raise Exception("Downloaded file not found")
            
            video_info = get_video_info(downloaded_file)
            logger.info(f"Regular download successful: {os.path.basename(downloaded_file)}")
            
            return {
                "success": True,
                "file_path": os.path.basename(downloaded_file),
                "download_url": f"/files/{os.path.basename(downloaded_file)}",
                "title": info.get('title', 'Video'),
                "url": request.url,
                "description": info.get('description', ''),
                "tags": info.get('tags', []),
                "duration": info.get('duration'),
                "uploader": info.get('uploader'),
                "file_size_bytes": os.path.getsize(downloaded_file),
                "file_size_mb": round(os.path.getsize(downloaded_file) / (1024 * 1024), 2),
                "video_info": video_info,
                "quality": f"{video_info['width']}x{video_info['height']}" if video_info['width'] > 0 else "Audio only"
            }
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"yt-dlp download error: {error_msg}")
        cleanup_files(download_id)
        return {
            "success": False,
            "error": f"Download failed: {error_msg}",
            "error_type": "download_error"
        }
    except Exception as e:
        logger.error(f"Download failed with exception: {str(e)}")
        cleanup_files(download_id)
        return {
            "success": False,
            "error": str(e),
            "error_type": "general_error"
        }

@app.get("/files")
async def list_files(api_key: str = Depends(verify_api_key)):
    """List available downloaded files"""
    try:
        files = []
        if os.path.exists(DOWNLOADS_DIR):
            for filename in os.listdir(DOWNLOADS_DIR):
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.isfile(file_path):
                    try:
                        size = os.path.getsize(file_path)
                        modified = os.path.getmtime(file_path)
                        files.append({
                            "filename": filename,
                            "download_url": f"/files/{filename}",
                            "size_bytes": size,
                            "size_mb": round(size / (1024 * 1024), 2),
                            "modified_timestamp": modified,
                            "modified_iso": datetime.fromtimestamp(modified).isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error processing file {filename}: {str(e)}")
        
        # Sort by modification time, newest first
        files.sort(key=lambda x: x['modified_timestamp'], reverse=True)
        
        return {
            "files": files,
            "file_count": len(files),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return {"error": str(e)}

@app.get("/files/{filename}")
async def get_file(filename: str, api_key: str = Depends(verify_api_key)):
    # Basic sanitization to prevent directory traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join(DOWNLOADS_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type based on file extension
    ext = os.path.splitext(filename)[1].lower()
    media_type = 'application/octet-stream'  # Default
    
    if ext == '.mp4':
        media_type = 'video/mp4'
    elif ext == '.webm':
        media_type = 'video/webm'
    elif ext == '.mkv':
        media_type = 'video/x-matroska'
    elif ext == '.m4a':
        media_type = 'audio/mp4'
    elif ext == '.mp3':
        media_type = 'audio/mpeg'
    elif ext in ['.jpg', '.jpeg']:
        media_type = 'image/jpeg'
    elif ext == '.png':
        media_type = 'image/png'
    
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )

@app.get("/cleanup")
async def cleanup_storage(api_key: str = Depends(verify_api_key)):
    """Clean up old files to free storage space"""
    await cleanup_old_files()
    
    # Get storage info after cleanup
    try:
        total_size = 0
        file_count = 0
        files = []
        
        for filename in os.listdir(DOWNLOADS_DIR):
            file_path = os.path.join(DOWNLOADS_DIR, filename)
            if os.path.isfile(file_path):
                try:
                    size = os.path.getsize(file_path)
                    modified = os.path.getmtime(file_path)
                    total_size += size
                    file_count += 1
                    files.append({
                        "filename": filename,
                        "size_bytes": size,
                        "size_mb": round(size / (1024 * 1024), 2),
                        "modified_timestamp": modified,
                        "modified_iso": datetime.fromtimestamp(modified).isoformat(),
                        "age_hours": round((time.time() - modified) / 3600, 1)
                    })
                except Exception as e:
                    logger.error(f"Error processing file {filename}: {str(e)}")
        
        # Sort files by modification time, newest first
        files.sort(key=lambda x: x['modified_timestamp'], reverse=True)
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "files": files,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Storage info error: {str(e)}")
        return {"error": str(e)}

@app.get("/storage")
async def get_storage_info(api_key: str = Depends(verify_api_key)):
    """Get storage usage information"""
    try:
        total_size = 0
        file_count = 0
        files = []
        
        for filename in os.listdir(DOWNLOADS_DIR):
            file_path = os.path.join(DOWNLOADS_DIR, filename)
            if os.path.isfile(file_path):
                try:
                    size = os.path.getsize(file_path)
                    modified = os.path.getmtime(file_path)
                    total_size += size
                    file_count += 1
                    files.append({
                        "filename": filename,
                        "size_bytes": size,
                        "size_mb": round(size / (1024 * 1024), 2),
                        "modified_timestamp": modified,
                        "modified_iso": datetime.fromtimestamp(modified).isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error processing file {filename}: {str(e)}")
        
        # Sort files by modification time, newest first
        files.sort(key=lambda x: x['modified_timestamp'], reverse=True)
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "files": files,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Storage info error: {str(e)}")
        return {"error": str(e)}

@app.get("/formats")
async def get_available_formats(url: str, api_key: str = Depends(verify_api_key)):
    """Get available formats for a URL without downloading"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            if 'formats' in info:
                for fmt in info['formats']:
                    formats.append({
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': f"{fmt.get('width', 'N/A')}x{fmt.get('height', 'N/A')}",
                        'fps': fmt.get('fps'),
                        'vcodec': fmt.get('vcodec'),
                        'acodec': fmt.get('acodec'),
                        'filesize': fmt.get('filesize'),
                        'filesize_mb': round(fmt.get('filesize', 0) / (1024 * 1024), 2) if fmt.get('filesize') else None,
                        'format_note': fmt.get('format_note'),
                        'format': fmt.get('format')
                    })
            
            return {
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration'),
                "uploader": info.get('uploader'),
                "formats": formats
            }
            
    except Exception as e:
        logger.error(f"Error getting formats: {str(e)}")
        return {"error": str(e)}

# Store download statuses in memory (in production, use Redis or database)
download_statuses = {}

@app.get("/status/{download_id}")
async def get_download_status(download_id: str, api_key: str = Depends(verify_api_key)):
    """Get the status of a background download"""
    if download_id not in download_statuses:
        raise HTTPException(status_code=404, detail="Download not found")
    
    return download_statuses[download_id]

@app.get("/downloads")
async def list_downloads(api_key: str = Depends(verify_api_key)):
    """List all current download statuses"""
    return {
        "downloads": download_statuses,
        "total_downloads": len(download_statuses),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)