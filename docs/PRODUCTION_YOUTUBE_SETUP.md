# Production YouTube Download Setup

## Architecture Overview

The bot uses a two-tier approach for YouTube downloads:

1. **Primary**: Dedicated YouTube download service (separate FastAPI service)
2. **Fallback**: Direct yt-dlp calls with multiple strategies

## Service Configuration

### Environment Variables

```bash
# YouTube Download Service
YTDL_SERVICE_URL=http://localhost:8000  # Internal service URL
YTDL_SERVICE_API_KEY=your_api_key_here  # Service API key
YTDL_MAX_RETRIES=3
YTDL_RETRY_DELAY=1
```

### Service Features

Your separate service includes:
- **Cookie handling**: Uses cookies from `/opt/ytdl_service/cookies/youtube_cookies.txt`
- **Multiple strategies**: Web, Android, iOS clients
- **Background processing**: For YouTube Shorts/Clips
- **Automatic updates**: Keeps yt-dlp up to date
- **File cleanup**: Manages storage automatically

## Bot Fallback Strategies

When the service is unavailable, the bot uses these strategies in order:

1. **Android Client** (most reliable without cookies)
   ```bash
   --user-agent "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"
   --extractor-args "youtube:player_client=android"
   ```

2. **iOS Client** (good fallback)
   ```bash
   --user-agent "com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)"
   --extractor-args "youtube:player_client=ios"
   ```

3. **Web Client** (with browser headers)
   ```bash
   --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
   --referer "https://www.youtube.com/"
   --extractor-args "youtube:player_client=web"
   ```

4. **Web + Cookies** (if browser available)
   ```bash
   --cookies-from-browser chrome
   ```

5. **Basic Web** (last resort)

## Production Deployment

### 1. Service Setup

On your production server, ensure the YouTube service is running:

```bash
# Check service status
curl -H "X-API-Key: your_api_key" http://localhost:8000/health

# Test download
curl -X POST -H "X-API-Key: your_api_key" -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/shorts/anOe3Q1vIS4"}' \
  http://localhost:8000/download
```

### 2. Bot Configuration

Update your bot's environment variables:

```bash
# Service configuration
YTDL_SERVICE_URL=http://localhost:8000
YTDL_SERVICE_API_KEY=your_actual_api_key_here

# Fallback configuration
YTDL_MAX_RETRIES=3
YTDL_RETRY_DELAY=1
```

### 3. Cookie Setup (Optional)

For better success rates, set up YouTube cookies on the service:

```bash
# Create cookies directory
sudo mkdir -p /opt/ytdl_service/cookies

# Export cookies from browser (manual process)
# Save to /opt/ytdl_service/cookies/youtube_cookies.txt
```

## Troubleshooting

### Service Issues

1. **Service not responding**:
   ```bash
   # Check if service is running
   ps aux | grep python | grep ytdl
   
   # Check service logs
   tail -f /var/log/ytdl_service.log
   
   # Restart service
   systemctl restart ytdl-service
   ```

2. **API key issues**:
   ```bash
   # Check API key file
   cat /opt/ytdl_service/api_key.txt
   
   # Regenerate if needed
   rm /opt/ytdl_service/api_key.txt
   # Service will generate new key on restart
   ```

### Bot Fallback Issues

1. **All strategies failing**:
   ```bash
   # Update yt-dlp
   pip install --upgrade yt-dlp
   
   # Test manually
   yt-dlp --extractor-args "youtube:player_client=android" "https://youtube.com/shorts/VIDEO_ID"
   ```

2. **Cookie errors**:
   ```bash
   # Install browser (if needed)
   sudo apt install firefox
   
   # Or ignore cookie strategies (they're optional)
   ```

## Monitoring

### Service Health

The service provides health endpoints:

```bash
# Basic health
curl -H "X-API-Key: your_key" http://localhost:8000/health

# Storage info
curl -H "X-API-Key: your_key" http://localhost:8000/storage

# Download status
curl -H "X-API-Key: your_key" http://localhost:8000/downloads
```

### Bot Logs

Monitor bot logs for download patterns:

```bash
# Look for service usage
grep "Service download successful" bot.log

# Look for fallback usage
grep "YouTube strategy" bot.log

# Look for failures
grep "All YouTube strategies failed" bot.log
```

## Performance Optimization

### Service Optimization

1. **Regular cleanup**: Service automatically cleans old files
2. **Background processing**: YouTube Shorts/Clips use background downloads
3. **Format optimization**: Uses iOS-compatible H.264 formats

### Bot Optimization

1. **Service priority**: Always tries service first for YouTube
2. **Smart fallback**: Only uses direct yt-dlp when service fails
3. **Strategy ordering**: Most reliable strategies first

## Security Considerations

1. **API Key**: Keep service API key secure
2. **Internal network**: Service should only be accessible internally
3. **File cleanup**: Automatic cleanup prevents storage issues
4. **Rate limiting**: Service includes built-in rate limiting

## Current Status

Based on your error logs, the issue was:

1. ✅ **Service is properly configured** with multiple strategies
2. ✅ **Bot prioritizes service** for YouTube URLs
3. ✅ **Fallback strategies** handle service unavailability
4. ✅ **Updated yt-dlp** to latest version (2025.8.11)

The bot should now successfully download YouTube videos using either the service or fallback strategies.