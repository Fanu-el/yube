"""Pytest configuration and fixtures."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables
os.environ["TELEGRAM_TOKEN"] = "test_token_123"
os.environ["YOUTUBE_API_KEY"] = "test_youtube_key_123"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["WEBHOOK_URL"] = "https://example.com"

# Import after setting env vars and path
from telegram import Bot, Update, User, Chat, Message
from telegram.constants import ParseMode


@pytest.fixture
def mock_update_message():
    """Create a mock Update with message."""
    user = User(id=123456, is_bot=False, first_name="Test")
    chat = Chat(id=123456, type="private")
    message = Message(
        message_id=1,
        date=None,
        chat=chat,
        from_user=user,
        text="test message",
    )
    update = Update(update_id=1, message=message)
    return update


@pytest.fixture
def mock_update_callback():
    """Create a mock Update with callback_query."""
    user = User(id=123456, is_bot=False, first_name="Test")
    from telegram import CallbackQuery
    
    callback_query = MagicMock(spec=CallbackQuery)
    callback_query.from_user = user
    callback_query.data = "playlists_0"
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()
    
    update = Update(update_id=2, callback_query=callback_query)
    return update


@pytest.fixture
def mock_channel_info():
    """Mock channel info response."""
    return {
        "name": "Test Channel",
        "description": "This is a test channel description.",
        "subscribers": "1000000",
        "total_videos": "500",
        "total_views": "50000000",
        "uploads_playlist_id": "UUtest123",
    }


@pytest.fixture
def mock_playlists():
    """Mock playlists response."""
    return [
        {
            "title": f"Playlist {i}",
            "playlist_id": f"PLtest{i}",
            "video_count": 50 + i * 10,
            "url": f"https://youtube.com/playlist?list=PLtest{i}",
        }
        for i in range(1, 13)  # 12 playlists for pagination testing
    ]


@pytest.fixture
def mock_videos():
    """Mock videos response."""
    return [
        {
            "title": f"Video {i}",
            "url": f"https://youtube.com/watch?v=vid{i}",
            "published": "2024-01-01T00:00:00Z",
            "thumbnail": f"https://img.youtube.com/vi/vid{i}/default.jpg",
        }
        for i in range(1, 26)  # 25 videos for pagination testing
    ]
