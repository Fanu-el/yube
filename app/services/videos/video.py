"""Video service for YouTube video lookups and formatting."""
import re
from typing import List
from urllib.parse import urlparse, parse_qs

import os

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from app.utils import html_escape


def parse_video_id(user_input: str) -> str | None:
    """Lightweight video id/url detection.

    Extracts video ID from YouTube URLs or validates direct video IDs.
    Does not access Redis or other I/O so tests can run without patching
    the cache.
    
    Examples:
        - "https://youtube.com/watch?v=dQw4w9WgXcQ" -> "dQw4w9WgXcQ"
        - "https://youtu.be/dQw4w9WgXcQ" -> "dQw4w9WgXcQ"
        - "dQw4w9WgXcQ" -> "dQw4w9WgXcQ"
    """
    normalized = (user_input or "").strip()
    if not normalized:
        return None

    try:
        parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
        # Check query params for v= (standard YouTube URL)
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if video_id:
            return video_id
        # Check for youtu.be shortened URL
        if "youtu.be" in parsed.netloc and parsed.path:
            video_id = parsed.path.lstrip("/")
            if video_id:
                return video_id
    except Exception:
        pass

    # Direct video ID: 11 alphanumeric characters
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", normalized):
        return normalized

    return None


def format_video_detail(
    video: dict,
    stats: dict,
    page: int,
    return_callback: str | None = None,
    channel_callback: str = "channel_info",
    playlist_id: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Format video detail message with stats and navigation buttons."""
    title = html_escape(video["title"])
    duration = html_escape(stats.get("duration", "N/A"))
    published = stats.get("published_at")
    published_text = html_escape(published.split("T")[0]) if published else "Unknown"

    message = (
        f"<b>▶ {title}</b>\n\n"
        f"<b>📅 Published:</b> {published_text}\n"
        f"<b>⏱ Duration:</b> {duration}\n"
        f"<b>👁 Views:</b> <b>{int(stats.get('views', '0')):,}</b>\n"
        f"<b>👍 Likes:</b> <b>{int(stats.get('likes', '0')):,}</b>\n"
        f"<b>💬 Comments:</b> <b>{int(stats.get('comments', '0')):,}</b>\n\n"
        f"<a href=\"{html_escape(video['url'])}\">Watch on YouTube</a>"
    )
    if video.get("thumbnail"):
        message += f"\n\n{html_escape(video['thumbnail'])}"

    if return_callback is None:
        return_callback = f"videos_{page}"

    # Optionally show the download button. Hidden by default to keep feature off.
    enable_downloads = os.environ.get("ENABLE_DOWNLOADS", "0").lower() in ("1", "true", "yes")
    download_callback = (
        f"download_video_{video['video_id']}_{page}"
        if playlist_id is None
        else f"download_video_{video['video_id']}_playlist_{playlist_id}_{page}"
    )

    back_text = "🔙 Videos"
    if return_callback and return_callback.startswith("playlist_items"):
        back_text = "🔙 Playlist"

    keyboard_rows = []
    if enable_downloads:
        keyboard_rows.append([InlineKeyboardButton("⬇️ Download", callback_data=download_callback)])
    keyboard_rows.append([
        InlineKeyboardButton(back_text, callback_data=return_callback),
        InlineKeyboardButton("🔙 Channel", callback_data=channel_callback),
    ])
    keyboard_rows.append([InlineKeyboardButton("🏠 Home", callback_data="action_home")])

    keyboard = InlineKeyboardMarkup(keyboard_rows)
    return message, keyboard


def format_videos_page(videos: List[dict], page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Format videos page with pagination."""
    ITEMS_PER_PAGE = 5
    total_pages = (len(videos) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(videos))

    page_videos = videos[start_idx:end_idx]

    video_lines = "\n".join(
        f"<b>{i + start_idx + 1}.</b> <a href=\"{html_escape(video['url'])}\">{html_escape(video['title'])}</a>"
        for i, video in enumerate(page_videos)
    ) or "No videos found."

    preview_line = ""
    if page_videos and page_videos[0].get("thumbnail"):
        preview_line = f"\n\n{page_videos[0]['thumbnail']}"

    message = (
        f"<b>✨ Latest Videos</b>\n\n"
        f"{video_lines}{preview_line}\n\n"
        f"<b>Page {page + 1} of {total_pages}</b> (showing {end_idx - start_idx} of {len(videos)})"
    )

    keyboard_rows = [
        [InlineKeyboardButton(
            f"▶ {html_escape(video['title'])[:30]}",
            callback_data=f"video_{video['video_id']}_{page}",
        )]
        for video in page_videos
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"videos_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"videos_{page + 1}"))
    nav_buttons.append(InlineKeyboardButton("🔙 Channel", callback_data="channel_info"))
    nav_buttons.append(InlineKeyboardButton("🏠 Home", callback_data="action_home"))
    keyboard_rows.append(nav_buttons)

    keyboard = InlineKeyboardMarkup(keyboard_rows)
    return message, keyboard
