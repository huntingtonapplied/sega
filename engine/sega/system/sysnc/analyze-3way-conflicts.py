#!/usr/bin/env python3
"""
3-Way Change Monitoring and Conflict Detection
Analyzes changes across Local, Instance 1, Instance 2

Part of FLEET Multi-System Tooling Suite
Location: ~/fleet/dispatcher/tools/analyze-3way-conflicts.py
"""

import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def read_file_list(path):
    """Read a file list and return as set of paths"""
    try:
        with open(path) as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(3)

def categorize_files(files):
    """Categorize files by subsystem"""
    categories = defaultdict(list)
    for f in sorted(files):
        if 'dispatcher/' in f:
            categories['DISPATCHER'].append(f)
        elif 'tracker/human/' in f:
            categories['Tracker/Human'].append(f)
        elif 'spro/' in f:
            categories['Spro'].append(f)
        elif 'orion/' in f:
            categories['ORION'].append(f)
        elif 'docs/healer' in f:
            categories['Healer'].append(f)
        elif 'docs/surgeon' in f:
            categories['Surgeon'].append(f)
        elif 'atlas/' in f:
            categories['Atlas'].append(f)
        elif 'docs/' in f:
            categories['Docs'].append(f)
        elif '.claude/settings' in f:
            categories['Claude Settings'].append(f)
        else:
            # Check for project names
            projects_g1 = ['telemetry', 'orion', 'atlas', 'atlas', 'hermes', 'hermes', 'orion']
            projects_g2 = ['hermes', 'hermes', 'vega', 'atlas', 'hermes', 'atlas', 'scanner_app', 'atlas']

            if any(p in f for p in projects_g1):
                categories['Projects Group 1'].append(f)
            elif any(p in f for p in projects_g2):
                categories['Projects Group 2'].append(f)
            else:
                categories['Other'].append(f)
    return categories

def analyze_conflicts(local_files, i1_files, i2_files):
    """Perform 3-way conflict analysis"""
    # Calculate statistics
    total_unique_files = local_files | i1_files | i2_files
    conflicts_local_i1 = local_files & i1_files
    conflicts_local_i2 = local_files & i2_files
    conflicts_i1_i2 = i1_files & i2_files
    three_way_conflicts = local_files & i1_files & i2_files

    # Files unique to each system
    local_only = local_files - i1_files - i2_files
    i1_only = i1_files - local_files - i2_files
    i2_only = i2_files - local_files - i1_files

    return {
        'total_unique_files': total_unique_files,
        'conflicts_local_i1': conflicts_local_i1,
        'conflicts_local_i2': conflicts_local_i2,
        'conflicts_i1_i2': conflicts_i1_i2,
        'three_way_conflicts': three_way_conflicts,
        'local_only': local_only,
        'i1_only': i1_only,
        'i2_only': i2_only
    }

def print_human_report(local_files, i1_files, i2_files, analysis):
    """Print human-readable report"""
    print("="*80)
    print("3-WAY CHANGE MONITORING & CONFLICT DETECTION REPORT")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("SYSTEM SUMMARY")
    print("-"*80)
    print(f"Local System:        {len(local_files):4d} changed files")
    print(f"Instance 1 (i1):     {len(i1_files):4d} changed files")
    print(f"Instance 2 (i2):     {len(i2_files):4d} changed files")
    print(f"Total unique files:  {len(analysis['total_unique_files']):4d}")
    print()

    print("CONFLICT SUMMARY")
    print("-"*80)
    print(f"Local <-> i1:        {len(analysis['conflicts_local_i1']):4d} files")
    print(f"Local <-> i2:        {len(analysis['conflicts_local_i2']):4d} files")
    print(f"i1 <-> i2:           {len(analysis['conflicts_i1_i2']):4d} files")
    print(f"THREE-WAY (all 3):   {len(analysis['three_way_conflicts']):4d} files 🔥")
    print()

    print("UNIQUE CHANGES (No Conflicts)")
    print("-"*80)
    print(f"Local only:          {len(analysis['local_only']):4d} files")
    print(f"Instance 1 only:     {len(analysis['i1_only']):4d} files")
    print(f"Instance 2 only:     {len(analysis['i2_only']):4d} files")
    print()

    # Detailed conflict breakdown
    if analysis['three_way_conflicts']:
        print("="*80)
        print("🔥 THREE-WAY CONFLICTS (Changed on ALL systems)")
        print("="*80)
        categories = categorize_files(analysis['three_way_conflicts'])
        for cat, files in sorted(categories.items()):
            print(f"\n{cat} ({len(files)}):")
            for f in files:
                print(f"  • {f}")
        print()

    if analysis['conflicts_local_i1'] - analysis['three_way_conflicts']:
        print("="*80)
        print("LOCAL <-> INSTANCE 1 CONFLICTS (not on i2)")
        print("="*80)
        categories = categorize_files(analysis['conflicts_local_i1'] - analysis['three_way_conflicts'])
        for cat, files in sorted(categories.items()):
            print(f"\n{cat} ({len(files)}):")
            for f in files[:20]:
                print(f"  • {f}")
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more")
        print()

    if analysis['conflicts_local_i2'] - analysis['three_way_conflicts']:
        print("="*80)
        print("LOCAL <-> INSTANCE 2 CONFLICTS (not on i1)")
        print("="*80)
        categories = categorize_files(analysis['conflicts_local_i2'] - analysis['three_way_conflicts'])
        for cat, files in sorted(categories.items()):
            print(f"\n{cat} ({len(files)}):")
            for f in files[:20]:
                print(f"  • {f}")
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more")
        print()

    if analysis['conflicts_i1_i2'] - analysis['three_way_conflicts']:
        print("="*80)
        print("INSTANCE 1 <-> INSTANCE 2 CONFLICTS (not on local)")
        print("="*80)
        categories = categorize_files(analysis['conflicts_i1_i2'] - analysis['three_way_conflicts'])
        for cat, files in sorted(categories.items()):
            print(f"\n{cat} ({len(files)}):")
            for f in files[:20]:
                print(f"  • {f}")
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more")
        print()

    print("="*80)
    print("CONSOLIDATION PRIORITY MATRIX")
    print("="*80)
    print()
    print("Priority 1: THREE-WAY CONFLICTS")
    print(f"  → {len(analysis['three_way_conflicts'])} files need manual review/merge")
    print()
    print("Priority 2: TWO-WAY CONFLICTS")
    print(f"  → Local <-> i1: {len(analysis['conflicts_local_i1'] - analysis['three_way_conflicts'])} files")
    print(f"  → Local <-> i2: {len(analysis['conflicts_local_i2'] - analysis['three_way_conflicts'])} files")
    print(f"  → i1 <-> i2: {len(analysis['conflicts_i1_i2'] - analysis['three_way_conflicts'])} files")
    print()
    print("Priority 3: UNIQUE CHANGES (safe to consolidate)")
    print(f"  → {len(analysis['local_only']) + len(analysis['i1_only']) + len(analysis['i2_only'])} files total")
    print()

def output_json(local_files, i1_files, i2_files, analysis):
    """Output JSON format"""
    # Convert sets to sorted lists for JSON serialization
    result = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'local_files': len(local_files),
            'instance1_files': len(i1_files),
            'instance2_files': len(i2_files),
            'total_unique_files': len(analysis['total_unique_files'])
        },
        'conflicts': {
            'local_i1': len(analysis['conflicts_local_i1']),
            'local_i2': len(analysis['conflicts_local_i2']),
            'i1_i2': len(analysis['conflicts_i1_i2']),
            'three_way': len(analysis['three_way_conflicts'])
        },
        'unique_changes': {
            'local_only': len(analysis['local_only']),
            'i1_only': len(analysis['i1_only']),
            'i2_only': len(analysis['i2_only'])
        },
        'details': {
            'three_way_conflicts': sorted(list(analysis['three_way_conflicts'])),
            'conflicts_local_i1': sorted(list(analysis['conflicts_local_i1'])),
            'conflicts_local_i2': sorted(list(analysis['conflicts_local_i2'])),
            'conflicts_i1_i2': sorted(list(analysis['conflicts_i1_i2'])),
            'local_only': sorted(list(analysis['local_only'])),
            'i1_only': sorted(list(analysis['i1_only'])),
            'i2_only': sorted(list(analysis['i2_only']))
        }
    }
    print(json.dumps(result, indent=2))

def save_output_files(analysis, output_dir):
    """Save detailed conflict lists to files"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Three-way conflicts
    three_way_file = output_dir / 'three-way-conflicts.txt'
    with open(three_way_file, 'w') as f:
        for file in sorted(analysis['three_way_conflicts']):
            f.write(f"{file}\n")

    # Two-way conflicts
    all_two_way = (analysis['conflicts_local_i1'] | analysis['conflicts_local_i2'] |
                   analysis['conflicts_i1_i2']) - analysis['three_way_conflicts']
    two_way_file = output_dir / 'two-way-conflicts.txt'
    with open(two_way_file, 'w') as f:
        for file in sorted(all_two_way):
            f.write(f"{file}\n")

    # Unique changes by system
    local_only_file = output_dir / 'local-only.txt'
    with open(local_only_file, 'w') as f:
        for file in sorted(analysis['local_only']):
            f.write(f"{file}\n")

    i1_only_file = output_dir / 'instance1-only.txt'
    with open(i1_only_file, 'w') as f:
        for file in sorted(analysis['i1_only']):
            f.write(f"{file}\n")

    i2_only_file = output_dir / 'instance2-only.txt'
    with open(i2_only_file, 'w') as f:
        for file in sorted(analysis['i2_only']):
            f.write(f"{file}\n")

    return {
        'three_way': three_way_file,
        'two_way': two_way_file,
        'local_only': local_only_file,
        'i1_only': i1_only_file,
        'i2_only': i2_only_file
    }

def main():
    parser = argparse.ArgumentParser(
        description='3-Way Change Monitoring and Conflict Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default usage (human-readable report)
  %(prog)s

  # JSON output
  %(prog)s --json

  # Custom input file locations
  %(prog)s --local /path/to/local-files.txt --i1 /path/to/i1-files.txt --i2 /path/to/i2-files.txt

  # Custom output directory
  %(prog)s --output ~/fleet/dispatcher/reports/conflicts-$(date +%%Y%%m%%d)
        """
    )

    parser.add_argument('--local', default='/tmp/local-files.txt',
                        help='Path to local system file list (default: /tmp/local-files.txt)')
    parser.add_argument('--i1', default='/tmp/instance1-files.txt',
                        help='Path to instance 1 file list (default: /tmp/instance1-files.txt)')
    parser.add_argument('--i2', default='/tmp/instance2-files.txt',
                        help='Path to instance 2 file list (default: /tmp/instance2-files.txt)')
    parser.add_argument('--output', default='/tmp',
                        help='Output directory for conflict files (default: /tmp)')
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format instead of human-readable')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress output file creation messages')

    args = parser.parse_args()

    # Load file lists
    local_files = read_file_list(args.local)
    i1_files = read_file_list(args.i1)
    i2_files = read_file_list(args.i2)

    # Perform analysis
    analysis = analyze_conflicts(local_files, i1_files, i2_files)

    # Output report
    if args.json:
        output_json(local_files, i1_files, i2_files, analysis)
    else:
        print_human_report(local_files, i1_files, i2_files, analysis)

    # Save output files
    if not args.json:
        output_files = save_output_files(analysis, args.output)
        if not args.quiet:
            print("="*80)
            print("Output files created:")
            print(f"  {output_files['three_way']}  - Files changed on all 3 systems")
            print(f"  {output_files['two_way']}  - Files changed on 2 systems")
            print(f"  {output_files['local_only']}  - Files changed only on local")
            print(f"  {output_files['i1_only']}  - Files changed only on instance 1")
            print(f"  {output_files['i2_only']}  - Files changed only on instance 2")
            print("="*80)

    # Exit code based on conflicts
    if len(analysis['three_way_conflicts']) > 0:
        sys.exit(1)  # Three-way conflicts detected
    elif len(analysis['conflicts_local_i1'] | analysis['conflicts_local_i2'] | analysis['conflicts_i1_i2']) > 0:
        sys.exit(1)  # Two-way conflicts detected
    else:
        sys.exit(0)  # No conflicts

if __name__ == '__main__':
    main()
