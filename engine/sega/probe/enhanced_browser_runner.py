#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Enhanced Browser Test Runner
============================
Implements advanced browser testing capabilities inspired by Orion BrowserAutomation.js
"""

import time
import requests
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from ..utils.paths import get_fleet_root
from ..core.config import get_config


@dataclass
class ValidationTestResult:
    """Result of validation testing with detailed reporting."""
    project: str
    tier: str  # static, dynamic, integration
    passed: bool
    duration: float
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    network_logs: List[Dict[str, Any]] = field(default_factory=list)


class IntelligentFormHandler:
    """Advanced form handling with intelligent field detection."""
    
    def __init__(self, playwright_page):
        self.page = playwright_page
    
    async def detect_and_fill_form(self, form_data: Dict[str, str]) -> bool:
        """Intelligently detect and fill form fields."""
        try:
            # Wait for form to be ready
            await self.page.wait_for_load_state('networkidle')
            
            for field_name, value in form_data.items():
                success = await self._fill_field_by_type(field_name, value)
                if not success:
                    return False
            
            return True
        except Exception as e:
            print(f"Form filling failed: {e}")
            return False
    
    async def _fill_field_by_type(self, field_name: str, value: str) -> bool:
        """Fill field based on intelligent detection."""
        # Try multiple selector strategies
        selectors = [
            f'[name="{field_name}"]',
            f'[id="{field_name}"]',
            f'[placeholder*="{field_name}" i]',
            f'label:has-text("{field_name}") + input',
            f'input[type="text"]:near(text="{field_name}")',
            f'[data-testid="{field_name}"]'
        ]
        
        if 'email' in field_name.lower():
            selectors.insert(0, 'input[type="email"]')
        elif 'password' in field_name.lower():
            selectors.insert(0, 'input[type="password"]')
        
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    await element.fill(value)
                    return True
            except:
                continue
        
        return False


class EnhancedSessionManager:
    """Enhanced session management with cookie persistence."""
    
    def __init__(self, playwright_context):
        self.context = playwright_context
        self.session_data = {}
    
    async def save_session_state(self, session_name: str):
        """Save current session state."""
        storage_state = await self.context.storage_state()
        self.session_data[session_name] = storage_state
    
    async def restore_session_state(self, session_name: str):
        """Restore saved session state."""
        if session_name in self.session_data:
            await self.context.add_cookies(self.session_data[session_name]['cookies'])


class ComprehensiveErrorCapture:
    """Comprehensive error capture during testing."""
    
    def __init__(self, playwright_page):
        self.page = playwright_page
        self.console_errors = []
        self.network_failures = []
        self.performance_metrics = {}
        
        # Set up event listeners
        self.page.on('console', self._handle_console_message)
        self.page.on('requestfailed', self._handle_request_failed)
    
    def _handle_console_message(self, msg):
        """Handle console messages."""
        if msg.type in ['error', 'warning']:
            self.console_errors.append({
                'type': msg.type,
                'text': msg.text,
                'timestamp': datetime.now().isoformat()
            })
    
    def _handle_request_failed(self, request):
        """Handle failed network requests."""
        self.network_failures.append({
            'url': request.url,
            'method': request.method,
            'timestamp': datetime.now().isoformat(),
            'failure_text': request.failure
        })
    
    async def capture_performance_metrics(self):
        """Capture page performance metrics."""
        try:
            metrics = await self.page.evaluate('''() => {
                const navigation = performance.getEntriesByType('navigation')[0];
                return {
                    loadTime: navigation.loadEventEnd - navigation.loadEventStart,
                    domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
                    firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime || 0,
                    firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime || 0
                };
            }''')
            self.performance_metrics = metrics
        except:
            pass


class ThreeTierValidator:
    """Three-tier validation framework implementation."""
    
    def __init__(self, project: str, fleet_root: Path):
        self.project = project
        self.fleet_root = fleet_root
        self.project_path = fleet_root / project
    
    async def run_validation(self) -> List[ValidationTestResult]:
        """Run all three tiers of validation."""
        results = []
        
        # Tier 1: Static Validation
        static_result = await self.run_static_validation()
        results.append(static_result)
        
        if static_result.passed:
            # Tier 2: Dynamic Validation
            dynamic_result = await self.run_dynamic_validation()
            results.append(dynamic_result)
            
            if dynamic_result.passed:
                # Tier 3: Integration Validation
                integration_result = await self.run_integration_validation()
                results.append(integration_result)
        
        return results
    
    async def run_static_validation(self) -> ValidationTestResult:
        """Tier 1: Static validation - app startup and basic rendering."""
        start_time = time.time()
        errors = []
        
        try:
            # Check if app starts without crashes
            port = self._get_project_port()
            health_url = f"http://localhost:{port}/health"
            
            # Wait for app to be ready
            for attempt in range(30):
                try:
                    response = requests.get(health_url, timeout=2)
                    if response.status_code == 200:
                        break
                except:
                    await asyncio.sleep(1)
            else:
                errors.append("AApplication failed to start within 30 seconds")
            
            # Test frontend rendering
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                error_capture = ComprehensiveErrorCapture(page)
                
                try:
                    await page.goto(f"http://localhost:{port}", timeout=10000)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                    # Check for JavaScript errors
                    if error_capture.console_errors:
                        errors.extend([f"Console error: {err['text']}" for err in error_capture.console_errors])
                    
                    # Basic navigation test
                    title = await page.title()
                    if not title or title == "Error":
                        errors.append("Page title indicates error or is empty")
                
                except Exception as e:
                    errors.append(f"Page loading failed: {str(e)}")
                
                await browser.close()
        
        except Exception as e:
            errors.append(f"Static validation failed: {str(e)}")
        
        duration = time.time() - start_time
        
        return ValidationTestResult(
            project=self.project,
            tier="static",
            passed=len(errors) == 0,
            duration=duration,
            errors=errors,
            details={"port": self._get_project_port()}
        )
    
    async def run_dynamic_validation(self) -> ValidationTestResult:
        """Tier 2: Dynamic validation - CRUD operations via UI."""
        start_time = time.time()
        errors = []
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                context = await browser.new_context()
                page = await context.new_page()
                
                form_handler = IntelligentFormHandler(page)
                session_manager = EnhancedSessionManager(context)
                error_capture = ComprehensiveErrorCapture(page)
                
                port = self._get_project_port()
                await page.goto(f"http://localhost:{port}")
                
                # Test data creation via UI (if forms exist)
                test_data = await self._create_test_data_via_api()
                
                # Verify data appears in UI
                if test_data:
                    success = await self._verify_data_in_ui(page, test_data)
                    if not success:
                        errors.append("Data created via API does not appear in UI")
                
                # Test form submission if available
                forms = await page.query_selector_all('form')
                if forms:
                    form_success = await form_handler.detect_and_fill_form({
                        'name': 'Test Item',
                        'description': 'Test Description'
                    })
                    if not form_success:
                        errors.append("Form filling and submission failed")
                
                await browser.close()
        
        except Exception as e:
            errors.append(f"Dynamic validation failed: {str(e)}")
        
        duration = time.time() - start_time
        
        return ValidationTestResult(
            project=self.project,
            tier="dynamic", 
            passed=len(errors) == 0,
            duration=duration,
            errors=errors
        )
    
    async def run_integration_validation(self) -> ValidationTestResult:
        """Tier 3: Integration validation - authentication, real-time features."""
        start_time = time.time()
        errors = []
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                context = await browser.new_context()
                page = await context.new_page()
                
                port = self._get_project_port()
                
                # Test authentication flow (if available)
                await page.goto(f"http://localhost:{port}")
                
                # Look for login forms
                login_form = await page.query_selector('form:has(input[type="password"])')
                if login_form:
                    # Test login flow
                    await self._test_authentication_flow(page)
                
                # Test WebSocket connections (if available)
                websocket_errors = await self._test_websocket_connections(page)
                errors.extend(websocket_errors)
                
                # Test API endpoints
                api_errors = await self._test_api_endpoints()
                errors.extend(api_errors)
                
                await browser.close()
        
        except Exception as e:
            errors.append(f"Integration validation failed: {str(e)}")
        
        duration = time.time() - start_time
        
        return ValidationTestResult(
            project=self.project,
            tier="integration",
            passed=len(errors) == 0,
            duration=duration,
            errors=errors
        )
    
    def _get_project_port(self) -> int:
        """Get the project's frontend port from central config.

        Frontend port = 3000 + project id (AUTHORITATIVE:
        /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md).
        Falls back to 3000 for unknown projects, matching prior behavior.
        """
        proj = get_config().get_project(self.project)
        if proj is None:
            return 3000
        return proj.ports.frontend
    
    async def _create_test_data_via_api(self) -> Optional[Dict[str, Any]]:
        """Create test data via API for speed and reliability."""
        try:
            port = self._get_project_port()
            api_url = f"http://localhost:{port}/api"
            
            # Try to create a test entity
            test_data = {
                'name': f'test-entity-{int(time.time())}',
                'description': 'Test entity for validation'
            }
            
            response = requests.post(f"{api_url}/entities", json=test_data, timeout=5)
            if response.status_code in [200, 201]:
                return response.json()
        except:
            pass
        
        return None
    
    async def _verify_data_in_ui(self, page, test_data: Dict[str, Any]) -> bool:
        """Verify API-created data appears in UI."""
        try:
            # Look for the test data in the page
            entity_name = test_data.get('name', '')
            if entity_name:
                element = await page.query_selector(f'text="{entity_name}"')
                return element is not None
        except:
            pass
        
        return False
    
    async def _test_authentication_flow(self, page) -> List[str]:
        """Test authentication flow."""
        errors = []
        try:
            # Basic login test with test credentials
            await page.fill('input[type="email"], input[name="email"]', 'test@example.com')
            await page.fill('input[type="password"]', 'testpassword')
            await page.click('button[type="submit"], input[type="submit"]')
            
            # Wait for redirect or response
            await page.wait_for_timeout(2000)
            
            # Check if login was successful (look for dashboard or profile elements)
            dashboard = await page.query_selector('[data-testid="dashboard"], .dashboard, #dashboard')
            if not dashboard:
                errors.append("Authentication flow may have failed - no dashboard found")
        
        except Exception as e:
            errors.append(f"Authentication test failed: {str(e)}")
        
        return errors
    
    async def _test_websocket_connections(self, page) -> List[str]:
        """Test WebSocket connections."""
        errors = []
        try:
            # Check for WebSocket connections in network activity
            websockets = await page.evaluate('''() => {
                return window.WebSocket ? true : false;
            }''')
            
            if not websockets:
                errors.append("WebSocket not available in browser")
        
        except Exception as e:
            errors.append(f"WebSocket test failed: {str(e)}")
        
        return errors
    
    async def _test_api_endpoints(self) -> List[str]:
        """Test API endpoints."""
        errors = []
        try:
            port = self._get_project_port()
            base_url = f"http://localhost:{port}/api"
            
            # Test health endpoint
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                if response.status_code != 200:
                    errors.append(f"Health endpoint returned {response.status_code}")
            except:
                errors.append("Health endpoint not accessible")
            
        except Exception as e:
            errors.append(f"API endpoint test failed: {str(e)}")
        
        return errors


class EnhancedBrowserTestRunner:
    """Enhanced browser test runner with Orion-inspired capabilities."""
    
    def __init__(self, fleet_root: Optional[str] = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
    
    async def run_comprehensive_validation(self, project: str) -> List[ValidationTestResult]:
        """Run comprehensive three-tier validation."""
        validator = ThreeTierValidator(project, self.fleet_root)
        return await validator.run_validation()
    
    def generate_validation_report(self, results: List[ValidationTestResult]) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        report = {
            'project': results[0].project if results else 'unknown',
            'timestamp': datetime.now().isoformat(),
            'total_duration': sum(r.duration for r in results),
            'tiers_completed': len(results),
            'overall_success': all(r.passed for r in results),
            'tier_results': []
        }
        
        for result in results:
            tier_data = {
                'tier': result.tier,
                'passed': result.passed,
                'duration': result.duration,
                'error_count': len(result.errors),
                'errors': result.errors,
                'details': result.details
            }
            report['tier_results'].append(tier_data)
        
        return report