# Simple Service Fix - Step by Step

## What to Change
You need to modify the `ydl_opts` configuration in your existing `/download` endpoint to use the working Android client strategy for YouTube URLs.

## Exact Location
In your service code, find this section (around line 200-300):
```python
# For non-clip content, proceed with synchronous download
try:
    logger.info(f"Starting download for URL: {request.url}")
    
    # Determine format string based on request parameters
    if request.audio_only:
        format_string = 'bestaudio[ext=m4a]/bestaudio/best'
    else:
        # Build format string prioritizing quality and aspect ratio
        # ... your existing complex format logic ...
    
    # Enhanced ydl_opts for iOS compatibility...
    ydl_opts = {
        # ... your existing complex configuration ...
    }
```

## Replace With
Replace the entire `ydl_opts` configuration section with the code from `service_patch.py`.

## Key Changes
1. **Detect YouTube URLs** and use Android client strategy
2. **Simplify format strings** - use `18/22/best[ext=mp4]/best` for YouTube
3. **Add Android user agent** and client specification
4. **Remove heavy post-processing** for YouTube
5. **Keep existing logic** for non-YouTube URLs but simplified

## Before/After Comparison

### BEFORE (Current - Failing):
```python
ydl_opts = {
    'format': 'bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4][height>=1080]...',  # Complex
    'postprocessors': [...],  # Heavy processing
    'http_headers': {
        'User-Agent': 'Mozilla/5.0...'  # Browser UA
    },
    # No YouTube client specification
}
```

### AFTER (Fixed - Working):
```python
if is_youtube:
    ydl_opts = {
        'format': '18/22/best[ext=mp4]/best',  # Simple, proven format
        'extractor_args': {
            'youtube': {
                'player_client': ['android']  # Key fix!
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/17.36.4...'  # Android UA
        },
        'postprocessors': [],  # No processing
    }
```

## Testing
After making the change:
1. Restart your service
2. Run: `python scripts/enhanced_youtube_debug.py`
3. Should see: ✅ Service Downloads: 3/3 successful

## Why This Works
- Uses the exact same configuration as the working bot strategies
- Android client bypasses YouTube's bot detection
- Simple format selection is more reliable
- No post-processing reduces failure points

The fix is minimal and surgical - just changing the yt-dlp configuration for YouTube URLs while keeping everything else the same.