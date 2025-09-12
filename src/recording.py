from __future__ import annotations
from pathlib import Path
from typing import Optional

from src.media import ensure_ffmpeg, spawn_record_process
from src.utils import sanitize_filename, timestamp


def start_record(app) -> None:
    try:
        ensure_ffmpeg()
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror("ffmpeg missing", str(e))
        return
    sid = app._get_selected_id()
    if not sid:
        return
    sess = app.sessions.get(sid)
    if not sess:
        return

    def work():
        stream_url = None
        
        # Try to use existing resolved_url first if available
        if sess.resolved_url:
            stream_url = sess.resolved_url
            app.log_write(f"Using cached stream URL for {app._extract_model_name(sess.page_url) or 'stream'}")
            
            # Try to start recording with cached URL
            input_headers = {"Referer": sess.page_url, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
            out_dir = Path(app.output_folder_var.get().strip()) if app.output_folder_var.get().strip() else (Path.home() / "Downloads")
            
            # Create model-specific subfolder
            model = app._extract_model_name(sess.page_url) or "stream"
            safe_model = sanitize_filename(model)
            model_dir = out_dir / safe_model
            try:
                model_dir.mkdir(parents=True, exist_ok=True)
                app.log_write(f"Created/verified model directory: {model_dir}")
            except Exception as e:
                app.log_write(f"Warning: Could not create model directory {model_dir}: {e}")
                model_dir = out_dir  # Fall back to main directory
            
            safe = sanitize_filename(model)
            fname = f"{safe}_{timestamp()}.{app.container_var.get()}"
            out_path = model_dir / fname
            
            try:
                # Try to start recording with cached URL
                test_proc = spawn_record_process(
                    stream_url,
                    out_path,
                    duration=None,
                    audio_volume=None,
                    input_headers=input_headers,
                )
                
                # If process started successfully, use it
                if test_proc and getattr(test_proc, 'pid', None) is not None:
                    sess.rec_proc = test_proc
                    app.log_write(f"Successfully started recording with cached URL")
                    
                    try:
                        if hasattr(app, "_proc_watch") and app._proc_watch:
                            app._proc_watch.add(int(sess.rec_proc.pid))
                    except Exception:
                        pass
                    app.with_thread(pipe_ffmpeg_stderr, app, sess)
                    sess.status = "Recording"
                    start_session_timer(app, sid)
                    app._update_tree_item(sid, "Recording")
                    app.status_var.set("Recording")
                    app.log_write(f"Recording to: {out_path}")
                    app._update_record_button()
                    
                    # Notify session-specific windows
                    if hasattr(app, '_notify_session_windows'):
                        app._notify_session_windows(sid)
                    
                    # Add to stream monitor for automatic reconnection
                    if hasattr(app, 'stream_monitor'):
                        app.stream_monitor.add_session(sid)
                        
                    wait_record_end_session(app, sid, out_path)
                    return
                else:
                    app.log_write("Cached URL failed to start recording, resolving new URL...")
                    stream_url = None
                    
            except Exception as e:
                app.log_write(f"Cached URL failed: {e}, resolving new URL...")
                stream_url = None
        
        # If no cached URL or cached URL failed, resolve new one
        if not stream_url:
            app.log_write(f"Resolving stream URL for {app._extract_model_name(sess.page_url) or 'stream'}...")
            stream_url = app._resolve(sess.page_url)
            if stream_url:
                sess.resolved_url = stream_url
                sess.status = "Live"
        
        if not stream_url:
            app.log_write("No stream URL available for recording")
            return
        # Start recording with newly resolved URL
        input_headers = {"Referer": sess.page_url, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
        out_dir = Path(app.output_folder_var.get().strip()) if app.output_folder_var.get().strip() else (Path.home() / "Downloads")
        
        # Create model-specific subfolder
        model = app._extract_model_name(sess.page_url) or "stream"
        safe_model = sanitize_filename(model)
        model_dir = out_dir / safe_model
        try:
            model_dir.mkdir(parents=True, exist_ok=True)
            app.log_write(f"Created/verified model directory: {model_dir}")
        except Exception as e:
            app.log_write(f"Warning: Could not create model directory {model_dir}: {e}")
            model_dir = out_dir  # Fall back to main directory
        
        safe = sanitize_filename(model)
        fname = f"{safe}_{timestamp()}.{app.container_var.get()}"
        out_path = model_dir / fname
        app.status_var.set("Recording")
        app.log_write(f"Recording to: {out_path}")
        try:
            sess.rec_proc = spawn_record_process(
                stream_url,
                out_path,
                duration=None,
                audio_volume=None,
                input_headers=input_headers,
            )
            try:
                if sess.rec_proc and getattr(sess.rec_proc, 'pid', None) is not None:
                    if hasattr(app, "_proc_watch") and app._proc_watch:
                        app._proc_watch.add(int(sess.rec_proc.pid))
            except Exception:
                pass
            app.with_thread(pipe_ffmpeg_stderr, app, sess)
            sess.status = "Recording"
            start_session_timer(app, sid)
            app._update_tree_item(sid, "Recording")
            
            # Notify session-specific windows
            if hasattr(app, '_notify_session_windows'):
                app._notify_session_windows(sid)
            
            # Add to stream monitor for automatic reconnection
            if hasattr(app, 'stream_monitor'):
                app.stream_monitor.add_session(sid)
        except Exception as e:
            app.status_var.set("Recording failed to start")
            app.log_write(f"[ERROR] Could not start ffmpeg: {e}")
            return
        app._update_record_button()
        wait_record_end_session(app, sid, out_path)

    app.with_thread(work)


def pipe_ffmpeg_stderr(app, sess) -> None:
    try:
        if not sess or not sess.rec_proc or not sess.rec_proc.stderr:
            return
        for raw in iter(lambda: sess.rec_proc.stderr.readline(), b""):
            try:
                line = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                line = str(raw)
            if not line:
                continue
            noisy = (
                "Will reconnect at",
                "HTTP error 404 Not Found",
                "Failed to open segment",
                "expired from playlists",
                "No trailing CRLF found in HTTP header",
            )
            if any(t in line for t in noisy):
                continue
            app.log_write(f"ffmpeg: {line}")
    except Exception:
        pass


def wait_record_end_session(app, sid: str, out_path: Path) -> None:
    def poll():
        sess = app.sessions.get(sid)
        if not sess:
            return
        if sess.rec_proc is None:
            return
        ret = sess.rec_proc.poll()
        if ret is None:
            app.after(500, poll)
            return
        try:
            if sess.rec_proc.stderr:
                rest = sess.rec_proc.stderr.read() or b""
                if rest:
                    try:
                        app.log_write(rest.decode("utf-8", errors="replace"))
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            if getattr(app, "_proc_watch", None) is not None and getattr(sess.rec_proc, 'pid', None) is not None:
                app._proc_watch.discard(int(sess.rec_proc.pid))
        except Exception:
            pass
        sess.elapsed_running = False
        sess.rec_proc = None
        sess.status = "Idle"
        app._update_tree_item(sid, "Idle")
        app._update_record_button()
        
        # Notify session-specific windows about stop
        if hasattr(app, '_notify_session_windows'):
            app._notify_session_windows(sid)
        
        # Remove from stream monitor
        if hasattr(app, 'stream_monitor'):
            app.stream_monitor.remove_session(sid)
        if ret == 0:
            try:
                size = out_path.stat().st_size
            except Exception:
                size = 0
            if size <= 0:
                app.status_var.set("Recording finished, but file is empty (0 KB)")
                app.log_write("[ERROR] Output file is 0 KB. See ffmpeg logs above for details.")
            else:
                app.status_var.set("Recording finished")
                app.log_write(f"Done: {out_path} ({size/1024:.0f} KB)")
        else:
            app.status_var.set(f"Recording stopped (code {ret})")
            app.log_write(f"[INFO] ffmpeg exited with code {ret}")

    app.after(500, poll)


def stop_record(app) -> None:
    sid = app._get_selected_id()
    if not sid:
        return
    sess = app.sessions.get(sid)
    if not sess or not sess.rec_proc:
        return
    app.status_var.set("Stopping recording...")
    try:
        if sess.rec_proc.stdin:
            sess.rec_proc.stdin.write(b"q\n")  # Added newline
            sess.rec_proc.stdin.flush()
            app.log_write(f"Sent graceful stop command to recording: {sess.page_url}")
    except Exception:
        app.log_write(f"Could not send graceful stop, terminating: {sess.page_url}")
        try:
            sess.rec_proc.terminate()
        except Exception:
            pass
    sess.elapsed_running = False
    
    # Notify session-specific windows about manual stop
    if hasattr(app, '_notify_session_windows'):
        app._notify_session_windows(sid)
    
    # Remove from stream monitor when manually stopped
    if hasattr(app, 'stream_monitor'):
        app.stream_monitor.remove_session(sid)


def start_session_timer(app, sid: str) -> None:
    sess = app.sessions.get(sid)
    if not sess:
        return
    sess.elapsed_seconds = 0
    sess.elapsed_running = True

    def tick():
        if not sess.elapsed_running:
            return
        sess.elapsed_seconds += 1
        app._update_tree_item(sid, "Recording")
        app.after(1000, tick)

    app.after(1000, tick)

