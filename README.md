# Sosmed Downloader

TikTok · Instagram · X/Twitter downloader API — no watermark, zero auth.

## Features

- 🔄 **Auto-detect** — satu endpoint buat semua platform
- 🎵 **TikTok** — no-watermark video + audio
- 📸 **Instagram** — post, reel, TV
- 🐦 **X/Twitter** — media dari tweet

## Quick Start

```bash
cd backend
pip install -r requirements.txt
python main.py
```

## API

| Endpoint | Method | Params |
|----------|--------|--------|
| `/api/download` | GET | `?url=` auto-detect |
| `/api/tiktok` | GET | `?url=` |
| `/api/instagram` | GET | `?url=` |
| `/api/x` | GET | `?url=` |

## Response

```json
{
  "platform": "tiktok",
  "type": "video",
  "author": "@creator",
  "video_no_watermark": "https://..."
}
```
