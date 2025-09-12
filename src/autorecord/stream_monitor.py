"""
Folyamatos stream monitorozás és újraindítás
Figyeli az aktív felvételeket és újraindítja őket, ha a stream megszakad
"""
from __future__ import annotations
import time
import threading
from typing import Dict, Set, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import App


class StreamMonitor:
    """Folyamatosan figyeli az aktív streameket és újraindítja őket, ha megszakadnak"""
    
    def __init__(self, app: App):
        self.app = app
        self.monitored_sessions: Set[str] = set()  # Session ID-k tárolása
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.check_interval = 15  # másodpercenként ellenőriz
        
    def start_monitoring(self):
        """Elindítja a monitorozást"""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Leállítja a monitorozást"""
        self.running = False
        self.monitored_sessions.clear()
        
    def add_session(self, session_id: str):
        """Hozzáad egy session-t a monitorozáshoz"""
        self.monitored_sessions.add(session_id)
        if not self.running:
            self.start_monitoring()
            
    def remove_session(self, session_id: str):
        """Eltávolít egy session-t a monitorozásból"""
        self.monitored_sessions.discard(session_id)
        
    def _monitor_loop(self):
        """A monitorozási ciklus"""
        while self.running:
            try:
                # Másolat készítése a set-ről, hogy ne változzon iterálás közben
                sessions_to_check = self.monitored_sessions.copy()
                
                for session_id in sessions_to_check:
                    if not self.running:
                        break
                        
                    # Ellenőrzi, hogy fut-e még a felvétel
                    if not self._is_recording_active(session_id):
                        # Ha nem fut, akkor eltávolítja a listából
                        self.monitored_sessions.discard(session_id)
                        continue
                        
                    # Ellenőrzi, hogy a stream még elérhető-e
                    if not self._check_stream_alive(session_id):
                        self._restart_recording(session_id)
                        
                time.sleep(self.check_interval)
                
            except Exception as e:
                # Hibakezelés - ne álljon le a monitorozás
                print(f"Stream monitor error: {e}")
                time.sleep(self.check_interval)
                
    def _is_recording_active(self, session_id: str) -> bool:
        """Ellenőrzi, hogy a session-höz tartozó felvétel még aktív-e"""
        try:
            sess = self.app.sessions.get(session_id)
            if not sess:
                return False
            
            # Ellenőrzi, hogy van-e aktív felvételi process
            return (hasattr(sess, 'rec_proc') and 
                    sess.rec_proc and 
                    sess.rec_proc.poll() is None)
        except:
            return False
            
    def _check_stream_alive(self, session_id: str) -> bool:
        """Ellenőrzi, hogy a stream még elérhető-e"""
        try:
            sess = self.app.sessions.get(session_id)
            if not sess or not sess.resolved_url:
                return True  # Ha nincs resolved URL, akkor nem tudunk ellenőrizni
                
            # Gyors ping-szerű ellenőrzés a stream URL-re
            try:
                import requests
                from urllib.parse import urlparse
                
                parsed = urlparse(sess.resolved_url)
                if not parsed.netloc:
                    return True  # Ha nem HTTP URL, akkor ne ellenőrizzük
                    
                # Gyors HEAD request
                response = requests.head(sess.resolved_url, timeout=5)
                return response.status_code < 400
            except ImportError:
                # Ha nincs requests, akkor ne ellenőrizzük a stream státuszt
                return True
                
        except Exception:
            # Ha bármilyen hiba van, akkor ne állítsuk le a felvételt
            return True
            
    def _restart_recording(self, session_id: str):
        """Újraindítja a felvételt az adott session-re"""
        try:
            sess = self.app.sessions.get(session_id)
            if not sess:
                return
                
            # UI thread-ben kell futtatni
            self.app.after(0, self._restart_in_ui_thread, session_id)
            
        except Exception as e:
            print(f"Failed to restart recording for session {session_id}: {e}")
            
    def _restart_in_ui_thread(self, session_id: str):
        """UI thread-ben újraindítja a felvételt"""
        try:
            sess = self.app.sessions.get(session_id)
            if not sess:
                return
                
            # Megállítja a jelenlegi felvételt
            if sess.rec_proc:
                try:
                    if sess.rec_proc.stdin:
                        sess.rec_proc.stdin.write(b"q\n")
                        sess.rec_proc.stdin.flush()
                    sess.rec_proc.terminate()
                except:
                    pass
                sess.rec_proc = None
                sess.elapsed_running = False
            
            model_name = self.app._extract_model_name(sess.page_url) or "stream"
            self.app.log_write(f"Stream disconnected, restarting: {model_name}")
            
            # Rövid várakozás után újraindítja
            def restart_after_delay():
                try:
                    from src.recording import start_record
                    
                    # Beállítja a kiválasztott session-t
                    for item in self.app.tree.get_children():
                        if self.app.tree.item(item)["values"] and \
                           self.app.tree.item(item)["values"][0] == session_id:
                            self.app.tree.selection_set(item)
                            break
                    
                    # Újraindítja a felvételt
                    start_record(self.app)
                    
                    model_name = self.app._extract_model_name(sess.page_url) or "stream"
                    self.app.log_write(f"Stream recording restarted: {model_name}")
                    
                except Exception as e:
                    model_name = self.app._extract_model_name(sess.page_url) or "stream"
                    self.app.log_write(f"Failed to restart stream {model_name}: {e}")
                    
            # 5 másodperc múlva újraindítja
            self.app.after(5000, restart_after_delay)
            
        except Exception as e:
            self.app.log_write(f"Error in stream restart: {e}")
