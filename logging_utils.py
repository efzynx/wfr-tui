import asyncio
from typing import Callable, Optional

class Logger:
    def __init__(self):
        self.messages = []
        self.callbacks = []

    def subscribe(self, callback: Callable[[str], None]):
        self.callbacks.append(callback)

    def log(self, message: str):
        self.messages.append(message)
        for cb in self.callbacks:
            try:
                cb(message)
            except Exception:
                pass

    def clear(self):
        self.messages.clear()

# Global logger instance
app_logger = Logger()

def log(msg: str):
    app_logger.log(msg)
