from __future__ import annotations

import threading
import time
from typing import Optional, Callable, Set
from dataclasses import dataclass

from src.autorecord.checker import check_session_status


@dataclass
class AutoRecordConfig:
    """Configuration for autorecord functionality"""
    enabled: bool = False
    check_interval: int = 60  # seconds
    retry_count: int = 3
    retry_delay: int = 30  # seconds between retries


class AutoRecordManager:
    """Manages automatic recording for streams"""
    
    def __init__(self, app, log_callback: Optional[Callable[[str], None]] = None):
        self.app = app
        self.log = log_callback or (lambda msg: None)
        self.config = AutoRecordConfig()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._monitored_sessions: Set[str] = set()
        self._recording_sessions: Set[str] = set()
        self._failed_sessions: dict[str, int] = {}  # session_id -> retry_count
        
    def start(self):
        """Start the autorecord monitoring"""
        if self._running:
            self.log("AutoRecord is already running")
            return
            
        self.config.enabled = True
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.log("AutoRecord started - checking streams every 60 seconds")
        
    def stop(self):
        """Stop the autorecord monitoring"""
        if not self._running:
            self.log("AutoRecord is not running")
            return
            
        self.config.enabled = False
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self.log("AutoRecord stopped")
        
    def is_running(self) -> bool:
        """Check if autorecord is currently running"""
        return self._running and self.config.enabled
        
    def add_session(self, session_id: str):
        """Add a session to be monitored for autorecording"""
        if session_id not in self._monitored_sessions:
            self._monitored_sessions.add(session_id)
            # Reset failed count when re-adding
            if session_id in self._failed_sessions:
                del self._failed_sessions[session_id]
            
            sess = self.app.sessions.get(session_id)
            if sess:
                model_name = self.app._extract_model_name(sess.page_url) or "Unknown"
                self.log(f"Added {model_name} to AutoRecord monitoring")
                # Save changes to persistence
                self.app._save_urls()
        
    def remove_session(self, session_id: str):
        """Remove a session from autorecord monitoring"""
        if session_id in self._monitored_sessions:
            self._monitored_sessions.discard(session_id)
            if session_id in self._failed_sessions:
                del self._failed_sessions[session_id]
            
            sess = self.app.sessions.get(session_id)
            if sess:
                model_name = self.app._extract_model_name(sess.page_url) or "Unknown"
                self.log(f"Removed {model_name} from AutoRecord monitoring")
                # Save changes to persistence
                self.app._save_urls()
                
    def toggle_session(self, session_id: str):
        """Toggle a session's autorecord monitoring"""
        if session_id in self._monitored_sessions:
            self.remove_session(session_id)
        else:
            self.add_session(session_id)
            
    def is_session_monitored(self, session_id: str) -> bool:
        """Check if a session is being monitored"""
        return session_id in self._monitored_sessions
        
    def get_monitored_count(self) -> int:
        """Get the number of monitored sessions"""
        return len(self._monitored_sessions)
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running and self.config.enabled:
            try:
                self._check_monitored_sessions()
            except Exception as e:
                self.log(f"AutoRecord monitor error: {e}")
                
            # Wait for the check interval, but check _running every second
            for _ in range(self.config.check_interval):
                if not self._running or not self.config.enabled:
                    break
                time.sleep(1)
                
    def _check_monitored_sessions(self):
        """Check all monitored sessions for stream availability"""
        if not self._monitored_sessions:
            return
            
        self.log(f"AutoRecord: Checking {len(self._monitored_sessions)} monitored streams...")
        
        for session_id in list(self._monitored_sessions):  # Copy to avoid modification during iteration
            if not self._running or not self.config.enabled:
                break
                
            try:
                self._check_single_session(session_id)
            except Exception as e:
                self.log(f"AutoRecord: Error checking session {session_id}: {e}")
                
    def _check_single_session(self, session_id: str):
        """Check a single session and start recording if stream is live"""
        sess = self.app.sessions.get(session_id)
        if not sess:
            # Session was removed, clean up
            self._monitored_sessions.discard(session_id)
            return
            
        model_name = self.app._extract_model_name(sess.page_url) or "Unknown"
        
        # Skip if already recording
        if self._is_session_recording(session_id):
            return
            
        # Check if we've exceeded retry limit
        if session_id in self._failed_sessions:
            if self._failed_sessions[session_id] >= self.config.retry_count:
                self.log(f"AutoRecord: {model_name} exceeded retry limit, will retry later...")
                # Don't remove from monitoring, just skip this round and reset failed count
                # This allows the user to keep AutoRecord enabled but gives the stream a break
                self._failed_sessions[session_id] = 0  # Reset counter to try again later
                return
        
        try:
            # Check stream status
            resolved_url, status = check_session_status(sess.page_url, log=self.log)
            
            if status == "Live" and resolved_url:
                # Stream is live, start recording
                self.log(f"AutoRecord: {model_name} stream is live, starting recording...")
                
                # Update session with resolved URL
                sess.resolved_url = resolved_url
                sess.status = status
                
                # Update UI
                self.app.after(0, lambda: self.app._update_tree_item(session_id, status))
                
                # Start recording
                self.app.after(0, lambda: self._start_recording_for_session(session_id))
                
                # Reset failed count on successful detection
                if session_id in self._failed_sessions:
                    del self._failed_sessions[session_id]
                    
            else:
                # Stream not available
                self.log(f"AutoRecord: {model_name} stream not available")
                
                # Increment failed count
                self._failed_sessions[session_id] = self._failed_sessions.get(session_id, 0) + 1
                
        except Exception as e:
            self.log(f"AutoRecord: Error checking {model_name}: {e}")
            # Increment failed count on error
            self._failed_sessions[session_id] = self._failed_sessions.get(session_id, 0) + 1
            
    def _is_session_recording(self, session_id: str) -> bool:
        """Check if a session is currently recording"""
        sess = self.app.sessions.get(session_id)
        if not sess:
            return False
            
        return (hasattr(sess, 'rec_proc') and 
                sess.rec_proc and 
                sess.rec_proc.poll() is None)
                
    def _start_recording_for_session(self, session_id: str):
        """Start recording for a session (called from main thread)"""
        try:
            # Use the existing app method to start recording
            self.app._start_recording_for_session(session_id)
            self._recording_sessions.add(session_id)
            
            sess = self.app.sessions.get(session_id)
            if sess:
                model_name = self.app._extract_model_name(sess.page_url) or "Unknown"
                self.log(f"AutoRecord: Successfully started recording for {model_name}")
                
        except Exception as e:
            self.log(f"AutoRecord: Failed to start recording for session {session_id}: {e}")
            
    def get_status_info(self) -> dict:
        """Get current status information for display"""
        return {
            'enabled': self.config.enabled,
            'running': self._running,
            'monitored_count': len(self._monitored_sessions),
            'recording_count': len([sid for sid in self._monitored_sessions if self._is_session_recording(sid)]),
            'failed_count': len(self._failed_sessions)
        }
