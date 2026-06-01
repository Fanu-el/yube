import logging

from telegram import Update
from telegram.constants import ParseMode

from app.services.channels.handlers import (
    format_about_message,
    format_channel_info,
    format_help_message,
    format_main_menu,
    format_playlist_items_page,
    format_playlists_page,
    handle_callback_query,
    handle_inline_query,
    handle_channel,
)
from app.services.videos import (
    format_video_detail,
    format_videos_page,
)

__all__ = [
    "format_about_message",
    "format_channel_info",
    "format_help_message",
    "format_main_menu",
    "format_playlist_items_page",
    "format_video_detail",
    "format_playlists_page",
    "format_videos_page",
    "handle_callback_query",
    "handle_inline_query",
    "handle_channel",
    "handle_start_command",
    "handle_help_command",
    "handle_about_command",
]

logger = logging.getLogger(__name__)

async def handle_start_command(update: Update) -> None:
    """Handle /start command."""
    welcome_message = (
        "👋 <b>Welcome to yube!</b>\n\n"
        "Discover YouTube channels, playlists, and videos in one place.\n\n"
        "<b>What you can do:</b>\n"
        "• Search channels by name, URL, or channel ID\n"
        "• Browse playlists with pagination\n"
        "• Open video details and previews\n"
        "• Use direct playlist/video URLs or IDs\n\n"
        "<b>Features:</b>\n"
        "• 🎬 Channel stats and description\n"
        "• 📋 Playlist overview and item navigation\n"
        "• ▶ Video details with thumbnail previews\n\n"
        "<b>Commands:</b>\n"
        "/start - Show this welcome message\n"
        "/help - Usage instructions\n"
        "/about - About this bot\n\n"
        "<b>Example:</b>\n"
        "Send: <code>YouTube</code> or <code>https://youtube.com/playlist?list=PL...</code>"
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
        "3️⃣ <b>Channel ID:</b> Send a channel ID starting with UC\n"
        "4️⃣ <b>Playlist URL/ID:</b> Send a playlist URL or playlist ID\n"
        "5️⃣ <b>Video URL/ID:</b> Send a video URL or video ID\n\n"
        "<b>What you'll get:</b>\n"
        "• Channel statistics, description, and uploads\n"
        "• Playlist details and item navigation\n"
        "• Video details, thumbnails, and playback links\n\n"
        "<b>Need quick actions?</b> Use /menu or click the buttons in chat."
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


