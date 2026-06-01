"""Tests for video service formatting."""
import pytest

from app.services.videos import format_video_detail, format_videos_page


class TestFormatVideoFunctions:
    """Test video message formatting functions."""

    def test_format_videos_page(self, mock_videos):
        """Test videos pagination."""
        message, keyboard = format_videos_page(mock_videos, 0)
        
        assert "✨ Latest Videos" in message
        assert "Page 1 of 5" in message  # 25 videos / 5 per page = 5 pages
        assert "Video 1" in message
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any(btn_text.startswith("▶") for btn_text in buttons)

    def test_format_video_detail(self, mock_videos):
        """Test video detail formatting."""
        stats = {
            "views": "1234",
            "likes": "100",
            "comments": "5",
            "duration": "3:45",
            "published_at": "2024-01-01T00:00:00Z",
        }
        message, keyboard = format_video_detail(mock_videos[0], stats, 0)

        assert "▶ Video 1" in message
        assert "⏱ Duration:" in message
        assert "👁 Views:" in message
        assert "🔙 Videos" in [btn.text for row in keyboard.inline_keyboard for btn in row]
