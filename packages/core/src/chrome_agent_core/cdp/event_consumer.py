#!/usr/bin/env python3
"""
Event Consumer — high-level consumer API for watchdog events
"""
import queue
import time


class EventConsumer:
    """
    High-level consumer for watchdog events.

    Usage:
        from utils.event import EventConsumer
        from core.browser_engine import init_watchdog_pipe, start_watchdog_monitor

        pipe = init_watchdog_pipe(maxsize=200)
        start_watchdog_monitor(interval=10)
        consumer = EventConsumer(pipe)

        # Blocking get
        event = consumer.get()              # blocks indefinitely
        event = consumer.get(timeout=5.0)   # blocks with timeout

        # Non-blocking
        event = consumer.try_get()           # returns None if empty

        # Drain all available events
        for event in consumer.drain():
            process(event)

        # Filtered get
        event = consumer.get_by_type('click_success', timeout=5)
        event = consumer.get_by_outcome('failure', timeout=5)
    """

    def __init__(self, pipe: 'queue.Queue'):
        self.pipe = pipe

    def get(self, timeout: float = None) -> dict | None:
        """
        Blocking get from queue.
        timeout=None means wait forever.
        Returns None on queue.Empty (timeout expired).
        """
        try:
            return self.pipe.get(timeout=timeout)
        except queue.Empty:
            return None

    def try_get(self) -> dict | None:
        """Non-blocking get. Returns None if queue is empty."""
        try:
            return self.pipe.get_nowait()
        except queue.Empty:
            return None

    def drain(self) -> list[dict]:
        """Drain all events currently in the queue. Non-blocking."""
        events = []
        while True:
            try:
                events.append(self.pipe.get_nowait())
            except queue.Empty:
                break
        return events

    def get_by_type(self, event_type: str, timeout: float = 60) -> dict | None:
        """
        Get next event of a specific type.
        Blocks until event_type is found or timeout expires.
        Returns None if timeout expires.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                remaining = max(0.1, deadline - time.time())
                event = self.pipe.get(timeout=remaining)
                if event.get('type') == event_type:
                    return event
            except queue.Empty:
                break
        return None

    def get_by_outcome(self, outcome: str, timeout: float = 60) -> dict | None:
        """
        Get next event with a specific outcome ('success', 'failure', 'warning', 'info').
        Blocks until outcome is found or timeout expires.
        Returns None if timeout expires.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                remaining = max(0.1, deadline - time.time())
                event = self.pipe.get(timeout=remaining)
                if event.get('outcome') == outcome:
                    return event
            except queue.Empty:
                break
        return None

    def drain_by_type(self, event_type: str) -> list[dict]:
        """Drain all events of a specific type."""
        events = []
        while True:
            try:
                event = self.pipe.get_nowait()
                if event.get('type') == event_type:
                    events.append(event)
            except queue.Empty:
                break
        return events

    def drain_by_outcome(self, outcome: str) -> list[dict]:
        """Drain all events with a specific outcome."""
        events = []
        while True:
            try:
                event = self.pipe.get_nowait()
                if event.get('outcome') == outcome:
                    events.append(event)
            except queue.Empty:
                break
        return events

    def wait_for(self, event_type: str, timeout: float = 30) -> dict | None:
        """Wait for a specific event type, return it. Alias for get_by_type."""
        return self.get_by_type(event_type, timeout)

    def wait_for_outcome(self, outcome: str, timeout: float = 30) -> dict | None:
        """Wait for a specific outcome, return it. Alias for get_by_outcome."""
        return self.get_by_outcome(outcome, timeout)


if __name__ == '__main__':
    print('EventConsumer utility')
    print('Use: from utils.event import EventConsumer')
