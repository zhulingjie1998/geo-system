import sys
import zipfile
import os

zip_path = r"c:\Users\Administrator\Desktop\geo-ops-system-full-170758.zip"

if not os.path.exists(zip_path):
    print(f"ERROR: File not found: {zip_path}")
    sys.exit(1)

size = os.path.getsize(zip_path)
print(f"File size: {size:,} bytes ({size / 1024 / 1024:.1f} MB)")

try:
    with zipfile.ZipFile(zip_path, 'r') as zf:
        entries = zf.namelist()
        print(f"Total entries: {len(entries)}")
        
        # Show some key files
        key_files = [
            "backend/app.py",
            "backend/dev_server.py",
            "backend/requirements.txt",
            "backend/.env",
            "frontend/package.json",
            "frontend/vite.config.js",
            "README.md",
        ]
        
        print("\nKey files check:")
        for kf in key_files:
            found = any(e.endswith(kf) for e in entries)
            print(f"  {'OK' if found else 'MISSING':>7}  {kf}")
        
        # Count by top-level dir
        dirs = {}
        for e in entries:
            parts = e.split('/')
            top = parts[0] if parts else '(root)'
            dirs[top] = dirs.get(top, 0) + 1
        
        print("\nEntries by top-level directory:")
        for d, c in sorted(dirs.items(), key=lambda x: -x[1])[:15]:
            print(f"  {c:>6}  {d}")
        
        # Check for node_modules and .venv
        nm_count = sum(1 for e in entries if 'node_modules' in e)
        venv_count = sum(1 for e in entries if '.venv' in e)
        print(f"\nnode_modules entries: {nm_count}")
        print(f".venv entries: {venv_count}")
        
        print("\nZIP file is VALID and readable.")
except Exception as e:
    print(f"ERROR reading zip: {e}")
    sys.exit(1)
