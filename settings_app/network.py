"""Helpers for the admin LAN / Wi-Fi sharing control panel.

Two jobs:

1. Detect this machine's local IPv4 address(es) so an administrator can point a
   device on the same network (e.g. the mobile app on a phone) at the dev server.
2. Optionally launch a *separate* ``runserver`` bound to ``0.0.0.0`` so external
   interfaces accept connections.

Why a separate process and not a live "rebind"?
    A view runs *inside* the already-running ``runserver`` process. It cannot
    rebind or restart its own listening socket, and starting a second server on
    the same port fails with "port already in use". So the one-click action
    spawns a detached server on a free port and always reports the manual
    command needed to relaunch the current server on ``0.0.0.0``.

Detection uses only the standard library (``socket`` + ``ipaddress``).
"""
from __future__ import annotations

import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from django.conf import settings

# Written by the spawned server so failures can be surfaced in the UI.
LOG_FILENAME = "lan_server.log"
# Records the port + PID of the background server we started, so a later
# request (or page reload) can tell whether sharing is still active and stop it.
STATE_FILENAME = "lan_server.state"


def _candidate_ipv4() -> set[str]:
    """Collect candidate IPv4 addresses from the OS."""
    ips: set[str] = set()

    # 1) UDP "connect" trick: reveals the source address chosen for the default
    #    route (the LAN IP) without actually transmitting any packets.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(0.5)
        sock.connect(("10.255.255.255", 1))
        ips.add(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()

    # 2) Everything the hostname resolves to (covers extra NICs / adapters).
    try:
        _, _, addrs = socket.gethostbyname_ex(socket.gethostname())
        ips.update(addrs)
    except OSError:
        pass

    return ips


def detect_addresses() -> list[dict]:
    """Return local IPv4 addresses with classification flags for the template."""
    results: list[dict] = []
    seen: set[str] = set()
    for raw in sorted(_candidate_ipv4()):
        if raw in seen:
            continue
        seen.add(raw)
        try:
            ip = ipaddress.IPv4Address(raw)
        except ipaddress.AddressValueError:
            continue
        results.append(
            {
                "ip": raw,
                "loopback": ip.is_loopback,
                "private": ip.is_private,  # normal LAN range (192.168.x, 10.x, ...)
                "link_local": ip.is_link_local,
            }
        )
    return results


def lan_addresses() -> list[str]:
    """Non-loopback IPv4 addresses — what a phone on the same Wi-Fi must use."""
    return [a["ip"] for a in detect_addresses() if not a["loopback"]]


def current_server_port(request) -> int | None:
    """Best-effort port the *current* request is being served on (as int)."""
    try:
        return int(request.get_port())
    except (TypeError, ValueError):
        pass
    except Exception:
        pass
    host = request.get_host()
    if ":" in host:
        try:
            return int(host.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            return None
    return None


def reached_via_ip(request) -> bool:
    """True when the admin already loads this page via a bare-IP host header.

    That implies the running server is already listening on a LAN-reachable
    interface (it was started with ``--bind 0.0.0.0`` or an explicit IP).
    """
    host = (request.get_host() or "").split(":")[0].strip("[]")
    try:
        ipaddress.IPv4Address(host)
        return True
    except ipaddress.AddressValueError:
        return False


def probe_port(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """Return True if something is already listening on ``port`` (TCP connect)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def suggest_free_port(start: int = 8001, tries: int = 25) -> int:
    """First TCP port at/after ``start`` with nothing listening on it.

    Lets the one-click Share button pick a port the current server is *not*
    holding, so a single click actually starts sharing instead of warning.
    """
    for port in range(start, start + tries):
        if not probe_port(port):
            return port
    return start


def log_path() -> Path:
    return Path(settings.BASE_DIR) / LOG_FILENAME


def read_log_tail(lines: int = 20) -> str:
    path = log_path()
    if not path.exists():
        return ""
    try:
        return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def build_command(port: int) -> str:
    """The manual command to relaunch the current server on all interfaces."""
    return f"python manage.py runserver 0.0.0.0:{port}"


def start_lan_server(port: int) -> int | None:
    """Spawn a detached ``runserver 0.0.0.0:<port>`` process. Returns its PID.

    ``--noreload`` is used deliberately: the autoreloader forks a child and makes
    detaching/orphan-handling messy. Output is redirected to ``lan_server.log``.
    """
    manage_py = Path(settings.BASE_DIR) / "manage.py"
    cmd = [
        sys.executable,
        str(manage_py),
        "runserver",
        f"0.0.0.0:{port}",
        "--noreload",
    ]
    try:
        log = open(log_path(), "ab")
    except OSError:
        log = subprocess.DEVNULL

    popen_kwargs = {
        "cwd": str(settings.BASE_DIR),
        "stdout": log,
        "stderr": subprocess.STDOUT if log is not subprocess.DEVNULL else log,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        popen_kwargs["creationflags"] = detached | new_group
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)
    return proc.pid


def wait_for_port(port: int, attempts: int = 10, delay: float = 0.5) -> bool:
    """Poll ``port`` for up to ``attempts * delay`` seconds."""
    for _ in range(attempts):
        if probe_port(port):
            return True
        time.sleep(delay)
    return False


def wait_for_port_release(port: int, attempts: int = 12, delay: float = 0.3) -> bool:
    """Wait until nothing is listening on ``port`` anymore."""
    for _ in range(attempts):
        if not probe_port(port):
            return True
        time.sleep(delay)
    return not probe_port(port)


def state_path() -> Path:
    return Path(settings.BASE_DIR) / STATE_FILENAME


def write_state(port: int, pid: int | None) -> None:
    try:
        state_path().write_text(json.dumps({"port": port, "pid": pid}))
    except OSError:
        pass


def read_state() -> dict | None:
    path = state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        port = int(data["port"])
        pid = data.get("pid")
        return {"port": port, "pid": int(pid) if pid else None}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def clear_state() -> None:
    try:
        state_path().unlink()
    except OSError:
        pass


def sharing_status() -> dict | None:
    """Return ``{'port', 'pid'}`` if our background server is still listening.

    Self-heals a stale state file: if the recorded port is no longer in use
    (process died or was stopped out-of-band), the state is cleared and None
    is returned so the UI falls back to idle rather than lying about sharing.
    """
    state = read_state()
    if not state or not state.get("port"):
        return None
    if probe_port(state["port"]):
        return state
    clear_state()
    return None


def stop_lan_server() -> bool:
    """Kill the background server we started and clear its state. Best-effort."""
    state = read_state()
    if not state:
        return False
    pid, port = state.get("pid"), state.get("port")
    killed = False
    if pid:
        if os.name == "nt":
            # /T kills the child tree; /F forces. Avoids os.kill's TerminateProcess pitfall.
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
            )
            killed = result.returncode == 0
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                killed = True
            except OSError:
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed = True
                except OSError:
                    killed = False
    released = wait_for_port_release(port) if port else True
    clear_state()
    return killed or released
