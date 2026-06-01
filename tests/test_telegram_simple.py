"""Tests for telegram service handlers and formatting."""

from app.services.telegram import (
    format_channel_info,
    format_playlists_page,
    format_videos_page,
)


class TestFormatFunctions:
    """Test message formatting functions."""
    
    def test_format_channel_info(self, mock_channel_info):
        """Test channel info formatting."""
        message, keyboard = format_channel_info(mock_channel_info, 10, 50)
        
        assert "🎬" in message
        assert "Test Channel" in message
        assert "1,000,000" in message
        assert "500" in message
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0
        buttons = keyboard.inline_keyboard[0]
        assert any("Playlists" in btn.text for btn in buttons)
        assert any("Videos" in btn.text for btn in buttons)
    
    def test_format_channel_info_description_truncation(self, mock_channel_info):
        """Test that description is truncated to 300 chars."""
        mock_channel_info["description"] = "x" * 500
        message, _ = format_channel_info(mock_channel_info, 0, 0)
        assert "x" * 300 in message
        assert "..." in message
    
    def test_format_playlists_page_first_page(self, mock_playlists):
        """Test playlists pagination - first page."""
        message, keyboard = format_playlists_page(mock_playlists, 0)
        
        assert "📋 Playlists" in message
        assert "Page 1 of 3" in message
        assert "Playlist 1" in message
        assert "Playlist 5" in message
        buttons_text = " ".join(btn.text for row in keyboard.inline_keyboard for btn in row)
        assert "Next" in buttons_text
    
    def test_format_playlists_page_middle_page(self, mock_playlists):
        """Test playlists pagination - middle page."""
        message, keyboard = format_playlists_page(mock_playlists, 1)
        
        assert "Page 2 of 3" in message
        assert "Playlist 6" in message
        buttons_text = " ".join(btn.text for row in keyboard.inline_keyboard for btn in row)
        assert "Previous" in buttons_text
        assert "Next" in buttons_text
    
    def test_format_playlists_page_last_page(self, mock_playlists):
        """Test playlists pagination - last page."""
        message, keyboard = format_playlists_page(mock_playlists, 2)
        
        assert "Page 3 of 3" in message
        assert "Playlist 11" in message
        buttons_text = " ".join(btn.text for row in keyboard.inline_keyboard for btn in row)
        assert "Previous" in buttons_text
    
    def test_format_videos_page(self, mock_videos):
        """Test videos pagination."""
        message, keyboard = format_videos_page(mock_videos, 0)
        
        assert "✨ Latest Videos" in message
        assert "Page 1 of 5" in message
        assert "Video 1" in message
        assert "Video 5" in message
    
    def test_format_videos_page_pagination(self, mock_videos):
        """Test videos page has proper item counts."""
        for page in range(5):
            message, _ = format_videos_page(mock_videos, page)
            # Each page should reference 5 items (except potentially last)
            if page < 4:
                assert "showing 5 of" in message
            else:
                assert "showing 5 of" in message or "Page 5 of 5" in message

