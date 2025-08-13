# YouTube Cookie Authentication Fix

## Problem
YouTube has implemented bot detection that blocks yt-dlp downloads with errors like:
```
ERROR: [youtube] anOe3Q1vIS4: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication.
```

## Solution
The video downloader now automatically tries multiple cookie authentication strategies:

1. **Chrome cookies** (primary)
2. **Firefox cookies** (fallback)
3. **Safari cookies** (fallback)
4. **Edge cookies** (fallback)
5. **No cookies** (last resort)

## How It Works

### Automatic Cookie Detection
The system automatically detects YouTube URLs and applies cookie authentication:
- YouTube Shorts: `youtube.com/shorts/*`
- YouTube Videos: `youtube.com/watch*`
- YouTube Clips: `youtube.com/clip/*`

### Browser Cookie Priority
1. **Chrome** - Most commonly used, highest success rate
2. **Firefox** - Good alternative if Chrome fails
3. **Safari** - macOS default browser
4. **Edge** - Windows alternative
5. **No cookies** - Fallback for non-YouTube or when all cookie methods fail

## Testing Your Setup

Run the cookie test script to verify your configuration:

```bash
python scripts/test_youtube_cookies.py
```

This will:
- Check yt-dlp installation
- Test cookie access for each browser
- Try downloading the problematic YouTube Shorts URL
- Provide troubleshooting suggestions

## Requirements

### For Users
1. **Be logged into YouTube** in at least one supported browser
2. **Visit the video URL** in your browser first (helps with authentication)
3. **Keep browser cookies enabled** for YouTube

### For System
1. **yt-dlp** must be installed and up-to-date
2. **Browser must be installed** (Chrome, Firefox, Safari, or Edge)
3. **Browser cookies must be accessible** to yt-dlp

## Troubleshooting

### If downloads still fail:

1. **Update yt-dlp**:
   ```bash
   pip install --upgrade yt-dlp
   ```

2. **Clear and refresh browser cookies**:
   - Log out of YouTube
   - Clear browser cache and cookies
   - Log back into YouTube
   - Visit the problematic video URL in browser

3. **Try different browsers**:
   - Install Chrome if not available
   - Make sure you're logged into YouTube in that browser

4. **Check browser permissions**:
   - Some browsers may block cookie access
   - Check browser security settings

### Common Issues

**"No browser cookies accessible"**
- Install a supported browser (Chrome recommended)
- Log into YouTube in that browser
- Make sure browser is not in private/incognito mode

**"Timeout" errors**
- Network connectivity issues
- Try again later
- Check if YouTube is accessible

**"Sign in to confirm you're not a bot" still appears**
- Browser cookies may be expired
- Log out and back into YouTube
- Try a different browser

## Implementation Details

### Code Changes
- Added `--cookies-from-browser` support to all YouTube configurations
- Implemented fallback mechanism for multiple browsers
- Enhanced error handling for cookie-related failures
- Added browser cookie availability checking

### Configuration Updates
- `youtube_shorts_config`: Added Chrome cookie authentication
- `youtube_clips_config`: Added Chrome cookie authentication  
- `Platform.OTHER`: Added Chrome cookie authentication for general YouTube videos

### Error Handling
- More specific error messages for YouTube authentication failures
- Automatic retry with different cookie strategies
- Graceful fallback to no-cookie mode

## Monitoring

The system logs cookie strategy attempts:
- `INFO`: Successful cookie strategy used
- `WARNING`: Cookie strategy failed, trying next
- `ERROR`: All cookie strategies failed

Check logs for messages like:
```
Attempting download with cookie strategy: ['--cookies-from-browser', 'chrome']
Download successful with cookie strategy: ['--cookies-from-browser', 'chrome']
```