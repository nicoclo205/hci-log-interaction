"""Mouse tracker usando pynput"""

import time
from pynput import mouse
from typing import Optional, Callable


class MouseTracker:
    """Simple mouse tracker para el prototipo"""

    def __init__(
        self,
        session_id: int,
        on_event_callback: Callable,
        movement_threshold: int = 5
    ):
        self.session_id = session_id
        self.on_event_callback = on_event_callback
        self.movement_threshold = movement_threshold

        self.listener: Optional[mouse.Listener] = None
        self._last_position = (0, 0)
        self.events_captured = 0

    def start(self):
        """Start listening to mouse events"""
        print(f"🖱️  Mouse tracker starting...")

        self.listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self.listener.start()
        print(f"✓ Mouse tracker started")

    def stop(self):
        """Stop listening to mouse events"""
        if self.listener:
            self.listener.stop()
            print(f"✓ Mouse tracker stopped ({self.events_captured} events captured)")

    def _on_move(self, x: int, y: int):
        """Handle mouse move event"""
        # Throttle movement events based on distance
        dx = abs(x - self._last_position[0])
        dy = abs(y - self._last_position[1])

        if dx > self.movement_threshold or dy > self.movement_threshold:
            event = {
                'session_id': self.session_id,
                'timestamp': time.time(),
                'event_type': 'move',
                'x': int(x),
                'y': int(y),
                'button': None,
                'pressed': None,
                'scroll_dx': None,
                'scroll_dy': None
            }
            self.on_event_callback(event)
            self._last_position = (x, y)
            self.events_captured += 1

    def _on_click(self, x: int, y: int, button, pressed: bool):
        """Handle mouse click event"""
        event = {
            'session_id': self.session_id,
            'timestamp': time.time(),
            'event_type': 'click',
            'x': int(x),
            'y': int(y),
            'button': button.name,  # 'left', 'right', 'middle'
            'pressed': pressed,
            'scroll_dx': None,
            'scroll_dy': None
        }
        self.on_event_callback(event)
        self.events_captured += 1

        # Mensaje visual para clicks
        if pressed:
            print(f"  🖱️  Click {button.name} en ({x}, {y})")

    def _on_scroll(self, x: int, y: int, dx: int, dy: int):
        """Handle mouse scroll event"""
        event = {
            'session_id': self.session_id,
            'timestamp': time.time(),
            'event_type': 'scroll',
            'x': int(x),
            'y': int(y),
            'button': None,
            'pressed': None,
            'scroll_dx': float(dx) if dx else None,
            'scroll_dy': float(dy) if dy else None
        }
        self.on_event_callback(event)
        self.events_captured += 1
