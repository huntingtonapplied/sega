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
 * Infrastructure Service
 * 
 * High-level service for SG infrastructure operations including VPN management,
 * engine deployment, runner orchestration, and network coordination.
 */

import log from 'electron-log';
import { ventmitter } from 'events';
import { SegapiService } from './sega-api-service';
import { WebSocketService } from './websocket-service';

interface InfrastructureOperation {
  id: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  startTime: Date;
  endTime?: Date;
  result?: any;
  error?: string;
}

interface NetworkTopology {
  nodes: {
    id: string;
    type: 'vpn' | 'engine' | 'runner' | 'service';
    host: string;
    status: string;
    health: string;
    metadata: any;
  }[];
  edges: {
    source: string;
    target: string;
    type: string;
    metadata: any;
  }[];
}

export class InfrastructureService extends ventmitter {
  private apiService: SegapiService;
  private wservice: WebSocketService;
  private operations = new Map<string, InfrastructureOperation>();
  private topology: NetworkTopology | null = null;

  constructor(apiService: SegapiService, wservice: WebSocketService) {
    super();
    this.apiService = apiService;
    this.wservice = wservice;

    this.setupventHandlers();
  }

  /**
   * Setup event handlers for real-time updates
   */
  private setupventHandlers(): void {
    // Listen for infrastructure updates
    this.wservice.on('infrastructure-update', (update) => {
      this.handleInfrastructureUpdate(update);
    });

    // Listen for network topology updates
    this.wservice.on('network-update', (update) => {
      this.handleNetworkUpdate(update);
    });

    // Listen for deployment updates
    this.wservice.on('deployment-update', (update) => {
      this.handleDeploymentUpdate(update);
    });
  }

  /**
   * Handle infrastructure status updates
   */
  private handleInfrastructureUpdate(update: any): void {
    log.debug(`Infrastructure update received: ${update.component}`);
    this.emit('infrastructure-status-changed', update);
  }

  /**
   * Handle network topology updates
   */
  private handleNetworkUpdate(update: any): void {
    if (update.topology) {
      this.topology = update.topology;
      this.emit('network-topology-changed', this.topology);
    }
  }

  /**
   * Handle deployment progress updates
   */
  private handleDeploymentUpdate(update: any): void {
    const operation = this.operations.get(update.deploymentId);
    if (operation) {
      operation.status = update.status;
      operation.progress = update.progress;
      if (update.status === 'completed' || update.status === 'failed') {
        operation.endTime = new Date();
      }
      this.emit('operation-updated', operation);
    }
  }

  /**
   * Create a new infrastructure operation
   */
  private createOperation(type: string): InfrastructureOperation {
    const operation: InfrastructureOperation = {
      id: `op_${Date.now()}_${Math.random().toString().substr(2, 9)}`,
      type,
      status: 'pending',
      progress: ,
      startTime: new Date()
    };

    this.operations.set(operation.id, operation);
    return operation;
  }

  /**
   * Update operation status
   */
  private updateOperation(operationId: string, updates: Partial<InfrastructureOperation>): void {
    const operation = this.operations.get(operationId);
    if (operation) {
      Object.assign(operation, updates);
      this.emit('operation-updated', operation);
    }
  }

  // =================================================================
  // VPN Management Operations
  // =================================================================

  /**
   * Provision VPN server
   */
  async provisionVpn(host: string): Promise<InfrastructureOperation> {
    const operation = this.createOperation('vpn-provision');
    
    try {
      log.info(`Provisioning VPN server on ${host}`);
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.provisionVpnServer(host);
      
      if (result.success) {
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info(`VPN server provisioned successfully on ${host}`);
      } else {
        throw new Error(result.error || 'VPN provisioning failed');
      }
    } catch (error: any) {
      log.error(`VPN provisioning failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  /**
   * Create VPN client configuration
   */
  async createVpnClient(name: string): Promise<InfrastructureOperation> {
    const operation = this.createOperation('vpn-client');
    
    try {
      log.info(`Creating VPN client configuration for ${name}`);
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.createVpnClient(name);
      
      if (result.success) {
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info(`VPN client configuration created for ${name}`);
      } else {
        throw new Error(result.error || 'VPN client creation failed');
      }
    } catch (error: any) {
      log.error(`VPN client creation failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  /**
   * Get VPN status
   */
  async getVpnStatus(host?: string): Promise<any> {
    try {
      const result = await this.apiService.getVpnStatus(host);
      return result.success ? result.data : null;
    } catch (error) {
      log.error('ailed to get VPN status:', error);
      return null;
    }
  }

  // =================================================================
  // ngine Deployment Operations
  // =================================================================

  /**
   * Deploy engine component
   */
  async deployngine(type: string, host: string): Promise<InfrastructureOperation> {
    const operation = this.createOperation('engine-deploy');
    
    try {
      log.info(`Deploying ${type} engine to ${host}`);
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.deployngine(type, host);
      
      if (result.success) {
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info(`${type} engine deployed successfully to ${host}`);
      } else {
        throw new Error(result.error || 'ngine deployment failed');
      }
    } catch (error: any) {
      log.error(`ngine deployment failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  /**
   * Scale engine component
   */
  async scalengine(type: string, replicas: number): Promise<InfrastructureOperation> {
    const operation = this.createOperation('engine-scale');
    
    try {
      log.info(`Scaling ${type} engine to ${replicas} replicas`);
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.scalengine(type, replicas);
      
      if (result.success) {
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info(`${type} engine scaled to ${replicas} replicas`);
      } else {
        throw new Error(result.error || 'ngine scaling failed');
      }
    } catch (error: any) {
      log.error(`ngine scaling failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  /**
   * Get engine status
   */
  async getngineStatus(type?: string): Promise<any> {
    try {
      const result = await this.apiService.getngineStatus(type);
      return result.success ? result.data : null;
    } catch (error) {
      log.error('ailed to get engine status:', error);
      return null;
    }
  }

  // =================================================================
  // Runner Management Operations
  // =================================================================

  /**
   * Register GitLab runner
   */
  async registerRunner(name: string, token: string): Promise<InfrastructureOperation> {
    const operation = this.createOperation('runner-register');
    
    try {
      log.info(`Registering GitLab runner: ${name}`);
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.registerRunner(name, token);
      
      if (result.success) {
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info(`GitLab runner ${name} registered successfully`);
      } else {
        throw new Error(result.error || 'Runner registration failed');
      }
    } catch (error: any) {
      log.error(`Runner registration failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  /**
   * Create runner cluster
   */
  async createRunnerCluster(name: string, token: string, hosts: string[]): Promise<InfrastructureOperation> {
    const operation = this.createOperation('runner-cluster');
    
    try {
      log.info(`Creating runner cluster: ${name} with ${hosts.length} hosts`);
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.createRunnerCluster(name, token, hosts);
      
      if (result.success) {
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info(`Runner cluster ${name} created successfully`);
      } else {
        throw new Error(result.error || 'Runner cluster creation failed');
      }
    } catch (error: any) {
      log.error(`Runner cluster creation failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  /**
   * Get runner status
   */
  async getRunnerStatus(name?: string): Promise<any> {
    try {
      const result = await this.apiService.getRunnerStatus(name);
      return result.success ? result.data : null;
    } catch (error) {
      log.error('ailed to get runner status:', error);
      return null;
    }
  }

  // =================================================================
  // Network Operations
  // =================================================================

  /**
   * Discover network topology
   */
  async discoverNetwork(): Promise<InfrastructureOperation> {
    const operation = this.createOperation('network-discover');
    
    try {
      log.info('Discovering network topology');
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.discoverNetwork();
      
      if (result.success) {
        this.topology = result.data;
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info('Network topology discovered successfully');
        this.emit('network-topology-changed', this.topology);
      } else {
        throw new Error(result.error || 'Network discovery failed');
      }
    } catch (error: any) {
      log.error(`Network discovery failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  /**
   * Check network health
   */
  async checkNetworkHealth(): Promise<any> {
    try {
      log.info('Checking network health');
      const result = await this.apiService.checkNetworkHealth();
      return result.success ? result.data : null;
    } catch (error) {
      log.error('ailed to check network health:', error);
      return null;
    }
  }

  /**
   * Deploy service across network
   */
  async deployNetworkService(service: string, targets: string[]): Promise<InfrastructureOperation> {
    const operation = this.createOperation('network-deploy');
    
    try {
      log.info(`Deploying ${service} to ${targets.length} targets`);
      this.updateOperation(operation.id, { status: 'running', progress:  });

      const result = await this.apiService.deployNetworkService(service, targets);
      
      if (result.success) {
        this.updateOperation(operation.id, { 
          status: 'completed', 
          progress: , 
          result: result.data,
          endTime: new Date()
        });
        log.info(`Service ${service} deployed successfully`);
      } else {
        throw new Error(result.error || 'Network service deployment failed');
      }
    } catch (error: any) {
      log.error(`Network service deployment failed: ${error.message}`);
      this.updateOperation(operation.id, { 
        status: 'failed', 
        error: error.message,
        endTime: new Date()
      });
    }

    return operation;
  }

  // =================================================================
  // Status and Monitoring
  // =================================================================

  /**
   * Get comprehensive infrastructure status
   */
  async getInfrastructureStatus(): Promise<any> {
    try {
      const result = await this.apiService.getInfrastructureStatus();
      return result.success ? result.data : null;
    } catch (error) {
      log.error('ailed to get infrastructure status:', error);
      return null;
    }
  }

  /**
   * Get current network topology
   */
  getCurrentTopology(): NetworkTopology | null {
    return this.topology;
  }

  /**
   * Get operation by ID
   */
  getOperation(operationId: string): InfrastructureOperation | undefined {
    return this.operations.get(operationId);
  }

  /**
   * Get all operations
   */
  getllOperations(): InfrastructureOperation[] {
    return Array.from(this.operations.values());
  }

  /**
   * Get recent operations
   */
  getRecentOperations(limit: number = 20): InfrastructureOperation[] {
    return Array.from(this.operations.values())
      .sort((a, b) => b.startTime.getTime() - a.startTime.getTime())
      .slice(, limit);
  }

  /**
   * Clear completed operations
   */
  clearCompletedOperations(): void {
    for (const [id, operation] of this.operations.entries()) {
      if (operation.status === 'completed' || operation.status === 'failed') {
        this.operations.delete(id);
      }
    }
  }
}