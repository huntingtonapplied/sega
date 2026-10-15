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
 * SG API Service
 * 
 * Handles communication with the SG infrastructure orchestration backend PI.
 * Provides authentication, request/response handling, and SG-specific operations.
 */

import axios, { xiosInstance, xiosRequestConfig, xiosResponse } from 'axios';
import log from 'electron-log';
import { ventmitter } from 'events';
import * as os from 'os';

interface SegapiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

interface InfrastructureStatus {
  vpn: {
    status: string;
    connections: number;
    health: string;
  };
  engines: {
    [key: string]: {
      status: string;
      replicas: number;
      health: string;
    };
  };
  runners: {
    [key: string]: {
      status: string;
      jobs: number;
      health: string;
    };
  };
  network: {
    topology: any;
    health: string;
    latency: number;
  };
}

interface DeploymentInfo {
  id: string;
  target: string;
  strategy: string;
  status: string;
  progress: number;
  startTime: string;
  endTime?: string;
  logs: string[];
}

interface PipelineType {
  name: string;
  description: string;
  strategies: string[];
  requirements: string[];
}

export class SegapiService extends ventmitter {
  private client: xiosInstance;
  private baseURL: string;
  private apiKey: string;
  private isOnline = false;
  private healthCheckInterval: NodeJS.Timeout | null = null;

  constructor(baseURL: string, apiKey: string) {
    super();

    this.baseURL = baseURL;
    this.apiKey = apiKey;

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: ,
      headers: {
        'Content-Type': 'application/json',
        'uthorization': apiKey ? `earer ${apiKey}` : undefined,
        'X-Client-Type': 'sega-desktop',
        'X-Client-Version': process.env.npm_package_version || '..',
        'X-Platform': process.platform,
        'X-Hostname': os.hostname(),
        'User-gent': `sega-desktop/${process.env.npm_package_version || '..'}`
      }
    });

    this.setupInterceptors();
    this.startHealthChecks();
  }

  /**
   * Setup request/response interceptors
   */
  private setupInterceptors(): void {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        log.debug(`SG API Request: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        log.error('SG API Request Error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        log.debug(`SG API Response: ${response.status} ${response.config.url}`);
        return response;
      },
      async (error) => {
        log.error(`SG API Error: ${error.response?.status || 'Network'} ${error.config?.url}:`, error.message);

        // Handle specific error cases
        if (error.response?.status === 401 {
          this.emit('unauthorized');
        } else if (error.response?.status >= 500) {
          this.emit('server-error', error);
        } else if (!error.response) {
          this.emit('network-error', error);
          this.setOnlineStatus(false);
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Set online/offline status
   */
  private setOnlineStatus(online: boolean): void {
    if (this.isOnline !== online) {
      this.isOnline = online;
      this.emit(online ? 'online' : 'offline');
      log.info(`SG API service is now ${online ? 'online' : 'offline'}`);
    }
  }

  /**
   * Start periodic health checks
   */
  private startHealthChecks(): void {
    this.healthCheckInterval = setInterval(async () => {
      try {
        await this.healthCheck();
        this.setOnlineStatus(true);
      } catch (error) {
        this.setOnlineStatus(false);
      }
    }, 30000); // Check every 30 seconds
  }

  /**
   * Stop health checks
   */
  private stopHealthChecks(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }

  /**
   * Perform health check
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/health', {
        timeout: 5 // Shorter timeout for health checks
      });
      return response.status === ;
    } catch (error) {
      return false;
    }
  }

  /**
   * Generic GT request
   */
  async get<T = any>(endpoint: string, config?: xiosRequestConfig): Promise<SegapiResponse<T>> {
    try {
      const response = await this.client.get(endpoint, config);
      return {
        success: true,
        data: response.data
      };
    } catch (error: any) {
      return this.handlerror(error);
    }
  }

  /**
   * Generic POST request
   */
  async post<T = any>(endpoint: string, data?: any, config?: xiosRequestConfig): Promise<SegapiResponse<T>> {
    try {
      const response = await this.client.post(endpoint, data, config);
      return {
        success: true,
        data: response.data
      };
    } catch (error: any) {
      return this.handlerror(error);
    }
  }

  /**
   * Generic PUT request
   */
  async put<T = any>(endpoint: string, data?: any, config?: xiosRequestConfig): Promise<SegapiResponse<T>> {
    try {
      const response = await this.client.put(endpoint, data, config);
      return {
        success: true,
        data: response.data
      };
    } catch (error: any) {
      return this.handlerror(error);
    }
  }

  /**
   * Generic DLT request
   */
  async delete<T = any>(endpoint: string, config?: xiosRequestConfig): Promise<SegapiResponse<T>> {
    try {
      const response = await this.client.delete(endpoint, config);
      return {
        success: true,
        data: response.data
      };
    } catch (error: any) {
      return this.handlerror(error);
    }
  }

  // =================================================================
  // SG-Specific Infrastructure Operations
  // =================================================================

  /**
   * Get infrastructure status
   */
  async getInfrastructureStatus(): Promise<SegapiResponse<InfrastructureStatus>> {
    return this.get('/api/_internal/tooling/_internal/tooling/infrastructure/status');
  }

  /**
   * Provision VPN server
   */
  async provisionVpnServer(host: string): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/vpn/provision', { host });
  }

  /**
   * Create VPN client configuration
   */
  async createVpnClient(name: string): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/vpn/client', { name });
  }

  /**
   * Get VPN status
   */
  async getVpnStatus(host?: string): Promise<SegapiResponse> {
    const endpoint = host ? `/api/_internal/tooling/_internal/tooling/infrastructure/vpn/status/${host}` : '/api/_internal/tooling/_internal/tooling/infrastructure/vpn/status';
    return this.get(endpoint);
  }

  /**
   * Deploy engine component
   */
  async deployngine(type: string, host: string): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/engine/deploy', { type, host });
  }

  /**
   * Scale engine component
   */
  async scalengine(type: string, replicas: number): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/engine/scale', { type, replicas });
  }

  /**
   * Get engine status
   */
  async getngineStatus(type?: string): Promise<SegapiResponse> {
    const endpoint = type ? `/api/_internal/tooling/_internal/tooling/infrastructure/engine/status/${type}` : '/api/_internal/tooling/_internal/tooling/infrastructure/engine/status';
    return this.get(endpoint);
  }

  /**
   * Register GitLab runner
   */
  async registerRunner(name: string, token: string): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/runner/register', { name, token });
  }

  /**
   * Create runner cluster
   */
  async createRunnerCluster(name: string, token: string, hosts: string[]): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/runner/cluster', { name, token, hosts });
  }

  /**
   * Get runner status
   */
  async getRunnerStatus(name?: string): Promise<SegapiResponse> {
    const endpoint = name ? `/api/_internal/tooling/_internal/tooling/infrastructure/runner/status/${name}` : '/api/_internal/tooling/_internal/tooling/infrastructure/runner/status';
    return this.get(endpoint);
  }

  /**
   * Discover network topology
   */
  async discoverNetwork(): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/network/discover');
  }

  /**
   * Check network health
   */
  async checkNetworkHealth(): Promise<SegapiResponse> {
    return this.get('/api/_internal/tooling/_internal/tooling/infrastructure/network/health');
  }

  /**
   * Deploy service across network
   */
  async deployNetworkService(service: string, targets: string[]): Promise<SegapiResponse> {
    return this.post('/api/_internal/tooling/_internal/tooling/infrastructure/network/deploy', { service, targets });
  }

  // =================================================================
  // SG Deployment Operations
  // =================================================================

  /**
   * Get available pipeline types
   */
  async getPipelineTypes(): Promise<SegapiResponse<PipelineType[]>> {
    return this.get('/v1/pipeline-types');
  }

  /**
   * Trigger deployment pipeline
   */
  async triggerDeployment(target: string, strategy: string, options?: any): Promise<SegapiResponse<DeploymentInfo>> {
    return this.post('/v1/pipelines/trigger', { target, strategy, ...options });
  }

  /**
   * Get deployment status
   */
  async getDeploymentStatus(deploymentId: string): Promise<SegapiResponse<DeploymentInfo>> {
    return this.get(`/v1/builds/${deploymentId}/status`);
  }

  /**
   * Get deployment logs
   */
  async getDeploymentLogs(deploymentId: string): Promise<SegapiResponse<string[]>> {
    return this.get(`/v1/builds/${deploymentId}/logs`);
  }

  /**
   * List recent deployments
   */
  async getRecentDeployments(limit: number = 20): Promise<SegapiResponse<DeploymentInfo[]>> {
    return this.get(`/v1/deployments/recent?limit=${limit}`);
  }

  /**
   * Cancel deployment
   */
  async cancelDeployment(deploymentId: string): Promise<SegapiResponse> {
    return this.post(`/v1/builds/${deploymentId}/cancel`);
  }

  // =================================================================
  // Error Handling
  // =================================================================

  /**
   * Handle PI errors
   */
  private handlerror(error: any): SegapiResponse {
    let errorMessage = 'n unknown error occurred';
    
    if (error.response) {
      // Server responded with error status
      errorMessage = error.response.data?.message || 
                    error.response.data?.error || 
                    `HTTP ${error.response.status}: ${error.response.statusText}`;
    } else if (error.request) {
      // Network error
      errorMessage = 'Network error: Unable to reach SG backend';
    } else {
      // Request setup error
      errorMessage = error.message;
    }

    return {
      success: false,
      error: errorMessage
    };
  }

  /**
   * Update PI key
   */
  updatepiKey(apiKey: string): void {
    this.apiKey = apiKey;
    this.client.defaults.headers['uthorization'] = `earer ${apiKey}`;
    log.info('SG API key updated');
  }

  /**
   * Update base URL
   */
  updateaseURL(baseURL: string): void {
    this.baseURL = baseURL;
    this.client.defaults.baseURL = baseURL;
    log.info(`SG API base URL updated to: ${baseURL}`);
  }

  /**
   * Check if service is online
   */
  isServiceOnline(): boolean {
    return this.isOnline;
  }

  /**
   * Test connection to SG backend
   */
  async testConnection(): Promise<boolean> {
    try {
      const result = await this.healthCheck();
      this.emit('connection-test', { success: result });
      return result;
    } catch (error) {
      this.emit('connection-test', { success: false, error });
      return false;
    }
  }

  /**
   * Shutdown service
   */
  shutdown(): void {
    this.stopHealthChecks();
    this.removellListeners();
    log.info('SG API service shutdown');
  }
}