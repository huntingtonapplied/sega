#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Enhanced Connection Manager
===========================
Provides circuit breaker, connection pooling, and failover for ecosystem services.
"""

import time
import socket
import threading
import logging
import queue
from typing import Optional, List, Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class ConnectionConfig:
    """Configuration for connection management."""
    host: str
    port: int
    timeout: float = 5.0
    max_retries: int = 3
    retry_delay: float = 1.0
    circuit_failure_threshold: int = 5
    circuit_timeout: float = 60.0
    pool_size: int = 3


class CircuitBreaker:
    """Circuit breaker implementation for service reliability."""
    
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = threading.RLock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN - service unavailable")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e
    
    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class ConnectionPool:
    """Connection pool for managing multiple connections."""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connections: List[socket.socket] = []
        self.available_connections = queue.Queue(maxsize=config.pool_size)
        self._lock = threading.RLock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool."""
        for _ in range(self.config.pool_size):
            try:
                conn = self._create_connection()
                if conn:
                    self.connections.append(conn)
                    self.available_connections.put(conn)
            except Exception as e:
                logging.warning(f"Failed to create connection: {e}")
    
    def _create_connection(self) -> Optional[socket.socket]:
        """Create a new socket connection."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.timeout)
            sock.connect((self.config.host, self.config.port))
            return sock
        except Exception as e:
            logging.error(f"Failed to create connection to {self.config.host}:{self.config.port}: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        connection = None
        try:
            connection = self.available_connections.get(timeout=self.config.timeout)
            yield connection
        except Exception as e:
            logging.error(f"Failed to get connection: {e}")
            # Try to create a new connection
            connection = self._create_connection()
            if connection:
                yield connection
            else:
                raise e
        finally:
            if connection:
                try:
                    self.available_connections.put_nowait(connection)
                except:
                    # Pool is full, close this connection
                    connection.close()
    
    def close_all(self):
        """Close all connections in the pool."""
        with self._lock:
            while not self.available_connections.empty():
                try:
                    conn = self.available_connections.get_nowait()
                    conn.close()
                except:
                    pass


class EnhancedConnectionManager:
    """Enhanced connection manager with circuit breaker and pooling."""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.circuit_failure_threshold,
            timeout=config.circuit_timeout
        )
        self.connection_pool = ConnectionPool(config)
        self.logger = logging.getLogger(__name__)
    
    def send_data(self, data: bytes) -> bool:
        """Send data with circuit breaker and connection pooling."""
        def _send():
            with self.connection_pool.get_connection() as conn:
                if not conn:
                    raise Exception("No connection available")
                
                # Send data length first (4 bytes)
                data_length = len(data)
                conn.sendall(data_length.to_bytes(4, byteorder='big'))
                
                # Send actual data
                conn.sendall(data)
                
                return True
        
        try:
            return self.circuit_breaker.call(_send)
        except Exception as e:
            self.logger.error(f"Failed to send data: {e}")
            return False
    
    def send_with_retry(self, data: bytes) -> bool:
        """Send data with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                if self.send_data(data):
                    return True
            except Exception as e:
                self.logger.warning(f"Send attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
        
        return False
    
    def get_circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.circuit_breaker.state
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get connection manager health status."""
        return {
            "circuit_state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "pool_size": len(self.connection_pool.connections),
            "available_connections": self.connection_pool.available_connections.qsize(),
            "last_failure": self.circuit_breaker.last_failure_time
        }
    
    def close(self):
        """Clean shutdown of connection manager."""
        self.connection_pool.close_all()