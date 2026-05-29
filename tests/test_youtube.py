import pytest
from unittest.mock import AsyncMock, patch

from app.services.youtube import _get_thumbnail_url


@pytest.mark.parametrize(
    "thumbnails, expected_url",
    [
        ({"medium": {"url": "https://example.com/medium.jpg"}}, "https://example.com/medium.jpg"),
        ({"high": {"url": "https://example.com/high.jpg"}}, "https://example.com/high.jpg"),
        ({"default": {"url": "https://example.com/default.jpg"}}, "https://example.com/default.jpg"),
        ({"sd": {"url": "https://example.com/sd.jpg"}}, "https://example.com/sd.jpg"),
        ({}, ""),
    ],
)
def test_get_thumbnail_url_fallback(thumbnails, expected_url):
    assert _get_thumbnail_url(thumbnails) == expected_url


@pytest.mark.asyncio
async def test_get_playlist_items_uses_thumbnail_fallback():
    from app.services.youtube import get_playlist_items

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

    with patch("app.services.youtube.get_cache", new_callable=AsyncMock) as mock_get_cache, patch(
        "app.services.youtube.set_cache", new_callable=AsyncMock
    ) as mock_set_cache, patch(
        "app.services.youtube._execute_youtube", new_callable=AsyncMock
    ) as mock_execute:
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
