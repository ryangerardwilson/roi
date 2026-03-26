# roi Agent Guide

## Workspace Defaults
- Follow `/home/ryan/Documents/agent_context/CLI_TUI_STYLE_GUIDE.md` for CLI taste and help shape.
- Follow `/home/ryan/Documents/agent_context/CANONICAL_REFERENCE_IMPLEMENTATION_FOR_CLI_AND_TUI_APPS.md` where it usefully applies to launcher and installer behavior.
- Follow `/home/ryan/Documents/agent_context/OMARCHY_THEME_WORKFLOW.md` for Omarchy theme source-of-truth rules.

## Scope
- `roi` owns one job: capture this laptop's Omarchy workstation state and re-apply it on another Arch laptop.
- Keep the managed state limited to:
  - the home-directory git repo
  - the six repo-backed Omarchy themes and active theme
  - the required top-level directories
  - repo inventories under `~/Apps`, `~/Libs`, and `~/Work`
  - explicitly installed system packages
- Do not grow this into a generic dotfiles framework, package manager replacement, or secret vault unless the user explicitly asks.

## Snapshot Rules
- Live cross-laptop state belongs in the private GitHub repo `roi_state`, not in this repo.
- The checked-in `snapshot/system_manifest.json` is only a local sample and development fixture for the public `roi` repo.
- When the user asks to "update the app with my latest work state", the default meaning is:
  - capture the current machine manifest
  - sync it to `roi_state`
  - leave the checked-in sample manifest alone unless the user explicitly asks to change it

## Current Machine Context
- The installer repo itself lives at `~/Apps/roi`.
- The installer repo remote should be `https://github.com/ryangerardwilson/roi.git`.
- The live state repo should be `https://github.com/<authenticated-user>/roi_state.git` and it must stay private.
- The home repo being captured is the git repo rooted at `~`.
- The default config path is `~/.config/roi/config.toml`.
- The default `paths.repo_root` is `~/Apps/roi`.
- The primary user-facing commands are `init`, `track`, and `install`.

## Latest Work State Refresh Playbook
- If the user asks to refresh or update the installer with the latest workstation state, prefer this sequence:
  1. run `roi init` or `roi track`
  2. confirm the resolved `roi_state` repo slug
  3. verify that the synced manifest reflects real workstation changes rather than accidental repo-shape drift
- Prefer syncing `roi_state` over touching the checked-in sample manifest.
- Do not assume the public `roi` repo should receive a live-state update unless the user explicitly asks for a sample-manifest change.

## Snapshot Review Rules
- The managed snapshot should reflect:
  - the home repo rooted at `~`
  - the six repo-backed Omarchy themes plus the active theme
  - required top-level directories
  - repo inventories under `~/Apps`, `~/Libs`, and `~/Work`
  - explicitly installed packages
- Only true git repo roots under `~/Apps`, `~/Libs`, and `~/Work` belong in the repo inventory.
- Do not treat directories that merely live inside the home repo worktree as standalone repos.
- When reviewing repo inventory diffs, prefer the current real directory names and remotes on disk over stale remembered names.
- Theme changes should follow the Omarchy theme workflow: canonical repo state first, then the manifest refresh.

## Push Rules
- For a pure work-state refresh, prefer syncing only `roi_state`.
- If code or docs also changed as part of the task, keep those changes in a separate commit unless the user explicitly wants them bundled.
- If the user asks to "push the repo", push the current branch of the public `roi` repo after verifying the scope of any code/doc changes.
- `track` should sync `roi_state` directly. It should not auto-commit the public `roi` repo.
- Only use `./push_release_upgrade.sh` when the user explicitly wants the shipped release path, not for ordinary snapshot refreshes.

## Install / Upgrade Deviation
- This repo is intended to be public on GitHub.
- `install.sh` should download public ROI releases without requiring GitHub auth.
- `roi_state` must stay private and use GitHub auth.
- Never hardcode a GitHub PAT into the repo, installer, or release artifact.
- On the source machine, prefer `GH_TOKEN` or `GITHUB_TOKEN` exported in `~/.bashrc` for non-interactive `roi_state` sync.
- On a fresh machine, prefer `gh auth login --web` during `roi install`.
- Preserve `./push_release_upgrade.sh` and the tagged release workflow so upgrades stay reproducible across laptops.

## Command Semantics
- `init` bootstraps the private `roi_state` repo for the authenticated user and uploads the current machine manifest.
- `track` is the source-laptop background tracking path. It should install a once-daily `systemd --user` timer and start one immediate `roi_state` sync.
- `install` is the fresh-machine apply path. It should authenticate, download the manifest from `roi_state`, and apply it to the current machine.
- The `track` timer should call the repo-owned tracking runner, not a long-lived loop.
- On a fresh machine, `install` is allowed to bootstrap GitHub auth through `gh auth login --web`, sync the home repo, source `~/.bashrc`, and then continue the remaining apply steps.
