#!/usr/bin/env python3
"""
Simple Audio Player for Selecta Library Manager
Cross-platform audio preview with basic controls
"""

import os
import threading
import time
from typing import Optional, Callable
from pathlib import Path

class AudioPlayer:
    """Simple audio player for file preview"""
    
    def __init__(self):
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
        self.duration = 0.0
        self.volume = 0.7
        
        # Callbacks
        self.position_callback: Optional[Callable] = None
        self.finished_callback: Optional[Callable] = None
        
        # Try to import audio library
        self.audio_backend = self._init_audio_backend()
        
    def _init_audio_backend(self):
        """Initialize audio backend (prefer pygame for simplicity)"""
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            return "pygame"
        except ImportError:
            try:
                # Fallback to system command for macOS
                return "system"
            except:
                return None
    
    def load_file(self, file_path: str) -> bool:
        """Load an audio file for playback"""
        if not os.path.exists(file_path):
            return False
            
        self.stop()
        self.current_file = file_path
        self.position = 0.0
        
        if self.audio_backend == "pygame":
            try:
                import pygame
                pygame.mixer.music.load(file_path)
                # Try to get duration (basic approach)
                self.duration = self._get_duration_pygame(file_path)
                return True
            except Exception as e:
                print(f"Error loading file with pygame: {e}")
                return False
        
        elif self.audio_backend == "system":
            # For system playback, we can't easily get duration
            self.duration = 0.0
            return True
            
        return False
    
    def _get_duration_pygame(self, file_path: str) -> float:
        """Get audio duration (basic implementation)"""
        try:
            # This is a simplified approach - for production, use librosa or mutagen
            from pathlib import Path
            file_size = Path(file_path).stat().st_size
            # Rough estimate: 1MB ≈ 8 seconds for typical audio
            estimated_duration = file_size / (1024 * 1024) * 8
            return min(estimated_duration, 300)  # Cap at 5 minutes
        except:
            return 120.0  # Default 2 minutes
    
    def play(self) -> bool:
        """Start playback"""
        if not self.current_file:
            return False
            
        if self.audio_backend == "pygame":
            try:
                import pygame
                if self.is_paused:
                    pygame.mixer.music.unpause()
                else:
                    pygame.mixer.music.play(start=self.position)
                
                self.is_playing = True
                self.is_paused = False
                
                # Start position tracking thread
                threading.Thread(target=self._track_position, daemon=True).start()
                return True
                
            except Exception as e:
                print(f"Error playing with pygame: {e}")
                return False
        
        elif self.audio_backend == "system":
            # Use macOS 'afplay' command
            try:
                import subprocess
                cmd = ["afplay", self.current_file]
                self.system_process = subprocess.Popen(cmd)
                self.is_playing = True
                self.is_paused = False
                
                # Start monitoring thread
                threading.Thread(target=self._monitor_system_playback, daemon=True).start()
                return True
                
            except Exception as e:
                print(f"Error playing with system: {e}")
                return False
        
        return False
    
    def pause(self):
        """Pause playback"""
        if not self.is_playing:
            return
            
        if self.audio_backend == "pygame":
            try:
                import pygame
                pygame.mixer.music.pause()
                self.is_paused = True
            except:
                pass
        
        elif self.audio_backend == "system":
            try:
                if hasattr(self, 'system_process'):
                    self.system_process.terminate()
                self.is_playing = False
            except:
                pass
    
    def stop(self):
        """Stop playback"""
        if self.audio_backend == "pygame":
            try:
                import pygame
                pygame.mixer.music.stop()
            except:
                pass
        
        elif self.audio_backend == "system":
            try:
                if hasattr(self, 'system_process'):
                    self.system_process.terminate()
            except:
                pass
        
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
    
    def set_volume(self, volume: float):
        """Set playback volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        
        if self.audio_backend == "pygame":
            try:
                import pygame
                pygame.mixer.music.set_volume(self.volume)
            except:
                pass
    
    def seek(self, position: float):
        """Seek to position in seconds"""
        if not self.current_file or position < 0:
            return
            
        self.position = min(position, self.duration)
        
        if self.is_playing and self.audio_backend == "pygame":
            # Pygame doesn't support seeking easily, so restart from beginning
            self.stop()
            self.play()
    
    def get_position(self) -> float:
        """Get current playback position in seconds"""
        return self.position
    
    def get_duration(self) -> float:
        """Get total duration in seconds"""
        return self.duration
    
    def is_busy(self) -> bool:
        """Check if player is currently playing"""
        return self.is_playing and not self.is_paused
    
    def _track_position(self):
        """Track playback position (pygame)"""
        start_time = time.time()
        
        while self.is_playing and not self.is_paused:
            if self.audio_backend == "pygame":
                try:
                    import pygame
                    if not pygame.mixer.music.get_busy():
                        # Playback finished
                        self.is_playing = False
                        if self.finished_callback:
                            self.finished_callback()
                        break
                except:
                    break
            
            # Update position
            elapsed = time.time() - start_time
            self.position = min(self.position + elapsed, self.duration)
            
            # Call position callback
            if self.position_callback:
                self.position_callback(self.position)
            
            time.sleep(0.1)
            start_time = time.time()
    
    def _monitor_system_playback(self):
        """Monitor system playback process"""
        if hasattr(self, 'system_process'):
            self.system_process.wait()
            self.is_playing = False
            if self.finished_callback:
                self.finished_callback()

class AudioPlayerWidget:
    """Tkinter widget for audio player controls"""
    
    def __init__(self, parent):
        import tkinter as tk
        from tkinter import ttk
        
        self.parent = parent
        self.player = AudioPlayer()
        self.current_file_id = None
        
        # Player state
        self.is_playing = False
        self.position_var = tk.StringVar(value="0:00")
        self.duration_var = tk.StringVar(value="0:00")
        
        # Callbacks
        self.player.position_callback = self._update_position
        self.player.finished_callback = self._on_playback_finished
        
        self.create_widget()
    
    def create_widget(self):
        """Create the player widget"""
        import tkinter as tk
        from tkinter import ttk
        
        # Main player frame
        self.player_frame = ttk.LabelFrame(self.parent, text="🎵 Audio Player", padding="10")
        
        # Now playing info
        self.now_playing_var = tk.StringVar(value="No file loaded")
        now_playing_label = ttk.Label(self.player_frame, textvariable=self.now_playing_var, 
                                     font=('Arial', 10, 'bold'))
        now_playing_label.pack(fill=tk.X, pady=(0, 10))
        
        # Control buttons
        controls_frame = ttk.Frame(self.player_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.play_btn = ttk.Button(controls_frame, text="▶️", command=self.toggle_play, width=3)
        self.play_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(controls_frame, text="⏹️", command=self.stop, width=3)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Volume control
        ttk.Label(controls_frame, text="🔊").pack(side=tk.LEFT, padx=(10, 5))
        self.volume_scale = ttk.Scale(controls_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                     command=self._on_volume_change, length=100)
        self.volume_scale.set(70)  # Default volume
        self.volume_scale.pack(side=tk.LEFT, padx=(0, 10))
        
        # Position info
        position_frame = ttk.Frame(self.player_frame)
        position_frame.pack(fill=tk.X)
        
        ttk.Label(position_frame, textvariable=self.position_var).pack(side=tk.LEFT)
        ttk.Label(position_frame, text=" / ").pack(side=tk.LEFT)
        ttk.Label(position_frame, textvariable=self.duration_var).pack(side=tk.LEFT)
        
        # Position bar (simplified)
        self.position_bar = ttk.Progressbar(position_frame, mode='determinate')
        self.position_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
    
    def load_file(self, file_path: str, file_id: int = None):
        """Load a file for playback"""
        if self.player.load_file(file_path):
            self.current_file_id = file_id
            filename = os.path.basename(file_path)
            self.now_playing_var.set(f"Loaded: {filename}")
            
            # Update duration
            duration = self.player.get_duration()
            self.duration_var.set(self._format_time(duration))
            self.position_bar.config(maximum=duration)
            
            return True
        return False
    
    def toggle_play(self):
        """Toggle play/pause"""
        if self.player.is_busy():
            self.player.pause()
            self.play_btn.config(text="▶️")
            self.is_playing = False
        else:
            if self.player.play():
                self.play_btn.config(text="⏸️")
                self.is_playing = True
                # Update now playing
                if self.player.current_file:
                    filename = os.path.basename(self.player.current_file)
                    self.now_playing_var.set(f"🎵 Playing: {filename}")
    
    def stop(self):
        """Stop playback"""
        self.player.stop()
        self.play_btn.config(text="▶️")
        self.is_playing = False
        self.position_var.set("0:00")
        self.position_bar.config(value=0)
        
        if self.player.current_file:
            filename = os.path.basename(self.player.current_file)
            self.now_playing_var.set(f"Stopped: {filename}")
    
    def _on_volume_change(self, value):
        """Handle volume change"""
        volume = float(value) / 100.0
        self.player.set_volume(volume)
    
    def _update_position(self, position: float):
        """Update position display"""
        try:
            self.position_var.set(self._format_time(position))
            self.position_bar.config(value=position)
        except:
            pass  # Handle case where widget is destroyed
    
    def _on_playback_finished(self):
        """Handle playback completion"""
        try:
            self.play_btn.config(text="▶️")
            self.is_playing = False
            
            if self.player.current_file:
                filename = os.path.basename(self.player.current_file)
                self.now_playing_var.set(f"Finished: {filename}")
        except:
            pass
    
    def _format_time(self, seconds: float) -> str:
        """Format time as MM:SS"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"
    
    def pack(self, **kwargs):
        """Pack the player frame"""
        self.player_frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the player frame"""
        self.player_frame.grid(**kwargs)

