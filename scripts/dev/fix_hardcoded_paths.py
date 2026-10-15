#!/usr/bin/env python3
"""Fix hardcoded /home/testuser paths in SEGA codebase"""

import re
from pathlib import Path

files_to_update = [
    'src/sega/commands/secrets_extended.py',
    'src/sega/commands/test_browser.py',
    'src/sega/commands/corruption_enhanced.py',
    'src/sega/commands/corruption.py',
    'src/sega/commands/test_local.py',
    'src/sega/commands/desktop.py',
    'src/sega/testing/unified_test_runner.py',
    'src/sega/testing/build_tool_manager.py',
    'src/sega/testing/dependency_resolver.py',
    'src/sega/testing/engine_test_runner.py',
    'src/sega/testing/enhanced_browser_runner.py',
    'src/sega/testing/browser_test_runner.py',
    'src/sega/installation/installer.py',
    'src/sega/core/optimized_resource_manager.py',
]

# Pattern replacements
patterns = [
    (r'Path\(os\.getenv\("FLEET_ROOT", "/home/testuser/workspace"\)\)', 'get_fleet_root()'),
    (r'Path\(os\.environ\.get\(\'FLEET_ROOT\', \'/home/testuser/workspace\'\)\)', 'get_fleet_root()'),
    (r'Path\("/home/testuser/workspace"\)', 'get_fleet_root()'),
    (r'Path\(\'/home/testuser/workspace\'\)', 'get_fleet_root()'),
]

for file_path in files_to_update:
    path = Path(file_path)
    if not path.exists():
        print(f'SKIP: {file_path}')
        continue

    content = path.read_text()
    original_content = content
    modified = False

    # Check if already has import
    has_import = 'from ..utils.paths import get_fleet_root' in content

    # Apply replacements
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            modified = True

    # Add import if needed and modifications were made
    if modified and not has_import:
        # Find the last import line
        lines = content.split('\n')
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_idx = i

        # Insert the import after the last import
        lines.insert(last_import_idx + 1, 'from ..utils.paths import get_fleet_root')
        content = '\n'.join(lines)

    if content != original_content:
        path.write_text(content)
        print(f'UPDATED: {file_path}')
    else:
        print(f'NO CHANGE: {file_path}')

print('\nDone!')
