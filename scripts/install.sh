#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
install -d -m 0755 /usr/lib/omarchy-sstp-manager /usr/share/polkit-1/rules.d /etc/ppp/ip-up.d /etc/ppp/ip-down.d
rm -f /usr/lib/omarchy-sstp-manager/route-hook.py
rm -f /etc/ppp/ip-up.d/95-sstp-manager-routes.sh /etc/ppp/ip-down.d/95-sstp-manager-routes.sh
install -o root -g root -m 0755 "$ROOT/scripts/privileged.py" /usr/lib/omarchy-sstp-manager/privileged.py
install -o root -g root -m 0644 "$ROOT/polkit/50-sstp-manager.rules" /usr/share/polkit-1/rules.d/50-sstp-manager.rules
printf '%s\n' 'Installed SSTP Manager helper and polkit rule.'
printf '%s\n' 'The rule authorizes administrator authentication for this helper path only.'
