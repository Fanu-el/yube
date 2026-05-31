import asyncio
import re
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from app.services.cache import get_cache, set_cache
from app.services.youtube import _execute_youtube, _get_thumbnail_url, youtube


def _parse_playlist_id(user_input: str) -> str | None:
    normalized = user_input.strip()
    if not normalized:
        return None

    try:
        parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
        playlist_id = parse_qs(parsed.query).get("list", [None])[0]
        if playlist_id:
            return playlist_id
    except Exception:
        pass

    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", normalized) and not normalized.startswith("UC"):
        return normalized

    return None


def _normalize_playlist_lookup_key(user_input: str) -> str:
    normalized = user_input.strip().lower()
    try:
        parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
        if parsed.netloc:
            key = f"{parsed.netloc}{parsed.path}"
            if parsed.query:
                key = f"{key}?{parsed.query}"
            return key
    except Exception:
        pass
    return normalized


async def resolve_playlist_id(user_input: str) -> str:
    lookup_key = f"youtube:resolve:playlist:{_normalize_playlist_lookup_key(user_input)}"
    cached = await get_cache(lookup_key)
    if cached:
        return cached

    playlist_id = _parse_playlist_id(user_input)
    if not playlist_id:
        raise ValueError("Playlist not found")

    await set_cache(lookup_key, playlist_id, ttl=86400)
    return playlist_id


async def get_playlist_info(playlist_id: str) -> Dict[str, Any]:
    cache_key = f"youtube:playlist:info:{playlist_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    request = youtube.playlists().list(
        part="snippet,contentDetails",
        id=playlist_id,
    )
    response = await _execute_youtube(request)
    items = response.get("items", [])
    if not items:
        raise ValueError("Playlist not found")

    playlist = items[0]
    snippet = playlist["snippet"]
    result = {
        "playlist_id": playlist_id,
        "title": snippet["title"],
        "description": snippet.get("description", ""),
        "item_count": playlist["contentDetails"].get("itemCount", 0),
        "url": f"https://youtube.com/playlist?list={playlist_id}",
        "channel_title": snippet.get("channelTitle"),
        "channel_id": snippet.get("channelId"),
        "thumbnail": _get_thumbnail_url(snippet.get("thumbnails", {})),
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
