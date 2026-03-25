# rgw_omarchy_installer

`rgw_omarchy_installer` snapshots this laptop's Omarchy workstation state and replays it on another Arch laptop.

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
cd ~/Apps/rgw_omarchy_installer
./install.sh -b .
```

That installs the public launcher at `~/.local/bin/rgw_omarchy_installer` and enables the user sync service by default.

Local source install via `./install.sh -b .` needs:

- `python3`
- optional `systemctl --user` if you want the service installed automatically

Private release install or upgrade via `install.sh -v` or `install.sh -u` needs:

- `python3`
- `gh`
- one of:
  - an active `gh auth login`
  - `GH_TOKEN` or `GITHUB_TOKEN` in the environment
  - a local token file at `~/.config/rgw_omarchy_installer/github_token`

The token file is local machine state. Keep it out of the repo and lock it down to your user.

If `~/.local/bin` is not already on `PATH`, add this line to `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Commands

```text
rgw_omarchy_installer -h
rgw_omarchy_installer -v
rgw_omarchy_installer -u
rgw_omarchy_installer conf
rgw_omarchy_installer snap
rgw_omarchy_installer show
rgw_omarchy_installer apply
rgw_omarchy_installer tick
rgw_omarchy_installer loop
rgw_omarchy_installer svc i|on|off|st
```

## Modes

The user config lives at `~/.config/rgw_omarchy_installer/config.toml`.

`source` mode:

- refreshes `snapshot/system_manifest.json` from the current machine
- auto-commits and auto-pushes only when the repo is otherwise clean

`follower` mode:

- pulls the configured installer repo when `paths.repo_root` points at a real git checkout
- applies the saved snapshot only when its digest changes

## Apply Order

`rgw_omarchy_installer apply` runs the requested order:

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

Release precondition: this directory must live in its own git repo rooted at `~/Apps/rgw_omarchy_installer` with `origin` set to `ryangerardwilson/rgw_omarchy_installer`.

When that repo exists privately on GitHub, `install.sh` uses authenticated GitHub CLI release downloads instead of anonymous public release URLs.
