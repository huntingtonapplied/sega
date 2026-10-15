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
 * Database Service
 * 
 * Handles local SQLite database operations for the {{PROJECT_DISPLAY_NAME}} desktop application.
 * Provides generic data access layer with sync support.
 */

import Database from 'better-sqlite3';
import * as path from 'path';
import * as fs from 'fs';
import log from 'electron-log';
import { v4 as uuidv4 } from 'uuid';

interface BaseEntity {
  id: string;
  createdAt: Date;
  updatedAt: Date;
}

interface SyncOperation {
  id: string;
  operationType: string;
  operationAction: string;
  resourceType: string;
  resourceId: string;
  data: string;
  status: string;
  error?: string;
  retryCount: number;
  createdAt: Date;
  syncedAt?: Date;
}

export class DatabaseService {
  private db: Database.Database | null = null;
  private readonly dbPath: string;
  private readonly projectName: string;

  constructor(dbPath: string, projectName = '{{PROJECT_NAME}}') {
    this.dbPath = dbPath;
    this.projectName = projectName;
  }

  /**
   * Initialize the database
   */
  async initialize(): Promise<void> {
    try {
      // Ensure directory exists
      const dir = path.dirname(this.dbPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      // Open database
      this.db = new Database(this.dbPath);
      
      // Enable foreign keys and WAL mode for better performance
      this.db.pragma('foreign_keys = ON');
      this.db.pragma('journal_mode = WAL');
      this.db.pragma('synchronous = NORMAL');
      this.db.pragma('cache_size = 1000');
      
      // Create base schema
      await this.createBaseSchema();
      
      // Create project-specific schema
      await this.createProjectSchema();
      
      log.info(`${this.projectName} database initialized successfully`);
    } catch (error) {
      log.error('Failed to initialize database:', error);
      throw error;
    }
  }

  /**
   * Create base database schema
   */
  private async createBaseSchema(): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    // Sync operations table (universal for all projects)
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS sync_operations (
        id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        operation_action TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        data TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        error TEXT,
        retry_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        synced_at TEXT
      )
    `);

    // System settings table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // AApplication logs table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS app_logs (
        id TEXT PRIMARY KEY,
        level TEXT NOT NULL,
        message TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // User preferences table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS user_preferences (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        preference_key TEXT NOT NULL,
        preference_value TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // File uploads/downloads tracking
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS file_operations (
        id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        status TEXT DEFAULT 'pending',
        progress INTEGER DEFAULT 0,
        error TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
      )
    `);

    // Create base indexes
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_sync_operations_status ON sync_operations(status);
      CREATE INDEX IF NOT EXISTS idx_sync_operations_resource ON sync_operations(resource_type, resource_id);
      CREATE INDEX IF NOT EXISTS idx_app_logs_level ON app_logs(level);
      CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);
      CREATE INDEX IF NOT EXISTS idx_file_operations_status ON file_operations(status);
    `);
  }

  /**
   * Create project-specific schema
   * Override this method in project-specific implementations
   */
  private async createProjectSchema(): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    // Generic data table for flexible schema
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS data_entities (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_data TEXT NOT NULL,
        sync_enabled INTEGER DEFAULT 1,
        last_synced TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Generic relationships table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS entity_relationships (
        id TEXT PRIMARY KEY,
        parent_id TEXT NOT NULL,
        child_id TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create indexes
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_data_entities_type ON data_entities(entity_type);
      CREATE INDEX IF NOT EXISTS idx_data_entities_sync ON data_entities(sync_enabled);
      CREATE INDEX IF NOT EXISTS idx_relationships_parent ON entity_relationships(parent_id);
      CREATE INDEX IF NOT EXISTS idx_relationships_child ON entity_relationships(child_id);
    `);
  }

  /**
   * Generic query method
   */
  async query(sql: string, params?: any[]): Promise<any[]> {
    if (!this.db) throw new Error('Database not initialized');

    try {
      const stmt = this.db.prepare(sql);
      const result = params ? stmt.all(...params) : stmt.all();
      return result;
    } catch (error) {
      log.error('Database query failed:', { sql, params, error });
      throw error;
    }
  }

  /**
   * Generic execute method for non-select queries
   */
  async execute(sql: string, params?: any[]): Promise<{ changes: number; lastInsertRowid: number }> {
    if (!this.db) throw new Error('Database not initialized');

    try {
      const stmt = this.db.prepare(sql);
      const result = params ? stmt.run(...params) : stmt.run();
      return { changes: result.changes, lastInsertRowid: Number(result.lastInsertRowid) };
    } catch (error) {
      log.error('Database execute failed:', { sql, params, error });
      throw error;
    }
  }

  /**
   * Create or update entity
   */
  async upsertEntity(entityType: string, entityData: any, createSyncOp = true): Promise<string> {
    if (!this.db) throw new Error('Database not initialized');

    const id = entityData.id || uuidv4();
    const dataJson = JSON.stringify(entityData);

    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO data_entities 
      (id, entity_type, entity_data, sync_enabled, last_synced, updated_at)
      VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `);

    stmt.run(id, entityType, dataJson, createSyncOp ? 1 : 0, null);

    if (createSyncOp) {
      await this.createSyncOperation(entityType, 'upsert', id, entityData);
    }

    return id;
  }

  /**
   * Get entity by ID
   */
  async getEntity(entityType: string, id: string): Promise<any | null> {
    if (!this.db) throw new Error('Database not initialized');

    const stmt = this.db.prepare(`
      SELECT entity_data FROM data_entities 
      WHERE entity_type = ? AND id = ?
    `);

    const row = stmt.get(entityType, id) as { entity_data: string } | undefined;
    return row ? JSON.parse(row.entity_data) : null;
  }

  /**
   * Get entities by type
   */
  async getEntitiesByType(entityType: string, limit?: number): Promise<any[]> {
    if (!this.db) throw new Error('Database not initialized');

    const sql = `
      SELECT entity_data FROM data_entities 
      WHERE entity_type = ? 
      ORDER BY created_at DESC
      ${limit ? 'LIMIT ?' : ''}
    `;

    const stmt = this.db.prepare(sql);
    const params = limit ? [entityType, limit] : [entityType];
    const rows = stmt.all(...params) as { entity_data: string }[];

    return rows.map(row => JSON.parse(row.entity_data));
  }

  /**
   * Delete entity
   */
  async deleteEntity(entityType: string, id: string, createSyncOp = true): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    if (createSyncOp) {
      await this.createSyncOperation(entityType, 'delete', id, { id });
    }

    const stmt = this.db.prepare(`
      DELETE FROM data_entities 
      WHERE entity_type = ? AND id = ?
    `);

    stmt.run(entityType, id);
  }

  /**
   * Search entities
   */
  async searchEntities(entityType: string, searchTerm: string): Promise<any[]> {
    if (!this.db) throw new Error('Database not initialized');

    const stmt = this.db.prepare(`
      SELECT entity_data FROM data_entities 
      WHERE entity_type = ? AND entity_data LIKE ?
      ORDER BY created_at DESC
    `);

    const rows = stmt.all(entityType, `%${searchTerm}%`) as { entity_data: string }[];
    return rows.map(row => JSON.parse(row.entity_data));
  }

  /**
   * Create sync operation
   */
  async createSyncOperation(
    resourceType: string,
    action: string,
    resourceId: string,
    data: any
  ): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    const stmt = this.db.prepare(`
      INSERT INTO sync_operations (id, operation_type, operation_action, 
        resource_type, resource_id, data)
      VALUES (?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      uuidv4(),
      `${resourceType}_sync`,
      action,
      resourceType,
      resourceId,
      JSON.stringify(data)
    );
  }

  /**
   * Get pending sync operations
   */
  async getPendingSyncOperations(): Promise<SyncOperation[]> {
    if (!this.db) throw new Error('Database not initialized');

    const rows = this.db.prepare(`
      SELECT * FROM sync_operations 
      WHERE status = 'pending' 
      ORDER BY created_at
    `).all();

    return rows.map((row: any) => ({
      ...row,
      data: JSON.parse(row.data),
      createdAt: new Date(row.created_at),
      syncedAt: row.synced_at ? new Date(row.synced_at) : undefined
    }));
  }

  /**
   * Mark operation as synced
   */
  async markOperationSynced(operationId: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    this.db.prepare(`
      UPDATE sync_operations 
      SET status = 'synced', synced_at = CURRENT_TIMESTAMP 
      WHERE id = ?
    `).run(operationId);
  }

  /**
   * Mark operation as failed
   */
  async markOperationFailed(operationId: string, error: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    this.db.prepare(`
      UPDATE sync_operations 
      SET status = 'failed', error = ? 
      WHERE id = ?
    `).run(error, operationId);
  }

  /**
   * Get failed sync operations
   */
  async getFailedSyncOperations(): Promise<SyncOperation[]> {
    if (!this.db) throw new Error('Database not initialized');

    const rows = this.db.prepare(`
      SELECT * FROM sync_operations 
      WHERE status = 'failed' 
      ORDER BY created_at DESC
    `).all();

    return rows.map((row: any) => ({
      ...row,
      data: JSON.parse(row.data),
      createdAt: new Date(row.created_at),
      syncedAt: row.synced_at ? new Date(row.synced_at) : undefined
    }));
  }

  /**
   * Clear failed sync operations
   */
  async clearFailedSyncOperations(): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');
    this.db.prepare('DELETE FROM sync_operations WHERE status = "failed"').run();
  }

  /**
   * Get last sync time
   */
  async getLastSyncTime(): Promise<Date | null> {
    if (!this.db) throw new Error('Database not initialized');

    const row = this.db.prepare(`
      SELECT value FROM system_settings WHERE key = 'last_sync_time'
    `).get() as { value: string } | undefined;

    return row ? new Date(row.value) : null;
  }

  /**
   * Update last sync time
   */
  async updateLastSyncTime(time: Date | null): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    if (time) {
      this.db.prepare(`
        INSERT OR REPLACE INTO system_settings (key, value) 
        VALUES ('last_sync_time', ?)
      `).run(time.toISOString());
    } else {
      this.db.prepare(`
        DELETE FROM system_settings WHERE key = 'last_sync_time'
      `).run();
    }
  }

  /**
   * Set application setting
   */
  async setSetting(key: string, value: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    this.db.prepare(`
      INSERT OR REPLACE INTO system_settings (key, value, updated_at) 
      VALUES (?, ?, CURRENT_TIMESTAMP)
    `).run(key, value);
  }

  /**
   * Get application setting
   */
  async getSetting(key: string): Promise<string | null> {
    if (!this.db) throw new Error('Database not initialized');

    const row = this.db.prepare(`
      SELECT value FROM system_settings WHERE key = ?
    `).get(key) as { value: string } | undefined;

    return row ? row.value : null;
  }

  /**
   * Log application event
   */
  async logEvent(level: string, message: string, metadata?: any): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    this.db.prepare(`
      INSERT INTO app_logs (id, level, message, metadata) 
      VALUES (?, ?, ?, ?)
    `).run(uuidv4(), level, message, metadata ? JSON.stringify(metadata) : null);
  }

  /**
   * Get application logs
   */
  async getLogs(level?: string, limit = 100): Promise<any[]> {
    if (!this.db) throw new Error('Database not initialized');

    const sql = level
      ? 'SELECT * FROM app_logs WHERE level = ? ORDER BY created_at DESC LIMIT ?'
      : 'SELECT * FROM app_logs ORDER BY created_at DESC LIMIT ?';

    const params = level ? [level, limit] : [limit];
    const rows = this.db.prepare(sql).all(...params);

    return rows.map((row: any) => ({
      ...row,
      metadata: row.metadata ? JSON.parse(row.metadata) : null,
      createdAt: new Date(row.created_at)
    }));
  }

  /**
   * Create relationship between entities
   */
  async createRelationship(
    parentId: string,
    childId: string,
    relationshipType: string,
    metadata?: any
  ): Promise<string> {
    if (!this.db) throw new Error('Database not initialized');

    const id = uuidv4();
    this.db.prepare(`
      INSERT INTO entity_relationships (id, parent_id, child_id, relationship_type, metadata)
      VALUES (?, ?, ?, ?, ?)
    `).run(id, parentId, childId, relationshipType, metadata ? JSON.stringify(metadata) : null);

    return id;
  }

  /**
   * Get entity relationships
   */
  async getRelationships(entityId: string, relationshipType?: string): Promise<any[]> {
    if (!this.db) throw new Error('Database not initialized');

    const sql = relationshipType
      ? `SELECT * FROM entity_relationships 
         WHERE (parent_id = ? OR child_id = ?) AND relationship_type = ?`
      : `SELECT * FROM entity_relationships 
         WHERE parent_id = ? OR child_id = ?`;

    const params = relationshipType ? [entityId, entityId, relationshipType] : [entityId, entityId];
    const rows = this.db.prepare(sql).all(...params);

    return rows.map((row: any) => ({
      ...row,
      metadata: row.metadata ? JSON.parse(row.metadata) : null,
      createdAt: new Date(row.created_at)
    }));
  }

  /**
   * Backup database
   */
  async backup(backupPath: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    try {
      this.db.backup(backupPath);
      log.info(`Database backed up to: ${backupPath}`);
    } catch (error) {
      log.error('Database backup failed:', error);
      throw error;
    }
  }

  /**
   * Get database statistics
   */
  async getStats(): Promise<{
    totalEntities: number;
    entitiesByType: Record<string, number>;
    pendingSyncOps: number;
    failedSyncOps: number;
    dbSize: number;
  }> {
    if (!this.db) throw new Error('Database not initialized');

    const totalEntities = this.db.prepare('SELECT COUNT(*) as count FROM data_entities').get() as { count: number };
    
    const entitiesByTypeRows = this.db.prepare(`
      SELECT entity_type, COUNT(*) as count 
      FROM data_entities 
      GROUP BY entity_type
    `).all() as { entity_type: string; count: number }[];

    const entitiesByType: Record<string, number> = {};
    entitiesByTypeRows.forEach(row => {
      entitiesByType[row.entity_type] = row.count;
    });

    const pendingSyncOps = this.db.prepare(`
      SELECT COUNT(*) as count FROM sync_operations WHERE status = 'pending'
    `).get() as { count: number };

    const failedSyncOps = this.db.prepare(`
      SELECT COUNT(*) as count FROM sync_operations WHERE status = 'failed'
    `).get() as { count: number };

    // Get database file size
    const stats = fs.statSync(this.dbPath);

    return {
      totalEntities: totalEntities.count,
      entitiesByType,
      pendingSyncOps: pendingSyncOps.count,
      failedSyncOps: failedSyncOps.count,
      dbSize: stats.size
    };
  }

  /**
   * Close database connection
   */
  async close(): Promise<void> {
    if (this.db) {
      this.db.close();
      this.db = null;
      log.info(`${this.projectName} database connection closed`);
    }
  }
}