# roi

`roi` snapshots this laptop's Omarchy workstation state and replays it on another Arch laptop.

The managed state covers:

- the git repo rooted at `~`
- the six custom Omarchy theme repos and the active theme
- the required top-level directories
- repo inventories under `~/Apps`, `~/Libs`, and `~/Work`
- explicitly installed packages

Live machine state is stored in a separate private GitHub repo named `roi_state`.

The checked-in `snapshot/system_manifest.json` in this repo is only a local sample and development fixture. It is not the cross-machine source of truth.

## Install

The current local-first install path is:

```bash
cd ~/Apps/roi
./install.sh -b .
```

That installs the public launcher at `~/.local/bin/roi`.

Release install or upgrade via `install.sh -v` or `install.sh -u` needs:

- `python3`
- `curl`

Local source install via `./install.sh -b .` needs:

- `python3`

Using `roi init`, `roi track`, or `roi install` needs:

- `gh`
- network access to GitHub

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
roi install
```

## Workflow

The user config lives at `~/.config/roi/config.toml`.

- `init` creates or confirms the private `roi_state` repo for the authenticated GitHub account, then uploads the current machine manifest there.
- `track` installs and enables a `systemd --user` daily timer, then immediately syncs the current machine manifest to `roi_state`.
- `install` starts GitHub web auth when needed, downloads the manifest from `roi_state`, and applies it to the current machine.

Default state repo config:

```toml
[state]
repo_owner = ""
repo_name = "roi_state"
manifest_path = "system_manifest.json"
```

If `repo_owner` is blank, ROI uses the currently authenticated GitHub user.

## Source Laptop

On the source machine:

```bash
roi init
roi track
```

`roi init` should be run from a shell where `GH_TOKEN` or `GITHUB_TOKEN` is already exported in `~/.bashrc`, or where `gh auth login` is already configured.

`roi track` uses that same auth context, installs the daily timer, and keeps `roi_state` current.

## New Machine

On a fresh machine:

```bash
roi install
```

`roi install` runs this order:

1. start GitHub web auth through `gh` when needed
2. download `system_manifest.json` from the authenticated user's private `roi_state` repo
3. sync the home repo at `~`
4. source `~/.bashrc` from the freshly synced home repo for the remaining apply steps
5. install themes, repos, required directories, and packages

## Apply Order

Once the manifest is loaded, ROI applies it in this order:

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

This repo is intended to be public. Personal workstation state belongs in the separate private `roi_state` repo, not in `roi` itself.
