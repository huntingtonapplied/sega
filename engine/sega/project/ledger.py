#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
SEGA PROJECT TESTING LEDGER
==============================================================================
File: engine/sega/project/ledger.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Project/Ledger
COMPONENT: Concurrent Testing Coordination
PURPOSE: Manage project reservations for concurrent agent testing
DEPENDENCIES: fcntl (file-based locking), datetime, json
USAGE: ProjectLedger().acquire(project_name, agent_id)

This module provides a file-based locking mechanism to ensure only one
agent can test a specific project at a time, preventing port conflicts
and resource contention during parallel testing operations.
==============================================================================
"""

import fcntl
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict


@dataclass
class ProjectReservation:
    """Represents a project reservation in the ledger."""
    project_name: str
    agent_id: str
    reserved_at: str
    expires_at: str
    pid: int
    status: str  # 'active', 'completed', 'failed', 'expired'
    ports_used: List[int]


class ProjectLedger:
    """
    File-based project reservation system for concurrent testing.

    Ensures mutual exclusion when multiple agents are testing projects
    simultaneously by maintaining a ledger of active reservations.

    Features:
    - Atomic file-based locking using fcntl
    - Automatic expiration of stale reservations
    - Support for forced release (timeout override)
    - Reservation history tracking
    - Port conflict detection

    Example:
        ledger = ProjectLedger()

        # Acquire project reservation
        if ledger.acquire('orion', 'agent-001'):
            try:
                # Run tests
                run_blacklab_tests()
            finally:
                ledger.release('orion', 'agent-001')
        else:
            print(f"Project in use by: {ledger.get_reservation('orion')}")
    """

    DEFAULT_LEDGER_PATH = Path.home() / '.sega' / 'project_ledger.json'
    DEFAULT_TIMEOUT_MINUTES = 30  # Auto-release after 30 minutes

    def __init__(self, ledger_path: Optional[Path] = None, timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES):
        """
        Initialize project ledger.

        Args:
            ledger_path: Path to ledger file (default: ~/.sega/project_ledger.json)
            timeout_minutes: Reservation timeout in minutes (default: 30)
        """
        self.ledger_path = ledger_path or self.DEFAULT_LEDGER_PATH
        self.timeout_minutes = timeout_minutes

        # Ensure ledger directory exists
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize ledger file if it doesn't exist
        if not self.ledger_path.exists():
            self._write_ledger({'reservations': {}, 'history': []})

    def acquire(self, project_name: str, agent_id: str, ports: Optional[List[int]] = None) -> bool:
        """
        Acquire reservation for a project.

        Args:
            project_name: Name of the project to reserve
            agent_id: Unique identifier for the agent
            ports: Optional list of ports that will be used

        Returns:
            True if reservation acquired successfully, False otherwise
        """
        with self._lock_ledger():
            ledger = self._read_ledger()

            # Clean up expired reservations first
            self._cleanup_expired(ledger)

            # Check if project is already reserved
            if project_name in ledger['reservations']:
                existing = ledger['reservations'][project_name]

                # Allow same agent to re-acquire (renewal)
                if existing['agent_id'] == agent_id:
                    # Update expiration
                    existing['expires_at'] = self._get_expiration_time()
                    existing['reserved_at'] = datetime.now().isoformat()
                    self._write_ledger(ledger)
                    return True
                else:
                    # Project reserved by different agent
                    return False

            # Check for port conflicts
            if ports:
                for reserved_project, reservation in ledger['reservations'].items():
                    if reserved_project != project_name:
                        reserved_ports = set(reservation.get('ports_used', []))
                        requested_ports = set(ports)
                        if reserved_ports & requested_ports:
                            # Port conflict detected
                            return False

            # Create new reservation
            reservation = ProjectReservation(
                project_name=project_name,
                agent_id=agent_id,
                reserved_at=datetime.now().isoformat(),
                expires_at=self._get_expiration_time(),
                pid=os.getpid(),
                status='active',
                ports_used=ports or []
            )

            ledger['reservations'][project_name] = asdict(reservation)
            self._write_ledger(ledger)
            return True

    def release(self, project_name: str, agent_id: str, status: str = 'completed') -> bool:
        """
        Release reservation for a project.

        Args:
            project_name: Name of the project to release
            agent_id: Agent ID that owns the reservation
            status: Final status ('completed', 'failed')

        Returns:
            True if released successfully, False if not owned by agent
        """
        with self._lock_ledger():
            ledger = self._read_ledger()

            if project_name not in ledger['reservations']:
                return False

            reservation = ledger['reservations'][project_name]

            # Verify ownership
            if reservation['agent_id'] != agent_id:
                return False

            # Update status and move to history
            reservation['status'] = status
            reservation['released_at'] = datetime.now().isoformat()
            ledger['history'].append(reservation)

            # Remove from active reservations
            del ledger['reservations'][project_name]

            # Keep only last 1000 history entries
            if len(ledger['history']) > 1000:
                ledger['history'] = ledger['history'][-1000:]

            self._write_ledger(ledger)
            return True

    def force_release(self, project_name: str) -> bool:
        """
        Force release a reservation (admin override).

        Args:
            project_name: Name of the project to force release

        Returns:
            True if released, False if not reserved
        """
        with self._lock_ledger():
            ledger = self._read_ledger()

            if project_name not in ledger['reservations']:
                return False

            reservation = ledger['reservations'][project_name]
            reservation['status'] = 'force_released'
            reservation['released_at'] = datetime.now().isoformat()
            ledger['history'].append(reservation)
            del ledger['reservations'][project_name]

            self._write_ledger(ledger)
            return True

    def get_reservation(self, project_name: str) -> Optional[Dict]:
        """
        Get current reservation for a project.

        Args:
            project_name: Name of the project

        Returns:
            Reservation dict or None if not reserved
        """
        with self._lock_ledger():
            ledger = self._read_ledger()
            self._cleanup_expired(ledger)
            return ledger['reservations'].get(project_name)

    def list_active_reservations(self) -> Dict[str, Dict]:
        """
        List all active reservations.

        Returns:
            Dictionary of project_name -> reservation
        """
        with self._lock_ledger():
            ledger = self._read_ledger()
            self._cleanup_expired(ledger)
            return ledger['reservations'].copy()

    def is_available(self, project_name: str, ports: Optional[List[int]] = None) -> bool:
        """
        Check if a project is available for reservation.

        Args:
            project_name: Name of the project
            ports: Optional list of ports to check for conflicts

        Returns:
            True if available, False if reserved or port conflict
        """
        with self._lock_ledger():
            ledger = self._read_ledger()
            self._cleanup_expired(ledger)

            # Check if project is reserved
            if project_name in ledger['reservations']:
                return False

            # Check for port conflicts
            if ports:
                for reserved_project, reservation in ledger['reservations'].items():
                    reserved_ports = set(reservation.get('ports_used', []))
                    requested_ports = set(ports)
                    if reserved_ports & requested_ports:
                        return False

            return True

    def get_history(self, project_name: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get reservation history.

        Args:
            project_name: Optional filter by project name
            limit: Maximum number of entries to return

        Returns:
            List of historical reservations (most recent first)
        """
        with self._lock_ledger():
            ledger = self._read_ledger()
            history = ledger['history']

            if project_name:
                history = [h for h in history if h['project_name'] == project_name]

            return list(reversed(history[-limit:]))

    def cleanup_all(self) -> int:
        """
        Clean up all expired reservations.

        Returns:
            Number of reservations cleaned up
        """
        with self._lock_ledger():
            ledger = self._read_ledger()
            before_count = len(ledger['reservations'])
            self._cleanup_expired(ledger)
            after_count = len(ledger['reservations'])
            return before_count - after_count

    def _cleanup_expired(self, ledger: Dict) -> None:
        """Remove expired reservations from ledger (in-place)."""
        now = datetime.now()
        expired = []

        for project_name, reservation in ledger['reservations'].items():
            expires_at = datetime.fromisoformat(reservation['expires_at'])
            if now > expires_at:
                expired.append(project_name)

        # Move expired to history
        for project_name in expired:
            reservation = ledger['reservations'][project_name]
            reservation['status'] = 'expired'
            reservation['released_at'] = datetime.now().isoformat()
            ledger['history'].append(reservation)
            del ledger['reservations'][project_name]

        # Write back if any expired
        if expired:
            self._write_ledger(ledger)

    def _get_expiration_time(self) -> str:
        """Get expiration timestamp based on timeout."""
        expires = datetime.now() + timedelta(minutes=self.timeout_minutes)
        return expires.isoformat()

    def _read_ledger(self) -> Dict:
        """Read ledger file."""
        try:
            with open(self.ledger_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'reservations': {}, 'history': []}

    def _write_ledger(self, ledger: Dict) -> None:
        """Write ledger file."""
        with open(self.ledger_path, 'w') as f:
            json.dump(ledger, f, indent=2)

    def _lock_ledger(self):
        """
        Context manager for exclusive file locking.

        Uses fcntl for atomic file-based locking to ensure mutual exclusion
        across multiple processes/agents.
        """
        class LedgerLock:
            def __init__(self, path):
                self.path = path
                self.lock_file = None

            def __enter__(self):
                # Create lock file
                lock_path = self.path.parent / f"{self.path.name}.lock"
                self.lock_file = open(lock_path, 'w')

                # Acquire exclusive lock (blocks until available)
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                # Release lock and close file
                if self.lock_file:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                    self.lock_file.close()

        return LedgerLock(self.ledger_path)


# Convenience functions for CLI usage
def acquire_project(project_name: str, agent_id: str, ports: Optional[List[int]] = None) -> bool:
    """Convenience function to acquire project reservation."""
    return ProjectLedger().acquire(project_name, agent_id, ports)


def release_project(project_name: str, agent_id: str, status: str = 'completed') -> bool:
    """Convenience function to release project reservation."""
    return ProjectLedger().release(project_name, agent_id, status)


def is_project_available(project_name: str, ports: Optional[List[int]] = None) -> bool:
    """Convenience function to check project availability."""
    return ProjectLedger().is_available(project_name, ports)
