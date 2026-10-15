#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Console Message Processing
===========================
Lightweight processing of browser console messages with truncation,
deduplication, and smart location extraction.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ConsoleMessage:
    """Lightweight console message with truncation."""

    type: str  # error, warning, info, log
    message: str  # First line only (truncated)
    location: Optional[str] = None  # file:line extracted from stack
    full_text: Optional[str] = None  # Store full for detailed report
    count: int = 1  # Deduplicate repeated messages
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __hash__(self):
        """Allow use in sets/dicts."""
        return hash(f"{self.type}|{self.message}|{self.location or ''}")


@dataclass
class NetworkFailure:
    """Network request failure."""

    url: str
    method: str
    status_code: Optional[int] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def extract_location_from_stack(stack_trace: str) -> Optional[str]:
    """
    Extract file:line from stack trace.

    Handles various stack trace formats:
    - at Button.tsx:1234:56
    - webpack://myapp/./src/components/Button.tsx?:1234
    - /src/components/Button.tsx:123:45
    - Component.tsx:123
    """
    patterns = [
        r"at\s+([^(]+\.tsx?):(\d+):(\d+)",  # at file.tsx:123:45
        r"at\s+([^(]+\.jsx?):(\d+):(\d+)",  # at file.jsx:123:45
        r"([^/]+\.tsx?)\?:(\d+):(\d+)",  # file.tsx?:123:45
        r"([^/]+\.jsx?)\?:(\d+):(\d+)",  # file.jsx?:123:45
        r"/([^/]+\.tsx?):(\d+):(\d+)",  # /src/file.tsx:123:45
        r"/([^/]+\.jsx?):(\d+):(\d+)",  # /src/file.jsx:123:45
        r"([A-Z][a-zA-Z]+\.tsx?):(\d+)",  # Component.tsx:123
        r"([A-Z][a-zA-Z]+\.jsx?):(\d+)",  # Component.jsx:123
        r"at\s+([^(]+\.js):(\d+):(\d+)",  # at file.js:123:45
        r"/([^/]+\.js):(\d+):(\d+)",  # /src/file.js:123:45
    ]

    for pattern in patterns:
        match = re.search(pattern, stack_trace)
        if match:
            filename = match.group(1)
            line = match.group(2)
            # Clean up webpack paths
            filename = filename.split("/")[-1].split("?")[0]
            return f"{filename}:{line}"

    return None


def process_console_message(
    msg,
    max_message_length: int = 150,
    max_full_text_length: int = 10000,
) -> ConsoleMessage:
    """
    Extract key info from verbose console message.

    Args:
        msg: Playwright console message object
        max_message_length: Maximum length for truncated message
        max_full_text_length: Maximum length for full text storage

    Returns:
        Processed ConsoleMessage with truncation applied
    """
    full_text = msg.text
    lines = full_text.split("\n")

    # Get first meaningful line (the actual error)
    message = lines[0].strip()

    # Truncate if too long
    if len(message) > max_message_length:
        message = message[: max_message_length - 3] + "..."

    # Extract location from stack trace
    location = extract_location_from_stack(full_text)

    # Truncate full text if needed
    truncated_full = full_text
    if len(full_text) > max_full_text_length:
        truncated_full = full_text[:max_full_text_length] + "\n...[truncated]"

    return ConsoleMessage(
        type=msg.type,
        message=message,
        location=location,
        full_text=truncated_full,
    )


# Common noise patterns to filter out (configurable)
DEFAULT_IGNORE_PATTERNS = [
    r"Download the React DevTools",
    r"React Router Future Flag Warning",
    r"Source map.*could not be loaded",
    r"\[HMR\]",  # Hot Module Replacement dev messages
    r"\[webpack-dev-server\]",
    r"Slow network is detected",
    r"LiveReload enabled",
    r"DevTools.*extension",
]


def should_ignore_message(message: str, ignore_patterns: List[str]) -> bool:
    """
    Check if message matches ignore patterns.

    Args:
        message: Console message text
        ignore_patterns: List of regex patterns to ignore

    Returns:
        True if message should be ignored
    """
    for pattern in ignore_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True
    return False


class ConsoleMessageCollector:
    """Deduplicate and aggregate console messages."""

    def __init__(self, ignore_patterns: Optional[List[str]] = None):
        """
        Initialize collector.

        Args:
            ignore_patterns: Optional list of regex patterns to ignore
        """
        self.messages: Dict[str, ConsoleMessage] = {}
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS

    def add_message(
        self,
        msg,
        max_message_length: int = 150,
        max_full_text_length: int = 10000,
    ) -> bool:
        """
        Add message, deduplicating identical ones.

        Args:
            msg: Playwright console message object
            max_message_length: Maximum length for truncated message
            max_full_text_length: Maximum length for full text storage

        Returns:
            True if message was added, False if ignored
        """
        processed = process_console_message(msg, max_message_length, max_full_text_length)

        # Check if should ignore
        if should_ignore_message(processed.message, self.ignore_patterns):
            return False

        # Create unique key (type + message + location)
        key = f"{processed.type}|{processed.message}|{processed.location or ''}"

        if key in self.messages:
            # Increment count for duplicate
            self.messages[key].count += 1
        else:
            # New unique message
            self.messages[key] = processed

        return True

    def get_summary(self, severity_filter: Optional[str] = None) -> List[ConsoleMessage]:
        """
        Get deduplicated messages sorted by severity and count.

        Args:
            severity_filter: Optional filter (error, warning, info)

        Returns:
            Sorted list of unique console messages
        """
        messages = list(self.messages.values())

        # Apply severity filter
        if severity_filter:
            messages = [m for m in messages if m.type == severity_filter]

        # Sort: errors first, then by count (most frequent first)
        severity_order = {"error": 0, "warning": 1, "info": 2, "log": 3}
        messages.sort(key=lambda m: (severity_order.get(m.type, 4), -m.count))

        return messages

    def get_counts(self) -> Dict[str, int]:
        """
        Get message counts by type.

        Returns:
            Dict of {type: count} for errors, warnings, etc.
        """
        counts = {
            "error": 0,
            "warning": 0,
            "info": 0,
            "log": 0,
        }

        for msg in self.messages.values():
            if msg.type in counts:
                counts[msg.type] += msg.count

        return counts

    def get_unique_counts(self) -> Dict[str, int]:
        """
        Get unique message counts by type.

        Returns:
            Dict of {type: unique_count}
        """
        counts = {
            "error": 0,
            "warning": 0,
            "info": 0,
            "log": 0,
        }

        for msg in self.messages.values():
            if msg.type in counts:
                counts[msg.type] += 1

        return counts
