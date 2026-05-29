"""Tests for telegram service handlers and formatting."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram.constants import ParseMode

from app.services.telegram import (
    format_channel_info,
    format_playlists_page,
    format_videos_page,
    handle_start_command,
    handle_help_command,
    handle_about_command,
    handle_channel,
    handle_callback_query,
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
        assert "📋 Playlists" in message or "playlists" in message.lower()
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0
    
    def test_format_channel_info_description_truncation(self, mock_channel_info):
        """Test that description is truncated to 300 chars."""
        mock_channel_info["description"] = "x" * 500
        message, _ = format_channel_info(mock_channel_info, 0, 0)
        
        # Should be truncated
        assert message.count("x") == 300
    
    def test_format_playlists_page_first_page(self, mock_playlists):
        """Test playlists pagination - first page."""
        message, keyboard = format_playlists_page(mock_playlists, 0)
        
        assert "📋 Playlists" in message
        assert "Page 1 of 3" in message  # 12 playlists / 5 per page = 3 pages
        assert "Playlist 1" in message
        assert "Playlist 5" in message
        assert "Next ➡️" in message or "Next" in message
        assert "⬅️ Previous" not in message  # No previous on first page
    
    def test_format_playlists_page_middle_page(self, mock_playlists):
        """Test playlists pagination - middle page."""
        message, keyboard = format_playlists_page(mock_playlists, 1)
        
        assert "Page 2 of 3" in message
        assert "Playlist 6" in message
        assert "Previous" in message
        assert "Next" in message
    
    def test_format_playlists_page_last_page(self, mock_playlists):
        """Test playlists pagination - last page."""
        message, keyboard = format_playlists_page(mock_playlists, 2)
        
        assert "Page 3 of 3" in message
        assert "Playlist 11" in message
        assert "⬅️ Previous" in message or "Previous" in message
        assert "Next" not in message  # No next on last page
    
    def test_format_videos_page(self, mock_videos):
        """Test videos pagination."""
        message, keyboard = format_videos_page(mock_videos, 0)
        
        assert "✨ Latest Videos" in message
        assert "Page 1 of 5" in message  # 25 videos / 5 per page = 5 pages
        assert "Video 1" in message
        assert "Video 5" in message


class TestCommandHandlers:
    """Test command handler functions."""
    
    @pytest.mark.asyncio
    async def test_handle_start_command(self, mock_update_message):
        """Test /start command."""
        mock_update_message.message.reply_text = AsyncMock()
        
        await handle_start_command(mock_update_message)
        
        mock_update_message.message.reply_text.assert_called_once()
        call_args = mock_update_message.message.reply_text.call_args
        assert "Welcome to yube" in call_args[0][0]
        assert ParseMode.HTML in call_args[1].values()
    
    @pytest.mark.asyncio
    async def test_handle_help_command(self, mock_update_message):
        """Test /help command."""
        mock_update_message.message.reply_text = AsyncMock()
        
        await handle_help_command(mock_update_message)
        
        mock_update_message.message.reply_text.assert_called_once()
        call_args = mock_update_message.message.reply_text.call_args
        assert "How to use yube" in call_args[0][0]
        assert "Channel name" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_about_command(self, mock_update_message):
        """Test /about command."""
        mock_update_message.message.reply_text = AsyncMock()
        
        await handle_about_command(mock_update_message)
        
        mock_update_message.message.reply_text.assert_called_once()
        call_args = mock_update_message.message.reply_text.call_args
        assert "About yube" in call_args[0][0]
        assert "FastAPI" in call_args[0][0]


class TestChannelHandler:
    """Test main channel handler."""
    
    @pytest.mark.asyncio
    async def test_handle_start_command_routing(self, mock_update_message):
        """Test /start command routing."""
        mock_update_message.message.text = "/start"
        mock_update_message.message.reply_text = AsyncMock()
        
        await handle_channel(mock_update_message)
        
        mock_update_message.message.reply_text.assert_called_once()
        call_args = mock_update_message.message.reply_text.call_args
        assert "Welcome to yube" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_help_command_routing(self, mock_update_message):
        """Test /help command routing."""
        mock_update_message.message.text = "/help"
        mock_update_message.message.reply_text = AsyncMock()
        
        await handle_channel(mock_update_message)
        
        call_args = mock_update_message.message.reply_text.call_args
        assert "How to use" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_about_command_routing(self, mock_update_message):
        """Test /about command routing."""
        mock_update_message.message.text = "/about"
        mock_update_message.message.reply_text = AsyncMock()
        
        await handle_channel(mock_update_message)
        
        call_args = mock_update_message.message.reply_text.call_args
        assert "About yube" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_unknown_command(self, mock_update_message):
        """Test unknown command."""
        mock_update_message.message.text = "/unknown"
        mock_update_message.message.reply_text = AsyncMock()
        
        await handle_channel(mock_update_message)
        
        call_args = mock_update_message.message.reply_text.call_args
        assert "Unknown command" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_channel_lookup(self, mock_update_message, mock_channel_info, mock_playlists, mock_videos):
        """Test channel lookup flow."""
        mock_update_message.message.text = "YouTube"
        mock_update_message.message.reply_text = AsyncMock()
        mock_update_message.message.from_user.id = 123
        
        with patch("app.services.telegram.resolve_channel_id", new_callable=AsyncMock) as mock_resolve:
            with patch("app.services.telegram.get_channel_info", new_callable=AsyncMock) as mock_info:
                with patch("app.services.telegram.get_playlists", new_callable=AsyncMock) as mock_pl:
                    with patch("app.services.telegram.get_latest_videos", new_callable=AsyncMock) as mock_vids:
                        with patch("app.services.telegram.set_cache", new_callable=AsyncMock):
                            mock_resolve.return_value = "UCtest123"
                            mock_info.return_value = mock_channel_info
                            mock_pl.return_value = mock_playlists
                            mock_vids.return_value = mock_videos
                            
                            await handle_channel(mock_update_message)
                            
                            # Should call resolve_channel_id
                            mock_resolve.assert_called_once_with("YouTube")
                            
                            # Should call get_channel_info
                            mock_info.assert_called_once_with("UCtest123")
                            
                            # Should call get_playlists
                            mock_pl.assert_called_once_with("UCtest123")
                            
                            # Should call get_latest_videos with max_results=50
                            mock_vids.assert_called_once_with("UCtest123", max_results=50)
                            
                            # Should reply with channel info
                            assert mock_update_message.message.reply_text.called
    
    @pytest.mark.asyncio
    async def test_handle_channel_lookup_error(self, mock_update_message):
        """Test channel lookup error handling."""
        mock_update_message.message.text = "NonExistentChannel12345"
        mock_update_message.message.reply_text = AsyncMock()
        mock_update_message.message.from_user.id = 123
        
        with patch("app.services.telegram.resolve_channel_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = ValueError("Channel not found")
            
            await handle_channel(mock_update_message)
            
            call_args = mock_update_message.message.reply_text.call_args
            assert "❌ Error" in call_args[0][0]


class TestCallbackHandler:
    """Test callback query handler."""
    
    @pytest.mark.asyncio
    async def test_handle_callback_playlists_pagination(self, mock_update_callback, mock_channel_info, mock_playlists, mock_videos):
        """Test playlists pagination callback."""
        mock_update_callback.callback_query.data = "playlists_0"
        mock_update_callback.callback_query.from_user.id = 123
        
        channel_data = {
            "channel_id": "UCtest123",
            "info": mock_channel_info,
            "playlists": mock_playlists,
            "videos": mock_videos,
        }
        
        with patch("app.services.telegram.get_cache", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = channel_data
            
            await handle_callback_query(mock_update_callback)
            
            mock_update_callback.callback_query.answer.assert_called_once()
            mock_update_callback.callback_query.edit_message_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_callback_session_expired(self, mock_update_callback):
        """Test callback with expired session."""
        mock_update_callback.callback_query.from_user.id = 123
        
        with patch("app.services.telegram.get_cache", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # Session expired
            
            await handle_callback_query(mock_update_callback)
            
            call_args = mock_update_callback.callback_query.edit_message_text.call_args
            assert "Session expired" in call_args[0][0]
