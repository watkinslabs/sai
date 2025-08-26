#!/usr/bin/env python3
"""
Simple script to show/unhide the overlay if it's running but not visible
"""

import psutil
import sys
import os

def find_overlay_process():
    """Find the overlay assistant process"""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['cmdline'] and 'overlay_assistant.py' in ' '.join(proc.info['cmdline']):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def main():
    proc = find_overlay_process()
    if proc:
        print(f"Overlay assistant is running (PID: {proc.pid})")
        print("If the window is not visible, try:")
        print("1. Check if it's hidden behind other windows")
        print("2. The window might have detected a 'video conferencing' app and auto-hid")
        print("3. Try killing and restarting:")
        print(f"   kill {proc.pid}")
        print("   uv run python overlay_assistant.py")
        
        # Check what processes might be triggering auto-hide
        print("\nChecking for processes that might trigger auto-hide:")
        excluded_procs = ['zoom', 'skype', 'teams', 'discord', 'slack', 'chrome', 'firefox', 'meet', 'webex']
        found_excluded = []
        
        for p in psutil.process_iter(['name']):
            try:
                proc_name = p.info['name'].lower()
                for excluded in excluded_procs:
                    if excluded in proc_name:
                        found_excluded.append(proc_name)
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if found_excluded:
            print("Found processes that trigger auto-hide:")
            for proc in set(found_excluded):
                print(f"  - {proc}")
            print("\nThe overlay auto-hides when these apps are running.")
            print("Close them or modify the EXCLUDED_PROCESSES list in overlay_assistant.py")
        else:
            print("No auto-hide trigger processes found.")
        
    else:
        print("Overlay assistant is not running.")
        print("Start it with: uv run python overlay_assistant.py")

if __name__ == "__main__":
    main()