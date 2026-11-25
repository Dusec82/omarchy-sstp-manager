#!/usr/bin/env python3
"""Safely manage short-lived credentials in pppd's root-only secrets file."""
import fcntl
import os
import re
import stat
import tempfile
from pathlib import Path

SECRETS = Path("/etc/ppp/chap-secrets")
LOCK = Path("/run/lock/omarchy-sstp-manager-chap-secrets.lock")
TOKEN_RE = re.compile(r"^sstpm-[0-9]+-[A-Za-z0-9_-]{1,48}-[a-f0-9]{24}$")
MARKER = "# omarchy-sstp-manager:"


def quote(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _read_lines():
    try:
        info = SECRETS.lstat()
    except FileNotFoundError:
        return []
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0:
        raise RuntimeError("/etc/ppp/chap-secrets must be a regular root-owned file")
    if info.st_mode & 0o022:
        raise RuntimeError("/etc/ppp/chap-secrets must not be writable by group or others")
    return SECRETS.read_text(encoding="utf-8").splitlines()


def _write_lines(lines):
    SECRETS.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".chap-secrets.", dir=str(SECRETS.parent))
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines).rstrip("\n") + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, SECRETS)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _locked_update(token, username=None, password=None):
    if not TOKEN_RE.fullmatch(token):
        raise RuntimeError("Invalid PPP credential token")
    LOCK.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    lock_fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        lock_info = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != 0:
            raise RuntimeError("Unsafe PPP secrets lock ownership")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        lines = _read_lines()
        marker = MARKER + token
        result = []
        skip_record = False
        for line in lines:
            if line == marker:
                skip_record = True
                continue
            if skip_record:
                skip_record = False
                continue
            result.append(line)
        if username is not None:
            result.extend([marker, "%s %s %s *" % (quote(username), quote(token), quote(password))])
        _write_lines(result)
    finally:
        os.close(lock_fd)


def install_secret(token, username, password):
    if any(c in username + password for c in "\x00\r\n"):
        raise RuntimeError("PPP credentials contain unsupported control characters")
    _locked_update(token, username, password)


def remove_secret(token):
    _locked_update(token)


def remove_profile_secrets(uid, profile_id):
    prefix = "sstpm-%d-%s-" % (uid, profile_id)
    LOCK.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    lock_fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        lock_info = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != 0:
            raise RuntimeError("Unsafe PPP secrets lock ownership")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        lines = _read_lines()
        result = []
        skip_record = False
        for line in lines:
            if line.startswith(MARKER) and line[len(MARKER):].startswith(prefix):
                skip_record = True
                continue
            if skip_record:
                skip_record = False
                continue
            result.append(line)
        _write_lines(result)
    finally:
        os.close(lock_fd)
