import logging

from telegram import Update
from telegram.constants import ParseMode

from app.services.channels.handlers import (
    format_channel_info,
    format_main_menu,
    format_playlist_items_page,
    format_video_detail,
    format_playlists_page,
    format_videos_page,
    handle_callback_query,
    handle_inline_query,
    handle_channel,
)

__all__ = [
    "format_channel_info",
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


