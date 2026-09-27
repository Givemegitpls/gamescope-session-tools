# gamescope-session-tools

Gamescope session integration for machines that are **not** Steam Decks: a
media/power-button daemon, a session switcher, and the SteamOS stubs Steam
expects inside a gamescope session.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Packaged for Arch Linux; the recipe (`PKGBUILD`, `arch=any`) installs the
scripts from `src/` into `/usr/bin` and a systemd unit into
`/usr/lib/systemd/system`.

## Why this exists

On a regular distribution running Steam's Game Mode (gamescope), two things are
broken out of the box:

1. **The power button** reaches logind and shuts the machine down instead of
   opening Steam's power menu, and the volume keys are swallowed by gamescope.
2. **Switching between the desktop session and gamescope** needs a helper that
   starts one and stops the other.

gamescope itself intercepts `XF86AudioLowerVolume`/`XF86AudioRaiseVolume`/
`XF86PowerOff` and sends them *only* to Steam's overlay
(gamescope upstream `src/wlserver.cpp`, "forbidden_key"). Steam shows the volume
OSD but never applies the change on a non-Deck machine, so the keys appear dead.

There is no way around reading the physical devices: `libei` cannot be used
because gamescope is an **Ei server** (it accepts injected input and never
emits key events), and `/dev/input/event*` is `root:input 0660` with no
`uaccess` ACL for keyboards.

## Components

| File | Installed as | Purpose |
|---|---|---|
| `src/gamescope-input-daemon` | `/usr/bin/gamescope-input-daemon` | reads `/dev/input`, drives `wpctl`, forwards power presses to Steam |
| `src/gamescope-session-switcher` | `/usr/bin/gamescope-session-switcher` | switches desktop <-> gamescope, tells the daemon the active mode |
| `src/steamos-session-select` | `/usr/bin/steamos-session-select` | called by Steam's "Switch to Desktop"; runs the switcher |
| `src/steamos-select-branch` | `/usr/bin/steamos-select-branch` | SteamOS stub |
| `src/steamos-update` | `/usr/bin/steamos-update` | SteamOS stub |
| `src/jupiter-biosupdate` | `/usr/bin/jupiter-biosupdate` | SteamOS stub |
| `src/gamescope-input-daemon@.service` | `/usr/lib/systemd/system/` | templated system unit, one instance per user |

## Repository layout

```
PKGBUILD       Arch package recipe (pulls this repo as a git source)
LICENSE        MIT
README.md      this file
.gitignore     build artifacts, editor files
src/           scripts and the systemd unit installed by the package
.opencode/     agent notes for this repository
```

## Requirements

- Python 3 and `python-evdev`
- PipeWire (`wpctl`) for volume control
- `uwsm` (used as the desktop session manager)
- `gamescope` and Steam (Game Mode)
- A Wayland compositor on the desktop (the switcher's `desktop` mode runs
  `uwsm start default`)

## Install

The PKGBUILD pulls this repository as a `git+https` source, so `makepkg` builds
the **pushed** state: local uncommitted edits are not picked up. Do **not** run
`makepkg` in the repository root — build in a scratch directory so makepkg does
not clone into the source tree:

```sh
mkdir -p /tmp/gst && cp PKGBUILD /tmp/gst/ && cd /tmp/gst
makepkg -f
sudo pacman -U gamescope-session-tools-*.pkg.tar.zst
```

Alternatively, clone the repository and copy the PKGBUILD out of it:

```sh
git clone https://github.com/Givemegitpls/gamescope-session-tools.git
cd gamescope-session-tools
mkdir -p /tmp/gst && cp PKGBUILD /tmp/gst/ && cd /tmp/gst
makepkg -f && sudo pacman -U gamescope-session-tools-*.pkg.tar.zst
```

### Updating

Bump `pkgver`/`pkgrel` in `PKGBUILD`, push, then rebuild:

```sh
makepkg -f                     # in the scratch directory, after refreshing PKGBUILD
sudo pacman -U gamescope-session-tools-*.pkg.tar.zst
sudo systemctl restart gamescope-input-daemon@$USER.service   # if the daemon is running
```

### Enable the daemon (once per user)

The daemon reads `/dev/input/event*`, which is `root:input 0660`. Instead of
adding the user to the `input` group — which would grant permanent access to
every input device — the unit grants the group **only to the daemon process**:

```ini
[Service]
User=%i
SupplementaryGroups=input
```

The daemon also needs `XDG_RUNTIME_DIR` to reach PipeWire (`wpctl` fails with
`Could not connect to PipeWire` without it). systemd's `%U` specifier resolves
to the *service manager's* UID (root), not the target user's, so the unit
computes the UID from `%i`:

```ini
ExecStart=/bin/sh -c 'XDG_RUNTIME_DIR=/run/user/$(id -u %i) exec /usr/bin/gamescope-input-daemon ...'
```

Enable one instance per user that needs it:

```sh
sudo systemctl enable --now gamescope-input-daemon@$USER.service
```

`%i` is expanded to the user name at `systemctl` time, so no user name is
baked into the package. This is the only root step; switching sessions
afterwards needs no privileges.

> **Note:** systemd *user* units cannot do this — the user manager has no
> `CAP_SETGID` and fails with `216/GROUP: Operation not permitted`. The unit
> must be a **system** unit.

## Configure the session

The switcher must run in the console session that starts the desktop
environment, so it can own the transition to gamescope. Add it to your shell
login for the target TTY, replacing any previous session launcher:

```sh
# ~/.zshrc (or ~/.bash_profile), started for the login TTY
function choose_session() {
  if which gamescope &>/dev/null; then
    exec gamescope-session-switcher
  else
    exec uwsm start default
  fi
}
```

The switcher starts the desktop session (`uwsm start default`) and stays
running, listening on `/tmp/gamescope-session-switcher.sock`. It can then be
driven from anywhere, e.g. from a launcher menu:

```sh
gamescope-session-switcher gamescope   # enter Game Mode
gamescope-session-switcher desktop     # return to the desktop
gamescope-session-switcher status
```

When Steam's Game Mode exits through "Switch to Desktop", Steam invokes
`steamos-session-select`, which calls `gamescope-session-switcher desktop`.

## Usage

```sh
# enter / leave Game Mode
gamescope-session-switcher gamescope
gamescope-session-switcher desktop

# ask the switcher what is running
gamescope-session-switcher status

# inspect / drive the input daemon directly
echo status | socat - UNIX-CONNECT:/run/gamescope-input-daemon/$USER/gamescope-input-daemon.sock
echo desktop | socat - UNIX-CONNECT:/run/gamescope-input-daemon/$USER/gamescope-input-daemon.sock
```

Daemon commands: `gamescope`, `desktop`, `status`, `stop`.

## Logs

`gamescope-session-switcher` writes to `/tmp/gamescope-session-switcher.log`
(mode `0600`) instead of the controlling TTY. Override the path with
`--log-file`:

```sh
gamescope-session-switcher --log-file /tmp/my-switcher.log
```

The file records session transitions, the input mode handed to the daemon, and
session start/exit codes. `gamescope-input-daemon` logs to the journal instead
(no file):

```sh
journalctl -u gamescope-input-daemon@$USER -f
```

## Behaviour

| Session   | Power button | Volume keys |
|-----------|--------------|-------------|
| gamescope | grabbed, sent to Steam (single press: power menu, double press within 0.6 s: suspend) | `wpctl` |
| desktop   | released — the compositor's own `XF86PowerOff` binding keeps working | untouched |

The daemon starts **without grabbing anything** and waits for a command. If the
switcher dies, the power button is never left captured on the desktop.

## Notes

Facts collected while implementing this, in case the setup has to be
revisited:

- **gamescope swallows the media keys.** gamescope upstream `src/wlserver.cpp`
  treats `XF86AudioLowerVolume`, `XF86AudioRaiseVolume` and `XF86PowerOff` as
  `forbidden_key` and routes them to Steam's overlay only. Nothing outside
  gamescope can observe them, hence the evdev daemon.
- **libei is not an option.** gamescope embeds an **Ei server** (`eis_*`):
  gamescope upstream `src/InputEmulation.cpp` handles `EIS_EVENT_KEYBOARD_KEY`
  and calls `wlserver_key()`. It accepts injected input and never emits key
  events, so a separate process cannot subscribe to it. `libei.so` exports no
  `eis_*` symbols at all.
- **libseat is not an option either.** The unit is owned by the compositor:
  opening a second seat from another process fails with
  `EBUSY / Device or resource busy` (the `logind` backend permits one
  controller per session). `seatd` is not running.
- **udev gives no `uaccess` on input devices.** `70-uaccess.rules` has no rule
  for keyboards or power buttons (only gamepads and special classes).
  `71-seat.rules` tags `input*` with `seat`, but `event*` nodes do not inherit
  it. Both the Power Button and the keyboards report
  `TAGS=:power-switch:` only.
- **user systemd units cannot add groups.** Verified:
  `SupplementaryGroups=input` in a `systemctl --user` unit fails with
  `Changing group credentials failed: Operation not permitted`
  (`status=216/GROUP`).
- **gamescope session ownership.** gamescope runs inside the login session's
  scope (not a unit of its own), so a systemd unit cannot track it. The
  switcher is the only reliable point that knows which session is active.
- **Socket layout.** One runtime directory per user
  (`RuntimeDirectory=gamescope-input-daemon/%i`) keeps instances isolated;
  `%i` in `RuntimeDirectory` is accepted by systemd.

## License

MIT — see [LICENSE](LICENSE).
