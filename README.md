# SSTP Manager for Omarchy

A third-party Quickshell plugin for managing `sstp-client` profiles from the Omarchy bar. The bar widget, panel, and background service load inside the existing `omarchy-shell`; the plugin never starts another Quickshell process.

## Установка

1. Install dependencies: `sudo pacman -S sstp-client ppp python`.
2. Install the plugin from its Git repository: `omarchy plugin add https://github.com/Dusec82/omarchy-sstp-manager --enable`.
3. From the installed plugin checkout, run `sudo ./scripts/install.sh`. This installs the root helper and a Polkit rule restricted to that helper path. Re-run it after plugin updates that change privileged helpers.
4. Restart the shell with `omarchy-restart-shell` if the widget does not appear. Use `omarchy bar move org.dusec.sstp-manager --section right` to place it.

The first connection may prompt for administrator authentication through Polkit. Profile files are stored in `~/.config/omarchy/sstp-manager/profiles/` with directory mode `0700` and file mode `0600`. The helper uses the `PKEXEC_UID` account and validates the profile and all forwarded PPP options. Logs are kept under `/run/omarchy-sstp-manager/` until reboot.

## Использование

Click the SSTP bar icon to add, edit, duplicate, remove, test, connect, and disconnect profiles. The panel shows the current state, assigned IPv4 address (when detected on a `ppp*` interface), uptime, and recent connection log. Enable **Route all traffic through VPN** to use the VPN as the default route. The optional server route, certificate warning, CA file, HTTP proxy, and a curated PPP option set are supported.

For troubleshooting, enable **Detailed SSTP/PPP logs** in a profile, reconnect, and watch `tail -F /run/omarchy-sstp-manager/$(id -u).log`. Disable verbose logging after troubleshooting.

The helper adds PPP `noauth` for client mode. This prevents pppd from demanding that the VPN server authenticate itself at the PPP layer; SSTP server identity is still checked using TLS certificates, and the profile credentials are still sent for client authentication.

If the server requires TLS hostname routing, enable **Send TLS hostname extension** (`sstpc --tls-ext`) in the profile. This is independent of TLS protocol-version selection, which the installed `sstpc` CLI does not expose.

`sstpc` 1.0.20's documented command line has no custom-port or TLS-protocol-version switch. The form retains the standard port field, but connection attempts currently accept only port 443; TLS protocol selection is not exposed. Do not enable `--cert-warn` unless you understand that it weakens server certificate verification. Passwords are protected at rest, though `sstpc` requires its password as a process argument and local process viewers may briefly see it.

## Разработка

Run `omarchy plugin validate .` from the repository root. The helper uses Python's standard library; UI code uses the Omarchy `qs.Ui`, `qs.Commons`, and Quickshell APIs already present in `omarchy-shell`. QML components remain `Item`-based plugin entries and use the host-injected `manifest`, `omarchyPath`, and `shell` values. Never launch `quickshell` or `qs` from the plugin.

## Installation

1. Install dependencies: `sudo pacman -S sstp-client ppp python`.
2. Install from Git: `omarchy plugin add https://github.com/Dusec82/omarchy-sstp-manager --enable`.
3. From the installed checkout, run `sudo ./scripts/install.sh`. It installs the root helper and narrowly scoped Polkit rule. Re-run after updates to privileged helpers.
4. If the widget does not appear, run `omarchy-restart-shell`. Place it with `omarchy bar move org.dusec.sstp-manager --section right`.

Profile data lives in `~/.config/omarchy/sstp-manager/profiles/`, protected by directory permissions `0700` and file permissions `0600`. Runtime logs are stored in `/run/omarchy-sstp-manager/` and disappear at reboot.

## Usage

Click the SSTP icon to create, edit, duplicate, delete, test, connect, or disconnect profiles. The panel displays state, the IPv4 address found on a `ppp*` interface, uptime, and recent logs. Enable **Route all traffic through VPN** to use the VPN as the default route. The helper also supports server-route preservation, certificate-warning mode, a CA certificate, HTTP proxy, and a curated set of PPP options.

For troubleshooting, enable **Detailed SSTP/PPP logs** in the profile, reconnect, and watch `tail -F /run/omarchy-sstp-manager/$(id -u).log`. Turn verbose logging off after troubleshooting.

The helper always passes PPP `noauth` in client mode. This disables the server-authentication requirement at the PPP layer; SSTP certificate verification still checks the server, and the profile credentials still authenticate the client.

The documented `sstpc` 1.0.20 command line does not provide a custom port or TLS protocol-version flag. The profile form includes the standard port field, but only port 443 can currently connect; TLS-version selection is not exposed. `--cert-warn` weakens certificate verification and should only be used when necessary. Passwords are protected at rest, but `sstpc` accepts passwords on its command line, where local process viewers may briefly see them.

For servers that route TLS by hostname, enable **Send TLS hostname extension** (`sstpc --tls-ext`) in the profile. This does not select a TLS protocol version.

## Development

Validate from the repository root with `omarchy plugin validate .`. Python helpers use only the standard library. The QML runs inside the existing shell using Omarchy's `qs.Ui`, `qs.Commons`, and Quickshell modules, and reads the shell-injected `manifest`, `omarchyPath`, and `shell` properties. Do not start another Quickshell process from the plugin.
