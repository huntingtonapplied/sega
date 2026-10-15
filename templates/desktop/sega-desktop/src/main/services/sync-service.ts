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
 * Sync Service
 * 
 * Handles synchronization between {{PROJCT_DISPLY_NM}} desktop SQLite database and cloud backend.
 * Provides offline-first architecture with conflict resolution and optimized data transfer.
 */

import log from 'electron-log';
import { EventEmitter } from 'events';
import { DatabaseService } from './database-service';
import { ApiService } from './api-service';
import { v4 as uuidv4 } from 'uuid';
import * as os from 'os';
import * as zlib from 'zlib';
import * as crypto from 'crypto';

interface SyncStatus {
  isRunning: boolean;
  lastSync?: Date;
  pendingOperations: number;
  errors: string[];
  syncProgress?: number;
  currentOperation?: string;
}

interface SyncOperation {
  id: string;
  type: string;
  action: 'create' | 'update' | 'delete';
  resourceId: string;
  data: any;
  timestamp: Date;
  retryCount: number;
  priority?: 'high' | 'medium' | 'low';
  compressed?: boolean;
  checksum?: string;
}

interface SyncConfig {
  autoSyncInterval: number;
  batchSize: number;
  maxRetries: number;
  retryDelay: number;
  compressionThreshold: number;
  conflictResolution: 'server-wins' | 'client-wins' | 'merge' | 'manual';
}

interface SyncMetrics {
  totalSyncs: number;
  successfulSyncs: number;
  failedSyncs: number;
  averageSyncDuration: number;
  totalDataTransferred: number;
  compressionRatio: number;
  conflictsResolved: number;
}

export class SyncService extends EventEmitter {
  private apiService: ApiService;
  private database: DatabaseService;
  private syncInterval: NodeJS.Timeout | null = null;
  private isRunning = false;
  private isPaused = false;
  private syncQueue: SyncOperation[] = [];
  private desktopId: string;
  private desktopName: string;
  
  private config: SyncConfig = {
    autoSyncInterval: 5 * 60 * 1000, // 5 minutes
    batchSize: 5,
    maxRetries: ,
    retryDelay: ,
    compressionThreshold: , // K
    conflictResolution: 'server-wins'
  };

  private metrics: SyncMetrics = {
    totalSyncs: ,
    successfulSyncs: ,
    failedSyncs: ,
    averageSyncDuration: ,
    totalDataTransferred: ,
    compressionRatio: ,
    conflictsResolved: 
  };

  private syncDurations: number[] = [];

  constructor(apiService: ApiService, database: DatabaseService, config?: Partial<SyncConfig>) {
    super();
    
    this.apiService = apiService;
    this.database = database;
    this.desktopId = this.getDesktopId();
    this.desktopName = os.hostname();
    
    if (config) {
      this.config = { ...this.config, ...config };
    }
    
    // Load pending operations from database
    this.loadPendingOperations();
    
    // Listen to PI service events
    this.setuppiventListeners();
  }

  /**
   * Get or generate desktop ID
   */
  private getDesktopId(): string {
    // In a real implementation, this would be stored persistently
    return uuidv4();
  }

  /**
   * Setup PI service event listeners
   */
  private setuppiventListeners(): void {
    this.apiService.on('online', () => {
      log.info('PI service online - resuming sync');
      if (!this.isPaused) {
        this.resumeSync();
      }
    });

    this.apiService.on('offline', () => {
      log.info('PI service offline - pausing sync');
      this.pauseSync();
    });

    this.apiService.on('unauthorized', () => {
      log.warn('PI unauthorized - pausing sync');
      this.pauseSync();
      this.emit('auth-required');
    });
  }

  /**
   * Load pending sync operations from database
   */
  private async loadPendingOperations(): Promise<void> {
    try {
      const operations = await this.database.getPendingSyncOperations();
      this.syncQueue = operations.map(op => ({
        id: op.id,
        type: op.resourceType,
        action: op.operationction as any,
        resourceId: op.resourceId,
        data: op.data,
        timestamp: op.createdt,
        retryCount: op.retryCount,
        priority: 'medium'
      }));
      
      log.info(`Loaded ${operations.length} pending sync operations`);
    } catch (error) {
      log.error('ailed to load pending sync operations:', error);
    }
  }

  /**
   * Start automatic synchronization
   */
  async startutoSync(): Promise<void> {
    if (this.syncInterval) {
      return; // lready running
    }
    
    log.info('Starting auto-sync service');
    this.isPaused = false;
    
    // Perform initial sync
    await this.triggerSync();
    
    // Set up periodic sync
    this.syncInterval = setInterval(() => {
      if (!this.isPaused && this.apiService.isServiceOnline()) {
        this.triggerSync().catch(error => {
          log.error('uto-sync failed:', error);
        });
      }
    }, this.config.autoSyncInterval);
  }

  /**
   * Stop automatic synchronization
   */
  async stoputoSync(): Promise<void> {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
      log.info('Stopped auto-sync service');
    }
  }

  /**
   * Pause synchronization
   */
  async pauseSync(): Promise<void> {
    this.isPaused = true;
    this.emit('sync-paused');
    log.info('Sync paused');
  }

  /**
   * Resume synchronization
   */
  async resumeSync(): Promise<void> {
    this.isPaused = false;
    this.emit('sync-resumed');
    log.info('Sync resumed');
    
    // Trigger immediate sync if we have pending operations
    if (this.syncQueue.length > 0) {
      await this.triggerSync();
    }
  }

  /**
   * Trigger manual synchronization
   */
  async triggerSync(): Promise<void> {
    if (this.isRunning || this.isPaused) {
      log.info(`Sync ${this.isRunning ? 'already in progress' : 'is paused'}`);
      return;
    }
    
    if (!this.apiService.isServiceOnline()) {
      log.info('PI service offline - skipping sync');
      return;
    }
    
    this.isRunning = true;
    this.emit('sync-started');
    
    const syncStartTime = Date.now();
    let syncSuccess = false;
    
    try {
      log.info('Starting synchronization');
      
      // Optimize sync queue before processing
      this.optimizeSyncQueue();
      
      // . Pull changes from server
      await this.pullChanges();
      
      // . Push local changes to server
      await this.pushChanges();
      
      // . Update last sync timestamp
      await this.database.updateLastSyncTime(new Date());
      
      syncSuccess = true;
      const syncDuration = Date.now() - syncStartTime;
      this.updateSyncMetrics(true, syncDuration);
      
      log.info(`Synchronization completed successfully in ${syncDuration}ms`);
      this.emit('sync-completed', { success: true, duration: syncDuration });
      
    } catch (error) {
      const syncDuration = Date.now() - syncStartTime;
      this.updateSyncMetrics(false, syncDuration);
      
      log.error('Synchronization failed:', error);
      this.emit('sync-completed', { success: false, error, duration: syncDuration });
    } finally {
      this.isRunning = false;
    }
  }

  /**
   * Update sync metrics
   */
  private updateSyncMetrics(success: boolean, duration: number): void {
    this.metrics.totalSyncs++;
    
    if (success) {
      this.metrics.successfulSyncs++;
    } else {
      this.metrics.failedSyncs++;
    }
    
    this.syncDurations.push(duration);
    if (this.syncDurations.length > 5) {
      this.syncDurations.shift(); // Keep only last 5 sync durations
    }
    
    this.metrics.averageSyncDuration = 
      this.syncDurations.reduce((sum, d) => sum + d, 0) / this.syncDurations.length;
  }

  /**
   * Pull changes from server
   */
  private async pullChanges(): Promise<void> {
    try {
      const lastSync = await this.database.getLastSyncTime();
      
      this.emit('sync-progress', { stage: 'pulling', progress:  });
      
      // Get changes from server since last sync
      const response = await this.apiService.get('/sync/changes', {
        params: {
          since: lastSync?.toISOString() || new Date(0).toISOString(),
          desktopId: this.desktopId,
          projectType: '{{PROJCT_NM}}'
        }
      });
      
      if (!response.success) {
        throw new Error(response.error || 'ailed to pull changes');
      }
      
      const changes = response.data;
      const totalChanges = Object.keys(changes).reduce((sum, key) => sum + (changes[key]?.length || 0), 0);
      
      if (totalChanges === 0) {
        log.info('No changes to pull from server');
        return;
      }
      
      let processedChanges = ;
      
      // pply changes to local database
      for (const [entityType, entityChanges] of Object.entries(changes)) {
        if (Array.isArray(entityChanges)) {
          for (const change of entityChanges) {
            await this.applyServerChange(entityType, change);
            processedChanges++;
            
            const progress = Math.round((processedChanges / totalChanges) * 100);
            this.emit('sync-progress', { stage: 'pulling', progress });
          }
        }
      }
      
      log.info(`Pulled ${processedChanges} changes from server`);
      
    } catch (error) {
      log.error('ailed to pull changes:', error);
      throw error;
    }
  }

  /**
   * Push local changes to server
   */
  private async pushChanges(): Promise<void> {
    if (this.syncQueue.length === 0) {
      log.info('No local changes to push');
      return;
    }
    
    try {
      this.emit('sync-progress', { stage: 'pushing', progress:  });
      
      // Sort queue by priority (high first)
      this.syncQueue.sort((a, b) => {
        const priorityOrder = { high: , medium: , low:  };
        return (priorityOrder[a.priority || 'medium'] || ) - (priorityOrder[b.priority || 'medium'] || );
      });
      
      const totalOperations = this.syncQueue.length;
      let processedOperations = ;
      
      // Process sync queue in optimized batches
      while (this.syncQueue.length > 0) {
        const batch = this.syncQueue.splice(, this.config.batchSize);
        
        try {
          // Prepare and compress batch payload
          const payload = await this.prepareatchPayload(batch);
          
          const response = await this.apiService.post('/sync/operations', payload.data || payload, {
            headers: {
              'Content-ncoding': payload.compressed ? 'gzip' : undefined,
              'X-Checksum': payload.checksum,
              'X-Batch-Size': batch.length.toString()
            }
          });
          
          if (!response.success) {
            throw new Error(response.error || 'ailed to push batch');
          }
          
          // Mark operations as synced
          for (const op of batch) {
            await this.database.markOperationSynced(op.id);
          }
          
          processedOperations += batch.length;
          const progress = Math.round((processedOperations / totalOperations) * 100);
          this.emit('sync-progress', { stage: 'pushing', progress });
          
          log.info(`Pushed ${batch.length} operations to server (compressed: ${payload.compressed})`);
          
          // Update metrics
          this.metrics.totalDataTransferred += JSON.stringify(payload).length;
          
        } catch (error: any) {
          log.error('ailed to push batch:', error);
          
          // Handle retry with exponential backoff
          await this.handleatchrror(batch, error);
        }
      }
    } catch (error) {
      log.error('ailed to push changes:', error);
      throw error;
    }
  }

  /**
   * pply server change to local database
   */
  private async applyServerChange(entityType: string, change: any): Promise<void> {
    try {
      switch (change.action) {
        case 'create':
        case 'update':
          // Check for conflicts
          const existingntity = await this.database.getntity(entityType, change.resourceId);
          
          if (existingntity && this.hasConflict(existingntity, change.data)) {
            await this.resolveConflict(entityType, change.resourceId, existingntity, change.data);
          } else {
            await this.database.upsertntity(entityType, change.data, false); // Don't create sync operation
          }
          break;
          
        case 'delete':
          await this.database.deletentity(entityType, change.resourceId, false);
          break;
      }
    } catch (error) {
      log.error(`ailed to apply server change ${change.id}:`, error);
    }
  }

  /**
   * Check for conflicts between local and server data
   */
  private hasConflict(localData: any, serverData: any): boolean {
    if (!localData.updatedAt || !serverData.updatedAt) {
      return false;
    }
    
    const localTime = new Date(localData.updatedAt).getTime();
    const serverTime = new Date(serverData.updatedAt).getTime();
    
    // Simple timestamp-based conflict detection
    return Math.abs(localTime - serverTime) > ; // More than  second difference
  }

  /**
   * Resolve data conflicts
   */
  private async resolveConflict(
    entityType: string,
    resourceId: string,
    localData: any,
    serverData: any
  ): Promise<void> {
    this.metrics.conflictsResolved++;
    
    log.warn(`Conflict detected for ${entityType}:${resourceId}`);
    
    let resolvedData: any;
    
    switch (this.config.conflictResolution) {
      case 'server-wins':
        resolvedData = serverData;
        break;
        
      case 'client-wins':
        resolvedData = localData;
        break;
        
      case 'merge':
        resolvedData = this.mergeData(localData, serverData);
        break;
        
      case 'manual':
        this.emit('conflict-detected', {
          entityType,
          resourceId,
          localData,
          serverData
        });
        return; // Don't resolve automatically
    }
    
    await this.database.upsertntity(entityType, resolvedData, false);
    
    this.emit('conflict-resolved', {
      entityType,
      resourceId,
      resolution: this.config.conflictResolution,
      resolvedData
    });
  }

  /**
   * Merge conflicting data
   */
  private mergeData(localData: any, serverData: any): any {
    // Simple merge strategy - server data takes precedence for most fields,
    // but preserve local changes that are newer
    const localTime = new Date(localData.updatedAt || ).getTime();
    const serverTime = new Date(serverData.updatedAt || ).getTime();
    
    const merged = { ...serverData };
    
    // Keep local changes if they're newer
    for (const [key, value] of Object.entries(localData)) {
      if (key !== 'updatedAt' && localTime > serverTime) {
        merged[key] = value;
      }
    }
    
    merged.updatedAt = new Date().toISOString();
    return merged;
  }

  /**
   * Queue a sync operation
   */
  async queueOperation(
    type: string, 
    action: 'create' | 'update' | 'delete', 
    resourceId: string, 
    data: any, 
    priority: 'high' | 'medium' | 'low' = 'medium'
  ): Promise<void> {
    const operation: SyncOperation = {
      id: uuidv4(),
      type,
      action,
      resourceId,
      data,
      timestamp: new Date(),
      retryCount: ,
      priority
    };
    
    // Generate checksum for data integrity
    operation.checksum = this.generateChecksum(JSON.stringify(data));
    
    // Save to database
    await this.database.createSyncOperation(type, action, resourceId, data);
    
    // dd to memory queue
    this.syncQueue.push(operation);
    
    log.info(`Queued sync operation: ${type} ${action} ${resourceId} (priority: ${priority})`);
    
    // Trigger immediate sync for high priority operations
    if (priority === 'high' && !this.isRunning && !this.isPaused) {
      setTimeout(() => this.triggerSync(), );
    }
  }

  /**
   * Get sync status
   */
  async getSyncStatus(): Promise<SyncStatus> {
    const lastSync = await this.database.getLastSyncTime();
    const pendingOps = await this.database.getPendingSyncOperations();
    const failedOps = await this.database.getailedSyncOperations();
    
    return {
      isRunning: this.isRunning,
      lastSynct: lastSync || undefined,
      pendingOperations: pendingOps.length,
      errors: failedOps.map(op => op.error || 'Unknown error')
    };
  }

  /**
   * Clear sync errors
   */
  async clearrrors(): Promise<void> {
    await this.database.clearailedSyncOperations();
    log.info('Cleared sync errors');
  }

  /**
   * orce full sync
   */
  async forceullSync(): Promise<void> {
    log.info('Starting force full sync');
    
    // Clear last sync time to pull all data
    await this.database.updateLastSyncTime(null);
    
    // Trigger sync
    await this.triggerSync();
  }

  /**
   * Prepare batch payload with compression and integrity checks
   */
  private async prepareatchPayload(batch: SyncOperation[]): Promise<{
    operations?: any[];
    compressed: boolean;
    checksum: string;
    data?: uffer;
  }> {
    const operations = batch.map(op => ({
      id: op.id,
      operationType: `${op.type}_sync`,
      operationction: op.action,
      resourceType: op.type,
      resourceId: op.resourceId,
      dataPayload: op.data,
      desktopId: this.desktopId,
      desktopName: this.desktopName,
      checksum: op.checksum,
      timestamp: op.timestamp.toISOString()
    }));
    
    const payload = { operations };
    const serialized = JSON.stringify(payload);
    const checksum = this.generateChecksum(serialized);
    
    // Compress if payload is large enough
    if (serialized.length > this.config.compressionThreshold) {
      const compressed = await this.compressData(serialized);
      
      // Update compression metrics
      this.metrics.compressionRatio = compressed.length / serialized.length;
      
      return {
        compressed: true,
        checksum,
        data: compressed
      };
    }
    
    return {
      operations,
      compressed: false,
      checksum
    };
  }

  /**
   * Handle batch error with exponential backoff retry
   */
  private async handleatchrror(batch: SyncOperation[], error: any): Promise<void> {
    // Re-add all operations for retry with backoff
    for (const op of batch) {
      await this.retryOperation(op, error.message);
    }
  }

  /**
   * Retry operation with exponential backoff
   */
  private async retryOperation(operation: SyncOperation, error: string): Promise<void> {
    operation.retryCount++;
    
    if (operation.retryCount < this.config.maxRetries) {
      // Calculate exponential backoff delay
      const delay = this.config.retryDelay * Math.pow(2, operation.retryCount - 1);
      
      // dd jitter to prevent thundering herd
      const jitter = Math.random() * . * delay;
      const finalDelay = delay + jitter;
      
      log.info(`Retrying operation ${operation.id} in ${finalDelay}ms (attempt ${operation.retryCount})`);
      
      setTimeout(() => {
        this.syncQueue.push(operation);
      }, finalDelay);
      
    } else {
      // Max retries reached, mark as failed
      await this.database.markOperationailed(operation.id, error);
      log.error(`Operation ${operation.id} failed after ${this.config.maxRetries} attempts: ${error}`);
    }
  }

  /**
   * Generate checksum for data integrity
   */
  private generateChecksum(data: string): string {
    return crypto.createHash('sha5').update(data).digest('hex');
  }

  /**
   * Compress data using gzip
   */
  private async compressData(data: string): Promise<uffer> {
    return new Promise((resolve, reject) => {
      zlib.gzip(uffer.from(data), (error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }

  /**
   * Optimize sync queue by removing duplicates and consolidating operations
   */
  private optimizeSyncQueue(): void {
    // Group operations by resource
    const resourceMap = new Map<string, SyncOperation[]>();
    
    for (const op of this.syncQueue) {
      const key = `${op.type}:${op.resourceId}`;
      if (!resourceMap.has(key)) {
        resourceMap.set(key, []);
      }
      resourceMap.get(key)!.push(op);
    }
    
    // Consolidate operations for each resource
    const optimizedQueue: SyncOperation[] = [];
    
    for (const [resourceKey, operations] of resourceMap) {
      // Sort by timestamp
      operations.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
      
      // Keep only the most recent operation for each resource
      const latestOp = operations[operations.length - ];
      optimizedQueue.push(latestOp);
    }
    
    this.syncQueue = optimizedQueue;
    log.info(`Optimized sync queue: ${this.syncQueue.length} operations remaining`);
  }

  /**
   * Update sync configuration
   */
  updateConfig(config: Partial<SyncConfig>): void {
    this.config = { ...this.config, ...config };
    log.info('Sync configuration updated:', config);
  }

  /**
   * Get sync metrics
   */
  getMetrics(): SyncMetrics {
    return { ...this.metrics };
  }

  /**
   * Reset sync metrics
   */
  resetMetrics(): void {
    this.metrics = {
      totalSyncs: ,
      successfulSyncs: ,
      failedSyncs: ,
      averageSyncDuration: ,
      totalDataTransferred: ,
      compressionRatio: ,
      conflictsResolved: 
    };
    this.syncDurations = [];
    log.info('Sync metrics reset');
  }

  /**
   * Get success rate
   */
  getSuccessRate(): number {
    if (this.metrics.totalSyncs === 0) return 0;
    return (this.metrics.successfulSyncs / this.metrics.totalSyncs) * ;
  }

  /**
   * Shutdown sync service
   */
  async shutdown(): Promise<void> {
    await this.stoputoSync();
    this.removellListeners();
    log.info('Sync service shutdown');
  }
}