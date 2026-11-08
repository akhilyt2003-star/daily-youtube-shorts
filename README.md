# Daily YouTube Shorts — review-before-publishing edition

This project generates a narrated, vertical MP4 draft in GitHub Actions. It does **not** upload or publish to YouTube. You review the downloaded MP4 and upload/schedule it yourself in YouTube Studio. This keeps the approval step real and avoids storing YouTube OAuth credentials in the first version.

## What it makes
- 9:16, 720 × 1280 MP4
- AI-written script, title and description using Gemini API
- Local eSpeak NG narration
- Six or more animated-colour-card scenes with short on-screen text
- A review checklist and metadata JSON

It does not generate photorealistic or 3D AI images. The visuals are simple original graphics.

## 1. Create accounts
1. Create a GitHub account at https://github.com/
2. Create a Gemini API key at https://aistudio.google.com/apikey
3. Check the current Gemini free-tier limits and terms before using it: https://ai.google.dev/gemini-api/docs/pricing

## 2. Create a public repository
Create a repository named `daily-youtube-shorts`. Public repositories are used here because standard GitHub-hosted Actions usage is free for public repositories. Do not put secrets or personal data in source files.

Upload all files from this project, preserving the `.github/workflows/daily-draft.yml` path.

## 3. Add the API key
Repository → Settings → Secrets and variables → Actions → New repository secret:
- Name: `GEMINI_API_KEY`
- Value: your Gemini API key

Never commit the key to the repository.

## 4. Set channel preferences
Repository → Settings → Secrets and variables → Actions → Variables → New repository variable:
- `CHANNEL_TOPIC`: e.g. `science and unusual history facts`
- `VIDEO_LANGUAGE`: e.g. `English`
- `VIDEO_DURATION`: `35-45 seconds`

## 5. Test it
Actions → Generate daily Short draft → Run workflow.
Open the run after it finishes. Download the artifact named `daily-short-review-N`. Unzip it on your Android tablet and inspect:
- `SHORT_REVIEW_ME.mp4`
- `script.txt`
- `metadata.json`
- `review_checklist.txt`

## 6. Daily schedule and manual approval
The workflow runs at 12:00 UTC (5:30 PM IST). GitHub Actions schedule cron is UTC-based. GitHub may delay scheduled runs. Review the MP4 when it completes. If approved:
1. Open YouTube Studio: https://studio.youtube.com/
2. Create → Upload videos.
3. Select `SHORT_REVIEW_ME.mp4`.
4. Copy the title and description from `metadata.json`.
5. Set visibility to Schedule and choose 7:00 PM IST.
6. Complete audience and synthetic-content disclosures accurately.

If the draft is not ready or you do not approve it, do not upload it. This is intentional.

## Important
- No workflow can guarantee a free Gemini API quota forever. Check the active limits in AI Studio.
- Gemini free-tier data handling may differ from paid-tier handling. Do not submit private information.
- AI output can be wrong. Verify factual claims before publishing.
- Use only media, music and sound effects you have rights to use. This starter project uses generated graphics and no third-party music.
- YouTube monetisation is not guaranteed. Repetitive, low-value or misleading mass-produced content may not qualify.
- The GitHub Actions schedule only generates a draft. It never uploads or publishes automatically.
