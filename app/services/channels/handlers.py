import logging
from typing import List
from uuid import uuid4
import re
from urllib.parse import urlparse, parse_qs

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.constants import ParseMode

from app.services.cache import get_cache, set_cache
from app.utils import html_escape
from app.services.youtube import (
    get_channel_info,
    get_latest_videos,
    get_video_stats,
    get_video_info,
    resolve_channel_id,
)
from app.services.playlists import (
    get_playlist_info,
    get_playlist_items,
    get_playlists,
    resolve_playlist_id,
)
from app.services.videos import (
    parse_video_id,
    format_video_detail,
    format_videos_page,
)

logger = logging.getLogger(__name__)
ITEMS_PER_PAGE = 5
SESSION_STATE_PREFIX = "telegram:state:"
SESSION_CHANNEL_PREFIX = "telegram:channel:"
SESSION_PLAYLIST_PREFIX = "telegram:playlist:"
SESSION_VIDEO_PREFIX = "telegram:video:"


def _parse_playlist_id(user_input: str) -> str | None:
    """Lightweight playlist id/url detection used to avoid touching cache.

    Mirrors the parsing logic in the playlist service but does not access
    Redis or other I/O so tests can run without patching the playlist cache.
    """
    normalized = (user_input or "").strip()
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


def format_main_menu() -> tuple[str, InlineKeyboardMarkup]:
    message = (
        "<b>🏠 Main Menu</b>\n\n"
        "Choose a feature to get started.\n"
        "Use the buttons below to search channels, playlists, or videos directly.\n\n"
        "You can also paste URLs or IDs directly:\n"
        "• Playlist: <code>https://youtube.com/playlist?list=PL...</code> or <code>PL...</code>\n"
        "• Video: <code>https://youtube.com/watch?v=...</code> or <code>11-char ID</code>"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 Channels", callback_data="action_channels"),
            InlineKeyboardButton("📋 Playlists", callback_data="action_playlists"),
        ],
        [
            InlineKeyboardButton("▶ Videos", callback_data="action_videos"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="action_help")],
        [InlineKeyboardButton("ℹ️ About", callback_data="action_about")],
    ])
    return message, keyboard


def format_help_message() -> tuple[str, InlineKeyboardMarkup]:
    message = (
        "<b>📖 Help</b>\n\n"
        "Send a channel name, URL, channel ID, or playlist URL/ID to see channel stats, description, playlists, latest uploads, or playlist details.\n\n"
        "<b>Commands:</b>\n"
        "/start - Show welcome message\n"
        "/help - Show this help screen\n"
        "/about - About this bot\n"
        "/menu or / - Show the action menu\n\n"
        "You can also click the buttons below."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Channels", callback_data="action_channels")],
        [InlineKeyboardButton("🏠 Home", callback_data="action_home")],
    ])
    return message, keyboard


def format_about_message() -> tuple[str, InlineKeyboardMarkup]:
    message = (
        "<b>ℹ️ About yube</b>\n\n"
        "yube is a Telegram bot for discovering YouTube channel information quickly.\n\n"
        "Features:\n"
        "• Fast channel lookup by name, URL, or ID\n"
        "• Channel statistics and description\n"
        "• Playlist browsing with pagination\n"
        "• Direct playlist lookup from URL or ID\n"
        "• Latest uploads and video details\n"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Channels", callback_data="action_channels")],
        [InlineKeyboardButton("🏠 Home", callback_data="action_home")],
    ])
    return message, keyboard


def format_full_description(info: dict) -> tuple[str, InlineKeyboardMarkup]:
    description = info.get("description", "")
    message = (
        f"<b>📌 Full description for {html_escape(info['name'])}</b>\n\n"
        f"{html_escape(description or 'No description available.')}."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Channel", callback_data="channel_info")],
        [InlineKeyboardButton("🏠 Home", callback_data="action_home")],
    ])
    return message, keyboard


def format_channel_info(info: dict, playlists_count: int, videos_count: int) -> tuple[str, InlineKeyboardMarkup]:
    """Format channel info with interactive buttons."""
    name = html_escape(info["name"])
    raw_description = info.get("description", "")
    description = raw_description[:300]
    truncated = len(raw_description) > 300
    created = info.get("published_at")
    country = info.get("country")

    message = (
        f"<b>🎬 {name}</b>\n\n"
        f"<b>📊 Statistics:</b>\n"
        f"👥 Subscribers: <b>{int(info['subscribers']):,}</b>\n"
        f"🎬 Total Videos: <b>{int(info['total_videos']):,}</b>\n"
        f"👁️ Total Views: <b>{int(info['total_views']):,}</b>\n"
    )

    if created:
        message += f"\n🗓 Created: <b>{html_escape(created.split('T')[0])}</b>"
    if country:
        message += f"\n🌍 Country: <b>{html_escape(country)}</b>"

    display_description = html_escape(description) if description else "No description available."
    if truncated:
        display_description += "..."

    message += f"\n\n<b>📝 Description:</b>\n{display_description}"

    keyboard_rows = []

    # If the description was truncated, show the More button immediately
    # below the description so it appears at the end of the truncated text.
    if truncated:
        keyboard_rows.append([InlineKeyboardButton("📌 More", callback_data="description_more")])

    # Primary channel actions
    keyboard_rows.append([
        InlineKeyboardButton("📋 Playlists", callback_data="playlists_0"),
        InlineKeyboardButton("✨ Latest Videos", callback_data="videos_0"),
    ])

    # Home button
    keyboard_rows.append([InlineKeyboardButton("🏠 Home", callback_data="action_home")])

    keyboard = InlineKeyboardMarkup(keyboard_rows)
    return message, keyboard


def format_playlist_info(info: dict) -> tuple[str, InlineKeyboardMarkup]:
    description = info.get("description", "")
    description_text = html_escape(description) if description else "No description available."
    message = (
        f"<b>📋 Playlist: {html_escape(info['title'])}</b>\n\n"
        f"<b>🎬 Videos:</b> <b>{int(info.get('item_count', 0)):,}</b>\n"
    )
    if info.get("channel_title"):
        message += f"\n👤 Channel: <b>{html_escape(info['channel_title'])}</b>"
    message += f"\n\n{description_text}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ View Videos", callback_data=f"playlist_items_direct_{info['playlist_id']}_0")],
        [InlineKeyboardButton("🏠 Home", callback_data="action_home")],
    ])
    return message, keyboard


def format_playlists_page(playlists: List[dict], page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Format playlists page with pagination."""
    total_pages = (len(playlists) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(playlists))
    
    page_playlists = playlists[start_idx:end_idx]
    
    playlist_lines = "\n".join(
        f"<b>{i + start_idx + 1}.</b> <a href=\"{html_escape(pl['url'])}\">{html_escape(pl['title'])}</a>\n"
        f"   🎬 {pl['video_count']} videos"
        for i, pl in enumerate(page_playlists)
    ) or "No playlists found."
    
    message = (
        f"<b>📋 Playlists</b>\n\n"
        f"{playlist_lines}\n\n"
        f"<b>Page {page + 1} of {total_pages}</b> (showing {end_idx - start_idx} of {len(playlists)})"
    )
    
    # Build playlist selection rows and pagination keyboard
    keyboard_rows = [
        [InlineKeyboardButton(
            f"▶ {html_escape(pl['title'])[:30]}",
            callback_data=f"playlist_{pl['playlist_id']}_0",
        )]
        for pl in page_playlists
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"playlists_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"playlists_{page + 1}"))
    nav_buttons.append(InlineKeyboardButton("🔙 Channel", callback_data="channel_info"))
    keyboard_rows.append(nav_buttons)

    keyboard = InlineKeyboardMarkup(keyboard_rows)
    return message, keyboard


def format_playlist_items_page(
    items: List[dict],
    page: int,
    playlist_id: str,
    playlist_title: str,
    back_callback: str = "playlists_0",
    direct: bool = False,
) -> tuple[str, InlineKeyboardMarkup]:
    total_pages = (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(items))

    page_items = items[start_idx:end_idx]
    item_lines = "\n".join(
        f"<b>{i + start_idx + 1}.</b> <a href=\"{html_escape(item['url'])}\">{html_escape(item['title'])}</a>"
        for i, item in enumerate(page_items)
    ) or "No videos found."

    message = (
        f"<b>📺 Playlist: {html_escape(playlist_title)}</b>\n\n"
        f"{item_lines}\n\n"
        f"<b>Page {page + 1} of {total_pages}</b> (showing {end_idx - start_idx} of {len(items)})"
    )

    keyboard_rows = [
        [
            InlineKeyboardButton(
                f"▶ {html_escape(item['title'])[:30]}",
                callback_data=(
                    f"video_{item['video_id']}_playlist_direct_{page}"
                    if direct
                    else f"video_{item['video_id']}_playlist_{playlist_id}_{page}"
                ),
            )
        ]
        for item in page_items
    ]

    page_nav_buttons = []
    if page > 0:
        page_nav_buttons.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=(
                    f"playlist_items_direct_{playlist_id}_{page - 1}"
                    if direct
                    else f"playlist_items_{playlist_id}_{page - 1}"
                ),
            )
        )
    if page < total_pages - 1:
        page_nav_buttons.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=(
                    f"playlist_items_direct_{playlist_id}_{page + 1}"
                    if direct
                    else f"playlist_items_{playlist_id}_{page + 1}"
                ),
            )
        )
    if page_nav_buttons:
        keyboard_rows.append(page_nav_buttons)

    back_text = "🔙 Playlists" if back_callback == "playlists_0" else "🔙 Playlist"
    keyboard_rows.append([
        InlineKeyboardButton(back_text, callback_data=back_callback),
        InlineKeyboardButton(
            "🔙 Channel",
            callback_data=("direct_playlist_channel" if direct else "channel_info"),
        ),
    ])
    keyboard_rows.append([InlineKeyboardButton("🏠 Home", callback_data="action_home")])

    keyboard = InlineKeyboardMarkup(keyboard_rows)
    return message, keyboard


async def handle_callback_query(update: Update) -> None:
    """Handle inline button callbacks for channel flows."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        # Query may be too old; log and continue with message editing
        logger.debug("Failed to answer callback query (possibly expired)")
    
    data = query.data
    try:
        # Simple actions that don't require a stored channel session
        if data == "action_channels":
            state_key = f"{SESSION_STATE_PREFIX}{query.from_user.id}"
            await set_cache(state_key, {"awaiting": "channel_search"}, ttl=300)
            await query.edit_message_text(
                "Please send the channel name, URL, or channel ID now.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="action_cancel")]]),
            )
            return

        if data == "action_playlists":
            state_key = f"{SESSION_STATE_PREFIX}{query.from_user.id}"
            await set_cache(state_key, {"awaiting": "playlist_search"}, ttl=300)
            await query.edit_message_text(
                "Please send the playlist URL or playlist ID now.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="action_cancel")]]),
            )
            return

        if data == "action_videos":
            state_key = f"{SESSION_STATE_PREFIX}{query.from_user.id}"
            await set_cache(state_key, {"awaiting": "video_search"}, ttl=300)
            await query.edit_message_text(
                "Please send the video URL or video ID now.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="action_cancel")]]),
            )
            return

        if data == "action_help":
            message, keyboard = format_help_message()
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

        if data == "action_about":
            message, keyboard = format_about_message()
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

        if data == "action_home":
            message, keyboard = format_main_menu()
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

        if data == "action_cancel":
            state_key = f"{SESSION_STATE_PREFIX}{query.from_user.id}"
            await set_cache(state_key, None, ttl=1)
            await query.edit_message_text("Cancelled. Send a channel name or use /help to see options.")
            return

        # Otherwise we expect a stored channel or playlist session for pagination
        user_channel_key = f"{SESSION_CHANNEL_PREFIX}{query.from_user.id}"
        user_playlist_key = f"{SESSION_PLAYLIST_PREFIX}{query.from_user.id}"
        channel_data = await get_cache(user_channel_key)
        playlist_data = await get_cache(user_playlist_key)

        if not channel_data and not playlist_data:
            await query.edit_message_text("❌ Session expired. Please search for a channel or playlist again.")
            return

        info = channel_data["info"] if channel_data else None
        playlists = channel_data["playlists"] if channel_data else []
        videos = channel_data["videos"] if channel_data else []

        if playlist_data and data.startswith("playlist_items_direct_"):
            payload = data[len("playlist_items_direct_"):]
            playlist_id, page_text = payload.rsplit("_", 1)
            page = int(page_text)
            playlist_title = playlist_data["info"]["title"]
            playlist_items = playlist_data.get("items")
            if playlist_items is None:
                playlist_items = await get_playlist_items(playlist_id)
                playlist_data["items"] = playlist_items
                await set_cache(user_playlist_key, playlist_data, ttl=3600)
            message, keyboard = format_playlist_items_page(
                playlist_items,
                page,
                playlist_id,
                playlist_title,
                back_callback="playlist_info_direct",
                direct=True,
            )
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return
        elif playlist_data and data.startswith("video_") and "_playlist_direct_" in data:
            payload = data[len("video_"):]
            video_id, page_text = payload.split("_playlist_direct_", 1)
            page = int(page_text)
            playlist_id = playlist_data["playlist_id"]
            return_callback = f"playlist_items_direct_{playlist_id}_{page}"
            video = next(
                (
                    item
                    for item in playlist_data.get("items", [])
                    if item.get("video_id") == video_id
                ),
                None,
            )
            if not video:
                await query.edit_message_text("❌ Video not found or session expired.")
                return
            stats = await get_video_stats(video_id)
            channel_callback = "direct_playlist_channel" if "_playlist_direct_" in data else "channel_info"
            message, keyboard = format_video_detail(
                video,
                stats,
                page,
                return_callback=return_callback,
                channel_callback=channel_callback,
            )
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

        if data == "channel_info":
            message, keyboard = format_channel_info(info, len(playlists), len(videos))
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data == "playlist_info_direct":
            message, keyboard = format_playlist_info(playlist_data["info"])
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data == "direct_playlist_channel":
            if not playlist_data:
                await query.edit_message_text("❌ Session expired. Please search for a playlist again.")
                return
            channel_id = playlist_data.get("channel_id")
            if not channel_id:
                await query.edit_message_text("❌ Channel information not available.")
                return
            try:
                channel_info = await get_channel_info(channel_id)
                playlists = await get_playlists(channel_id)
                videos = await get_latest_videos(channel_id, max_results=50)
                # Store channel data for pagination
                user_channel_key = f"{SESSION_CHANNEL_PREFIX}{query.from_user.id}"
                channel_data = {
                    "channel_id": channel_id,
                    "info": channel_info,
                    "playlists": playlists,
                    "videos": videos,
                }
                await set_cache(user_channel_key, channel_data, ttl=3600)
                # Also keep the playlist data for navigation
                message, keyboard = format_channel_info(channel_info, len(playlists), len(videos))
                await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            except Exception as exc:
                logger.exception("Error fetching channel from direct playlist")
                await query.edit_message_text(f"❌ Error: {html_escape(str(exc))}")
        elif data == "video_info_direct":
            user_video_key = f"{SESSION_VIDEO_PREFIX}{query.from_user.id}"
            video_data = await get_cache(user_video_key)
            if not video_data:
                await query.edit_message_text("❌ Session expired. Please search for a video again.")
                return
            video_info = video_data["info"]
            stats = video_info
            message, keyboard = format_video_detail(video_info, stats, page=0, return_callback="video_info_direct")
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data == "direct_video_channel":
            user_video_key = f"{SESSION_VIDEO_PREFIX}{query.from_user.id}"
            video_data = await get_cache(user_video_key)
            if not video_data:
                await query.edit_message_text("❌ Session expired. Please search for a video again.")
                return
            channel_id = video_data.get("channel_id")
            if not channel_id:
                await query.edit_message_text("❌ Channel information not available.")
                return
            try:
                channel_info = await get_channel_info(channel_id)
                playlists = await get_playlists(channel_id)
                videos = await get_latest_videos(channel_id, max_results=50)
                # Store channel data for pagination
                user_channel_key = f"{SESSION_CHANNEL_PREFIX}{query.from_user.id}"
                channel_data = {
                    "channel_id": channel_id,
                    "info": channel_info,
                    "playlists": playlists,
                    "videos": videos,
                }
                await set_cache(user_channel_key, channel_data, ttl=3600)
                message, keyboard = format_channel_info(channel_info, len(playlists), len(videos))
                await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            except Exception as exc:
                logger.exception("Error fetching channel from direct video")
                await query.edit_message_text(f"❌ Error: {html_escape(str(exc))}")
        elif data == "description_more":
            message, keyboard = format_full_description(info)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data.startswith("playlist_items_"):
            payload = data[len("playlist_items_"):]
            playlist_id, page_text = payload.rsplit("_", 1)
            page = int(page_text)
            playlist_title = next(
                (pl["title"] for pl in playlists if pl["playlist_id"] == playlist_id),
                "Playlist",
            )
            playlist_items = channel_data.get("playlist_items", {}).get(playlist_id)
            if playlist_items is None:
                playlist_items = await get_playlist_items(playlist_id)
                channel_data.setdefault("playlist_items", {})[playlist_id] = playlist_items
                await set_cache(user_channel_key, channel_data, ttl=3600)
            message, keyboard = format_playlist_items_page(playlist_items, page, playlist_id, playlist_title)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data.startswith("playlist_"):
            payload = data[len("playlist_"):]
            playlist_id, page_text = payload.rsplit("_", 1)
            page = int(page_text)
            playlist_title = next(
                (pl["title"] for pl in playlists if pl["playlist_id"] == playlist_id),
                "Playlist",
            )
            playlist_items = await get_playlist_items(playlist_id)
            channel_data.setdefault("playlist_items", {})[playlist_id] = playlist_items
            await set_cache(user_channel_key, channel_data, ttl=3600)
            message, keyboard = format_playlist_items_page(playlist_items, page, playlist_id, playlist_title)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data.startswith("video_"):
            payload = data[len("video_"):]
            return_callback = None
            if "_playlist_" in payload:
                video_id, rest = payload.split("_playlist_", 1)
                playlist_id, page_text = rest.rsplit("_", 1)
                page = int(page_text)
                return_callback = f"playlist_items_{playlist_id}_{page}"
                video = next((v for v in videos if v["video_id"] == video_id), None)
                if video is None:
                    video = next(
                        (
                            item
                            for item in channel_data.get("playlist_items", {}).get(playlist_id, [])
                            if item.get("video_id") == video_id
                        ),
                        None,
                    )
            else:
                video_id, page_text = payload.rsplit("_", 1)
                page = int(page_text)
                return_callback = f"videos_{page}"
                video = next((v for v in videos if v["video_id"] == video_id), None)

            if not video:
                await query.edit_message_text("❌ Video not found or session expired.")
                return
            stats = await get_video_stats(video_id)
            message, keyboard = format_video_detail(video, stats, page, return_callback=return_callback)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data.startswith("playlists_"):
            page = int(data.split("_")[1])
            message, keyboard = format_playlists_page(playlists, page)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif data.startswith("videos_"):
            page = int(data.split("_")[1])
            message, keyboard = format_videos_page(videos, page)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception as exc:
        logger.exception("Error handling callback query")
        await query.edit_message_text(f"❌ Error: {html_escape(str(exc))}")


async def handle_inline_query(update: Update) -> None:
    """Handle inline mode queries (type @yourbot query in any chat)."""
    inline = update.inline_query
    query_text = (inline.query or "").strip()
    if not query_text:
        await inline.answer([], cache_time=5)
        return

    try:
        # Resolve channel id and fetch details
        channel_id = await resolve_channel_id(query_text)
        info = await get_channel_info(channel_id)
        # Build a single article result with the channel info
        message, _ = format_channel_info(info, 0, 0)
        content = InputTextMessageContent(message, parse_mode=ParseMode.HTML)
        result = InlineQueryResultArticle(id=str(uuid4()), title=info.get("name", "Channel"), input_message_content=content, description=f"Subscribers: {int(info.get('subscribers',0)):,}")
        await inline.answer([result], cache_time=60)
    except Exception:
        await inline.answer([], cache_time=5)


async def handle_channel(update: Update) -> None:
    if update.message is None or update.message.text is None:
        return

    user_input = update.message.text.strip()

    # Handle commands
    if user_input.startswith("/"):
        command = user_input.split()[0].lower()
        if command == "/start":
            from app.services.telegram import handle_start_command
            await handle_start_command(update)
        elif command == "/help":
            from app.services.telegram import handle_help_command
            await handle_help_command(update)
        elif command == "/about":
            from app.services.telegram import handle_about_command
            await handle_about_command(update)
        elif command in ("/menu", "/"):
            message, keyboard = format_main_menu()
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            await update.message.reply_text(
                "❓ Unknown command. Send /help to see available commands."
            )
        return

    # Check for direct playlist URLs or IDs before other input handling
    # First do a lightweight parse to avoid unnecessary I/O. If the input
    # looks like a playlist, call `resolve_playlist_id` so tests that patch
    # that function can observe the call. If resolution fails, fall back
    # to the parsed value.
    playlist_id = None
    candidate = _parse_playlist_id(user_input)
    if candidate:
        try:
            playlist_id = await resolve_playlist_id(user_input)
        except Exception:
            playlist_id = candidate

    # Check for direct video URLs or IDs
    video_id = None
    video_candidate = parse_video_id(user_input)
    if video_candidate:
        video_id = video_candidate

    # Check if user is in an awaiting state (e.g., clicked Channels or Playlists and should send query)
    state_key = f"{SESSION_STATE_PREFIX}{update.message.from_user.id}"
    state = await get_cache(state_key)

    if state and state.get("awaiting") == "playlist_search":
        await set_cache(state_key, None, ttl=1)
        if not playlist_id:
            await update.message.reply_text("❌ Please send a valid playlist URL or playlist ID.")
            return

    if state and state.get("awaiting") == "video_search":
        await set_cache(state_key, None, ttl=1)
        if not video_id:
            await update.message.reply_text("❌ Please send a valid video URL or video ID.")
            return

    if video_id:
        await update.message.reply_text("🔍 Looking up video...")
        try:
            video_info = await get_video_info(video_id)
            user_video_key = f"{SESSION_VIDEO_PREFIX}{update.message.from_user.id}"
            video_data = {
                "video_id": video_id,
                "info": video_info,
                "channel_id": video_info.get("channel_id"),
            }
            await set_cache(user_video_key, video_data, ttl=3600)

            stats = video_info
            message, keyboard = format_video_detail(
                video_info,
                stats,
                page=0,
                return_callback="video_info_direct",
                channel_callback="direct_video_channel",
            )
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.exception("Error handling video lookup")
            await update.message.reply_text(f"❌ Error: {html_escape(str(exc))}")
        return

    if playlist_id:
        await update.message.reply_text("🔍 Looking up playlist...")
        try:
            playlist_info = await get_playlist_info(playlist_id)
            playlist_items = await get_playlist_items(playlist_id)

            user_playlist_key = f"{SESSION_PLAYLIST_PREFIX}{update.message.from_user.id}"
            playlist_data = {
                "playlist_id": playlist_id,
                "channel_id": playlist_info.get("channel_id"),
                "info": playlist_info,
                "items": playlist_items,
            }
            await set_cache(user_playlist_key, playlist_data, ttl=3600)

            message, keyboard = format_playlist_info(playlist_info)
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.exception("Error handling playlist lookup")
            await update.message.reply_text(f"❌ Error: {html_escape(str(exc))}")
        return

    if state and state.get("awaiting") == "channel_search":
        # Clear state
        await set_cache(state_key, None, ttl=1)

        await update.message.reply_text("🔍 Looking up channel...")

        try:
            channel_id = await resolve_channel_id(user_input)
            info = await get_channel_info(channel_id)
            playlists = await get_playlists(channel_id)
            videos = await get_latest_videos(channel_id, max_results=50)

            # Store channel data for pagination
            user_channel_key = f"{SESSION_CHANNEL_PREFIX}{update.message.from_user.id}"
            channel_data = {
                "channel_id": channel_id,
                "info": info,
                "playlists": playlists,
                "videos": videos,
            }
            await set_cache(user_channel_key, channel_data, ttl=3600)

            # Send channel info with buttons
            message, keyboard = format_channel_info(info, len(playlists), len(videos))
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.exception("Error handling channel lookup")
            await update.message.reply_text(f"❌ Error: {html_escape(str(exc))}")
        return

    # Otherwise show a simple action menu
    message, menu = format_main_menu()
    await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=menu)
