#!/usr/bin/env python3
"""Unprivileged profile and status store for SSTP Manager."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path.home() / ".config/omarchy/sstp-manager"
PROFILES = BASE / "profiles"
LOG = BASE / "sstp-manager.log"
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")
ALLOWED = {"name", "server", "port", "username", "password", "certWarn", "saveServerRoute", "proxy", "tlsVersion", "caCert", "routeMode", "pppOptions", "debugLogging", "tlsExt"}


def ensure_dirs():
    PROFILES.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(BASE, 0o700)
    os.chmod(PROFILES, 0o700)


def profile_path(profile_id):
    if not ID_RE.fullmatch(str(profile_id)):
        raise ValueError("Invalid profile id")
    return PROFILES / (profile_id + ".json")


def valid_profile(data):
    if not isinstance(data, dict):
        raise ValueError("Profile must be an object")
    data = {key: value for key, value in data.items() if key in ALLOWED}
    for key, limit in (("name", 80), ("server", 253), ("username", 256), ("password", 1024), ("proxy", 512), ("caCert", 1024)):
        value = str(data.get(key, ""))
        if len(value) > limit or "\x00" in value or "\n" in value:
            raise ValueError("Invalid " + key)
        data[key] = value
    if not data["name"].strip() or not data["server"].strip():
        raise ValueError("Profile name and server are required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:%_-]*", data["server"]):
        raise ValueError("Server must be a hostname or IP address")
    data["port"] = int(data.get("port", 443))
    if not 1 <= data["port"] <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    if data.get("proxy") and not re.fullmatch(r"https?://[A-Za-z0-9._:-]+(?::[0-9]{1,5})?", data["proxy"]):
        raise ValueError("Proxy must be an http(s) URL without credentials or path")
    if data.get("tlsVersion", "default") not in ("default", "1.0", "1.1", "1.2", "1.3"):
        raise ValueError("Unsupported TLS version")
    if data.get("caCert") and (not data["caCert"].startswith("/") or ".." in Path(data["caCert"]).parts):
        raise ValueError("CA certificate path must be absolute")
    data["routeMode"] = data.get("routeMode", "split")
    if data["routeMode"] not in ("split", "full"):
        raise ValueError("Invalid route mode")
    allowed_ppp = {"require-mschap-v2", "refuse-eap", "usepeerdns", "defaultroute", "nodefaultroute", "noauth", "noipdefault", "noccp", "mtu"}
    opts = data.get("pppOptions", [])
    if not isinstance(opts, list):
        opts = []
    clean = []
    for opt in opts:
        if isinstance(opt, str) and (opt in allowed_ppp or (re.fullmatch(r"mtu=(?:[0-9]{3,4})", opt) and 576 <= int(opt.split("=", 1)[1]) <= 1500)):
            clean.append(opt)
    data["pppOptions"] = list(dict.fromkeys(clean))
    data["certWarn"] = bool(data.get("certWarn", False))
    data["saveServerRoute"] = bool(data.get("saveServerRoute", True))
    data["debugLogging"] = data.get("debugLogging") is True
    data["tlsExt"] = data.get("tlsExt") is True
    data["tlsVersion"] = data.get("tlsVersion", "default")
    return data


def write_json(path, value):
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def read_profile(path):
    st = path.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError("Profile permissions must be 0600 and owned by the current user")
    return json.loads(path.read_text(encoding="utf-8"))


def run():
    ensure_dirs()
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    if command == "list":
        rows = []
        for path in sorted(PROFILES.glob("*.json")):
            try:
                item = read_profile(path)
                item["id"] = path.stem
                item["password"] = ""  # Never return saved secrets to QML.
                item["hasPassword"] = bool(read_profile(path).get("password"))
                rows.append(item)
            except Exception:
                continue
        print(json.dumps(rows))
    elif command == "save":
        ident = sys.argv[2] if len(sys.argv) > 2 else ""
        data = valid_profile(json.loads(sys.argv[3]))
        target = profile_path(ident)
        if not data.get("password") and target.exists():
            previous = read_profile(target)
            data["password"] = previous.get("password", "")
        write_json(target, data)
        print(json.dumps({"ok": True}))
    elif command == "delete":
        profile_path(sys.argv[2]).unlink(missing_ok=True)
        print(json.dumps({"ok": True}))
    elif command == "duplicate":
        source = read_profile(profile_path(sys.argv[2]))
        ident = sys.argv[3]
        source["name"] = str(source.get("name", "Profile")) + " copy"
        write_json(profile_path(ident), valid_profile(source))
        print(json.dumps({"ok": True}))
    elif command == "status":
        state = Path("/run/omarchy-sstp-manager") / (str(os.getuid()) + ".json")
        try:
            value = json.loads(state.read_text(encoding="utf-8"))
            pid_file = Path("/run/omarchy-sstp-manager") / (str(os.getuid()) + ".pid")
            pid = int(pid_file.read_text().strip())
            try:
                os.kill(pid, 0)
            except PermissionError:
                pass
            try:
                links = json.loads(subprocess.check_output(["ip", "-j", "address"], text=True, timeout=2))
                for link in links:
                    if str(link.get("ifname", "")).startswith("ppp"):
                        for addr in link.get("addr_info", []):
                            if addr.get("family") == "inet":
                                value["ip"] = addr.get("local", "")
                                value["state"] = "connected"
                                break
            except Exception:
                pass
            dns = []
            for resolver in (Path("/etc/ppp/resolv.conf"), Path("/run/pppd/resolv.conf")):
                try:
                    for line in resolver.read_text(encoding="utf-8", errors="replace").splitlines():
                        fields = line.split()
                        if len(fields) == 2 and fields[0] == "nameserver" and fields[1] not in dns:
                            dns.append(fields[1])
                except OSError:
                    continue
            value["dns"] = dns
            print(json.dumps(value))
        except FileNotFoundError:
            print('{"state":"disconnected","profileId":"","ip":"","since":0,"message":""}')
        except ProcessLookupError:
            print('{"state":"disconnected","profileId":"","ip":"","since":0,"message":""}')
    elif command == "logs":
        try:
            log_path = Path("/run/omarchy-sstp-manager") / (str(os.getuid()) + ".log")
            print("".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines(True)[-100:]))
        except FileNotFoundError:
            print("No connection log yet.")
    elif command == "connect" or command == "disconnect" or command == "test":
        ident = sys.argv[2] if len(sys.argv) > 2 else ""
        profile_path(ident)
        helper = "/usr/lib/omarchy-sstp-manager/privileged.py"
        result = subprocess.run(["pkexec", helper, command, ident], text=True, capture_output=True, timeout=45)
        if result.stdout:
            print(result.stdout.strip())
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Privileged helper failed")
    else:
        raise ValueError("Unknown command")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        sys.exit(1)
