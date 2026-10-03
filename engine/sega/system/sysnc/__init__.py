"""
SEGA Sysnc Module - Multi-System Git Synchronization

Provides git synchronization utilities for the FLEET 3-system architecture:
- Local system
- Instance 1 (203.0.113.10)
- Instance 2 (203.0.113.20)

Scripts:
    Consolidation (full workflow):
    - bulk-stash-pull-pop-push.sh: Primary sync workflow (stash→pull→pop→commit→push)
    - consolidate-with-submodules.sh: Automated orchestration
    - option-b-consolidation.sh: Alternative consolidation approach

    Analysis:
    - analyze-3way-conflicts.py: Conflict detection and analysis

    Inspection:
    - inspect-ec2-changes.sh: Basic change inspection
    - inspect-ec2-changes-enhanced.sh: Enhanced change inspection

    Settings:
    - sync-claude-settings-to-ec2.sh: Sync Claude settings
    - sync-cleaned-history.sh: Sync cleaned history

    Simple Push/Pull (from gitlab/):
    - gitlab-bulk-push.sh: Simple bulk push all projects
    - gitlab-bulk-pull.sh: Simple bulk pull all projects
    - gitlab-bulk-branch-push.sh: Branch-specific bulk push
    - gitlab-bulk-push-projects1.sh: Instance 1 specific push
    - gitlab-bulk-push-projects2.sh: Instance 2 specific push
    - gitlab-bulk-push-projects3.sh: Instance 3 specific push
    - gitlab-bulk-pull-projects1.sh: Instance 1 specific pull
    - gitlab-bulk-pull-projects2.sh: Instance 2 specific pull
    - gitlab-bulk-pull-projects3.sh: Instance 3 specific pull

    Verification:
    - gitlab-verify-sync.sh: Verify 3-system sync status

    Secrets:
    - setup-gitlab-secrets.sh: GitLab secrets setup

Usage:
    sega sysnc run                    # Full consolidation workflow
    sega sysnc analyze                # Analyze 3-way conflicts
    sega sysnc inspect                # Inspect EC2 changes
    sega sysnc push --bulk "cc123"    # Simple bulk push
    sega sysnc pull --bulk            # Simple bulk pull
    sega sysnc verify                 # Verify 3-system sync
"""

from pathlib import Path

SYSNC_DIR = Path(__file__).parent

# Consolidation scripts (existing)
BULK_SYNC_SCRIPT = SYSNC_DIR / "bulk-stash-pull-pop-push.sh"
CONSOLIDATE_SCRIPT = SYSNC_DIR / "consolidate-with-submodules.sh"
OPTION_B_SCRIPT = SYSNC_DIR / "option-b-consolidation.sh"

# Analysis scripts (existing)
ANALYZE_SCRIPT = SYSNC_DIR / "analyze-3way-conflicts.py"

# Inspection scripts (existing)
INSPECT_SCRIPT = SYSNC_DIR / "inspect-ec2-changes.sh"
INSPECT_ENHANCED_SCRIPT = SYSNC_DIR / "inspect-ec2-changes-enhanced.sh"

# Settings sync scripts (existing)
SETTINGS_SYNC_SCRIPT = SYSNC_DIR / "sync-claude-settings-to-ec2.sh"
CLEANED_HISTORY_SCRIPT = SYSNC_DIR / "sync-cleaned-history.sh"

# Simple push/pull scripts (NEW - from gitlab/)
GITLAB_BULK_PUSH_SCRIPT = SYSNC_DIR / "gitlab-bulk-push.sh"
GITLAB_BULK_PULL_SCRIPT = SYSNC_DIR / "gitlab-bulk-pull.sh"
GITLAB_BULK_BRANCH_PUSH_SCRIPT = SYSNC_DIR / "gitlab-bulk-branch-push.sh"
GITLAB_BULK_PUSH_PROJECTS1_SCRIPT = SYSNC_DIR / "gitlab-bulk-push-projects1.sh"
GITLAB_BULK_PUSH_PROJECTS2_SCRIPT = SYSNC_DIR / "gitlab-bulk-push-projects2.sh"
GITLAB_BULK_PUSH_PROJECTS3_SCRIPT = SYSNC_DIR / "gitlab-bulk-push-projects3.sh"
GITLAB_BULK_PULL_PROJECTS1_SCRIPT = SYSNC_DIR / "gitlab-bulk-pull-projects1.sh"
GITLAB_BULK_PULL_PROJECTS2_SCRIPT = SYSNC_DIR / "gitlab-bulk-pull-projects2.sh"
GITLAB_BULK_PULL_PROJECTS3_SCRIPT = SYSNC_DIR / "gitlab-bulk-pull-projects3.sh"

# Verification scripts (NEW - from gitlab/)
GITLAB_VERIFY_SYNC_SCRIPT = SYSNC_DIR / "gitlab-verify-sync.sh"

# Secrets scripts (NEW - from gitlab/)
SETUP_GITLAB_SECRETS_SCRIPT = SYSNC_DIR / "setup-gitlab-secrets.sh"

__all__ = [
    "SYSNC_DIR",
    # Consolidation
    "BULK_SYNC_SCRIPT",
    "CONSOLIDATE_SCRIPT",
    "OPTION_B_SCRIPT",
    # Analysis
    "ANALYZE_SCRIPT",
    # Inspection
    "INSPECT_SCRIPT",
    "INSPECT_ENHANCED_SCRIPT",
    # Settings
    "SETTINGS_SYNC_SCRIPT",
    "CLEANED_HISTORY_SCRIPT",
    # Simple push/pull
    "GITLAB_BULK_PUSH_SCRIPT",
    "GITLAB_BULK_PULL_SCRIPT",
    "GITLAB_BULK_BRANCH_PUSH_SCRIPT",
    "GITLAB_BULK_PUSH_PROJECTS1_SCRIPT",
    "GITLAB_BULK_PUSH_PROJECTS2_SCRIPT",
    "GITLAB_BULK_PUSH_PROJECTS3_SCRIPT",
    "GITLAB_BULK_PULL_PROJECTS1_SCRIPT",
    "GITLAB_BULK_PULL_PROJECTS2_SCRIPT",
    "GITLAB_BULK_PULL_PROJECTS3_SCRIPT",
    # Verification
    "GITLAB_VERIFY_SYNC_SCRIPT",
    # Secrets
    "SETUP_GITLAB_SECRETS_SCRIPT",
]
