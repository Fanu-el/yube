import json
import logging
from typing import List, Optional
from uuid import uuid4

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
from app.services.youtube import get_channel_info, get_latest_videos, get_playlists, resolve_channel_id

logger = logging.getLogger(__name__)
ITEMS_PER_PAGE = 5
SESSION_STATE_PREFIX = "telegram:state:"
SESSION_CHANNEL_PREFIX = "telegram:channel:"


def format_channel_info(info: dict, playlists_count: int, videos_count: int) -> tuple[str, InlineKeyboardMarkup]:
    """Format channel info with interactive buttons."""
    name = html_escape(info["name"])
    description = html_escape(info["description"][:300])
    
    message = (
        f"<b>🎬 {name}</b>\n\n"
        f"<b>📊 Statistics:</b>\n"
        f"👥 Subscribers: <b>{int(info['subscribers']):,}</b>\n"
        f"🎬 Total Videos: <b>{int(info['total_videos']):,}</b>\n"
        f"👁️ Total Views: <b>{int(info['total_views']):,}</b>\n\n"
        f"<b>📝 Description:</b>\n{description}"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Playlists", callback_data="playlists_0"),
            InlineKeyboardButton("✨ Latest Videos", callback_data="videos_0"),
        ]
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
    
    # Build pagination keyboard
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"playlists_{page - 1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"playlists_{page + 1}"))
    
    buttons.append(InlineKeyboardButton("🔙 Back", callback_data="channel_info"))
    
    keyboard = InlineKeyboardMarkup([buttons]) if buttons else InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="channel_info")]])
    
    return message, keyboard


def format_videos_page(videos: List[dict], page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Format videos page with pagination."""
    total_pages = (len(videos) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(videos))
    
    page_videos = videos[start_idx:end_idx]
    
    video_lines = "\n".join(
        f"<b>{i + start_idx + 1}.</b> <a href=\"{html_escape(video['url'])}\">{html_escape(video['title'])}</a>"
        for i, video in enumerate(page_videos)
    ) or "No videos found."
    
    message = (
        f"<b>✨ Latest Videos</b>\n\n"
        f"{video_lines}\n\n"
        f"<b>Page {page + 1} of {total_pages}</b> (showing {end_idx - start_idx} of {len(videos)})"
    )
    
    # Build pagination keyboard
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"videos_{page - 1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"videos_{page + 1}"))
    
    buttons.append(InlineKeyboardButton("🔙 Back", callback_data="channel_info"))
    
    keyboard = InlineKeyboardMarkup([buttons]) if buttons else InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="channel_info")]])
    
    return message, keyboard


async def handle_start_command(update: Update) -> None:
    """Handle /start command."""
    welcome_message = (
        "👋 <b>Welcome to yube!</b>\n\n"
        "I help you discover YouTube channel information quickly.\n\n"
        "<b>How to use:</b>\n"
        "Just send me a channel name, URL, or channel ID and I'll show you:\n"
        "• 👥 Subscriber count\n"
        "• 🎬 Total videos\n"
        "• 👁 Total views\n"
        "• 📋 Top playlists\n"
        "• ✨ Latest uploads\n\n"
        "<b>Commands:</b>\n"
        "/start - Show this welcome message\n"
        "/help - Show help information\n"
        "/about - About this bot\n\n"
        "<b>Example:</b>\n"
        "Send: <code>@YouTube</code>"
    )
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.HTML)


async def handle_help_command(update: Update) -> None:
    """Handle /help command."""
    help_message = (
        "<b>📖 How to use yube</b>\n\n"
        "<b>Search methods:</b>\n"
        "1️⃣ <b>Channel name:</b> Send the channel name (e.g., <code>YouTube</code>)\n"
        "2️⃣ <b>Channel URL:</b> Send a YouTube channel URL\n"
        "   • youtube.com/channel/UCxxxxx\n"
        "   • youtube.com/c/ChannelName\n"
        "   • youtube.com/@ChannelHandle\n"
        "3️⃣ <b>Channel ID:</b> Send a channel ID starting with UC (e.g., <code>UCkRfArvrzheW2E7b6SVV8Jg</code>)\n\n"
        "<b>What you'll get:</b>\n"
        "• Channel statistics (subscribers, videos, views)\n"
        "• Channel description\n"
        "• Top playlists with video counts\n"
        "• Latest 5 uploaded videos\n\n"
        "<b>All results include clickable links!</b>"
    )
    await update.message.reply_text(help_message, parse_mode=ParseMode.HTML)


async def handle_about_command(update: Update) -> None:
    """Handle /about command."""
    about_message = (
        "<b>ℹ️ About yube</b>\n\n"
        "yube is a Telegram bot that helps you discover YouTube channel information quickly.\n\n"
        "<b>Features:</b>\n"
        "✨ Fast channel lookup by name, URL, or ID\n"
        "📊 Real-time channel statistics\n"
        "🎬 Playlist and video information\n"
        "🔗 Direct links to playlists and videos\n"
        "⚡ Cached results for better performance\n\n"
        "<b>Powered by:</b>\n"
        "• FastAPI for high performance\n"
        "• YouTube Data API v3\n"
        "• Redis for caching\n\n"
        "<b>Need help?</b> Send /help to see usage instructions."
    )
    await update.message.reply_text(about_message, parse_mode=ParseMode.HTML)


async def handle_callback_query(update: Update) -> None:
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()
    
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

        if data == "action_cancel":
            state_key = f"{SESSION_STATE_PREFIX}{query.from_user.id}"
            await set_cache(state_key, None, ttl=1)
            await query.edit_message_text("Cancelled. Send a channel name or use /help to see options.")
            return

        # Otherwise we expect a stored channel session for pagination
        user_channel_key = f"{SESSION_CHANNEL_PREFIX}{query.from_user.id}"
        channel_data = await get_cache(user_channel_key)

        if not channel_data:
            await query.edit_message_text("❌ Session expired. Please search for a channel again.")
            return

        channel_id = channel_data["channel_id"]
        info = channel_data["info"]
        playlists = channel_data["playlists"]
        videos = channel_data["videos"]

        if data == "channel_info":
            message, keyboard = format_channel_info(info, len(playlists), len(videos))
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
            await handle_start_command(update)
        elif command == "/help":
            await handle_help_command(update)
        elif command == "/about":
            await handle_about_command(update)
        else:
            await update.message.reply_text(
                "❓ Unknown command. Send /help to see available commands."
            )
        return

    # Check if user is in an awaiting state (e.g., clicked Channels and should send query)
    state_key = f"{SESSION_STATE_PREFIX}{update.message.from_user.id}"
    state = await get_cache(state_key)

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
    menu = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Channels", callback_data="action_channels")],
        [InlineKeyboardButton("/help", callback_data="action_help")],
    ])
    await update.message.reply_text("Choose an action:", reply_markup=menu)
