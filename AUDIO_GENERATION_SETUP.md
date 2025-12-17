# Audio Generation Setup Guide

This guide explains how to set up and use Google Text-to-Speech (gTTS) for generating audio narration for story pages.

## Overview

The audio generation system:
- ✅ Uses **gTTS (Google Text-to-Speech)** - Free, no API keys required!
- ✅ Generates age-appropriate voices for children (3-6, 7-10, 11-12)
- ✅ Creates audio for 5 story pages per story
- ✅ Uploads audio files to Supabase storage
- ✅ Stores audio URLs in story content JSONB field
- ✅ Completes within 60 seconds per page
- ✅ Only generates audio for Story Adventure (not Interactive Search)

## Prerequisites

1. **No API Keys Required!** 🎉
   - gTTS uses Google's free TTS service
   - No Google Cloud account needed
   - No service account keys required
   - Just install the library and use it!

2. **Supabase Storage Bucket**
   - Create an "audio" bucket in your Supabase storage (or use the existing "images" bucket)
   - Ensure the bucket has public read access for audio files

3. **Install Dependencies**
   ```bash
   pip install gtts>=2.5.0
   ```

That's it! No additional setup needed.

## Environment Variables

**No environment variables required!** gTTS works out of the box.

## Age-Appropriate Voice Selection

The system automatically adjusts speech for different age groups:

- **3-6 years**: Slower speech, US English accent
- **7-10 years**: Normal speed, US English accent
- **11-12 years**: Normal speed, US English accent

Note: gTTS uses Google Translate's TTS service, which provides natural-sounding voices without requiring API keys.

## How It Works

1. **Story Generation**: When a Story Adventure job is processed, after story text and scenes are generated, audio generation begins.

2. **Audio Generation**: For each of the 5 story pages:
   - Text is sent to Google's TTS service (via gTTS)
   - Age-appropriate settings are applied (speed, accent)
   - Audio is generated in MP3 format
   - Audio file is uploaded to Supabase storage

3. **Storage**: Audio URLs are stored in:
   - Job `result_data.audio_urls` (array of 5 URLs)
   - Story `story_result.audio_urls` (for reference)

4. **Story Content**: When saving the story, include audio URLs in the `story_content` JSON:

```json
{
  "pages": [
    {
      "pageNumber": 1,
      "text": "Story text here...",
      "sceneImage": "https://...",
      "audioUrl": "https://...audio_urls[0]..."
    },
    {
      "pageNumber": 2,
      "text": "Story text here...",
      "sceneImage": "https://...",
      "audioUrl": "https://...audio_urls[1]..."
    },
    // ... pages 3-5
  ]
}
```

## Usage in Frontend

When retrieving job results and saving the story:

```typescript
// Get job status
const jobStatus = await fetch(`/api/books/${jobId}/status`);

// Extract audio URLs from result_data
const audioUrls = jobStatus.result_data?.audio_urls || [];

// When creating story_content, include audio URLs:
const storyContent = {
  pages: storyPages.map((page, index) => ({
    pageNumber: index + 1,
    text: page.text,
    sceneImage: page.sceneImage,
    audioUrl: audioUrls[index] || null  // Include audio URL or null
  }))
};
```

## Audio Streaming Endpoint

To stream audio files, use the Supabase public URL directly, or create a streaming endpoint:

```python
@app.get("/api/books/story/{story_id}/audio/{page}")
async def get_story_audio(story_id: int, page: int):
    # Fetch story from database
    # Extract audioUrl from story_content.pages[page-1].audioUrl
    # Stream the audio file
    pass
```

## Troubleshooting

### Audio Generation Fails

1. **Check gTTS Installation**
   ```bash
   pip list | grep gtts
   ```
   Should show `gtts` version 2.5.0 or higher

2. **Check Internet Connection**
   - gTTS requires internet connection to Google's TTS service
   - Ensure your server has internet access

3. **Check Logs**
   - Look for "gTTS not available" errors
   - Check for network timeout errors

### Audio Upload Fails

1. **Check Supabase Storage**
   - Verify bucket exists ("audio" or "images")
   - Check bucket permissions (public read for audio files)

2. **Check File Size**
   - Audio files are typically 50-200 KB per page
   - Ensure Supabase storage limits are not exceeded

### Timeout Issues

- Default timeout is 60 seconds per page
- If consistently timing out, check:
  - Network connectivity to Google's TTS service
  - Text length (very long pages may take longer)
  - Rate limiting (Google may throttle requests if too many)

### Rate Limiting

- Google's TTS service has rate limits for free usage
- If you hit rate limits:
  - Add delays between requests
  - Consider caching frequently used audio
  - For production, consider upgrading to paid TTS service

## Advantages of gTTS

✅ **No API Keys**: Works immediately without setup  
✅ **Free**: No cost for reasonable usage  
✅ **Simple**: Easy to use and maintain  
✅ **Reliable**: Uses Google's infrastructure  
✅ **Natural Voices**: High-quality speech synthesis  

## Limitations

⚠️ **Rate Limits**: Free tier has usage limits  
⚠️ **Internet Required**: Needs internet connection  
⚠️ **Voice Options**: Limited customization compared to paid services  
⚠️ **Language**: Primarily English (though supports many languages)  

## Notes

- Audio generation only runs for **Story Adventure** jobs (not Interactive Search)
- If audio generation fails, the story generation continues (audio is optional)
- Audio files are stored in MP3 format for optimal quality/size balance
- Each audio file is uniquely named with timestamp and UUID
- gTTS uses Google Translate's TTS service, which is free and doesn't require authentication
