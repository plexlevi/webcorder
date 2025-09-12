from __future__ import annotations
from pathlib import Path
from typing import Optional, Sequence, Dict

from src.utils import ensure_dir, sanitize_filename, timestamp
from .ffmpeg import ensure_ffmpeg, run_ffprobe as _run_ffprobe, spawn_record_process as _spawn_record_process


def build_output_path(out: Optional[str], page_url: str, container: str = "mp4") -> Path:
    if out:
        p = Path(out)
        ensure_dir(p.parent)
        return p
    safe = sanitize_filename(page_url.split("/")[-1] or "stream")
    return ensure_dir(Path("recordings")).joinpath(f"{safe}_{timestamp()}.{container}")


def run_ffprobe(stream_url: str):
    return _run_ffprobe(stream_url)


def record_stream(
    stream_url: str,
    output: Path,
    duration: Optional[str] = None,
    extra_ffmpeg_args: Optional[Sequence[str]] = None,
    audio_volume: Optional[float] = None,
) -> int:
    proc = _spawn_record_process(
        stream_url=stream_url,
        output_path=str(output),
        duration=duration,
        extra_ffmpeg_args=extra_ffmpeg_args,
        audio_volume=audio_volume,
        input_headers=None,
    )
    return proc.wait()


def spawn_record_process(
    stream_url: str,
    output: Path,
    duration: Optional[str] = None,
    extra_ffmpeg_args: Optional[Sequence[str]] = None,
    audio_volume: Optional[float] = None,
    input_headers: Optional[Dict[str, str]] = None,
):
    return _spawn_record_process(
        stream_url=stream_url,
        output_path=str(output),
        duration=duration,
        extra_ffmpeg_args=extra_ffmpeg_args,
        audio_volume=audio_volume,
        input_headers=input_headers,
    )
