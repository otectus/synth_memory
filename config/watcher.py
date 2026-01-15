import time
import threading
from pathlib import Path
from typing import Callable

class ConfigurationWatcher:
    def __init__(self, config_path: Path, callback: Callable):
        self.config_path = config_path
        self.callback = callback
        self._running = False
        self._last_mtime = 0

    def start(self):
        if self._running: return
        self._running = True
        if self.config_path.exists():
            self._last_mtime = self.config_path.stat().st_mtime
        
        thread = threading.Thread(target=self._watch_loop, daemon=True)
        thread.start()

    def _watch_loop(self):
        while self._running:
            try:
                if self.config_path.exists():
                    current_mtime = self.config_path.stat().st_mtime
                    if current_mtime > self._last_mtime:
                        self._last_mtime = current_mtime
                        # Trigger the reload callback
                        self.callback()
            except Exception as e:
                print(f"[SynthMemory Watcher] Error: {e}")
            time.sleep(2) # Config check interval

    def stop(self):
        self._running = False