import subprocess
import re
import sys
import os
import time
import socket
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_EXE = BASE_DIR / "cloudflared.exe"

def get_local_ip():
    """Get local Wi-Fi IPv4 address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run():
    print("=" * 65)
    print("      ⚡ CLIPZY AI - SUPERCHARGED MOBILE CONNECTOR ⚡")
    print("=" * 65)
    
    local_ip = get_local_ip()
    print(f"\n[1] Starting local Clipzy AI backend on http://0.0.0.0:8000...")

    # Start FastAPI backend bound to 0.0.0.0 so both Wi-Fi and Tunnel can reach it
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(BASE_DIR / "backend"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    tunnel_url = None
    if CLOUDFLARED_EXE.exists():
        print("[2] Starting Cloudflare secure HTTPS tunnel (using HTTP/2 for Indian ISPs)...")
        # Enforce --protocol http2 to prevent Airtel/Jio UDP QUIC packet drops
        tunnel_cmd = [
            str(CLOUDFLARED_EXE), "tunnel",
            "--url", "http://127.0.0.1:8000",
            "--protocol", "http2",
            "--no-autoupdate"
        ]
        
        tunnel_proc = subprocess.Popen(
            tunnel_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace"
        )

        url_found_event = threading.Event()
        extracted_url = [None]
        url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

        def log_reader():
            try:
                for line in iter(tunnel_proc.stderr.readline, ""):
                    if not line:
                        break
                    match = url_pattern.search(line)
                    if match and not extracted_url[0]:
                        extracted_url[0] = match.group(0)
                        url_found_event.set()
            except Exception:
                pass

        t = threading.Thread(target=log_reader, daemon=True)
        t.start()

        # Wait up to 15 seconds
        url_found_event.wait(timeout=15)
        tunnel_url = extracted_url[0]

    print("\n" + "=" * 65)
    print("   🎉 SUCCESS! CLIPZY AI IS ONLINE & READY FOR YOUR IPHONE!")
    print("=" * 65)
    
    if tunnel_url:
        print("\n👉 OPTION A: Open this link on your iPhone (5G, 4G, or Wi-Fi):")
        print(f"   \033[96m{tunnel_url}\033[0m")
        
    if local_ip != "127.0.0.1":
        print(f"\n👉 OPTION B: Open this link on your iPhone (if on same Wi-Fi / Hotspot):")
        print(f"   \033[92mhttp://{local_ip}:8000\033[0m")

    print("\n" + "=" * 65)
    print("💡 Zero Bot Checks Guaranteed:")
    print("   Running through your home connection bypasses ALL YouTube cloud bot checks!")
    print("\n(Keep this terminal open while clipping from your iPhone)")
    print("Press Ctrl+C to stop the server when you are done.\n")

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("Notice: Backend process stopped.")
                break
    except KeyboardInterrupt:
        print("\nStopping Clipzy AI server...")
        backend_proc.terminate()
        try:
            if 'tunnel_proc' in locals():
                tunnel_proc.terminate()
        except:
            pass
        print("Done. Goodbye!")

if __name__ == "__main__":
    run()
