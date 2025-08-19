# YouTube Service Fix Instructions

## Problem Identified
The YouTube download service is failing because it's using different yt-dlp configuration than the working bot strategies. The service uses complex format strings and missing client specifications that cause "Failed to extract video information" errors.

## Root Cause
1. **Missing Android client specification**: Service doesn't use `youtube:player_client=android`
2. **Complex format strings**: Service uses overly complex format selection
3. **Heavy post-processing**: Service applies unnecessary video conversion
4. **Wrong user agent**: Uses browser UA instead of Android client UA

## Solution
Replace the YouTube download logic in your service with the proven working strategies from the bot.

## Key Changes Needed

### 1. Add YouTube-Specific Handler
Add the `download_youtube_video()` function from `temp_service_fix.py` to your service.

### 2. Modify Main Download Endpoint
Update your `/download` endpoint to detect YouTube URLs and use the specialized handler.

### 3. Use Working yt-dlp Configuration
The Android client strategy that works:
```python
{
    'format': '18/22/best[ext=mp4]/best',
    'extractor_args': {
        'youtube': {
            'player_client': ['android']
        }
    },
    'http_headers': {
        'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'
    },
    'postprocessors': []  # No post-processing
}
```

## Testing Results
- ✅ **Bot direct strategies**: 3/3 YouTube Shorts work perfectly
- ❌ **Current service**: 0/3 YouTube Shorts work
- ✅ **Service health**: Service is running and accessible

## Implementation Steps

1. **Backup your current service code**
2. **Add the YouTube handler function** from `temp_service_fix.py`
3. **Update the main download endpoint** to use YouTube handler for YouTube URLs
4. **Test with the problematic URLs**:
   - `https://youtube.com/shorts/aV3v4rY5lAc`
   - `https://youtube.com/shorts/REgWLOCgvT4`
5. **Restart the service**
6. **Run the bot test** to verify it works

## Expected Results After Fix
- ✅ Service should successfully download YouTube Shorts
- ✅ Bot should prefer service over direct strategies
- ✅ Better logging and error handling
- ✅ Faster downloads (service is local)

## Verification Commands
```bash
# Test service after fix
python scripts/enhanced_youtube_debug.py

# Test bot functionality
python scripts/test_bot_video_download.py
```

## Current Status
- **Service**: Healthy but failing YouTube extraction
- **Bot**: Working with direct fallback strategies
- **Impact**: Bot works but uses slower direct downloads instead of fast service

The fix will make the service work properly so the bot can use it as the primary download method.