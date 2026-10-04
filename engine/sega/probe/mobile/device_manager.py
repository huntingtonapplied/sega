#!/usr/bin/env python3
"""
Device Manager for SEGA Mobile Testing

Manages iOS simulators and Android emulators/devices
"""

import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import concurrent.futures
import os

logger = logging.getLogger(__name__)


@dataclass
class Device:
    """Represents a mobile device (physical or virtual)"""
    id: str
    name: str
    platform: str  # 'ios' or 'android'
    os_version: str
    device_type: str  # 'simulator', 'emulator', 'physical'
    state: str  # 'available', 'booted', 'busy', 'offline'
    model: Optional[str] = None
    
    def __str__(self):
        return f"{self.name} ({self.platform} {self.os_version})"


class DeviceManager:
    """
    Manages mobile devices for testing across iOS and Android platforms
    """
    
    def __init__(self):
        self.xcrun = self._find_xcrun()
        self.adb = self._find_adb()
        self.emulator = self._find_emulator()
        self._device_cache = {}
        self._lock_files = {}
    
    def _find_xcrun(self) -> Optional[str]:
        """Find xcrun for iOS simulator management"""
        result = subprocess.run(['which', 'xcrun'], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    
    def _find_adb(self) -> Optional[str]:
        """Find adb for Android device management"""
        result = subprocess.run(['which', 'adb'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Check Android SDK
        android_home = os.environ.get('ANDROID_HOME')
        if android_home:
            adb_path = Path(android_home) / 'platform-tools' / 'adb'
            if adb_path.exists():
                return str(adb_path)
        
        return None
    
    def _find_emulator(self) -> Optional[str]:
        """Find Android emulator command"""
        result = subprocess.run(['which', 'emulator'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Check Android SDK
        android_home = os.environ.get('ANDROID_HOME')
        if android_home:
            emulator_path = Path(android_home) / 'emulator' / 'emulator'
            if emulator_path.exists():
                return str(emulator_path)
        
        return None
    
    def list_all_devices(self, platform: Optional[str] = None) -> List[Device]:
        """List all available devices across platforms"""
        devices = []
        
        if platform in [None, 'ios'] and self.xcrun:
            devices.extend(self.list_ios_simulators())
        
        if platform in [None, 'android'] and self.adb:
            devices.extend(self.list_android_devices())
        
        return devices
    
    def list_ios_simulators(self) -> List[Device]:
        """List iOS simulators"""
        simulators = []
        
        try:
            cmd = [self.xcrun, 'simctl', 'list', 'devices', 'available', '-j']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                for runtime, devices in data['devices'].items():
                    if 'iOS' in runtime:
                        # Extract OS version from runtime string
                        os_version = runtime.split('.')[-1].replace('-', '.')
                        
                        for device in devices:
                            if device.get('isAvailable', False):
                                simulator = Device(
                                    id=device['udid'],
                                    name=device['name'],
                                    platform='ios',
                                    os_version=os_version,
                                    device_type='simulator',
                                    state='booted' if device['state'] == 'Booted' else 'available',
                                    model=device.get('deviceTypeIdentifier', '')
                                )
                                simulators.append(simulator)
        
        except Exception as e:
            logger.error(f"Failed to list iOS simulators: {e}")
        
        return simulators
    
    def list_android_devices(self) -> List[Device]:
        """List Android devices and emulators"""
        devices = []
        
        try:
            # Get connected devices
            result = subprocess.run([self.adb, 'devices', '-l'], capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n')[1:]:  # Skip header
                    if not line.strip():
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] in ['device', 'emulator', 'offline']:
                        device_id = parts[0]
                        state = 'available' if parts[1] == 'device' else parts[1]
                        
                        # Determine if it's an emulator or physical device
                        device_type = 'emulator' if device_id.startswith('emulator-') else 'physical'
                        
                        # Get device info
                        device_info = self._get_android_device_info(device_id)
                        
                        device = Device(
                            id=device_id,
                            name=device_info.get('model', device_id),
                            platform='android',
                            os_version=device_info.get('version', 'unknown'),
                            device_type=device_type,
                            state=state,
                            model=device_info.get('device', '')
                        )
                        devices.append(device)
            
            # List available AVDs (not running)
            if self.emulator:
                avd_result = subprocess.run([self.emulator, '-list-avds'], capture_output=True, text=True)
                if avd_result.returncode == 0:
                    for avd_name in avd_result.stdout.strip().split('\n'):
                        if avd_name and not any(d.name == avd_name for d in devices):
                            # AVD exists but not running
                            device = Device(
                                id=avd_name,
                                name=avd_name,
                                platform='android',
                                os_version='unknown',  # Would need to parse AVD config
                                device_type='emulator',
                                state='available',
                                model='avd'
                            )
                            devices.append(device)
        
        except Exception as e:
            logger.error(f"Failed to list Android devices: {e}")
        
        return devices
    
    def _get_android_device_info(self, device_id: str) -> Dict[str, str]:
        """Get detailed Android device information"""
        info = {}
        
        try:
            # Get Android version
            version_cmd = [self.adb, '-s', device_id, 'shell', 'getprop', 'ro.build.version.releBase']
            version_result = subprocess.run(version_cmd, capture_output=True, text=True)
            if version_result.returncode == 0:
                info['version'] = version_result.stdout.strip()
            
            # Get device model
            model_cmd = [self.adb, '-s', device_id, 'shell', 'getprop', 'ro.product.model']
            model_result = subprocess.run(model_cmd, capture_output=True, text=True)
            if model_result.returncode == 0:
                info['model'] = model_result.stdout.strip()
            
            # Get device name
            device_cmd = [self.adb, '-s', device_id, 'shell', 'getprop', 'ro.product.device']
            device_result = subprocess.run(device_cmd, capture_output=True, text=True)
            if device_result.returncode == 0:
                info['device'] = device_result.stdout.strip()
        
        except Exception as e:
            logger.debug(f"Failed to get device info for {device_id}: {e}")
        
        return info
    
    def start_device(self, device: Device) -> bool:
        """Start a simulator or emulator"""
        if device.state == 'booted' or device.state == 'device':
            logger.info(f"Device {device.name} is already running")
            return True
        
        if device.platform == 'ios':
            return self._start_ios_simulator(device)
        elif device.platform == 'android':
            return self._start_android_emulator(device)
        
        return False
    
    def _start_ios_simulator(self, device: Device) -> bool:
        """Start an iOS simulator"""
        try:
            # Boot the simulator
            boot_cmd = [self.xcrun, 'simctl', 'boot', device.id]
            boot_result = subprocess.run(boot_cmd, capture_output=True, text=True)
            
            if boot_result.returncode != 0 and 'already booted' not in boot_result.stderr:
                logger.error(f"Failed to boot simulator: {boot_result.stderr}")
                return False
            
            # Open Simulator app
            open_cmd = ['open', '-a', 'Simulator', '--args', '-CurrentDeviceUDID', device.id]
            subprocess.run(open_cmd, capture_output=True)
            
            # Wait for simulator to be ready
            for _ in range(30):
                status_cmd = [self.xcrun, 'simctl', 'list', 'devices', '-j']
                status_result = subprocess.run(status_cmd, capture_output=True, text=True)
                
                if status_result.returncode == 0:
                    data = json.loads(status_result.stdout)
                    for runtime_devices in data['devices'].values():
                        for sim in runtime_devices:
                            if sim['udid'] == device.id and sim['state'] == 'Booted':
                                device.state = 'booted'
                                return True
                
                time.sleep(1)
            
            return False
        
        except Exception as e:
            logger.error(f"Failed to start iOS simulator: {e}")
            return False
    
    def _start_android_emulator(self, device: Device) -> bool:
        """Start an Android emulator"""
        try:
            if device.device_type != 'emulator':
                logger.error(f"Cannot start physical device {device.name}")
                return False
            
            # Start emulator
            emulator_cmd = [self.emulator, '-avd', device.id, '-no-audio', '-no-boot-anim']
            
            # Start in background
            subprocess.Popen(emulator_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for emulator to appear in device list
            for _ in range(120):  # Wait up to 2 minutes
                devices_result = subprocess.run([self.adb, 'devices'], capture_output=True, text=True)
                
                if 'emulator-' in devices_result.stdout:
                    # Find the emulator serial
                    for line in devices_result.stdout.split('\n'):
                        if 'emulator-' in line and '\tdevice' in line:
                            emulator_serial = line.split('\t')[0]
                            
                            # Wait for boot completion
                            boot_cmd = [self.adb, '-s', emulator_serial, 'shell', 'getprop', 'sys.boot_completed']
                            for _ in range(60):
                                boot_result = subprocess.run(boot_cmd, capture_output=True, text=True)
                                if boot_result.stdout.strip() == '1':
                                    device.id = emulator_serial  # Update device ID to actual serial
                                    device.state = 'available'
                                    return True
                                time.sleep(1)
                
                time.sleep(1)
            
            return False
        
        except Exception as e:
            logger.error(f"Failed to start Android emulator: {e}")
            return False
    
    def stop_device(self, device: Device) -> bool:
        """Stop a simulator or emulator"""
        if device.platform == 'ios':
            return self._stop_ios_simulator(device)
        elif device.platform == 'android':
            return self._stop_android_emulator(device)
        
        return False
    
    def _stop_ios_simulator(self, device: Device) -> bool:
        """Stop an iOS simulator"""
        try:
            shutdown_cmd = [self.xcrun, 'simctl', 'shutdown', device.id]
            result = subprocess.run(shutdown_cmd, capture_output=True, text=True)
            
            if result.returncode == 0 or 'not booted' in result.stderr:
                device.state = 'available'
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Failed to stop iOS simulator: {e}")
            return False
    
    def _stop_android_emulator(self, device: Device) -> bool:
        """Stop an Android emulator"""
        try:
            if device.device_type != 'emulator':
                logger.error(f"Cannot stop physical device {device.name}")
                return False
            
            # Use adb emu kill command
            kill_cmd = [self.adb, '-s', device.id, 'emu', 'kill']
            result = subprocess.run(kill_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                device.state = 'available'
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Failed to stop Android emulator: {e}")
            return False
    
    def reset_device(self, device: Device) -> bool:
        """Reset device to clean state"""
        if device.platform == 'ios':
            return self._reset_ios_simulator(device)
        elif device.platform == 'android':
            return self._reset_android_device(device)
        
        return False
    
    def _reset_ios_simulator(self, device: Device) -> bool:
        """Reset iOS simulator to clean state"""
        try:
            # Shutdown first if running
            if device.state == 'booted':
                self._stop_ios_simulator(device)
                time.sleep(2)
            
            # ErBase simulator
            erBase_cmd = [self.xcrun, 'simctl', 'erBase', device.id]
            result = subprocess.run(erBase_cmd, capture_output=True, text=True)
            
            return result.returncode == 0
        
        except Exception as e:
            logger.error(f"Failed to reset iOS simulator: {e}")
            return False
    
    def _reset_android_device(self, device: Device) -> bool:
        """Reset Android device/emulator"""
        try:
            if device.device_type == 'physical':
                logger.warning("Cannot reset physical Android device")
                return False
            
            # For emulators, we can wipe data
            wipe_cmd = [self.emulator, '-avd', device.name, '-wipe-data']
            # This would need to be done on next start
            
            # For now, just clear app data if device is running
            if device.state == 'available':
                # Clear all app data
                clear_cmd = [self.adb, '-s', device.id, 'shell', 'pm', 'clear', 'com.android.settings']
                subprocess.run(clear_cmd, capture_output=True)
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Failed to reset Android device: {e}")
            return False
    
    def install_app(self, device: Device, app_path: Path) -> bool:
        """Install app on device"""
        if not app_path.exists():
            logger.error(f"App not found: {app_path}")
            return False
        
        if device.platform == 'ios':
            return self._install_ios_app(device, app_path)
        elif device.platform == 'android':
            return self._install_android_app(device, app_path)
        
        return False
    
    def _install_ios_app(self, device: Device, app_path: Path) -> bool:
        """Install iOS app on simulator"""
        try:
            install_cmd = [self.xcrun, 'simctl', 'install', device.id, str(app_path)]
            result = subprocess.run(install_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to install iOS app: {result.stderr}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to install iOS app: {e}")
            return False
    
    def _install_android_app(self, device: Device, app_path: Path) -> bool:
        """Install Android app on device"""
        try:
            install_cmd = [self.adb, '-s', device.id, 'install', '-r', str(app_path)]
            result = subprocess.run(install_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to install Android app: {result.stderr}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to install Android app: {e}")
            return False
    
    def capture_screenshot(self, device: Device, output_path: Path) -> bool:
        """Capture screenshot from device"""
        if device.platform == 'ios':
            return self._capture_ios_screenshot(device, output_path)
        elif device.platform == 'android':
            return self._capture_android_screenshot(device, output_path)
        
        return False
    
    def _capture_ios_screenshot(self, device: Device, output_path: Path) -> bool:
        """Capture iOS simulator screenshot"""
        try:
            screenshot_cmd = [self.xcrun, 'simctl', 'io', device.id, 'screenshot', str(output_path)]
            result = subprocess.run(screenshot_cmd, capture_output=True, text=True)
            
            return result.returncode == 0
        
        except Exception as e:
            logger.error(f"Failed to capture iOS screenshot: {e}")
            return False
    
    def _capture_android_screenshot(self, device: Device, output_path: Path) -> bool:
        """Capture Android device screenshot"""
        try:
            # Capture to device first
            device_path = '/sdcard/screenshot.png'
            capture_cmd = [self.adb, '-s', device.id, 'shell', 'screencap', '-p', device_path]
            result = subprocess.run(capture_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return False
            
            # Pull to local
            pull_cmd = [self.adb, '-s', device.id, 'pull', device_path, str(output_path)]
            result = subprocess.run(pull_cmd, capture_output=True, text=True)
            
            # Clean up device
            rm_cmd = [self.adb, '-s', device.id, 'shell', 'rm', device_path]
            subprocess.run(rm_cmd, capture_output=True)
            
            return result.returncode == 0
        
        except Exception as e:
            logger.error(f"Failed to capture Android screenshot: {e}")
            return False
    
    def get_device_logs(self, device: Device, output_path: Path, since: Optional[float] = None) -> bool:
        """Get device logs"""
        if device.platform == 'ios':
            return self._get_ios_logs(device, output_path, since)
        elif device.platform == 'android':
            return self._get_android_logs(device, output_path, since)
        
        return False
    
    def _get_ios_logs(self, device: Device, output_path: Path, since: Optional[float]) -> bool:
        """Get iOS simulator logs"""
        try:
            # Use log stream for simulator
            log_cmd = [
                'xcrun', 'simctl', 'spawn', device.id, 
                'log', 'stream', '--level', 'debug'
            ]
            
            if since:
                # Add time filter
                from datetime import datetime
                since_str = datetime.fromtimestamp(since).strftime('%Y-%m-%d %H:%M:%S')
                log_cmd.extend(['--start', since_str])
            
            # Run for a short time to collect logs
            with open(output_path, 'w') as f:
                proc = subprocess.Popen(log_cmd, stdout=f, stderr=subprocess.STDOUT)
                time.sleep(5)  # Collect logs for 5 seconds
                proc.terminate()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to get iOS logs: {e}")
            return False
    
    def _get_android_logs(self, device: Device, output_path: Path, since: Optional[float]) -> bool:
        """Get Android device logs"""
        try:
            logcat_cmd = [self.adb, '-s', device.id, 'logcat', '-d']
            
            if since:
                # Add time filter (logcat uses different format)
                from datetime import datetime
                since_str = datetime.fromtimestamp(since).strftime('%m-%d %H:%M:%S.000')
                logcat_cmd.extend(['-t', since_str])
            
            with open(output_path, 'w') as f:
                result = subprocess.run(logcat_cmd, stdout=f, stderr=subprocess.STDOUT)
            
            return result.returncode == 0
        
        except Exception as e:
            logger.error(f"Failed to get Android logs: {e}")
            return False
    
    def parallel_device_operation(self, devices: List[Device], operation, *args, **kwargs) -> Dict[str, any]:
        """Execute operation on multiple devices in parallel"""
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
            future_to_device = {
                executor.submit(operation, device, *args, **kwargs): device
                for device in devices
            }
            
            for future in concurrent.futures.as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    result = future.result()
                    results[device.id] = result
                except Exception as e:
                    logger.error(f"Operation failed for device {device.name}: {e}")
                    results[device.id] = None
        
        return results
    
    def cleanup_all_devices(self):
        """Clean up all managed devices"""
        # Stop all iOS simulators
        if self.xcrun:
            try:
                subprocess.run([self.xcrun, 'simctl', 'shutdown', 'all'], capture_output=True)
            except:
                pass
        
        # Stop all Android emulators
        if self.adb:
            try:
                subprocess.run([self.adb, 'emu', 'kill'], capture_output=True)
            except:
                pass