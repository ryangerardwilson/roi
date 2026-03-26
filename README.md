# roi

`roi` snapshots this laptop's Omarchy workstation state and replays it on another Arch laptop.

The managed snapshot covers:

- the git repo rooted at `~`
- the six custom Omarchy theme repos and the active theme
- the required top-level directories
- repo inventories under `~/Apps`, `~/Libs`, and `~/Work`
- explicitly installed packages

The checked-in source of truth is `snapshot/system_manifest.json`.

## Install

The current local-first install path is:

```bash
cd ~/Apps/roi
./install.sh -b .
```

That installs the public launcher at `~/.local/bin/roi`.

Local source install via `./install.sh -b .` needs:

- `python3`
- optional `systemctl --user` if you want the service installed automatically

Private release install or upgrade via `install.sh -v` or `install.sh -u` needs:

- `python3`
- `gh`
- one of:
  - an active `gh auth login`
  - `GH_TOKEN` or `GITHUB_TOKEN` in the environment
  - a local token file at `~/.config/roi/github_token`

The token file is local machine state. Keep it out of the repo and lock it down to your user.

If none of those auth paths are present, the installer starts `gh auth login --web` automatically.

If `~/.local/bin` is not already on `PATH`, add this line to `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Commands

```text
roi -h
roi -v
roi -u
roi init
roi track
```

## Workflow

The user config lives at `~/.config/roi/config.toml`.

- `init` initializes this machine from the saved snapshot.
- `track` installs and enables a `systemd --user` daily timer, then immediately runs one tracking cycle.
- The daily tracking cycle refreshes `snapshot/system_manifest.json` from the current machine and auto-commits and auto-pushes to `origin/main` only when the repo is otherwise clean and the current branch is `main`.

First bootstrap flow on a new machine:

1. start GitHub web auth through `gh` when needed
2. sync the home repo at `~`
3. source `~/.bashrc` from the freshly synced home repo for the remaining apply steps

## Apply Order

`roi init` runs the required order:

1. sync the home repo at `~`
2. install the Omarchy theme repos and activate the saved `active_theme`
3. ensure `~/Work`, `~/Infra`, `~/Music`, `~/Apps`, and `~/Libs`
4. clone or pull repos under `~/Apps`, `~/Libs`, and `~/Work`, then run `install.sh -u` for app repos that ship an installer
5. install and update the explicit package set

## Release Path

This app still ships the normal release path:

```bash
./push_release_upgrade.sh
```

Release precondition: this directory must live in its own git repo rooted at `~/Apps/roi` with `origin` set to `ryangerardwilson/roi`.

When that repo exists privately on GitHub, `install.sh` uses authenticated GitHub CLI release downloads instead of anonymous public release URLs.
