"""Pytest configuration and fixtures."""
import os
import sys
import pytest

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables
os.environ["TELEGRAM_TOKEN"] = "test_token_123"
os.environ["YOUTUBE_API_KEY"] = "test_youtube_key_123"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["WEBHOOK_URL"] = "https://example.com"

# Import after setting env vars and path


@pytest.fixture
def mock_update_message():
    """Create a mock Update with message."""
    from unittest.mock import MagicMock, AsyncMock

    user = MagicMock()
    user.id = 123456
    user.is_bot = False
    user.first_name = "Test"

    message = MagicMock()
    message.message_id = 1
    message.date = None
    message.chat = MagicMock()
    message.from_user = user
    message.text = "test message"
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.update_id = 1
    update.message = message
    return update


@pytest.fixture
def mock_update_callback():
    """Create a mock Update with callback_query."""
    from telegram import CallbackQuery
    from unittest.mock import MagicMock, AsyncMock

    callback_query = MagicMock(spec=CallbackQuery)
    callback_query.from_user = MagicMock()
    callback_query.from_user.id = 123456
    callback_query.data = "playlists_0"
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()

    update = MagicMock()
    update.update_id = 2
    update.callback_query = callback_query
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
            "video_id": f"vid{i}",
            "published": "2024-01-01T00:00:00Z",
            "thumbnail": f"https://img.youtube.com/vi/vid{i}/default.jpg",
        }
        for i in range(1, 26)  # 25 videos for pagination testing
    ]


@pytest.fixture
def mock_playlist_items():
    """Mock playlist item response."""
    return [
        {
            "title": f"Playlist Video {i}",
            "url": f"https://youtube.com/watch?v=plvid{i}",
            "video_id": f"plvid{i}",
            "published": "2024-01-01T00:00:00Z",
            "thumbnail": f"https://img.youtube.com/vi/plvid{i}/default.jpg",
        }
        for i in range(1, 21)
    ]
