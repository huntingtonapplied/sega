-- SEGA Infrastructure Orchestration Desktop Application Database Schema
-- Copyright 2022-2026 Huntington Applied
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

PRAGMA foreign_keys = ON;

-- =================================================================
-- INFRASTRUCTURE COMPONENTS
-- =================================================================

-- VPN Servers and Clients
CREATE TABLE vpn_servers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  host TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending',
  config TEXT, -- JSON configuration
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vpn_clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  server_id INTEGER,
  config TEXT, -- JSON configuration
  status TEXT NOT NULL DEFAULT 'active',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (server_id) REFERENCES vpn_servers(id) ON DELETE SET NULL
);

-- Engine Components (e.g. atlas, hermes, orion, FPGA)
CREATE TABLE engines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL, -- e.g. 'atlas', 'hermes', 'orion', 'fpga'
  name TEXT NOT NULL,
  host TEXT NOT NULL,
  port INTEGER,
  replicas INTEGER DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'pending',
  health TEXT DEFAULT 'unknown',
  config TEXT, -- JSON configuration
  metrics TEXT, -- JSON metrics data
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(type, name)
);

-- GitLab Runners
CREATE TABLE runners (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  token TEXT NOT NULL,
  host TEXT NOT NULL,
  cluster_name TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  jobs_running INTEGER DEFAULT 0,
  jobs_completed INTEGER DEFAULT 0,
  config TEXT, -- JSON configuration
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Network Topology Nodes
CREATE TABLE network_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL, -- 'vpn', 'engine', 'runner', 'service'
  host TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unknown',
  health TEXT DEFAULT 'unknown',
  metadata TEXT, -- JSON metadata
  discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Network Connections/Edges
CREATE TABLE network_edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_node TEXT NOT NULL,
  target_node TEXT NOT NULL,
  type TEXT NOT NULL, -- 'vpn', 'service', 'data'
  latency REAL,
  bandwidth REAL,
  metadata TEXT, -- JSON metadata
  discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_node) REFERENCES network_nodes(node_id),
  FOREIGN KEY (target_node) REFERENCES network_nodes(node_id),
  UNIQUE(source_node, target_node, type)
);

-- =================================================================
-- DEPLOYMENTS AND OPERATIONS
-- =================================================================

-- Infrastructure Operations (provision, deploy, scale, etc.)
CREATE TABLE infrastructure_operations (
  id TEXT PRIMARY KEY, -- UUID
  type TEXT NOT NULL, -- 'vpn-provision', 'engine-deploy', etc.
  status TEXT NOT NULL DEFAULT 'pending',
  progress INTEGER DEFAULT 0,
  target TEXT, -- Host, service, or component target
  config TEXT, -- JSON operation configuration
  result TEXT, -- JSON operation result
  error TEXT, -- Error message if failed
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  created_by TEXT DEFAULT 'desktop'
);

-- Deployment History
CREATE TABLE deployments (
  id TEXT PRIMARY KEY, -- UUID from SEGA backend
  target TEXT NOT NULL,
  strategy TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  progress INTEGER DEFAULT 0,
  logs TEXT, -- JSON array of log entries
  metadata TEXT, -- JSON deployment metadata
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  triggered_by TEXT DEFAULT 'desktop'
);

-- =================================================================
-- MONITORING AND METRICS
-- =================================================================

-- System Metrics (CPU, memory, network, etc.)
CREATE TABLE system_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT NOT NULL,
  metric_type TEXT NOT NULL, -- 'cpu', 'memory', 'network', 'disk'
  value REAL NOT NULL,
  unit TEXT, -- 'percent', 'bytes', 'mbps', etc.
  metadata TEXT, -- JSON additional data
  recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (node_id) REFERENCES network_nodes(node_id)
);

-- Infrastructure Health Checks
CREATE TABLE health_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  component_type TEXT NOT NULL, -- 'vpn', 'engine', 'runner', 'network'
  component_id TEXT NOT NULL,
  status TEXT NOT NULL, -- 'healthy', 'warning', 'critical', 'unknown'
  message TEXT,
  details TEXT, -- JSON health check details
  checked_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Alerts and Notifications
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  severity TEXT NOT NULL, -- 'info', 'warning', 'error', 'critical'
  source TEXT NOT NULL, -- Component that generated the alert
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  metadata TEXT, -- JSON alert metadata
  acknowledged BOOLEAN DEFAULT FALSE,
  resolved BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  acknowledged_at DATETIME,
  resolved_at DATETIME
);

-- =================================================================
-- CONFIGURATION AND SETTINGS
-- =================================================================

-- Application Settings
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  type TEXT DEFAULT 'string', -- 'string', 'number', 'boolean', 'json'
  category TEXT DEFAULT 'general',
  description TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Configuration Templates
CREATE TABLE config_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL, -- 'vpn', 'engine', 'runner', 'deployment'
  template TEXT NOT NULL, -- JSON template
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =================================================================
-- SYNC AND BACKUP
-- =================================================================

-- Sync Status with SEGA Backend
CREATE TABLE sync_status (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  table_name TEXT NOT NULL UNIQUE,
  last_sync DATETIME,
  sync_hash TEXT, -- Hash of last synced data
  records_synced INTEGER DEFAULT 0,
  sync_errors INTEGER DEFAULT 0,
  last_error TEXT
);

-- Configuration Backups
CREATE TABLE config_backups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  backup_type TEXT NOT NULL, -- 'full', 'incremental'
  data TEXT NOT NULL, -- JSON backup data
  checksum TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  restored_at DATETIME
);

-- =================================================================
-- INDEXES FOR PERFORMANCE
-- =================================================================

-- Infrastructure queries
CREATE INDEX idx_vpn_servers_status ON vpn_servers(status);
CREATE INDEX idx_engines_type_status ON engines(type, status);
CREATE INDEX idx_runners_cluster_status ON runners(cluster_name, status);
CREATE INDEX idx_network_nodes_type ON network_nodes(type);

-- Operations and deployments
CREATE INDEX idx_operations_type_status ON infrastructure_operations(type, status);
CREATE INDEX idx_operations_started_at ON infrastructure_operations(started_at);
CREATE INDEX idx_deployments_status ON deployments(status);
CREATE INDEX idx_deployments_started_at ON deployments(started_at);

-- Monitoring
CREATE INDEX idx_metrics_node_type ON system_metrics(node_id, metric_type);
CREATE INDEX idx_metrics_recorded_at ON system_metrics(recorded_at);
CREATE INDEX idx_health_checks_component ON health_checks(component_type, component_id);
CREATE INDEX idx_alerts_severity_resolved ON alerts(severity, resolved);

-- =================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- =================================================================

-- Update timestamps on record changes
CREATE TRIGGER vpn_servers_updated_at
  AFTER UPDATE ON vpn_servers
  BEGIN
    UPDATE vpn_servers SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END;

CREATE TRIGGER engines_updated_at
  AFTER UPDATE ON engines
  BEGIN
    UPDATE engines SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END;

CREATE TRIGGER runners_updated_at
  AFTER UPDATE ON runners
  BEGIN
    UPDATE runners SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END;

CREATE TRIGGER network_nodes_updated_at
  AFTER UPDATE ON network_nodes
  BEGIN
    UPDATE network_nodes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END;

-- =================================================================
-- INITIAL DATA
-- =================================================================

-- Default settings
INSERT INTO settings (key, value, type, category, description) VALUES
('sega_api_url', 'http://localhost:5000', 'string', 'api', 'SEGA API base URL'),
('sega_ws_url', 'ws://localhost:5001', 'string', 'api', 'SEGA WebSocket URL'),
('auto_sync', 'true', 'boolean', 'sync', 'Enable automatic synchronization'),
('sync_interval', '30', 'number', 'sync', 'Sync interval in seconds'),
('real_time_updates', 'true', 'boolean', 'ui', 'Enable real-time updates via WebSocket'),
('minimize_to_tray', 'true', 'boolean', 'ui', 'Minimize to system tray'),
('dashboard_refresh_rate', '5', 'number', 'ui', 'Dashboard refresh rate in seconds'),
('max_log_entries', '1000', 'number', 'logging', 'Maximum log entries to store'),
('backup_retention_days', '30', 'number', 'backup', 'Days to retain backups');

-- Default configuration templates
INSERT INTO config_templates (name, type, template, description) VALUES
('default_vpn_server', 'vpn', '{"port": 1194, "protocol": "udp", "encryption": "AES-256-GCM"}', 'Default VPN server configuration'),
('atlas_engine', 'engine', '{"memory": "2Gi", "cpu": "1", "gpu": false}', 'Atlas engine default configuration'),
('hermes_engine', 'engine', '{"memory": "4Gi", "cpu": "2", "gpu": true}', 'Hermes engine default configuration'),
('orion_engine', 'engine', '{"memory": "1Gi", "cpu": "1", "gpu": false}', 'Orion engine default configuration'),
('fpga_engine', 'engine', '{"memory": "2Gi", "cpu": "1", "fpga_type": "xilinx"}', 'FPGA engine default configuration'),
('gitlab_runner', 'runner', '{"concurrent": 4, "check_interval": 0, "tags": ["sega", "docker"]}', 'Default GitLab runner configuration');

-- Initialize sync status for all tables
INSERT INTO sync_status (table_name) VALUES
('vpn_servers'), ('vpn_clients'), ('engines'), ('runners'),
('network_nodes'), ('network_edges'), ('deployments'),
('system_metrics'), ('health_checks'), ('alerts');