# Sosmed Downloader — Backend
# TikTok · Instagram · X/Twitter

import re
import json
import httpx
from typing import Optional
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse

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
    """No-watermark TikTok via tikwm.com API (clean no-WM)"""
    async with httpx.AsyncClient(timeout=30) as client:
        api_url = "https://www.tikwm.com/api/"
        resp = await client.post(api_url, data={"url": url})
        data = resp.json()

        if data.get("code") != 0:
            raise HTTPException(400, "Gagal download TikTok")

        video = data.get("data", {})

        # Check for photo slideshow
        if video.get("images") and len(video["images"]) > 0:
            return {
                "platform": "tiktok",
                "type": "image",
                "author": video.get("author", {}).get("nickname", ""),
                "title": video.get("title", ""),
                "cover": video.get("cover", ""),
                "media": [{"type": "image", "url": img} for img in video["images"]],
                "music": video.get("music", ""),
            }

        return {
            "platform": "tiktok",
            "type": "video",
            "author": video.get("author", {}).get("nickname", ""),
            "title": video.get("title", ""),
            "duration": video.get("duration", 0),
            "cover": video.get("cover", ""),
            "video_no_watermark": video.get("play", ""),   # NO watermark
            "video_watermark": video.get("wmplay", ""),     # WITH watermark
            "music": video.get("music", ""),
        }


# ═══════════════════════════════════════
# INSTAGRAM
# ═══════════════════════════════════════

async def instagram_download(url: str) -> dict:
    """Instagram post/reel download via yt-dlp"""
    import subprocess, tempfile, os

    try:
        # Use yt-dlp to extract info (dump JSON)
        cmd = [
            "python3", "-m", "yt_dlp",
            "--dump-json",
            "--no-playlist",
            "--no-check-certificates",
            "--extractor-args", "instagram:no_login",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not result.stdout.strip():
            raise HTTPException(400, "Tidak dapat mengakses konten Instagram. Mungkin akun private.")

        data = json.loads(result.stdout)

        # Determine media type
        is_video = data.get("duration") is not None
        media_url = data.get("url", "")
        thumbnail = data.get("thumbnail", "")

        return {
            "platform": "instagram",
            "type": "video" if is_video else "image",
            "author": data.get("uploader", ""),
            "title": data.get("title", "")[:200] if data.get("title") else "",
            "duration": int(data["duration"]) if is_video and data.get("duration") else None,
            "media_url": media_url,
            "thumbnail": thumbnail or media_url,
            "likes": data.get("like_count"),
            "comments": data.get("comment_count"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Gagal download Instagram: {str(e)[:100]}")


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
            "author": data.get("user_name", "") or data.get("user_screen_name", ""),
            "text": data.get("text", ""),
            "likes": data.get("likes", 0),
            "retweets": data.get("retweets", 0),
            "media": media,
        }


# ═══════════════════════════════════════
# YOUTUBE
# ═══════════════════════════════════════

async def youtube_download(url: str) -> dict:
    """YouTube video download via yt-dlp"""
    import subprocess, json, tempfile, os

    try:
        # Get formats as JSON
        cmd = [
            "python3", "-m", "yt_dlp",
            "--dump-json",
            "--no-playlist",
            "--no-check-certificates",
            "--format-sort", "res,codec:av1",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not result.stdout.strip():
            raise HTTPException(400, "Tidak dapat mengakses video YouTube")

        data = json.loads(result.stdout)

        # Find best combined format (video+audio)
        formats = data.get("formats", [])
        best_video_audio = None
        best_video_only = None
        best_audio_only = None

        for f in formats:
            vcodec = f.get("vcodec", "none")
            acodec = f.get("acodec", "none")
            has_video = vcodec != "none"
            has_audio = acodec != "none"
            height = f.get("height") or 0
            filesize = f.get("filesize") or f.get("filesize_approx") or 0
            fmt_id = f.get("format_id", "")

            if has_video and has_audio:
                if not best_video_audio or height > (best_video_audio.get("height") or 0):
                    best_video_audio = {"url": f.get("url", ""), "height": height, "ext": f.get("ext", "mp4"), "filesize": filesize}
            elif has_video and not has_audio:
                if not best_video_only or height > (best_video_only.get("height") or 0):
                    best_video_only = {"url": f.get("url", ""), "height": height, "ext": f.get("ext", "mp4"), "filesize": filesize}
            elif not has_video and has_audio:
                if not best_audio_only or (f.get("abr") or 0) > (best_audio_only.get("abr") or 0):
                    best_audio_only = {"url": f.get("url", ""), "ext": f.get("ext", "m4a"), "abr": f.get("abr", 0), "filesize": filesize}

        return {
            "platform": "youtube",
            "type": "video",
            "author": data.get("uploader", ""),
            "title": data.get("title", ""),
            "duration": int(data.get("duration", 0)),
            "thumbnail": data.get("thumbnail", ""),
            "formats": {
                "video_audio": best_video_audio,
                "video_only": best_video_only,
                "audio_only": best_audio_only,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Gagal download YouTube: {str(e)[:100]}")


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
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return await youtube_download(url)
    else:
        raise HTTPException(400, "Platform tidak didukung. Support: TikTok, Instagram, X/Twitter, YouTube")


@app.get("/api/tiktok")
async def api_tiktok(url: str = Query(...)):
    return await tiktok_download(url)


@app.get("/api/instagram")
async def api_instagram(url: str = Query(...)):
    return await instagram_download(url)


@app.get("/api/x")
async def api_x(url: str = Query(...)):
    return await twitter_download(url)


@app.get("/api/youtube")
async def api_youtube(url: str = Query(...)):
    return await youtube_download(url)


# ═══════════════════════════════════════
# MEDIA PROXY — bypass Twitter Referer 403
# ═══════════════════════════════════════

@app.get("/api/proxy/media")
async def proxy_media(url: str = Query(..., description="Media URL to proxy")):
    """Proxy media with proper Referer to bypass CDN block"""
    import httpx

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://twitter.com/",
        }
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

            return StreamingResponse(
                resp.aiter_bytes(),
                status_code=200,
                media_type=resp.headers.get("content-type", "application/octet-stream"),
                headers={
                    "Content-Disposition": f"attachment; filename=media_{url.split('/')[-1].split('?')[0]}",
                    "Cache-Control": "public, max-age=86400",
                }
            )
    except Exception as e:
        raise HTTPException(400, f"Proxy error: {str(e)[:100]}")


# ═══════════════════════════════════════
# RUN
# ═══════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
