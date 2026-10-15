#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Cached Project Detector
=======================
Optimizes project detection with intelligent caching for the FLEET ecosystem.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class ProjectCacheEntry:
    """Cache entry for project detection results."""
    project_path: str
    project_type: str
    build_config: Dict[str, Any]
    file_hash: str
    timestamp: float
    last_modified: float


class ExpiringDict:
    """Dictionary with automatic expiration of entries."""
    
    def __init__(self, max_len: int = 50, max_age_seconds: int = 3600):
        self.max_len = max_len
        self.max_age_seconds = max_age_seconds
        self.data: Dict[str, Tuple[Any, float]] = {}
    
    def __contains__(self, key: str) -> bool:
        if key in self.data:
            _, timestamp = self.data[key]
            if time.time() - timestamp <= self.max_age_seconds:
                return True
            else:
                del self.data[key]
        return False
    
    def __getitem__(self, key: str) -> Any:
        if key in self:
            return self.data[key][0]
        raise KeyError(key)
    
    def __setitem__(self, key: str, value: Any):
        # Clean expired entries
        self._cleanup_expired()
        
        # Limit size
        if len(self.data) >= self.max_len:
            # Remove oldest entry
            oldest_key = min(self.data.keys(), key=lambda k: self.data[k][1])
            del self.data[oldest_key]
        
        self.data[key] = (value, time.time())
    
    def _cleanup_expired(self):
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.data.items()
            if current_time - timestamp > self.max_age_seconds
        ]
        for key in expired_keys:
            del self.data[key]
    
    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
    
    def clear(self):
        """Clear all cached entries."""
        self.data.clear()


class CachedProjectDetector:
    """Project detector with intelligent caching for performance optimization."""
    
    def __init__(self, cache_duration: int = 3600):
        self.cache_duration = cache_duration
        self.project_cache = ExpiringDict(max_len=100, max_age_seconds=cache_duration)
        self.file_hash_cache = ExpiringDict(max_len=200, max_age_seconds=cache_duration * 2)
        self.cache_file = Path.home() / '.sega' / 'project_cache.json'
        self.cache_file.parent.mkdir(exist_ok=True)
        
        # Load persistent cache
        self._load_persistent_cache()
    
    def detect_project_type(self, project_path: Path) -> Dict[str, Any]:
        """Detect project type with intelligent caching."""
        project_path = Path(project_path).resolve()
        
        # Generate cache key based on path and modification time
        cache_key = self._generate_cache_key(project_path)
        
        # Check cache first
        cached_result = self.project_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Perform actual detection
        result = self._perform_detection(project_path)
        
        # Cache the result
        self.project_cache[cache_key] = result
        
        # Update persistent cache
        self._save_persistent_cache()
        
        return result
    
    def _generate_cache_key(self, project_path: Path) -> str:
        """Generate cache key based on path and key files' modification times."""
        try:
            # Key files that affect project type detection
            key_files = [
                'package.json', 'requirements.txt', 'Cargo.toml', 'Makefile',
                'sega.yaml', 'sega.yml', 'Dockerfile', 'docker-compose.yml'
            ]
            
            file_info = []
            for filename in key_files:
                file_path = project_path / filename
                if file_path.exists():
                    stat = file_path.stat()
                    file_info.append(f"{filename}:{stat.st_mtime}")
            
            # Include directory modification time as well
            dir_stat = project_path.stat()
            file_info.append(f"dir:{dir_stat.st_mtime}")
            
            # Create hash of path and file modification times
            cache_content = f"{project_path}:{'|'.join(file_info)}"
            return hashlib.md5(cache_content.encode()).hexdigest()
        
        except Exception:
            # Fallback to simple path-based key
            return hashlib.md5(str(project_path).encode()).hexdigest()
    
    def _perform_detection(self, project_path: Path) -> Dict[str, Any]:
        """Perform actual project detection (delegated to original detector)."""
        # Import here to avoid circular imports
        from .project_detector import ProjectDetector
        
        detector = ProjectDetector(str(project_path))
        
        # Build comprehensive project information
        result = {
            'project_type': detector.detect(),
            'build_config': detector.build_config(),
            'detected_files': self._get_detected_files(project_path),
            'capabilities': self._detect_capabilities(project_path),
            'frameworks': self._detect_frameworks(project_path),
            'detection_timestamp': time.time()
        }
        
        return result
    
    def _get_detected_files(self, project_path: Path) -> Dict[str, bool]:
        """Get information about detected project files."""
        files_to_check = [
            'package.json', 'requirements.txt', 'Cargo.toml', 'go.mod',
            'Makefile', 'CMakeLists.txt', 'build.gradle', 'pom.xml',
            'sega.yaml', 'sega.yml', 'Dockerfile', 'docker-compose.yml',
            '.env', '.env.example', 'README.md'
        ]
        
        return {
            filename: (project_path / filename).exists()
            for filename in files_to_check
        }
    
    def _detect_capabilities(self, project_path: Path) -> Dict[str, bool]:
        """Detect project capabilities."""
        capabilities = {
            'has_tests': self._has_test_directory(project_path),
            'has_docker': (project_path / 'Dockerfile').exists(),
            'has_ci': self._has_ci_config(project_path),
            'has_databBase': self._has_database_config(project_path),
            'has_frontend': self._has_frontend_assets(project_path),
            'has_api': self._has_api_endpoints(project_path),
            'has_mobile': self._has_mobile_config(project_path),
            'has_desktop': self._has_desktop_config(project_path)
        }
        
        return capabilities
    
    def _detect_frameworks(self, project_path: Path) -> List[str]:
        """Detect frameworks used in the project."""
        frameworks = []
        
        # Check package.json for JavaScript/TypeScript frameworks
        package_json_path = project_path / 'package.json'
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                
                deps = {**package_data.get('dependencies', {}), 
                       **package_data.get('devDependencies', {})}
                
                if 'react' in deps:
                    frameworks.append('React')
                if 'next' in deps:
                    frameworks.append('Next.js')
                if 'vue' in deps:
                    frameworks.append('Vue.js')
                if 'angular' in deps:
                    frameworks.append('Angular')
                if 'express' in deps:
                    frameworks.append('Express')
                if 'fastify' in deps:
                    frameworks.append('Fastify')
                if 'electron' in deps:
                    frameworks.append('Electron')
                if 'expo' in deps:
                    frameworks.append('Expo')
                
            except:
                pass
        
        # Check requirements.txt for Python frameworks
        requirements_path = project_path / 'requirements.txt'
        if requirements_path.exists():
            try:
                with open(requirements_path, 'r') as f:
                    requirements = f.read().lower()
                
                if 'django' in requirements:
                    frameworks.append('Django')
                if 'flask' in requirements:
                    frameworks.append('Flask')
                if 'fastapi' in requirements:
                    frameworks.append('FastAPI')
                if 'pytorch' in requirements:
                    frameworks.append('PyTorch')
                if 'tensorflow' in requirements:
                    frameworks.append('TensorFlow')
                
            except:
                pass
        
        return frameworks
    
    def _has_test_directory(self, project_path: Path) -> bool:
        """Check if project has test directory."""
        test_dirs = ['tests', 'test', '__tests__', 'spec']
        return any((project_path / dirname).exists() for dirname in test_dirs)
    
    def _has_ci_config(self, project_path: Path) -> bool:
        """Check if project has CI configuration."""
        ci_files = ['.github/workflows', '.gitlab-ci.yml', '.travis.yml', 'Jenkinsfile']
        return any((project_path / filename).exists() for filename in ci_files)
    
    def _has_database_config(self, project_path: Path) -> bool:
        """Check if project has database configuration."""
        return (project_path / 'docker-compose.yml').exists() and self._check_docker_compose_for_db(project_path)
    
    def _check_docker_compose_for_db(self, project_path: Path) -> bool:
        """Check docker-compose.yml for database services."""
        compose_file = project_path / 'docker-compose.yml'
        if not compose_file.exists():
            return False
        
        try:
            with open(compose_file, 'r') as f:
                content = f.read().lower()
            
            db_indicators = ['postgres', 'mysql', 'mongodb', 'redis', 'timescaledb']
            return any(indicator in content for indicator in db_indicators)
        
        except:
            return False
    
    def _has_frontend_assets(self, project_path: Path) -> bool:
        """Check if project has frontend assets."""
        frontend_dirs = ['src', 'public', 'assets', 'static', 'frontend']
        frontend_files = ['index.html', 'app.js', 'main.js']
        
        return (any((project_path / dirname).exists() for dirname in frontend_dirs) or
                any((project_path / filename).exists() for filename in frontend_files))
    
    def _has_api_endpoints(self, project_path: Path) -> bool:
        """Check if project likely has API endpoints."""
        api_indicators = [
            'src/api', 'api', 'routes', 'controllers', 'handlers',
            'app.py', 'main.py', 'server.js', 'app.js'
        ]
        
        return any((project_path / indicator).exists() for indicator in api_indicators)
    
    def _has_mobile_config(self, project_path: Path) -> bool:
        """Check if project has mobile configuration."""
        mobile_files = ['app.json', 'expo.json', 'metro.config.js', 'react-native.config.js']
        return any((project_path / filename).exists() for filename in mobile_files)
    
    def _has_desktop_config(self, project_path: Path) -> bool:
        """Check if project has desktop configuration."""
        desktop_indicators = ['electron', 'tauri', 'nwjs']
        
        package_json_path = project_path / 'package.json'
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                
                deps = {**package_data.get('dependencies', {}), 
                       **package_data.get('devDependencies', {})}
                
                return any(indicator in deps for indicator in desktop_indicators)
            except:
                pass
        
        return False
    
    def _load_persistent_cache(self):
        """Load cache from persistent storage."""
        if not self.cache_file.exists():
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Only load non-expired entries
            current_time = time.time()
            for key, entry_data in cache_data.items():
                if current_time - entry_data.get('timestamp', 0) < self.cache_duration:
                    self.project_cache.data[key] = (entry_data, entry_data.get('timestamp', current_time))
        
        except:
            pass
    
    def _save_persistent_cache(self):
        """Save cache to persistent storage."""
        try:
            cache_data = {}
            for key, (value, timestamp) in self.project_cache.data.items():
                if isinstance(value, dict):
                    cache_data[key] = {**value, 'cache_timestamp': timestamp}
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        
        except:
            pass
    
    def invalidate_cache(self, project_path: Optional[Path] = None):
        """Invalidate cache entries."""
        if project_path:
            # Invalidate specific project
            cache_key = self._generate_cache_key(Path(project_path))
            if cache_key in self.project_cache.data:
                del self.project_cache.data[cache_key]
        else:
            # Clear all cache
            self.project_cache.clear()
            self.file_hash_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'project_cache_size': len(self.project_cache.data),
            'file_hash_cache_size': len(self.file_hash_cache.data),
            'cache_duration': self.cache_duration,
            'cache_file': str(self.cache_file)
        }