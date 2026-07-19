# Sosmed Downloader — Backend
# TikTok · Instagram · X/Twitter

import re
import json
import httpx
from typing import Optional
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

app = FastAPI(title="Sosmed Downloader", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════
# TIKTOK
# ═══════════════════════════════════════

async def tiktok_download(url: str) -> dict:
    """No-watermark TikTok via tikwm.com API"""
    video_id = None
    # Extract video ID from various URL formats
    for pattern in [r'/video/(\d+)', r'/v/(\d+)', r'vm\.tiktok\.com/(\w+)']:
        m = re.search(pattern, url)
        if m:
            video_id = m.group(1)
            break

    async with httpx.AsyncClient(timeout=30) as client:
        # Use tikwm API (public, no auth needed)
        api_url = "https://www.tikwm.com/api/"
        resp = await client.post(api_url, data={"url": url})
        data = resp.json()

        if data.get("code") != 0:
            raise HTTPException(400, "Gagal download TikTok")

        video = data.get("data", {})
        return {
            "platform": "tiktok",
            "type": "video",
            "author": video.get("author", {}).get("nickname", ""),
            "title": video.get("title", ""),
            "duration": video.get("duration", 0),
            "cover": video.get("cover", ""),
            "video_no_watermark": video.get("play", ""),
            "video_watermark": video.get("wmplay", ""),
            "music": video.get("music", ""),
        }


# ═══════════════════════════════════════
# INSTAGRAM
# ═══════════════════════════════════════

async def instagram_download(url: str) -> dict:
    """Instagram post/reel download via public API"""
    # Extract shortcode
    shortcode = None
    for pattern in [r'/p/([\w-]+)', r'/reel/([\w-]+)', r'/tv/([\w-]+)']:
        m = re.search(pattern, url)
        if m:
            shortcode = m.group(1)
            break

    if not shortcode:
        raise HTTPException(400, "URL Instagram tidak valid")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            "Accept": "text/html,application/xhtml+xml"
        }

        # Try rapidapi-style endpoint first
        api_url = f"https://instagram-downloader-download-instagram-videos-stories1.p.rapidapi.com/"
        # Fallback: scrape from public page
        try:
            resp = await client.get(
                f"https://ddinstagram.com/{shortcode}",
                headers=headers
            )
            html = resp.text

            # Extract media URLs from meta tags
            video_match = re.search(r'<meta property="og:video"[^>]+content="([^"]+)"', html)
            image_match = re.search(r'<meta property="og:image"[^>]+content="([^"]+)"', html)
            title_match = re.search(r'<meta property="og:title"[^>]+content="([^"]+)"', html)

            media_type = "video" if video_match else "image"
            media_url = (video_match or image_match).group(1) if (video_match or image_match) else ""

            return {
                "platform": "instagram",
                "type": media_type,
                "shortcode": shortcode,
                "title": title_match.group(1) if title_match else "",
                "media_url": media_url,
                "thumbnail": image_match.group(1) if image_match and video_match else media_url,
            }
        except Exception:
            raise HTTPException(400, "Gagal download Instagram")


# ═══════════════════════════════════════
# X / TWITTER
# ═══════════════════════════════════════

async def twitter_download(url: str) -> dict:
    """Twitter/X media download via public API"""
    # Extract tweet ID
    tid_match = re.search(r'/status/(\d+)', url)
    if not tid_match:
        raise HTTPException(400, "URL X/Twitter tidak valid")

    tweet_id = tid_match.group(1)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TelegramBot/2.0)"
        }

        # Try vxtwitter API (public, no auth)
        resp = await client.get(f"https://api.vxtwitter.com/Twitter/status/{tweet_id}")
        if resp.status_code != 200:
            # Fallback: fxtwitter
            resp = await client.get(f"https://api.fxtwitter.com/status/{tweet_id}")

        data = resp.json()

        if not data or data.get("code") == 404:
            raise HTTPException(400, "Tweet tidak ditemukan")

        media = []
        for m in data.get("media_extended", []):
            media.append({
                "type": m.get("type", "image"),
                "url": m.get("url", ""),
                "thumbnail": m.get("thumbnail_url", ""),
                "size": m.get("size", {}),
            })

        return {
            "platform": "x",
            "type": "tweet",
            "tweet_id": tweet_id,
            "author": data.get("user", {}).get("screen_name", ""),
            "text": data.get("text", ""),
            "likes": data.get("likes", 0),
            "retweets": data.get("retweets", 0),
            "media": media,
        }


# ═══════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════

@app.get("/")
async def root():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(f.read())
    return {
        "service": "Sosmed Downloader API",
        "endpoints": {
            "/api/download": "GET ?url= (auto-detect platform)",
            "/api/tiktok": "GET ?url=",
            "/api/instagram": "GET ?url=",
            "/api/x": "GET ?url=",
        }
    }


@app.get("/api/download")
async def auto_download(url: str = Query(..., description="URL konten")):
    """Auto-detect platform dari URL"""
    url_lower = url.lower()

    if "tiktok.com" in url_lower:
        return await tiktok_download(url)
    elif "instagram.com" in url_lower:
        return await instagram_download(url)
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return await twitter_download(url)
    else:
        raise HTTPException(400, "Platform tidak didukung. Support: TikTok, Instagram, X/Twitter")


@app.get("/api/tiktok")
async def api_tiktok(url: str = Query(...)):
    return await tiktok_download(url)


@app.get("/api/instagram")
async def api_instagram(url: str = Query(...)):
    return await instagram_download(url)


@app.get("/api/x")
async def api_x(url: str = Query(...)):
    return await twitter_download(url)


# ═══════════════════════════════════════
# RUN
# ═══════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
