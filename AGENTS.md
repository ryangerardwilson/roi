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
- The checked-in machine snapshot lives at `snapshot/system_manifest.json`.
- Treat that manifest as the cross-laptop source of truth for apply operations.
- Daily tracking work may auto-commit and push only the snapshot file.
- If the repo has unrelated local changes, skip auto-commit and auto-push instead of folding those changes into daemon commits.
- When the user asks to "update the app with my latest work state", the default meaning is:
  - refresh `snapshot/system_manifest.json` from this machine
  - review the snapshot diff
  - commit and push the snapshot only if the user asked for the repo to be updated or pushed

## Current Machine Context
- The installer repo itself lives at `~/Apps/roi`.
- The installer repo remote should be `https://github.com/ryangerardwilson/roi.git`.
- The home repo being captured is the git repo rooted at `~`.
- The default config path is `~/.config/roi/config.toml`.
- The default `paths.repo_root` is `~/Apps/roi`.
- The primary user-facing commands are `init` and `track`.

## Latest Work State Refresh Playbook
- If the user asks to refresh or update the installer with the latest workstation state, prefer this sequence:
  1. run `python3 main.py snap` from the repo root, or `roi snap` if the installed launcher is already available
  2. inspect `git diff -- snapshot/system_manifest.json`
  3. verify that the diff reflects real workstation changes rather than accidental repo-shape drift
  4. if the user asked to push, commit only `snapshot/system_manifest.json` and push
- Prefer `snap` for an explicit operator-driven refresh.
- Use `tick` only when you intentionally want source-mode daemon behavior, including the repo self-pull and opportunistic auto-commit path.
- Do not assume a refresh should be pushed unless the user explicitly asks for that outcome.
- If the repo has unrelated changes, do not mix them into a snapshot update commit.

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
- For a pure work-state refresh, the preferred commit scope is `snapshot/system_manifest.json` only.
- If code or docs also changed as part of the task, keep those changes in a separate commit unless the user explicitly wants them bundled.
- If the user asks to "push the repo", push the current branch after verifying the snapshot diff and commit scope.
- `track` should auto-push only to `origin/main`, and only when the current branch is `main`.
- Only use `./push_release_upgrade.sh` when the user explicitly wants the shipped release path, not for ordinary snapshot refreshes.

## Install / Upgrade Deviation
- This repo is private on GitHub.
- Keep the launcher contract (`-h`, `-v`, `-u`) but use authenticated GitHub CLI release downloads in `install.sh` instead of anonymous public `curl` URLs.
- Never hardcode a GitHub PAT into the repo, installer, or release artifact.
- If private-release auth needs to be hands-off on a machine, use user-local auth such as `gh auth login`, `GH_TOKEN`, or a local token file outside the repo.
- Preserve `./push_release_upgrade.sh` and the tagged release workflow so upgrades stay reproducible across laptops.

## Command Semantics
- `init` is the machine bootstrap path. It should apply the saved snapshot to the current machine.
- `track` is the source-laptop background tracking path. It should install a once-daily `systemd --user` timer and start one immediate tracking run.
- The `track` timer should call the repo-owned tracking runner, not a long-lived loop.
- On a fresh machine, `init` is allowed to bootstrap GitHub auth through `gh auth login --web`, sync the home repo, source `~/.bashrc`, and then continue the remaining apply steps.
