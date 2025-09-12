from __future__ import annotations
import os
import subprocess
import sys
from typing import Optional, Sequence, Dict
from urllib.parse import urlparse

from src.utils import which

# Windows constants for subprocess creation flags
if sys.platform.startswith("win"):
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


class FFmpegNotFound(Exception):
    pass


def ensure_ffmpeg() -> None:
    # Only require ffmpeg for recording, not ffprobe or ffplay
    names = ("ffmpeg",)
    if sys.platform.startswith("win"):
        names = tuple(n + ".exe" for n in names)
    for exe in names:
        if which(exe) is None:
            raise FFmpegNotFound(f"Missing {exe} in PATH or packaged resources. Bundle ffmpeg or install it.")
    try:
        if sys.platform.startswith("win"):
            subprocess.run(
                ["ffmpeg", "-version"], 
                capture_output=True, 
                check=True,
                creationflags=CREATE_NO_WINDOW
            )
        else:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except Exception:
        raise FFmpegNotFound(
            "ffmpeg found but failed to run. On Windows, ensure required DLLs are next to ffmpeg.exe."
        )


def ensure_ffplay() -> None:
    """Ensure ffplay is available and runnable."""
    exe = "ffplay.exe" if sys.platform.startswith("win") else "ffplay"
    if which(exe) is None:
        raise FFmpegNotFound("Missing ffplay in PATH or packaged resources. Bundle ffmpeg/ffplay or install it.")
    try:
        if sys.platform.startswith("win"):
            subprocess.run(
                [exe, "-version"], 
                capture_output=True, 
                check=True,
                creationflags=CREATE_NO_WINDOW
            )
        else:
            subprocess.run([exe, "-version"], capture_output=True, check=True)
    except Exception:
        raise FFmpegNotFound(
            "ffplay found but failed to run. On Windows, ensure required DLLs are next to ffplay.exe."
        )


def run_ffprobe(
    stream_url: str,
    *,
    input_headers: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
) -> subprocess.CompletedProcess:
    ensure_ffmpeg()
    args: list[str] = ["ffprobe", "-hide_banner", "-v", "error", "-show_streams", "-show_format"]
    if user_agent:
        args.extend(["-user_agent", user_agent])
    if input_headers:
        hdr = "\r\n".join(f"{k}: {v}" for k, v in input_headers.items())
        args.extend(["-headers", hdr])
    args.append(stream_url)
    
    if sys.platform.startswith("win"):
        return subprocess.run(args, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    else:
        return subprocess.run(args, capture_output=True, text=True)


def spawn_record_process(
    stream_url: str,
    output_path: str,
    duration: Optional[str] = None,
    extra_ffmpeg_args: Optional[Sequence[str]] = None,
    audio_volume: Optional[float] = None,
    input_headers: Optional[Dict[str, str]] = None,
) -> subprocess.Popen:
    ensure_ffmpeg()
    is_mp4 = str(output_path).lower().endswith(".mp4")
    input_args: list[str] = []
    scheme = urlparse(stream_url).scheme.lower() if "://" in stream_url else ""
    if scheme in ("http", "https"):
        input_args.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_delay_max", "30",
            "-rw_timeout", str(60 * 1000000),
        ])
        if input_headers:
            hdr = "\r\n".join(f"{k}: {v}" for k, v in input_headers.items())
            input_args.extend(["-headers", hdr])
    cmd: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-fflags",
        "+genpts",
        "-avoid_negative_ts", "make_zero",
        "-async", "1",
        "-y",
        *input_args,
        "-i",
        stream_url,
    ]
    if ".m3u8" in stream_url:
        cmd.extend([
            "-analyzeduration", "10M",
            "-probesize", "10M",
            "-max_reload", "1000",
            "-hls_time", "10",
            "-hls_list_size", "0",
        ])
    if duration:
        cmd.extend(["-t", str(duration)])
    if extra_ffmpeg_args:
        cmd.extend(list(extra_ffmpeg_args))
    if audio_volume is not None and abs(audio_volume - 1.0) > 1e-3:
        vol = max(0.0, float(audio_volume))
        cmd.extend(["-af", f"volume={vol}"])
    cmd.extend(["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "copy", "-copyts"])
    if audio_volume is not None and abs(audio_volume - 1.0) > 1e-3:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.extend(["-c:a", "copy"])
    if is_mp4:
        cmd.extend([
            "-tag:v", "avc1", 
            "-tag:a", "mp4a", 
            "-bsf:a", "aac_adtstoasc", 
            "-movflags", "+faststart+frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration", "1000000",
            "-min_frag_duration", "1000000"
        ])
    else:
        cmd.extend(["-tag:v", "0", "-tag:a", "0"])
    cmd.append(str(output_path))
    
    # Windows-specifikus beállítások a konzol ablak elrejtéséhez
    if sys.platform.startswith("win"):
        return subprocess.Popen(
            cmd, 
            stdin=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW
        )
    else:
        return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)


def spawn_ffplay(
    stream_url: str,
    *,
    hwnd: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    volume: Optional[int] = None,
    input_headers: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
    low_latency: bool = True,
) -> subprocess.Popen:
    """Start ffplay for preview purposes, optionally embedding into an existing window via SDL.

    On Windows, if hwnd is provided, we set SDL_WINDOWID so the video is rendered inside that control.
    """
    ensure_ffplay()
    input_args: list[str] = []
    if stream_url.startswith("http"):
        input_args.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_delay_max", "30",
            "-rw_timeout", str(60 * 1000000),
        ])
        if input_headers:
            hdr = "\r\n".join(f"{k}: {v}" for k, v in input_headers.items())
            input_args.extend(["-headers", hdr])
        if user_agent:
            input_args.extend(["-user_agent", user_agent])

    cmd: list[str] = [
        "ffplay",
        "-hide_banner",
        "-loglevel", "error",
        "-nostats",
        "-autoexit",
        *input_args,
    ]

    if low_latency:
        cmd.extend(["-fflags", "nobuffer", "-flags", "low_delay", "-probesize", "32k", "-analyzeduration", "0"])

    if volume is not None:
        v = max(0, min(100, int(volume)))
        cmd.extend(["-volume", str(v)])

    if width and height:
        cmd.extend(["-x", str(int(width)), "-y", str(int(height))])

    cmd.extend(["-i", stream_url])

    env = os.environ.copy()
    if hwnd:
        # Embed into an existing window (works with SDL2 on Windows)
        env["SDL_WINDOWID"] = str(int(hwnd))
        # Force windowed mode, not fullscreen
        env["SDL_VIDEODRIVER"] = "windows"
        env["SDL_VIDEO_WINDOW_POS"] = "0,0"
        env["SDL_VIDEO_CENTERED"] = "0"
        # Disable fullscreen by default
        cmd.extend(["-fs", "0"])
    
    # Windows-specifikus beállítások a konzol ablak elrejtéséhez
    if sys.platform.startswith("win"):
        return subprocess.Popen(
            cmd, 
            env=env, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
    else:
        return subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
