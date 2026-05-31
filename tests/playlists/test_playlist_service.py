import pytest
from unittest.mock import AsyncMock, patch

from app.services.playlists import get_playlist_info, get_playlist_items, get_playlists, resolve_playlist_id


@pytest.mark.asyncio
async def test_resolve_playlist_id_from_url():
    api_input = "https://youtube.com/playlist?list=PLfallback123"

    with patch("app.services.playlists.playlist.get_cache", new_callable=AsyncMock) as mock_get_cache, patch(
        "app.services.playlists.playlist.set_cache", new_callable=AsyncMock
    ) as mock_set_cache:
        mock_get_cache.return_value = None

        playlist_id = await resolve_playlist_id(api_input)

    assert playlist_id == "PLfallback123"
    mock_set_cache.assert_called_once_with(
        "youtube:resolve:playlist:youtube.com/playlist?list=plfallback123",
        "PLfallback123",
        ttl=86400,
    )


@pytest.mark.asyncio
async def test_resolve_playlist_id_from_id():
    api_input = "PLfallback123"

    with patch("app.services.playlists.playlist.get_cache", new_callable=AsyncMock) as mock_get_cache, patch(
        "app.services.playlists.playlist.set_cache", new_callable=AsyncMock
    ) as mock_set_cache:
        mock_get_cache.return_value = None

        playlist_id = await resolve_playlist_id(api_input)

    assert playlist_id == "PLfallback123"
    mock_set_cache.assert_called_once_with(
        "youtube:resolve:playlist:plfallback123",
        "PLfallback123",
        ttl=86400,
    )


@pytest.mark.asyncio
async def test_get_playlist_info_parses_details():
    api_response = {
        "items": [
            {
                "id": "PLtest123",
                "snippet": {
                    "title": "Test Playlist",
                    "description": "A playlist description.",
                    "channelTitle": "Test Channel",
                    "channelId": "UCtestchannel",
                    "thumbnails": {"default": {"url": "https://example.com/default.jpg"}},
                },
                "contentDetails": {"itemCount": 8},
            }
        ]
    }

    with patch("app.services.playlists.playlist.get_cache", new_callable=AsyncMock) as mock_get_cache, patch(
        "app.services.playlists.playlist.set_cache", new_callable=AsyncMock
    ) as mock_set_cache, patch("app.services.playlists.playlist._execute_youtube", new_callable=AsyncMock) as mock_execute:
        mock_get_cache.return_value = None
        mock_execute.return_value = api_response

        playlist_info = await get_playlist_info("PLtest123")

    assert playlist_info == {
        "playlist_id": "PLtest123",
        "title": "Test Playlist",
        "description": "A playlist description.",
        "item_count": 8,
        "url": "https://youtube.com/playlist?list=PLtest123",
        "channel_title": "Test Channel",
        "channel_id": "UCtestchannel",
        "thumbnail": "https://example.com/default.jpg",
    }


@pytest.mark.asyncio
async def test_get_playlists_returns_parsed_playlist_items():
    api_response = {
        "items": [
            {
                "id": "PLtest123",
                "snippet": {"title": "Test Playlist"},
                "contentDetails": {"itemCount": 8},
            }
        ]
    }

    with patch("app.services.playlists.playlist.get_cache", new_callable=AsyncMock) as mock_get_cache, patch(
        "app.services.playlists.playlist.set_cache", new_callable=AsyncMock
    ) as mock_set_cache, patch("app.services.playlists.playlist._execute_youtube", new_callable=AsyncMock) as mock_execute:
        mock_get_cache.return_value = None
        mock_execute.return_value = api_response

        playlists = await get_playlists("UCtest123")

    assert playlists == [
        {
            "title": "Test Playlist",
            "playlist_id": "PLtest123",
            "video_count": 8,
            "url": "https://youtube.com/playlist?list=PLtest123",
        }
    ]


@pytest.mark.asyncio
async def test_get_playlist_items_uses_thumbnail_fallback():
    api_response = {
        "items": [
            {
                "snippet": {
                    "title": "Fallback Video",
                    "resourceId": {"videoId": "fallback123"},
                    "publishedAt": "2026-01-01T00:00:00Z",
                    "thumbnails": {
                        "default": {"url": "https://example.com/default.jpg"}
                    },
                }
            }
        ]
    }

    with patch("app.services.playlists.playlist.get_cache", new_callable=AsyncMock) as mock_get_cache, patch(
        "app.services.playlists.playlist.set_cache", new_callable=AsyncMock
    ) as mock_set_cache, patch("app.services.playlists.playlist._execute_youtube", new_callable=AsyncMock) as mock_execute:
        mock_get_cache.return_value = None
        mock_execute.return_value = api_response

        playlist_items = await get_playlist_items("PLfallback")

    assert playlist_items == [
        {
            "title": "Fallback Video",
            "url": "https://youtube.com/watch?v=fallback123",
            "video_id": "fallback123",
            "published": "2026-01-01T00:00:00Z",
            "thumbnail": "https://example.com/default.jpg",
        }
    ]
