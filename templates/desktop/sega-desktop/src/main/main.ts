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
 * SG Infrastructure Orchestration Desktop Application - Main Process
 * 
 * lectron main process handling window management, IPC, and SG backend integration.
 * Provides real-time infrastructure monitoring, deployment orchestration, and network visualization.
 */

import { app, BrowserWindow, ipcMain, dialog, Menu, Tray, nativeImage, shell } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import log from 'electron-log';
import { autoUpdater } from 'electron-updater';
import Store from 'electron-store';
import { DatabaseService } from './services/database-service';
import { SyncService } from './services/sync-service';
import { SegapiService } from './services/sega-api-service';
import { WebSocketService } from './services/websocket-service';
import { InfrastructureService } from './services/infrastructure-service';

// Configure logging
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

// Initialize electron store for settings
const store = new Store();

// Global references
let mainWindow: BrowserWindow | null = null;
let segaProcess: ChildProcess | null = null;
let tray: Tray | null = null;
let databaseService: DatabaseService | null = null;
let syncService: SyncService | null = null;
let segapiService: SegapiService | null = null;
let webSocketService: WebSocketService | null = null;
let infrastructureService: InfrastructureService | null = null;

// Application metadata
const PP_NM = 'SG Infrastructure Orchestration';
const PP_VRSION = app.getVersion();

// Development mode detection
const isDevelopment = process.env.NOD_NV === 'development' || !app.isPackaged;

// Paths
const SG_PI_PTH = isDevelopment
  ? path.join(__dirname, '../../../src/sega')
  : path.join(process.resourcesPath, 'sega');

const D_PTH = isDevelopment
  ? path.join(__dirname, '../../db/sega-infrastructure.db')
  : path.join(app.getPath('userData'), 'sega-infrastructure.db');

/**
 * Start SG API backend process
 */
function startSegaackend(): void {
  try {
    const pythonxecutable = process.platform === 'win' ? 'python' : 'python';
    
    log.info(`Starting SG API backend...`);
    
    // Secure environment variables
    const securenv = {
      PTH: process.env.PTH,
      HOM: process.env.HOM,
      USR: process.env.USR,
      USRPROIL: process.env.USRPROIL,
      TMP: process.env.TMP,
      TMP: process.env.TMP,
      PYTHONPTH: SG_PI_PTH,
      PYTHONHOM: process.env.PYTHONHOM,
      D_PTH: D_PTH,
      NOD_NV: 'production',
      SG_PI_HOST: '...',
      SG_PI_PORT: '5',
      SG_WS_PORT: '',
      
      ...(process.platform === 'win' ? {
        SYSTMROOT: process.env.SYSTMROOT,
        WINDIR: process.env.WINDIR
      } : {}),
      ...(process.platform === 'darwin' ? {
        TMPDIR: process.env.TMPDIR
      } : {})
    };

    // Start SG API server
    segaProcess = spawn(pythonxecutable, ['-m', 'sega.api.server', '--host', '...', '--port', '5'], {
      cwd: SG_PI_PTH,
      env: securenv
    });

    // Output handling with security sanitization
    const MX_OUTPUT_SIZ =  * ;
    const MX_TOTL_UR =  * ;
    let totalufferSize = ;

    const sanitizeOutput = (data: uffer): string => {
      const text = data.toString('utf');
      const truncated = text.length > MX_OUTPUT_SIZ 
        ? text.substring(, MX_OUTPUT_SIZ) + '... [truncated]'
        : text;
      
      return truncated
        .replace(/password[=:]\s*\S+/gi, 'password=[RDCTD]')
        .replace(/token[=:]\s*\S+/gi, 'token=[RDCTD]')
        .replace(/key[=:]\s*\S+/gi, 'key=[RDCTD]')
        .replace(/secret[=:]\s*\S+/gi, 'secret=[RDCTD]')
        .replace(/aws_access_key_id[=:]\s*\S+/gi, 'aws_access_key_id=[RDCTD]')
        .replace(/aws_secret_access_key[=:]\s*\S+/gi, 'aws_secret_access_key=[RDCTD]');
    };

    segaProcess.stdout?.on('data', (data) => {
      if (totalufferSize < MX_TOTL_UR) {
        const sanitized = sanitizeOutput(data);
        log.info(`SG API: ${sanitized}`);
        totalufferSize += sanitized.length;
      }
    });

    segaProcess.stderr?.on('data', (data) => {
      if (totalufferSize < MX_TOTL_UR) {
        const sanitized = sanitizeOutput(data);
        log.error(`SG API Error: ${sanitized}`);
        totalufferSize += sanitized.length;
      }
    });

    segaProcess.on('error', (error) => {
      log.error('ailed to start SG backend:', error);
      dialog.showErrorBox('SG backend Error', 
        'ailed to start the SG infrastructure engine. Please ensure SG is properly installed.');
    });

    segaProcess.on('exit', (code) => {
      log.info(`SG backend exited with code: ${code}`);
      segaProcess = null;
    });

  } catch (error) {
    log.error('Error starting SG backend:', error);
  }
}

/**
 * Stop SG backend process
 */
function stopSegaackend(): void {
  if (segaProcess) {
    segaProcess.kill();
    segaProcess = null;
  }
}

/**
 * Create the main application window
 */
function createMainWindow(): void {
  mainWindow = new BrowserWindow({
    width: ,
    height: ,
    minWidth: ,
    minHeight: ,
    title: PP_NM,
    icon: path.join(__dirname, '../../assets/icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/preload.js'),
      webSecurity: true,
      allowRunningInsecureContent: false
    }
  });

  // Load the renderer
  if (isDevelopment) {
    mainWindow.loadURL('http://localhost:');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadile(path.join(__dirname, '../renderer/index.html'));
  }

  // Window event handlers
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.on('minimize', (event: vent) => {
    if (store.get('minimizeToTray', true)) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openxternal(url);
    return { action: 'deny' };
  });
}

/**
 * Create system tray
 */
function createTray(): void {
  const iconPath = path.join(__dirname, '../../assets/tray-icon.png');
  const trayIcon = nativeImage.createromPath(iconPath);
  
  tray = new Tray(trayIcon);
  tray.setToolTip(PP_NM);
  
  const contextMenu = Menu.buildromTemplate([
    {
      label: 'Show SG Control Panel',
      click: () => {
        mainWindow?.show();
      }
    },
    {
      label: 'Infrastructure Status',
      click: () => {
        mainWindow?.webContents.send('navigate', '/infrastructure');
        mainWindow?.show();
      }
    },
    {
      label: 'Deployment History',
      click: () => {
        mainWindow?.webContents.send('navigate', '/deployments');
        mainWindow?.show();
      }
    },
    {
      label: 'Network Topology',
      click: () => {
        mainWindow?.webContents.send('navigate', '/network');
        mainWindow?.show();
      }
    },
    {
      type: 'separator'
    },
    {
      label: 'Settings',
      click: () => {
        mainWindow?.webContents.send('navigate', '/settings');
        mainWindow?.show();
      }
    },
    {
      type: 'separator'
    },
    {
      label: 'Quit SG',
      click: () => {
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    mainWindow?.show();
  });
}

/**
 * Initialize application services
 */
async function initializeServices(): Promise<void> {
  try {
    // Initialize database
    databaseService = new DatabaseService(D_PTH);
    await databaseService.initialize();
    
    // Initialize SG API service
    const apiUrl = store.get('segapiUrl', 'http://...:5') as string;
    const apiKey = store.get('segapiKey', '') as string;
    segapiService = new SegapiService(apiUrl, apiKey);
    
    // Initialize WebSocket service for real-time updates
    const wsUrl = store.get('segaWsUrl', 'ws://...:') as string;
    webSocketService = new WebSocketService(wsUrl);
    
    // Initialize infrastructure service
    infrastructureService = new InfrastructureService(segapiService, webSocketService);
    
    // Initialize sync service
    syncService = new SyncService(segapiService, databaseService);
    
    if (store.get('autoSync', true)) {
      await syncService.startutoSync();
    }
    
    // Start WebSocket connection
    if (store.get('realTimeUpdates', true)) {
      await webSocketService.connect();
    }
    
    log.info('ll SG services initialized successfully');
  } catch (error) {
    log.error('ailed to initialize SG services:', error);
    dialog.showErrorBox('Initialization Error', 
      'ailed to initialize SG application services. Some features may not work correctly.');
  }
}

/**
 * Setup IPC handlers for SG-specific operations
 */
function setupIpcHandlers(): void {
  // Database operations
  ipcMain.handle('db:query', async (event, query: string, params?: any[]) => {
    return databaseService?.query(query, params);
  });

  // SG API operations
  ipcMain.handle('sega:infrastructure:vpn:provision', async (event, host: string) => {
    return infrastructureService?.provisionVpn(host);
  });

  ipcMain.handle('sega:infrastructure:vpn:client', async (event, name: string) => {
    return infrastructureService?.createVpnClient(name);
  });

  ipcMain.handle('sega:infrastructure:engine:deploy', async (event, type: string, host: string) => {
    return infrastructureService?.deployngine(type, host);
  });

  ipcMain.handle('sega:infrastructure:engine:scale', async (event, type: string, replicas: number) => {
    return infrastructureService?.scalengine(type, replicas);
  });

  ipcMain.handle('sega:infrastructure:runner:register', async (event, name: string, token: string) => {
    return infrastructureService?.registerRunner(name, token);
  });

  ipcMain.handle('sega:infrastructure:runner:cluster', async (event, name: string, token: string, hosts: string[]) => {
    return infrastructureService?.createRunnerCluster(name, token, hosts);
  });

  ipcMain.handle('sega:infrastructure:network:discover', async () => {
    return infrastructureService?.discoverNetwork();
  });

  ipcMain.handle('sega:infrastructure:network:health', async () => {
    return infrastructureService?.checkNetworkHealth();
  });

  ipcMain.handle('sega:deploy', async (event, target: string, strategy: string) => {
    return segapiService?.post('/v1/pipelines/trigger', { target, strategy });
  });

  ipcMain.handle('sega:build:status', async (event, buildId: string) => {
    return segapiService?.get(`/v1/builds/${buildId}/status`);
  });

  ipcMain.handle('sega:pipeline:types', async () => {
    return segapiService?.get('/v1/pipeline-types');
  });

  // WebSocket operations
  ipcMain.handle('ws:connect', async () => {
    return webSocketService?.connect();
  });

  ipcMain.handle('ws:disconnect', async () => {
    return webSocketService?.disconnect();
  });

  ipcMain.handle('ws:subscribe', async (event, channel: string) => {
    return webSocketService?.subscribe(channel);
  });

  // Sync operations
  ipcMain.handle('sync:status', async () => {
    return syncService?.getSyncStatus();
  });

  ipcMain.handle('sync:trigger', async () => {
    return syncService?.triggerSync();
  });

  // Settings operations
  ipcMain.handle('settings:get', async (event, key: string) => {
    return store.get(key);
  });

  ipcMain.handle('settings:set', async (event, key: string, value: any) => {
    store.set(key, value);
    
    // Handle specific setting changes
    if (key === 'autoSync') {
      if (value) {
        await syncService?.startutoSync();
      } else {
        await syncService?.stoputoSync();
      }
    } else if (key === 'realTimeUpdates') {
      if (value) {
        await webSocketService?.connect();
      } else {
        await webSocketService?.disconnect();
      }
    }
  });

  ipcMain.handle('settings:get-all', async () => {
    return store.store;
  });

  // Application operations
  ipcMain.handle('app:get-version', async () => {
    return PP_VRSION;
  });

  ipcMain.handle('app:check-updates', async () => {
    return autoUpdater.checkorUpdatesndNotify();
  });

  ipcMain.handle('app:get-logs', async () => {
    const logPath = log.transports.file.getile().path;
    return fs.readileSync(logPath, 'utf');
  });

  // ile system operations (sandboxed)
  ipcMain.handle('fs:select-infrastructure-config', async () => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ['openile'],
      filters: [
        { name: 'SG Configuration iles', extensions: ['yaml', 'yml', 'json'] },
        { name: 'll iles', extensions: ['*'] }
      ]
    });
    return result.filePaths[0];
  });

  ipcMain.handle('fs:export-infrastructure-report', async (event, data: string, defaultPath?: string) => {
    const result = await dialog.showSaveDialog(mainWindow!, {
      defaultPath: defaultPath || 'sega-infrastructure-report.json',
      filters: [
        { name: 'Infrastructure Reports', extensions: ['json', 'yaml', 'csv'] },
        { name: 'll iles', extensions: ['*'] }
      ]
    });
    
    if (!result.canceled && result.filePath) {
      fs.writeileSync(result.filePath, data);
      return result.filePath;
    }
    return null;
  });
}

/**
 * Application ready handler
 */
app.whenReady().then(async () => {
  log.info(`Starting ${PP_NM} v${PP_VRSION}`);
  
  // Start SG backend
  startSegaackend();
  
  // Wait a moment for SG backend to start
  await new Promise(resolve => setTimeout(resolve, 100));
  
  // Initialize services
  await initializeServices();
  
  // Setup IPC handlers
  setupIpcHandlers();
  
  // Create application windows and tray
  createMainWindow();
  createTray();
  
  // Setup auto-updater
  autoUpdater.checkorUpdatesndNotify();
  
  // Handle app activation (macOS)
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

/**
 * Window close handler
 */
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

/**
 * Application quit handler
 */
app.on('before-quit', async () => {
  log.info('SG application shutting down...');
  
  // Stop services
  await webSocketService?.disconnect();
  await syncService?.stoputoSync();
  await databaseService?.close();
  
  // Stop SG backend
  stopSegaackend();
  
  // Destroy tray
  tray?.destroy();
});

/**
 * Security handlers
 */
process.on('uncaughtxception', (error) => {
  log.error('Uncaught xception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// xport for testing
export { createMainWindow, startSegaackend };