import pytest

from app.utils.downloads import get_download_formats, split_video_file


@pytest.mark.asyncio
async def test_get_download_formats_filters_mp4_and_height(monkeypatch):
    fake_info = {
        "formats": [
            {
                "format_id": "18",
                "height": 360,
                "ext": "mp4",
                "filesize": 20 * 1024 * 1024,
                "tbr": 300,
                "vcodec": "avc1.4d401f",
                "acodec": "mp4a.40.2",
            },
            {
                "format_id": "22",
                "height": 720,
                "ext": "mp4",
                "filesize": 40 * 1024 * 1024,
                "tbr": 2000,
                "vcodec": "avc1.64001f",
                "acodec": "mp4a.40.2",
            },
            {
                "format_id": "299",
                "height": 1080,
                "ext": "mp4",
                "filesize": 80 * 1024 * 1024,
                "tbr": 5000,
                "vcodec": "avc1.640028",
                "acodec": "mp4a.40.2",
            },
            {
                "format_id": "133",
                "height": 240,
                "ext": "mp4",
                "filesize": 10 * 1024 * 1024,
                "tbr": 100,
                "vcodec": "avc1.4d4015",
                "acodec": "mp4a.40.2",
            },
            {
                "format_id": "140",
                "height": 0,
                "ext": "mp4",
                "filesize": 5 * 1024 * 1024,
                "tbr": 50,
                "vcodec": "none",
                "acodec": "mp4a.40.2",
            },
        ]
    }

    monkeypatch.setattr("app.utils.downloads._extract_video_info", lambda url: fake_info)
    formats = await get_download_formats("https://youtube.com/watch?v=test")

    assert len(formats) == 3
    assert formats[0]["format_id"] == "22"
    assert formats[1]["format_id"] == "18"
    assert formats[2]["format_id"] == "133"


@pytest.mark.asyncio
async def test_split_video_file_requires_ffmpeg(monkeypatch, tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_text("dummy")

    monkeypatch.setattr("app.utils.downloads.shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="ffmpeg is required to split large video files"):
        await split_video_file(str(video_path))


@pytest.mark.asyncio
async def test_split_video_file_returns_parts(monkeypatch, tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_text("dummy")
    part_path = tmp_path / "video_part000.mp4"
    part_path.write_text("dummy")

    monkeypatch.setattr("app.utils.downloads.shutil.which", lambda name: str(tmp_path / "ffmpeg"))
    monkeypatch.setattr("app.utils.downloads.subprocess.run", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.utils.downloads.glob.glob", lambda pattern: [str(part_path)])

    parts = await split_video_file(str(video_path))

    assert parts == [str(part_path)]
