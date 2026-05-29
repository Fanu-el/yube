import asyncio
import re
from typing import Any, Dict, List

from app.services.cache import get_cache, set_cache
from googleapiclient.discovery import build
from app.settings import settings


youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)
CHANNEL_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/(?:channel/|c/|user/|@)?(?P<id>[^/?&]+)",
    re.IGNORECASE,
)


async def _execute_youtube(request: Any) -> Dict[str, Any]:
    return await asyncio.to_thread(request.execute)


def _get_thumbnail_url(thumbnails: dict) -> str:
    if not thumbnails:
        return ""
    for size in ("medium", "high", "standard", "default"):
        url = thumbnails.get(size, {}).get("url")
        if url:
            return url
    for thumb in thumbnails.values():
        if isinstance(thumb, dict):
            url = thumb.get("url")
            if url:
                return url
    return ""


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

    request = youtube.search().list(
        part="snippet",
        q=normalized,
        type="channel",
        maxResults=1,
    )
    response = await _execute_youtube(request)
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
        "published_at": channel["snippet"].get("publishedAt"),
        "country": channel["snippet"].get("country"),
        "uploads_playlist_id": channel["contentDetails"]["relatedPlaylists"].get("uploads"),
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


async def get_playlist_items(playlist_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
    cache_key = f"youtube:playlist:items:{playlist_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    request = youtube.playlistItems().list(
        part="snippet",
        playlistId=playlist_id,
        maxResults=max_results,
    )
    response = await _execute_youtube(request)
    items = [
        {
            "title": item["snippet"]["title"],
            "url": f"https://youtube.com/watch?v={item['snippet']['resourceId']['videoId']}",
            "video_id": item["snippet"]["resourceId"]["videoId"],
            "published": item["snippet"].get("publishedAt"),
            "thumbnail": _get_thumbnail_url(item["snippet"].get("thumbnails", {})),
        }
        for item in response.get("items", [])
        if item.get("snippet", {}).get("resourceId", {}).get("videoId")
    ]
    await set_cache(cache_key, items, ttl=300)
    return items


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
            "video_id": item["id"]["videoId"],
            "published": item["snippet"].get("publishedAt"),
            "thumbnail": _get_thumbnail_url(item["snippet"].get("thumbnails", {})),
        }
        for item in response.get("items", [])
    ]
    await set_cache(cache_key, videos, ttl=300)
    return videos


async def _format_duration(duration: str) -> str:
    match = re.match(r"PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?$", duration or "")
    if not match:
        return "N/A"

    hours = int(match.group("h") or 0)
    minutes = int(match.group("m") or 0)
    seconds = int(match.group("s") or 0)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


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
        "duration": await _format_duration(video["contentDetails"].get("duration", "")),
        "published_at": video["snippet"].get("publishedAt"),
    }
