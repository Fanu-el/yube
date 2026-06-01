"""Download utilities for YouTube video handling."""
import asyncio
import glob
import os
import shutil
import subprocess
import tempfile
from typing import List

from yt_dlp import YoutubeDL

MAX_TELEGRAM_VIDEO_BYTES = 45 * 1024 * 1024


def _format_file_size(size: int | None) -> str:
    if size is None:
        return "unknown size"
    for unit in ["B", "KB", "MB"]:
        if size < 1024 or unit == "MB":
            return f"{size / 1024**(["B", "KB", "MB"].index(unit)):.1f} {unit}"
    return f"{size / 1024**2:.1f} MB"


def _choose_download_formats(info: dict) -> List[dict]:
    candidates: dict[int, dict] = {}
    for fmt in info.get("formats", []):
        if fmt.get("vcodec") == "none" or fmt.get("acodec") == "none":
            continue

        height = fmt.get("height")
        if height is None or height > 720:
            continue

        ext = fmt.get("ext", "mp4")
        if ext != "mp4":
            continue

        filesize = fmt.get("filesize") or fmt.get("filesize_approx")
        label = f"{height}p"
        if fmt.get("fps"):
            label += f" {fmt['fps']}fps"
        if filesize is not None:
            label += f" • {_format_file_size(filesize)}"

        current = candidates.get(height)
        better = False
        if current is None:
            better = True
        elif fmt.get("tbr", 0) > current.get("tbr", 0):
            better = True
        elif current.get("ext") != "mp4" and ext == "mp4":
            better = True

        if better:
            candidates[height] = {
                "format_id": str(fmt["format_id"]),
                "label": label,
                "filesize": filesize,
                "height": height,
                "ext": ext,
                "tbr": fmt.get("tbr", 0),
            }

    return sorted(candidates.values(), key=lambda item: item["height"], reverse=True)


def _extract_video_info(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


async def get_download_formats(url: str) -> List[dict]:
    info = await asyncio.to_thread(_extract_video_info, url)
    return _choose_download_formats(info)


def _download_video_sync(url: str, format_id: str) -> str:
    temp_dir = tempfile.mkdtemp(prefix="yube_download_")
    outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
    ydl_opts = {
        "format": format_id,
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    filename = ydl.prepare_filename(info)
    if not os.path.exists(filename):
        raise FileNotFoundError("Downloaded file not found")
    return filename


def _split_video_file_sync(input_path: str) -> List[str]:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to split large video files")

    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        raise FileNotFoundError("Input video file does not exist for splitting")

    base_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_pattern = os.path.join(base_dir, f"{base_name}_part%03d.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-c",
        "copy",
        "-segment_time",
        "600",
        "-f",
        "segment",
        "-reset_timestamps",
        "1",
        output_pattern,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    parts = sorted(glob.glob(os.path.join(base_dir, f"{base_name}_part*.mp4")))
    if not parts:
        raise RuntimeError("ffmpeg split did not produce any video parts")
    return parts


async def split_video_file(input_path: str) -> List[str]:
    return await asyncio.to_thread(_split_video_file_sync, input_path)


async def download_video_file(url: str, format_id: str) -> str:
    return await asyncio.to_thread(_download_video_sync, url, format_id)
