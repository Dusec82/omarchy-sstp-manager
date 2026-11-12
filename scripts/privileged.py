#!/usr/bin/env python3
"""Root helper. Install as /usr/lib/omarchy-sstp-manager/privileged.py."""
import json
import os
import pwd
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
STATE_DIR = Path("/run/omarchy-sstp-manager")
ALLOWED_PPP = {"require-mschap-v2", "refuse-eap", "usepeerdns", "defaultroute", "nodefaultroute", "noauth", "noipdefault", "noccp"}


def managed_process(pid):
    try:
        if os.getpgid(pid) != pid:
            return False
        with open("/proc/%d/cmdline" % pid, "rb") as stream:
            return stream.read(4096).split(b"\0", 1)[0] == b"/usr/bin/sstpc"
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return False


def main():
    if os.geteuid() != 0 or len(sys.argv) != 3:
        raise RuntimeError("This helper must be run through pkexec")
    uid = int(os.environ.get("PKEXEC_UID", "-1"))
    user = pwd.getpwuid(uid)
    op, ident = sys.argv[1], sys.argv[2]
    if op not in ("connect", "disconnect", "test") or not ID_RE.fullmatch(ident):
        raise RuntimeError("Unsupported operation or profile id")
    STATE_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o755)
    pid_file = STATE_DIR / (str(uid) + ".pid")
    state_file = STATE_DIR / (str(uid) + ".json")
    if op == "disconnect":
        try:
            pid = int(pid_file.read_text().strip())
            if managed_process(pid):
                os.killpg(pid, signal.SIGTERM)
            pid_file.unlink(missing_ok=True)
        except (FileNotFoundError, ProcessLookupError, ValueError):
            pid_file.unlink(missing_ok=True)
        state_file.write_text(json.dumps({"state": "disconnected", "profileId": "", "profileName": "", "ip": "", "since": 0, "message": ""}))
        os.chmod(state_file, 0o644)
        print("Disconnected")
        return
    if not Path("/usr/bin/pppd").is_file():
        raise RuntimeError("ppp is required; install it with: sudo pacman -S ppp")
    config = Path(user.pw_dir) / ".config/omarchy/sstp-manager/profiles" / (ident + ".json")
    fd_config = os.open(config, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    st = os.fstat(fd_config)
    if st.st_uid != uid or st.st_mode & 0o077:
        os.close(fd_config)
        raise RuntimeError("Profile must be owned by the caller and have mode 0600")
    with os.fdopen(fd_config, "r", encoding="utf-8") as stream:
        profile = json.load(stream)
    if not isinstance(profile, dict):
        raise RuntimeError("Invalid profile format")
    host = str(profile.get("server", ""))
    name = str(profile.get("username", ""))
    secret = str(profile.get("password", ""))
    if not host or len(host) > 253 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:%_-]*", host):
        raise RuntimeError("Invalid server")
    if not name or len(name) > 256 or any(c in name for c in "\n\r\x00"):
        raise RuntimeError("Invalid username")
    if not secret or len(secret) > 1024 or any(c in secret for c in "\n\r\x00"):
        raise RuntimeError("Password is required")
    if int(profile.get("port", 443)) != 443:
        raise RuntimeError("This sstpc build exposes no custom port option; use port 443")
    args = ["/usr/bin/sstpc", "--log-stderr"]
    if profile.get("debugLogging") is True:
        args.extend(["--log-level", "4"])
    args.extend(["--user", name, "--password", secret])
    if profile.get("tlsExt") is True:
        args.append("--tls-ext")
    if profile.get("certWarn") is True:
        args.append("--cert-warn")
    ca = str(profile.get("caCert", ""))
    if ca:
        if not ca.startswith("/") or ".." in Path(ca).parts:
            raise RuntimeError("Invalid CA path")
        args.extend(["--ca-cert", ca])
    proxy = str(profile.get("proxy", ""))
    if proxy:
        if not re.fullmatch(r"https?://[A-Za-z0-9._:-]+(?::[0-9]{1,5})?", proxy):
            raise RuntimeError("Invalid proxy")
        args.extend(["--proxy", proxy])
    if profile.get("saveServerRoute", True) is True:
        args.append("--save-server-route")
    args.append(host)
    opts = profile.get("pppOptions", []) if isinstance(profile.get("pppOptions", []), list) else []
    for option in opts:
        if option in ALLOWED_PPP:
            args.append(option)
        elif isinstance(option, str) and re.fullmatch(r"mtu=(?:[0-9]{3,4})", option) and 576 <= int(option.split("=", 1)[1]) <= 1500:
            args.extend(["mtu", option.split("=", 1)[1]])
    # Client mode must not require the VPN peer to authenticate itself over PPP.
    # Server identity is checked by SSTP's TLS certificate validation.
    args.append("noauth")
    if profile.get("debugLogging") is True:
        args.append("debug")
    args.append("nodetach")
    if profile.get("routeMode", "split") == "full":
        args.append("defaultroute")
    else:
        args.append("nodefaultroute")
    log = STATE_DIR / (str(uid) + ".log")
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.fchown(fd, uid, user.pw_gid)
    os.fchmod(fd, 0o600)
    if op == "test":
        try:
            test_args = [arg for arg in args if arg != "defaultroute"]
            if "nodefaultroute" not in test_args:
                test_args.append("nodefaultroute")
            completed = subprocess.run(["/usr/bin/timeout", "12"] + test_args, stdin=subprocess.DEVNULL, stdout=fd, stderr=fd, timeout=15, check=False, start_new_session=True)
            print("SSTP stayed active for 12 seconds; inspect the log for PPP details" if completed.returncode == 124 else "SSTP test completed" if completed.returncode == 0 else "SSTP test failed; see log")
        finally:
            os.close(fd)
        return
    if pid_file.exists():
        try:
            existing_pid = int(pid_file.read_text().strip())
            if managed_process(existing_pid):
                raise RuntimeError("A connection is already starting or active")
            pid_file.unlink(missing_ok=True)
        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
    child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=fd, stderr=fd, start_new_session=True, close_fds=True)
    os.close(fd)
    pid_file.write_text(str(child.pid))
    os.chmod(pid_file, 0o644)
    state_file.write_text(json.dumps({"state": "connecting", "profileId": ident, "profileName": str(profile.get("name", "SSTP"))[:80], "ip": "", "since": int(time.time()), "message": ""}))
    os.chmod(state_file, 0o644)
    time.sleep(0.7)
    if child.poll() is not None:
        pid_file.unlink(missing_ok=True)
        raise RuntimeError("sstpc exited during startup; see connection log")
    print("Connection started")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
