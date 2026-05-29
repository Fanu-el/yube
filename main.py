import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from pydantic import Field
from pydantic_settings import BaseSettings
from telegram import Bot, Update
from telegram.constants import ParseMode


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class Settings(BaseSettings):
    telegram_token: str = Field(..., env="TELEGRAM_TOKEN")
    youtube_api_key: str = Field(..., env="YOUTUBE_API_KEY")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    webhook_url: Optional[str] = Field(None, env="WEBHOOK_URL")
    webhook_path: str = Field("/webhook", env="WEBHOOK_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)
bot = Bot(token=settings.telegram_token)
app = FastAPI()

CHANNEL_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/(?:channel/|c/|user/|@)?(?P<id>[^/?&]+)",
    re.IGNORECASE,
)


async def _execute_youtube(request: Any) -> Dict[str, Any]:
    return await asyncio.to_thread(request.execute)


async def get_cache(key: str) -> Optional[Any]:
    raw = await redis_client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def set_cache(key: str, value: Any, ttl: int = 3600) -> None:
    await redis_client.set(key, json.dumps(value), ex=ttl)


async def resolve_channel_id(user_input: str) -> str:
    lookup_key = f"youtube:resolve:{user_input.strip().lower()}"
    cached = await get_cache(lookup_key)
    if cached:
        return cached

    normalized = user_input.strip()
    if normalized.startswith("UC"):
        await set_cache(lookup_key, normalized, ttl=86400)
        return normalized

    match = CHANNEL_URL_RE.match(normalized)
    if match:
        candidate = match.group("id")
        if candidate.startswith("UC"):
            await set_cache(lookup_key, candidate, ttl=86400)
            return candidate
        normalized = candidate

    search_request = youtube.search().list(
        part="snippet",
        q=normalized,
        type="channel",
        maxResults=1,
    )
    response = await _execute_youtube(search_request)
    items = response.get("items", [])
    if not items:
        raise ValueError("Channel not found")

    channel_id = items[0]["snippet"]["channelId"]
    await set_cache(lookup_key, channel_id, ttl=86400)
    return channel_id


async def get_channel_info(channel_id: str) -> Dict[str, Any]:
    cache_key = f"youtube:channel:info:{channel_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    request = youtube.channels().list(
        part="snippet,statistics,contentDetails",
        id=channel_id,
    )
    response = await _execute_youtube(request)
    items = response.get("items", [])
    if not items:
        raise ValueError("Channel info not found")

    channel = items[0]
    result = {
        "name": channel["snippet"]["title"],
        "description": channel["snippet"].get("description", ""),
        "subscribers": channel["statistics"].get("subscriberCount", "0"),
        "total_videos": channel["statistics"].get("videoCount", "0"),
        "total_views": channel["statistics"].get("viewCount", "0"),
        "playlist_count": channel["contentDetails"]["relatedPlaylists"].get("uploads"),
    }
    await set_cache(cache_key, result, ttl=900)
    return result


async def get_playlists(channel_id: str) -> List[Dict[str, Any]]:
    cache_key = f"youtube:channel:playlists:{channel_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    request = youtube.playlists().list(
        part="snippet,contentDetails",
        channelId=channel_id,
        maxResults=25,
    )
    response = await _execute_youtube(request)
    playlists = [
        {
            "title": item["snippet"]["title"],
            "playlist_id": item["id"],
            "video_count": item["contentDetails"].get("itemCount", 0),
            "url": f"https://youtube.com/playlist?list={item['id']}",
        }
        for item in response.get("items", [])
    ]
    await set_cache(cache_key, playlists, ttl=1800)
    return playlists


async def get_latest_videos(channel_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
    cache_key = f"youtube:channel:latest:{channel_id}:{max_results}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",
        type="video",
        maxResults=max_results,
    )
    response = await _execute_youtube(request)
    videos = [
        {
            "title": item["snippet"]["title"],
            "url": f"https://youtube.com/watch?v={item['id']['videoId']}",
            "published": item["snippet"].get("publishedAt"),
            "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
        }
        for item in response.get("items", [])
    ]
    await set_cache(cache_key, videos, ttl=300)
    return videos


async def get_video_stats(video_id: str) -> Dict[str, Any]:
    request = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=video_id,
    )
    response = await _execute_youtube(request)
    items = response.get("items", [])
    if not items:
        raise ValueError("Video not found")

    video = items[0]
    return {
        "title": video["snippet"]["title"],
        "views": video["statistics"].get("viewCount", "0"),
        "likes": video["statistics"].get("likeCount", "0"),
        "comments": video["statistics"].get("commentCount", "0"),
        "duration": video["contentDetails"]["duration"],
    }


async def handle_channel(update: Update) -> None:
    if update.message is None or update.message.text is None:
        return

    user_input = update.message.text.strip()
    if user_input.startswith("/"):
        await update.message.reply_text(
            "Send a channel name, URL, or channel ID to look up YouTube channel details."
        )
        return

    await update.message.reply_text("🔍 Looking up channel...")

    try:
        channel_id = await resolve_channel_id(user_input)
        info = await get_channel_info(channel_id)
        playlists = await get_playlists(channel_id)
        latest_videos = await get_latest_videos(channel_id, max_results=5)

        name = html_escape(info["name"])
        description = html_escape(info["description"][:500])
        playlist_lines = "\n".join(
            f"• <a href=\"{html_escape(pl['url'])}\">{html_escape(pl['title'])}</a> — {pl['video_count']} videos"
            for pl in playlists[:5]
        ) or "No playlists found."

        latest_lines = "\n".join(
            f"• <a href=\"{html_escape(video['url'])}\">{html_escape(video['title'])}</a>"
            for video in latest_videos
        ) or "No recent videos found."

        message = (
            f"<b>{name}</b>\n"
            f"👥 Subscribers: {int(info['subscribers']):,}\n"
            f"🎬 Total Videos: {int(info['total_videos']):,}\n"
            f"👁 Total Views: {int(info['total_views']):,}\n"
            f"\n{description}\n\n"
            f"<b>Playlists ({len(playlists)}):</b>\n{playlist_lines}\n\n"
            f"<b>Latest uploads:</b>\n{latest_lines}"
        )

        await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: {html_escape(str(exc))}")


@app.post("/webhook")
async def telegram_webhook(request: Request) -> JSONResponse:
    payload = await request.json()
    update = Update.de_json(payload, bot)
    await handle_channel(update)
    return JSONResponse({"ok": True})


@app.get("/set_webhook")
async def set_webhook() -> Dict[str, str]:
    if not settings.webhook_url:
        raise HTTPException(400, detail="WEBHOOK_URL is required in .env to register a webhook")

    webhook_target = f"{settings.webhook_url.rstrip('/')}{settings.webhook_path}"
    result = await bot.set_webhook(webhook_target)
    if not result:
        raise HTTPException(500, detail="Failed to register webhook")
    return {"webhook": webhook_target}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
