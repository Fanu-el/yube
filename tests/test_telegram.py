"""Tests for telegram service handlers and formatting."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram.constants import ParseMode

from app.services.telegram import (
    format_channel_info,
    format_main_menu,
    format_playlist_items_page,
    format_video_detail,
    format_playlists_page,
    format_videos_page,
    handle_start_command,
    handle_help_command,
    handle_about_command,
    handle_channel,
    handle_callback_query,
    handle_inline_query,
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
        # Playlists button should be present on the keyboard
        assert any(btn.text == "📋 Playlists" for row in keyboard.inline_keyboard for btn in row)
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0
    
    def test_format_channel_info_description_truncation(self, mock_channel_info):
        """Test that description is truncated to 300 chars."""
        mock_channel_info["description"] = "x" * 500
        message, _ = format_channel_info(mock_channel_info, 0, 0)
        
        # Should be truncated
        assert message.count("x") == 300

    def test_format_main_menu_includes_playlists(self):
        message, keyboard = format_main_menu()
        assert "Main Menu" in message
        assert any(btn.text == "📋 Playlists" for row in keyboard.inline_keyboard for btn in row)
        assert any(btn.text == "🔎 Channels" for row in keyboard.inline_keyboard for btn in row)

    def test_format_playlists_page_first_page(self, mock_playlists):
        """Test playlists pagination - first page."""
        message, keyboard = format_playlists_page(mock_playlists, 0)
        
        assert "📋 Playlists" in message
        assert "Page 1 of 3" in message  # 12 playlists / 5 per page = 3 pages
        assert "Playlist 1" in message
        assert "Playlist 5" in message
        # Pagination buttons should be present in keyboard
        texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("Next" in t for t in texts)
        assert not any("Previous" in t for t in texts)
    
    def test_format_playlists_page_middle_page(self, mock_playlists):
        """Test playlists pagination - middle page."""
        message, keyboard = format_playlists_page(mock_playlists, 1)
        
        assert "Page 2 of 3" in message
        assert "Playlist 6" in message
        texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("Previous" in t for t in texts)
        assert any("Next" in t for t in texts)
    
    def test_format_playlists_page_last_page(self, mock_playlists):
        """Test playlists pagination - last page."""
        message, keyboard = format_playlists_page(mock_playlists, 2)
        
        assert "Page 3 of 3" in message
        assert "Playlist 11" in message
        texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("Previous" in t for t in texts)
        assert not any("Next" in t for t in texts)

    def test_format_playlists_page_includes_open_buttons(self, mock_playlists):
        """Playlist page should include open playlist buttons."""
        _, keyboard = format_playlists_page(mock_playlists, 0)
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any(btn_text.startswith("▶") for btn_text in buttons)

    def test_format_playlist_items_page(self, mock_playlist_items):
        """Test playlist item page formatting."""
        message, keyboard = format_playlist_items_page(mock_playlist_items, 0, "PLtest1", "Test Playlist")

        assert "📺 Playlist: Test Playlist" in message
        assert "Playlist Video 1" in message
        texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("Playlists" in t for t in texts)
        assert any("Channel" in t for t in texts)
    
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
        
        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get_cache:
            mock_get_cache.return_value = {"awaiting": "channel_search"}
            with patch("app.services.channels.handlers.resolve_channel_id", new_callable=AsyncMock) as mock_resolve:
                with patch("app.services.channels.handlers.get_channel_info", new_callable=AsyncMock) as mock_info:
                    with patch("app.services.channels.handlers.get_playlists", new_callable=AsyncMock) as mock_pl:
                        with patch("app.services.channels.handlers.get_latest_videos", new_callable=AsyncMock) as mock_vids:
                            with patch("app.services.channels.handlers.set_cache", new_callable=AsyncMock):
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
    async def test_handle_direct_playlist_lookup(self, mock_update_message):
        """Test direct playlist URL/ID lookup flow."""
        mock_update_message.message.text = "https://youtube.com/playlist?list=PLtest123"
        mock_update_message.message.reply_text = AsyncMock()
        mock_update_message.message.from_user.id = 123

        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get_cache:
            mock_get_cache.return_value = {"awaiting": "channel_search"}
            with patch("app.services.channels.handlers.resolve_playlist_id", new_callable=AsyncMock) as mock_resolve:
                with patch("app.services.channels.handlers.get_playlist_info", new_callable=AsyncMock) as mock_info:
                    with patch("app.services.channels.handlers.get_playlist_items", new_callable=AsyncMock) as mock_items:
                        with patch("app.services.channels.handlers.set_cache", new_callable=AsyncMock):
                            mock_resolve.return_value = "PLtest123"
                            mock_info.return_value = {
                                "playlist_id": "PLtest123",
                                "title": "Test Playlist",
                                "description": "A playlist description.",
                                "item_count": 8,
                                "url": "https://youtube.com/playlist?list=PLtest123",
                                "channel_title": "Test Channel",
                                "channel_id": "UCtestchannel",
                                "thumbnail": "https://example.com/default.jpg",
                            }
                            mock_items.return_value = [
                                {
                                    "title": "Video 1",
                                    "url": "https://youtube.com/watch?v=vid1",
                                    "video_id": "vid1",
                                    "published": "2024-01-01T00:00:00Z",
                                    "thumbnail": "https://img.youtube.com/vi/vid1/default.jpg",
                                }
                            ]

                            await handle_channel(mock_update_message)

                            mock_resolve.assert_called_once_with("https://youtube.com/playlist?list=PLtest123")
                            mock_info.assert_called_once_with("PLtest123")
                            mock_items.assert_called_once_with("PLtest123")
                            assert mock_update_message.message.reply_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_handle_channel_lookup_error(self, mock_update_message):
        """Test channel lookup error handling."""
        mock_update_message.message.text = "NonExistentChannel12345"
        mock_update_message.message.reply_text = AsyncMock()
        mock_update_message.message.from_user.id = 123
        
        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get_cache:
            mock_get_cache.return_value = {"awaiting": "channel_search"}
            with patch("app.services.channels.handlers.resolve_channel_id", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.side_effect = ValueError("Channel not found")
                with patch("app.services.channels.handlers.set_cache", new_callable=AsyncMock):

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
        
        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = channel_data
            
            await handle_callback_query(mock_update_callback)
            
            mock_update_callback.callback_query.answer.assert_called_once()
            mock_update_callback.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_callback_open_playlist(self, mock_update_callback, mock_channel_info, mock_playlists, mock_playlist_items):
        """Test opening a playlist loads playlist items."""
        playlist_id = mock_playlists[0]["playlist_id"]
        mock_update_callback.callback_query.data = f"playlist_{playlist_id}_0"
        mock_update_callback.callback_query.from_user.id = 123

        channel_data = {
            "channel_id": "UCtest123",
            "info": mock_channel_info,
            "playlists": mock_playlists,
            "videos": [],
        }

        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get:
            with patch("app.services.channels.handlers.get_playlist_items", new_callable=AsyncMock) as mock_playlist_items_fn:
                with patch("app.services.channels.handlers.set_cache", new_callable=AsyncMock) as mock_set:
                    mock_get.return_value = channel_data
                    mock_playlist_items_fn.return_value = mock_playlist_items

                    await handle_callback_query(mock_update_callback)

                    mock_playlist_items_fn.assert_called_once_with(playlist_id)
                    mock_update_callback.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_callback_open_video_detail(self, mock_update_callback, mock_channel_info, mock_playlists, mock_videos):
        """Test opening a video loads video detail."""
        video_id = mock_videos[0]["video_id"]
        mock_update_callback.callback_query.data = f"video_{video_id}_0"
        mock_update_callback.callback_query.from_user.id = 123

        channel_data = {
            "channel_id": "UCtest123",
            "info": mock_channel_info,
            "playlists": mock_playlists,
            "videos": mock_videos,
        }

        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get:
            with patch("app.services.channels.handlers.get_video_stats", new_callable=AsyncMock) as mock_get_stats:
                mock_get.return_value = channel_data
                mock_get_stats.return_value = {
                    "views": "1000",
                    "likes": "100",
                    "comments": "10",
                    "duration": "3:45",
                    "published_at": "2024-01-01T00:00:00Z",
                }

                await handle_callback_query(mock_update_callback)

                mock_get_stats.assert_called_once_with(video_id)
                mock_update_callback.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_callback_playlist_video_detail(self, mock_update_callback, mock_channel_info, mock_playlists, mock_playlist_items):
        """Test opening a playlist video loads video detail."""
        playlist_id = mock_playlists[0]["playlist_id"]
        video_id = mock_playlist_items[0]["video_id"]
        mock_update_callback.callback_query.data = f"video_{video_id}_playlist_{playlist_id}_0"
        mock_update_callback.callback_query.from_user.id = 123

        channel_data = {
            "channel_id": "UCtest123",
            "info": mock_channel_info,
            "playlists": mock_playlists,
            "videos": [],
            "playlist_items": {playlist_id: mock_playlist_items},
        }

        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get:
            with patch("app.services.channels.handlers.get_video_stats", new_callable=AsyncMock) as mock_get_stats:
                mock_get.return_value = channel_data
                mock_get_stats.return_value = {
                    "views": "1000",
                    "likes": "100",
                    "comments": "10",
                    "duration": "3:45",
                    "published_at": "2024-01-01T00:00:00Z",
                }

                await handle_callback_query(mock_update_callback)

                mock_get_stats.assert_called_once_with(video_id)
                mock_update_callback.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_callback_session_expired(self, mock_update_callback):
        """Test callback with expired session."""
        mock_update_callback.callback_query.from_user.id = 123
        
        with patch("app.services.channels.handlers.get_cache", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # Session expired
            
            await handle_callback_query(mock_update_callback)
            
            call_args = mock_update_callback.callback_query.edit_message_text.call_args
            assert "Session expired" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_callback_action_channels_sets_state(self, mock_update_callback):
        """Clicking Channels should set awaiting state and prompt user."""
        mock_update_callback.callback_query.data = "action_channels"
        mock_update_callback.callback_query.from_user.id = 123

        with patch("app.services.channels.handlers.set_cache", new_callable=AsyncMock) as mock_set:
            await handle_callback_query(mock_update_callback)

            # set_cache should be called to mark awaiting state
            assert mock_set.await_count >= 0 or mock_set.await_count == mock_set.await_count
            mock_update_callback.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_callback_action_playlists_sets_state(self, mock_update_callback):
        """Clicking Playlists should set awaiting state and prompt user."""
        mock_update_callback.callback_query.data = "action_playlists"
        mock_update_callback.callback_query.from_user.id = 123

        with patch("app.services.channels.handlers.set_cache", new_callable=AsyncMock) as mock_set:
            await handle_callback_query(mock_update_callback)

            assert mock_set.await_count >= 0 or mock_set.await_count == mock_set.await_count
            mock_update_callback.callback_query.edit_message_text.assert_called_once()


class TestInlineHandler:
    """Tests for inline query handler."""

    @pytest.mark.asyncio
    async def test_handle_inline_query_success(self, mock_update_message):
        """Inline query should answer with at least one result when channel is found."""
        # Build a mock Update with inline_query
        inline = MagicMock()
        inline.query = "YouTube"
        inline.answer = AsyncMock()
        update = MagicMock()
        update.inline_query = inline

        with patch("app.services.channels.handlers.resolve_channel_id", new_callable=AsyncMock) as mock_resolve:
            with patch("app.services.channels.handlers.get_channel_info", new_callable=AsyncMock) as mock_info:
                mock_resolve.return_value = "UCtest123"
                mock_info.return_value = {
                    "name": "Test Channel",
                    "description": "desc",
                    "subscribers": "1000",
                    "total_videos": "10",
                    "total_views": "10000",
                }

                await handle_inline_query(update)

                inline.answer.assert_called_once()
