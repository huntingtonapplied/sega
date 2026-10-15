#!/usr/bin/env node
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
 * SEGA HELLO WORLD APPLICATION
 * =============================================================================
 * File: examples/basic/hello-world/app.js
 * Project: SEGA (Scalable Engineering & Growth Automation)
 * Copyright: 2022-2025 FLEET
 * License: Apache-2.0
 * 
 * SEGA MODULE: Examples/BasicApplications
 * COMPONENT: Hello World Express Application
 * PURPOSE: Demonstrate basic SEGA-compliant web application with health monitoring
 * DEPENDENCIES: express
 * USAGE: node app.js or npm start
 * 
 * This example application showcases SEGA platform integration with required
 * health endpoints, environment detection, and containerized deployment support.
 * =============================================================================
 */

const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

// Health check endpoint (required by SEGA)
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: process.env.npm_package_version || '1.0.0'
  });
});

// Main route
app.get('/', (req, res) => {
  res.json({
    message: 'Hello World from SEGA Platform!',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    features: [
      'Containerized deployment',
      'Health monitoring',
      'Auto-scaling',
      'Security scanning',
      'Intelligence insights'
    ]
  });
});

// Status endpoint with system info
app.get('/status', (req, res) => {
  res.json({
    application: 'sega-hello-world',
    status: 'running',
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    environment: {
      node_version: process.version,
      environment: process.env.NODE_ENV,
      port: port
    },
    sega_features: {
      deployment_strategy: process.env.DEPLOYMENT_STRATEGY || 'rolling',
      auto_scaling: process.env.AUTO_SCALING || 'enabled',
      monitoring: process.env.MONITORING || 'enabled'
    }
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    error: 'Something went wrong!',
    timestamp: new Date().toISOString()
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    error: 'Not found',
    path: req.path,
    timestamp: new Date().toISOString()
  });
});

app.listen(port, () => {
  console.log(`SEGA Hello World app listening at http://localhost:${port}`);
  console.log(`Health check available at http://localhost:${port}/health`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

module.exports = app;