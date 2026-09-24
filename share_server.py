"""
One-click LAN share launcher for the Poultry Farm app.

Auto-detects this machine's local network IP, copies the share URLs to the
clipboard, prints them (app + API for PCs and phones), then starts the Django
dev server bound to 0.0.0.0 so every device on the Wi-Fi/LAN can open it.

Usage:
    uv run python share_server.py            # share on port 8000 (default)
    uv run python share_server.py 8080       # share on a custom port

Or just double-click "Share Farm App.bat".
"""

import os
import socket
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = "8000"


def detect_lan_ips():
    """Return the local network IP(s) this machine advertises to the LAN."""
    ips = []

    # Preferred trick: open a UDP socket toward a public address (no traffic
    # is actually sent) and read back the local interface IP it would use.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        ips.append(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()

    # Fallback: resolve the hostname, which on home/office LANs usually maps
    # to the local IPv4 address.
    if not ips:
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if not ip.startswith("127.") and ip not in ips:
                    ips.append(ip)
        except OSError:
            pass

    return ips


def copy_to_clipboard(text):
    """Copy text to the Windows clipboard via PowerShell (no extra deps)."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{text}'"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def firewall_is_clear(port):
    """Best-effort check: True if a allow rule for this port likely exists."""
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule",
             "name=Poultry Farm App Share"],
            capture_output=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return True


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    ips = detect_lan_ips()

    print("=" * 62)
    print("  POULTRY FARM APP - LOCAL NETWORK SHARE")
    print("=" * 62)

    if not ips:
        print("\n  [!] Could not detect a LAN IP - is Wi-Fi/Ethernet connected?")
        print("      The app will still be available on this computer:")
        print(f"      http://127.0.0.1:{port}/")
    else:
        lan_ip = ips[0]
        app_url = f"http://{lan_ip}:{port}/"
        api_url = f"http://{lan_ip}:{port}/api/"

        print("\n  Share these addresses with devices on the same Wi-Fi/LAN:\n")
        print(f"    Other computers  ->  {app_url}")
        print(f"    Mobile phones    ->  {app_url}")
        print(f"    API (any device) ->  {api_url}")
        if len(ips) > 1:
            print(f"\n    Extra interface:     http://{ips[1]}:{port}/")

        if copy_to_clipboard(app_url):
            print(f"\n  [OK] App URL ({app_url}) is already COPIED to your")
            print("       clipboard - just paste (Ctrl+V) and send it around.")

        if not firewall_is_clear(port):
            print("\n  [!] Windows Firewall may block other devices. If a phone")
            print("      or PC cannot connect, right-click")
            print("      'Allow Network Access (once).bat' -> Run as administrator.")

    print("\n  Press Ctrl+C (or close this window) to STOP sharing.")
    print("=" * 62 + "\n")

    os.chdir(BASE_DIR)
    cmd = [sys.executable, "manage.py", "runserver", f"0.0.0.0:{port}", "--noreload"]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n  Sharing stopped.")


if __name__ == "__main__":
    main()
