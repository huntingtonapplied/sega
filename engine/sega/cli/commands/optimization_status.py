#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Optimization Status Command
===========================
Provides status and testing for all SEGA optimization components.
"""

import click
import json
import asyncio
import time
from pathlib import Path
from datetime import datetime

# Import optimization components
from ...core.lazy_command_registry import command_registry
from ...core.enhanced_connection_manager import ConnectionConfig, EnhancedConnectionManager
from ...core.parallel_execution_manager import ParallelExecutionManager
from ...core.ecosystem_error_reporter import EcosystemErrorReporter, ErrorContext
from ...core.optimized_resource_manager import OptimizedResourceManager
from ...project.cached_project_detector import CachedProjectDetector
from ...utils.logger import get_logger

logger = get_logger(__name__)


@click.group()
def optimization():
    """SEGA optimization status and testing commands."""
    pass


@optimization.command()
@click.option('--format', default='table', type=click.Choice(['table', 'json']),
              help='Output format')
def status(format: str):
    """Show status of all optimization components."""
    click.echo(" SEGA Optimization Status Report")
    click.echo("=" * 50)
    
    status_data = {
        'timestamp': datetime.now().isoformat(),
        'components': {}
    }
    
    # Test lazy command registry
    click.echo("\n Lazy Command Registry:")
    try:
        registry_commands = len(command_registry.get_all_command_names())
        loaded_commands = len(command_registry._loaded_commands)
        
        status_data['components']['lazy_command_registry'] = {
            'status': 'operational',
            'total_commands': registry_commands,
            'loaded_commands': loaded_commands,
            'lazy_loading': True
        }
        
        if format == 'table':
            click.echo(f"   Total commands available: {registry_commands}")
            click.echo(f"   Commands loaded on-demand: {loaded_commands}")
    except Exception as e:
        status_data['components']['lazy_command_registry'] = {
            'status': 'error',
            'error': str(e)
        }
        if format == 'table':
            click.echo(f"   Error: {e}")
    
    # Test resource manager
    click.echo("\n Resource Management:")
    try:
        resource_manager = OptimizedResourceManager()
        summary = resource_manager.get_resource_summary()
        
        status_data['components']['resource_manager'] = {
            'status': 'operational',
            'active_allocations': summary['allocations']['total_active'],
            'monitored_projects': len(summary['project_usage']),
            'system_health': 'healthy' if summary['system_resources']['cpu_percent'] else 'unknown'
        }
        
        if format == 'table':
            click.echo(f"   Active allocations: {summary['allocations']['total_active']}")
            click.echo(f"   Monitored projects: {len(summary['project_usage'])}")
        
        resource_manager.cleanup()
    except Exception as e:
        status_data['components']['resource_manager'] = {
            'status': 'error',
            'error': str(e)
        }
        if format == 'table':
            click.echo(f"   Error: {e}")
    
    # Test project detector cache
    click.echo("\n Cached Project Detection:")
    try:
        detector = CachedProjectDetector()
        cache_stats = detector.get_cache_stats()
        
        status_data['components']['project_detector'] = {
            'status': 'operational',
            'cache_size': cache_stats['project_cache_size'],
            'cache_duration': cache_stats['cache_duration']
        }
        
        if format == 'table':
            click.echo(f"   Cache entries: {cache_stats['project_cache_size']}")
            click.echo(f"  ️  Cache duration: {cache_stats['cache_duration']}s")
    except Exception as e:
        status_data['components']['project_detector'] = {
            'status': 'error',
            'error': str(e)
        }
        if format == 'table':
            click.echo(f"   Error: {e}")
    
    # Test connection manager
    click.echo("\n Enhanced Connection Management:")
    try:
        config = ConnectionConfig(host='localhost', port=3308, timeout=2.0)
        conn_manager = EnhancedConnectionManager(config)
        health = conn_manager.get_health_status()
        
        status_data['components']['connection_manager'] = {
            'status': 'operational',
            'circuit_state': health['circuit_state'],
            'pool_size': health['pool_size']
        }
        
        if format == 'table':
            click.echo(f"   Circuit breaker: {health['circuit_state']}")
            click.echo(f"   Connection pool: {health['pool_size']} connections")
        
        conn_manager.close()
    except Exception as e:
        status_data['components']['connection_manager'] = {
            'status': 'error',
            'error': str(e)
        }
        if format == 'table':
            click.echo(f"   Error: {e}")
    
    # Output results
    if format == 'json':
        click.echo(json.dumps(status_data, indent=2))
    else:
        click.echo("\n Overall Status:")
        operational_count = sum(1 for comp in status_data['components'].values() 
                              if comp.get('status') == 'operational')
        total_count = len(status_data['components'])
        
        if operational_count == total_count:
            click.echo("   All optimization components operational")
        else:
            click.echo(f"   {operational_count}/{total_count} components operational")


@optimization.command()
@click.option('--projects', default=2, help='Number of projects to test')
async def test_parallel(projects: int):
    """Test parallel execution optimization."""
    click.echo(f" Testing parallel execution with {projects} projects...")
    
    try:
        manager = ParallelExecutionManager(max_workers=min(projects, 4))
        
        # Create test tasks
        tasks = []
        for i in range(projects):
            task = manager.create_task_from_project_operation(
                project=f'test_project_{i}',
                operation='test',
                timeout=5.0
            )
            tasks.append(task)
        
        # Execute in parallel
        start_time = time.time()
        result = await manager.execute_parallel(tasks)
        duration = time.time() - start_time
        
        click.echo(f"   Executed {result.total_tasks} tasks in {duration:.2f}s")
        click.echo(f"   Results: {result.completed} completed, {result.failed} failed")
        
        if result.failed > 0:
            click.echo("  ️  Some tasks failed (expected in test environment)")
        
        return True
    
    except Exception as e:
        click.echo(f"   Parallel execution test failed: {e}")
        return False


@optimization.command()
def test_error_reporting():
    """Test ecosystem error reporting."""
    click.echo(" Testing error reporting system...")
    
    try:
        reporter = EcosystemErrorReporter()
        
        # Create test error context
        context = ErrorContext(
            project='test_project',
            operation='optimization_test',
            environment='development',
            timestamp=datetime.now().isoformat(),
            user='test_user',
            command='sega optimization test-error-reporting',
            working_directory=str(Path.cwd())
        )
        
        # Test error reporting
        test_exception = Exception("Test error for optimization validation")
        error = reporter.report_error(test_exception, context)
        
        click.echo(f"   Error reported with ID: {error.error_id}")
        click.echo(f"   Category: {error.category.value}")
        click.echo(f"   Severity: {error.severity.value}")
        click.echo(f"   Suggested fixes: {len(error.suggested_fixes)}")
        
        return True
    
    except Exception as e:
        click.echo(f"   Error reporting test failed: {e}")
        return False


@optimization.command()
@click.option('--project', default='sega', help='Project to test detection for')
def test_detection(project: str):
    """Test cached project detection."""
    click.echo(f" Testing project detection for: {project}")
    
    try:
        detector = CachedProjectDetector()
        project_path = Path.cwd().parent / project if project != 'sega' else Path.cwd()
        
        if not project_path.exists():
            click.echo(f"  ️  Project path not found: {project_path}")
            return False
        
        # First detection (should cache)
        start_time = time.time()
        result1 = detector.detect_project_type(project_path)
        first_duration = time.time() - start_time
        
        # Second detection (should use cache)
        start_time = time.time()
        result2 = detector.detect_project_type(project_path)
        second_duration = time.time() - start_time
        
        click.echo(f"   Project type: {result1['project_type']}")
        click.echo(f"   First detection: {first_duration:.3f}s")
        click.echo(f"   Cached detection: {second_duration:.3f}s")
        
        if second_duration < first_duration:
            speedup = first_duration / second_duration
            click.echo(f"   Cache speedup: {speedup:.1f}x faster")
        
        frameworks = result1.get('frameworks', [])
        if frameworks:
            click.echo(f"  ️  Detected frameworks: {', '.join(frameworks)}")
        
        return True
    
    except Exception as e:
        click.echo(f"   Detection test failed: {e}")
        return False


@optimization.command()
async def benchmark():
    """Run comprehensive optimization benchmarks."""
    click.echo(" Running SEGA Optimization Benchmark Suite")
    click.echo("=" * 50)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': {}
    }
    
    # Test 1: Command loading speed
    click.echo("\n Testing command loading performance...")
    start_time = time.time()
    registry = command_registry
    registry.preload_common_commands()
    load_time = time.time() - start_time
    
    results['tests']['command_loading'] = {
        'duration_seconds': load_time,
        'commands_loaded': len(registry._loaded_commands),
        'status': 'passed' if load_time < 2.0 else 'slow'
    }
    
    click.echo(f"  ️  Loaded {len(registry._loaded_commands)} commands in {load_time:.3f}s")
    
    # Test 2: Parallel execution performance
    click.echo("\n Testing parallel execution performance...")
    manager = ParallelExecutionManager(max_workers=4)
    
    tasks = []
    for i in range(6):  # More tasks than workers to test queueing
        task = manager.create_task_from_project_operation(
            project=f'benchmark_project_{i}',
            operation='test',
            timeout=10.0
        )
        tasks.append(task)
    
    start_time = time.time()
    parallel_result = await manager.execute_parallel(tasks)
    parallel_duration = time.time() - start_time
    
    results['tests']['parallel_execution'] = {
        'duration_seconds': parallel_duration,
        'tasks_completed': parallel_result.completed,
        'tasks_failed': parallel_result.failed,
        'efficiency': parallel_result.completed / len(tasks) if tasks else 0,
        'status': 'passed' if parallel_result.completed >= len(tasks) * 0.8 else 'degraded'
    }
    
    click.echo(f"  ️  Executed {parallel_result.completed}/{len(tasks)} tasks in {parallel_duration:.3f}s")
    
    # Test 3: Resource monitoring overhead
    click.echo("\n Testing resource monitoring overhead...")
    resource_manager = OptimizedResourceManager()
    
    start_time = time.time()
    for _ in range(10):
        summary = resource_manager.get_resource_summary()
    monitoring_duration = time.time() - start_time
    
    results['tests']['resource_monitoring'] = {
        'duration_seconds': monitoring_duration,
        'calls_per_second': 10 / monitoring_duration,
        'overhead': monitoring_duration / 10,
        'status': 'passed' if monitoring_duration < 1.0 else 'slow'
    }
    
    click.echo(f"  ️  Resource monitoring: {monitoring_duration:.3f}s for 10 calls")
    resource_manager.cleanup()
    
    # Summary
    click.echo("\n Benchmark Summary:")
    total_tests = len(results['tests'])
    passed_tests = sum(1 for test in results['tests'].values() if test['status'] == 'passed')
    
    click.echo(f"   Tests passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        click.echo("   All optimization components performing well!")
    else:
        click.echo("   Some performance issues detected")
    
    # Export results
    benchmark_file = Path.cwd() / '.sega' / 'benchmark_results.json'
    benchmark_file.parent.mkdir(exist_ok=True)
    
    with open(benchmark_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    click.echo(f"   Results saved to: {benchmark_file}")


# Make commands available when imported
def run_parallel_test(projects: int):
    """Wrapper for async test function."""
    return asyncio.run(test_parallel.callback(projects))

def run_benchmark():
    """Wrapper for async benchmark function."""
    return asyncio.run(benchmark.callback())