# Upgraded YouTube Shorts draft generator

This version creates 1080x1920 vertical videos with six original faux-3D vector-cartoon scenes and yellow karaoke-style word highlighting.

Important limitations:
- The cartoon scenes are generated programmatically from vector shapes. They are not photorealistic or AI-generated 3D renders.
- Word highlighting timing is estimated from word length, not speech-aligned. Review and correct synchronization before publishing.
- eSpeak NG is a basic free synthetic voice.
- No YouTube upload is performed. Download, review and schedule the approved MP4 manually in YouTube Studio.

## GitHub setup
1. Replace `main.py` and `requirements.txt` in your existing repository with these files.
2. Replace `.github/workflows/daily-draft.yml` with the included workflow.
3. Keep the existing `GEMINI_API_KEY` repository secret.
4. Keep `CHANNEL_TOPIC`, `VIDEO_LANGUAGE`, `VIDEO_DURATION` variables.
5. Optional: create repository variable `GEMINI_MODEL` with a currently supported Gemini `generateContent` model. If blank, the code defaults to `gemini-3.5-flash-lite`. Verify model availability in Google AI Studio if the API returns 404.
6. Run Actions > Generate daily Short draft > Run workflow.
7. Download `daily-short-review` artifact and inspect MP4, script, metadata and checklist.

## Budget
Uses GitHub public-repository Actions, Gemini free-tier quota (subject to Google's current limits), open-source Python/Pillow/FFmpeg/eSpeak. No paid image generation, paid TTS or paid video-rendering API is used. Do not assume free quotas are unlimited or permanent.
