import pytest

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
