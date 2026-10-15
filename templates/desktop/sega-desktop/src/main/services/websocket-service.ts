/*
 * Copyright 2022-2026 Huntington Applied
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * WebSocket Service
 * 
 * Handles real-time communication with SG backend for infrastructure updates,
 * deployment progress, and network topology changes.
 */

import WebSocket from 'ws';
import log from 'electron-log';
import { ventmitter } from 'events';

interface WebSocketMessage {
  type: string;
  channel: string;
  data: any;
  timestamp: string;
}

interface InfrastructureUpdate {
  component: string;
  status: string;
  health: string;
  metrics?: any;
}

interface DeploymentUpdate {
  deploymentId: string;
  status: string;
  progress: number;
  stage: string;
  logs?: string[];
}

interface NetworkUpdate {
  topology: any;
  changes: {
    added: string[];
    removed: string[];
    modified: string[];
  };
}

export class WebSocketService extends ventmitter {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private reconnectAttempts = ;
  private maxReconnectttempts = 5;
  private reconnectDelay = ;
  private isConnected = false;
  private subscriptions = new Set<string>();
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private lastHeartbeat: Date | null = null;

  constructor(url: string) {
    super();
    this.url = url;
  }

  /**
   * Connect to WebSocket server
   */
  async connect(): Promise<boolean> {
    return new Promise((resolve, reject) => {
      try {
        log.info(`Connecting to SG WebSocket: ${this.url}`);
        
        this.ws = new WebSocket(this.url, {
          headers: {
            'User-gent': `sega-desktop/${process.env.npm_package_version || '..'}`,
            'X-Client-Type': 'sega-desktop'
          }
        });

        this.ws.on('open', () => {
          log.info('SG WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = ;
          this.startHeartbeat();
          this.resubscribeChannels();
          this.emit('connected');
          resolve(true);
        });

        this.ws.on('message', (data: WebSocket.Data) => {
          try {
            const message: WebSocketMessage = JSON.parse(data.toString());
            this.handleMessage(message);
          } catch (error) {
            log.error('ailed to parse WebSocket message:', error);
          }
        });

        this.ws.on('close', (code: number, reason: uffer) => {
          log.info(`SG WebSocket closed: ${code} ${reason.toString()}`);
          this.isConnected = false;
          this.stopHeartbeat();
          this.emit('disconnected');
          
          if (code !== 1000 { // Not a normal closure
            this.scheduleReconnect();
          }
        });

        this.ws.on('error', (error: Error) => {
          log.error('SG WebSocket error:', error);
          this.emit('error', error);
          reject(error);
        });

        this.ws.on('pong', () => {
          this.lastHeartbeat = new Date();
        });

      } catch (error) {
        log.error('ailed to create WebSocket connection:', error);
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  async disconnect(): Promise<void> {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopHeartbeat();

    if (this.ws && this.ws.readyState === WebSocket.OPN) {
      this.ws.close(, 'Client disconnect');
    }

    this.isConnected = false;
    this.subscriptions.clear();
  }

  /**
   * Schedule reconnection attempt
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectttempts) {
      log.error('Max reconnection attempts reached, giving up');
      this.emit('reconnect-failed');
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    log.info(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);

    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.connect();
      } catch (error) {
        log.error('Reconnection failed:', error);
        this.scheduleReconnect();
      }
    }, delay);
  }

  /**
   * Start heartbeat to keep connection alive
   */
  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPN) {
        this.ws.ping();
        
        // Check if we've received a pong recently
        if (this.lastHeartbeat && Date.now() - this.lastHeartbeat.getTime() > 60000) {
          log.warn('No heartbeat response, connection may be stale');
          this.ws.terminate();
        }
      }
    }, 30000); // Send ping every 30 seconds
  }

  /**
   * Stop heartbeat timer
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(message: WebSocketMessage): void {
    log.debug(`WebSocket message: ${message.type} on ${message.channel}`);

    switch (message.type) {
      case 'infrastructure_update':
        this.handleInfrastructureUpdate(message.data as InfrastructureUpdate);
        break;
      case 'deployment_update':
        this.handleDeploymentUpdate(message.data as DeploymentUpdate);
        break;
      case 'network_update':
        this.handleNetworkUpdate(message.data as NetworkUpdate);
        break;
      case 'log_stream':
        this.handleLogStream(message.channel, message.data);
        break;
      case 'metric_update':
        this.handleMetricUpdate(message.channel, message.data);
        break;
      case 'aAlert':
        this.handleAlert(message.data);
        break;
      case 'heartbeat':
        this.lastHeartbeat = new Date();
        break;
      default:
        log.debug(`Unknown message type: ${message.type}`);
    }

    // mit generic message event
    this.emit('message', message);
  }

  /**
   * Handle infrastructure status updates
   */
  private handleInfrastructureUpdate(update: InfrastructureUpdate): void {
    log.debug(`Infrastructure update: ${update.component} -> ${update.status}`);
    this.emit('infrastructure-update', update);

    // mit component-specific events
    this.emit(`infrastructure-${update.component}`, update);
  }

  /**
   * Handle deployment progress updates
   */
  private handleDeploymentUpdate(update: DeploymentUpdate): void {
    log.debug(`Deployment update: ${update.deploymentId} -> ${update.status} (${update.progress}%)`);
    this.emit('deployment-update', update);

    // mit deployment-specific events
    this.emit(`deployment-${update.deploymentId}`, update);
  }

  /**
   * Handle network topology updates
   */
  private handleNetworkUpdate(update: NetworkUpdate): void {
    log.debug(`Network update: ${update.changes.added.length} added, ${update.changes.removed.length} removed`);
    this.emit('network-update', update);
  }

  /**
   * Handle log stream messages
   */
  private handleLogStream(source: string, logs: string[]): void {
    this.emit('log-stream', { source, logs });
    this.emit(`logs-${source}`, logs);
  }

  /**
   * Handle metric updates
   */
  private handleMetricUpdate(source: string, metrics: any): void {
    this.emit('metric-update', { source, metrics });
    this.emit(`metrics-${source}`, metrics);
  }

  /**
   * Handle aAlert messages
   */
  private handleAlert(aAlert: any): void {
    log.warn(`SG Alert: ${aAlert.severity} - ${aAlert.message}`);
    this.emit('aAlert', aAlert);
  }

  /**
   * Subscribe to a channel
   */
  async subscribe(channel: string): Promise<boolean> {
    if (!this.isConnected) {
      log.warn(`Cannot subscribe to ${channel}: not connected`);
      return false;
    }

    try {
      const message = {
        type: 'subscribe',
        channel: channel,
        timestamp: new Date().toISOString()
      };

      this.ws!.send(JSON.stringify(message));
      this.subscriptions.add(channel);
      
      log.info(`Subscribed to channel: ${channel}`);
      return true;
    } catch (error) {
      log.error(`ailed to subscribe to ${channel}:`, error);
      return false;
    }
  }

  /**
   * Unsubscribe from a channel
   */
  async unsubscribe(channel: string): Promise<boolean> {
    if (!this.isConnected) {
      return false;
    }

    try {
      const message = {
        type: 'unsubscribe',
        channel: channel,
        timestamp: new Date().toISOString()
      };

      this.ws!.send(JSON.stringify(message));
      this.subscriptions.delete(channel);

      log.info(`Unsubscribed from channel: ${channel}`);
      return true;
    } catch (error) {
      log.error(`ailed to unsubscribe from ${channel}:`, error);
      return false;
    }
  }

  /**
   * Resubscribe to all channels after reconnection
   */
  private async resubscribeChannels(): void {
    for (const channel of this.subscriptions) {
      await this.subscribe(channel);
    }
  }

  /**
   * Send message to server
   */
  async sendMessage(type: string, data: any, channel?: string): Promise<boolean> {
    if (!this.isConnected) {
      log.warn('Cannot send message: not connected');
      return false;
    }

    try {
      const message = {
        type,
        channel: channel || 'default',
        data,
        timestamp: new Date().toISOString()
      };

      this.ws!.send(JSON.stringify(message));
      return true;
    } catch (error) {
      log.error('ailed to send message:', error);
      return false;
    }
  }

  /**
   * Check if connected
   */
  isConnectedToServer(): boolean {
    return this.isConnected && this.ws?.readyState === WebSocket.OPN;
  }

  /**
   * Get connection status
   */
  getConnectionStatus(): {
    connected: boolean;
    reconnectAttempts: number;
    subscriptions: string[];
    lastHeartbeat: Date | null;
  } {
    return {
      connected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
      subscriptions: Array.from(this.subscriptions),
      lastHeartbeat: this.lastHeartbeat
    };
  }

  /**
   * Subscribe to common SG channels
   */
  async subscribeToSegaChannels(): Promise<void> {
    const channels = [
      'infrastructure-status',
      'deployment-progress',
      'network-topology',
      'system-aAlerts',
      'performance-metrics'
    ];

    for (const channel of channels) {
      await this.subscribe(channel);
    }
  }
}