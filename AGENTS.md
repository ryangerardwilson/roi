# rgw_omarchy_installer Agent Guide

## Workspace Defaults
- Follow `/home/ryan/Documents/agent_context/CLI_TUI_STYLE_GUIDE.md` for CLI taste and help shape.
- Follow `/home/ryan/Documents/agent_context/CANONICAL_REFERENCE_IMPLEMENTATION_FOR_CLI_AND_TUI_APPS.md` where it usefully applies to launcher and installer behavior.
- Follow `/home/ryan/Documents/agent_context/OMARCHY_THEME_WORKFLOW.md` for Omarchy theme source-of-truth rules.

## Scope
- `rgw_omarchy_installer` owns one job: capture this laptop's Omarchy workstation state and re-apply it on another Arch laptop.
- Keep the managed state limited to:
  - the home-directory git repo
  - the six repo-backed Omarchy themes and active theme
  - the required top-level directories
  - repo inventories under `~/Apps`, `~/Libs`, and `~/Work`
  - explicitly installed system packages
- Do not grow this into a generic dotfiles framework, package manager replacement, or secret vault unless the user explicitly asks.

## Snapshot Rules
- The checked-in machine snapshot lives at `snapshot/system_manifest.json`.
- Treat that manifest as the cross-laptop source of truth for apply operations.
- Source-mode daemon work may auto-commit and push only the snapshot file.
- If the repo has unrelated local changes, skip auto-commit and auto-push instead of folding those changes into daemon commits.

## Install / Upgrade Deviation
- This repo is private on GitHub.
- Keep the launcher contract (`-h`, `-v`, `-u`) but use authenticated GitHub CLI release downloads in `install.sh` instead of anonymous public `curl` URLs.
- Never hardcode a GitHub PAT into the repo, installer, or release artifact.
- If private-release auth needs to be hands-off on a machine, use user-local auth such as `gh auth login`, `GH_TOKEN`, or a local token file outside the repo.
- Preserve `./push_release_upgrade.sh` and the tagged release workflow so upgrades stay reproducible across laptops.

## Service Rules
- The user service exists to run repeated sync cycles, not to hide errors.
- Keep source mode conservative: refresh the manifest, then auto-commit only when the worktree is clean apart from the snapshot file.
- Keep follower mode conservative: pull the installer repo and apply only when the snapshot digest changes.
