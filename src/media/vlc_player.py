"""VLC-based video player with simplified functionality"""
from __future__ import annotations
import os
import tkinter as tk
from typing import Optional, Any
import time
import random

try:
    import vlc  # type: ignore
    VLC_AVAILABLE = True
except ImportError:
    vlc = None  # type: ignore
    VLC_AVAILABLE = False


class VLCVideoPlayer:
    """VLC-based video player that renders to a Tkinter canvas with independent volume control"""
    
    def __init__(self, canvas: tk.Canvas):
        if not VLC_AVAILABLE:
            raise ImportError("python-vlc not available")
            
        self.canvas = canvas
        self.instance: Optional[Any] = None
        self.player: Optional[Any] = None
        self.current_url: Optional[str] = None
        self._volume: int = 50  # Saját hangerő állapot tárolása
        self._is_muted: bool = False  # Mute állapot tárolása
        self._volume_before_mute: int = 50  # Hangerő mute előtt
        self._player_id: int = int(time.time() * 1000000) + random.randint(1000, 9999)  # Egyedi ID
        self._software_volume: float = 0.5  # Software volume multiplier (0.0-1.0)
        self._init_vlc()
        
    def _init_vlc(self):
        """Initialize VLC with player-specific configuration"""
        try:
            if not VLC_AVAILABLE or vlc is None:
                raise ImportError("VLC not available")
                
            # Player-specifikus VLC options - KRITIKUS: directsound külön audio device-okhoz
            vlc_options = [
                '--intf', 'dummy',
                '--no-video-title-show',
                '--no-osd',
                '--quiet',
                '--network-caching=1000',
                '--live-caching=1000',
                '--file-caching=1000',
                '--clock-jitter=0',
                '--clock-synchro=0',
                '--drop-late-frames',
                '--skip-frames',
                '--no-spu',
                '--no-snapshot-preview',
                '--mouse-events',
                '--verbose=0',
                # MEGOLDÁS: külön audio output device minden instance-nek
                '--aout=directsound',  # Windows DirectSound - különálló audio stream
            ]
            
            # Minden player teljesen saját VLC instance-t kap saját audio outputtal
            self.instance = vlc.Instance(vlc_options)
            if self.instance is not None:
                self.player = self.instance.media_player_new()
            
            print(f"VLC Player #{self._player_id} initialized successfully with DirectSound")
            
            # Set up video output for canvas embedding
            if hasattr(self.canvas, 'winfo_id') and self.player is not None:
                try:
                    # Windows embedding
                    hwnd = self.canvas.winfo_id()
                    self.player.set_hwnd(hwnd)
                    print(f"VLC Player #{self._player_id} embedded in canvas with HWND: {hwnd}")
                except Exception:
                    try:
                        # Linux/Mac fallback
                        self.player.set_xwindow(self.canvas.winfo_id())
                        print(f"VLC Player #{self._player_id} embedded using XWindow")
                    except Exception as e:
                        print(f"Failed to embed VLC Player #{self._player_id}: {e}")
                    
        except Exception as e:
            print(f"VLC Player #{self._player_id} initialization error: {e}")

    def load_url(self, url: str) -> bool:
        """Load a media URL"""
        try:
            if not self.instance or not self.player:
                print(f"VLC not initialized when trying to load: {url}")
                return False
                
            print(f"🎬 VLC loading URL: {url}")
            print(f"🎬 URL length: {len(url)} characters")
            
            media = self.instance.media_new(url)
            if not media:
                print(f"🎬 VLC failed to create media object for: {url}")
                return False
                
            self.player.set_media(media)
            self.current_url = url
            print(f"🎬 VLC successfully loaded URL")
            return True
        except Exception as e:
            print(f"Failed to load URL {url}: {e}")
            return False

    def play(self) -> bool:
        """Start playback"""
        try:
            if not self.player:
                return False
            result = self.player.play()
            return result == 0  # VLC returns 0 on success
        except Exception as e:
            print(f"Failed to play: {e}")
            return False

    def stop(self):
        """Stop playback"""
        try:
            if self.player:
                self.player.stop()
        except Exception as e:
            print(f"Failed to stop: {e}")

    def set_volume(self, volume: int):
        """Set volume (0-100) - VLC player hangerő beállítása"""
        try:
            if self.player:
                # Tároljuk a saját hangerő állapotot
                self._volume = max(0, min(100, volume))
                
                # Ha mute-ban vagyunk, csak a _volume változót frissítjük, de nem állítjuk a VLC-t
                if self._is_muted:
                    # Mute-ban vagyunk, ne változtassuk a tényleges VLC volume-ot
                    print(f"VLC Player #{self._player_id} volume stored to {self._volume}% (muted, not applied)")
                    return
                
                # Normál állapotban állítsuk a VLC volume-ot
                result = self.player.audio_set_volume(self._volume)
                print(f"VLC Player #{self._player_id} volume set to {self._volume}% (result: {result})")
                
        except Exception as e:
            print(f"VLC Player #{self._player_id} failed to set volume: {e}")

    def get_volume(self) -> int:
        """Get current volume (0-100)"""
        return self._volume

    def mute(self):
        """Mute audio - normális video player mute viselkedés"""
        if not self._is_muted:
            # Mentjük a jelenlegi volume-ot
            self._volume_before_mute = self._volume
            print(f"VLC Player #{self._player_id} muting (was {self._volume}%)")
            
            # VLC player-t némítjuk, de a _volume értékét NEM változtatjuk meg
            if self.player:
                self.player.audio_set_volume(0)
            
            self._is_muted = True

    def unmute(self):
        """Unmute audio - normális video player unmute viselkedés"""
        if self._is_muted:
            print(f"VLC Player #{self._player_id} unmuting (restore to {self._volume_before_mute}%)")
            
            # Visszaállítjuk az eredeti volume-ot
            self._volume = self._volume_before_mute
            
            # VLC player volume visszaállítása
            if self.player:
                self.player.audio_set_volume(self._volume)
                
            self._is_muted = False

    def toggle_mute(self):
        """Toggle mute/unmute"""
        print(f"VLC Player #{self._player_id} toggle_mute called (currently muted: {self._is_muted})")
        if self._is_muted:
            self.unmute()
        else:
            self.mute()

    def is_muted(self) -> bool:
        """Check if currently muted"""
        return self._is_muted

    def is_playing_state(self) -> bool:
        """Check if currently playing"""
        try:
            if not self.player or not VLC_AVAILABLE or vlc is None:
                return False
            state = self.player.get_state()
            # Use numeric comparison to avoid attribute access issues
            return state == 3  # vlc.State.Playing = 3
        except Exception:
            return False

    def cleanup(self):
        """Clean up VLC resources"""
        try:
            if self.player:
                self.player.stop()
                self.player.release()
            if self.instance:
                self.instance.release()
        except Exception as e:
            print(f"Cleanup error: {e}")


def create_vlc_player(canvas: tk.Canvas) -> Optional[VLCVideoPlayer]:
    """Create VLC player instance"""
    try:
        return VLCVideoPlayer(canvas)
    except Exception as e:
        print(f"Failed to create VLC player: {e}")
        return None


def is_vlc_available() -> bool:
    """Check if VLC is available"""
    return VLC_AVAILABLE
