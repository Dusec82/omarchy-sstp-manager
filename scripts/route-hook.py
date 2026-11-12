#!/usr/bin/env python3
"""Install and remove profile-approved split routes from PPP lifecycle hooks."""
import ipaddress
import json
import os
import re
import subprocess
import sys
import syslog
from pathlib import Path

STATE_DIR = Path("/run/omarchy-sstp-manager/routes")
TOKEN_RE = re.compile(r"^sstpm-([0-9]+)-([A-Za-z0-9_-]{1,48})-([a-f0-9]{24})$")
IFACE_RE = re.compile(r"^ppp[0-9]+$")


def log(priority, message):
    syslog.syslog(priority, message)


def atomic_write(path, value):
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def read_state(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    info = os.fstat(fd)
    if info.st_uid != 0 or info.st_mode & 0o077:
        os.close(fd)
        raise RuntimeError("unsafe route state permissions")
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        value = json.load(stream)
    routes = value.get("routes", [])
    if not isinstance(routes, list) or len(routes) > 32:
        raise RuntimeError("invalid route state")
    normalized = []
    for route in routes:
        if not isinstance(route, str) or "/" not in route.strip():
            raise RuntimeError("split routes must use CIDR notation")
        network = ipaddress.ip_network(route.strip(), strict=False)
        if network.prefixlen == 0:
            raise RuntimeError("default routes are not accepted by split-route hooks")
        normalized.append(str(network))
    value["routes"] = list(dict.fromkeys(normalized))
    return value


def route_command(action, network, interface):
    parsed = ipaddress.ip_network(network, strict=False)
    family = "-6" if parsed.version == 6 else "-4"
    return subprocess.run(
        ["/usr/bin/ip", family, "route", action, str(parsed), "dev", interface],
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )


def main():
    syslog.openlog("sstp-manager-routes", syslog.LOG_PID, syslog.LOG_DAEMON)
    # pppd passes: interface, tty, speed, local IP, remote IP, ipparam.
    if os.geteuid() != 0 or len(sys.argv) != 8:
        return 0
    mode = sys.argv[1]
    interface = sys.argv[2]
    token = sys.argv[7]
    match = TOKEN_RE.fullmatch(token)
    if mode not in ("up", "down") or not match or not IFACE_RE.fullmatch(interface):
        return 0

    uid, profile_id = int(match.group(1)), match.group(2)
    state_path = STATE_DIR / (token + ".json")
    try:
        state = read_state(state_path)
    except FileNotFoundError:
        return 0
    if state.get("uid") != uid or state.get("profileId") != profile_id:
        raise RuntimeError("route authorization does not match ipparam")
    if mode == "up":
        state["interface"] = interface
        state["installed"] = []
        atomic_write(state_path, state)
        for network in state["routes"]:
            result = route_command("add", network, interface)
            if result.returncode == 0:
                state["installed"].append(network)
                atomic_write(state_path, state)
                log(syslog.LOG_INFO, "added %s dev %s" % (network, interface))
            else:
                detail = (result.stderr or result.stdout).strip()[:240]
                log(syslog.LOG_ERR, "could not add %s dev %s: %s" % (network, interface, detail))
        return 0

    state_interface = state.get("interface", "")
    if state_interface and state_interface != interface:
        raise RuntimeError("ip-down interface does not match route state")
    for network in state.get("installed", []):
        result = route_command("del", network, interface)
        if result.returncode == 0:
            log(syslog.LOG_INFO, "removed %s dev %s" % (network, interface))
        else:
            detail = (result.stderr or result.stdout).strip()[:240]
            log(syslog.LOG_WARNING, "could not remove %s dev %s: %s" % (network, interface, detail))
    state_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        syslog.openlog("sstp-manager-routes", syslog.LOG_PID, syslog.LOG_DAEMON)
        log(syslog.LOG_ERR, str(error))
        raise SystemExit(1)
