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
 * SEGA HELLO WORLD APPLICATION TESTS
 * =============================================================================
 * File: examples/basic/hello-world/app.test.js
 * Project: SEGA (Scalable Engineering & Growth Automation)
 * Copyright: 2022-2025 FLEET
 * License: Apache-2.0
 *
 * SEGA MODULE: Examples/BasicApplications
 * COMPONENT: Hello World Test Suite
 * PURPOSE: Demonstrate comprehensive testing patterns for SEGA applications
 * DEPENDENCIES: supertest, jest
 * USAGE: npm test or jest app.test.js
 *
 * This test suite demonstrates SEGA-compliant testing patterns including
 * health endpoint validation, API response structure testing, and error handling.
 * =============================================================================
 */

const request = require('supertest');
const app = require('./app');

describe('SEGA Hello World App', () => {
  describe('GET /', () => {
    it('should return hello world message', async () => {
      const response = await request(app)
        .get('/')
        .expect(200);

      expect(response.body).toHaveProperty('message');
      expect(response.body.message).toBe('Hello World from SEGA Platform!');
      expect(response.body).toHaveProperty('timestamp');
      expect(response.body).toHaveProperty('features');
      expect(Array.isArray(response.body.features)).toBe(true);
    });
  });

  describe('GET /health', () => {
    it('should return health status', async () => {
      const response = await request(app)
        .get('/health')
        .expect(200);

      expect(response.body).toHaveProperty('status', 'healthy');
      expect(response.body).toHaveProperty('timestamp');
      expect(response.body).toHaveProperty('version');
    });
  });

  describe('GET /status', () => {
    it('should return application status', async () => {
      const response = await request(app)
        .get('/status')
        .expect(200);

      expect(response.body).toHaveProperty('application', 'sega-hello-world');
      expect(response.body).toHaveProperty('status', 'running');
      expect(response.body).toHaveProperty('uptime');
      expect(response.body).toHaveProperty('memory');
      expect(response.body).toHaveProperty('environment');
      expect(response.body).toHaveProperty('sega_features');
    });
  });

  describe('GET /nonexistent', () => {
    it('should return 404 for unknown routes', async () => {
      const response = await request(app)
        .get('/nonexistent')
        .expect(404);

      expect(response.body).toHaveProperty('error', 'Not found');
      expect(response.body).toHaveProperty('path', '/nonexistent');
    });
  });
});
