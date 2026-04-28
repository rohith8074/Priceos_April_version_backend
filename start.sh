#!/bin/bash
set -e

echo "[STARTUP] Clearing pip cache for motor..."
pip cache remove motor 2>/dev/null || true

echo "[STARTUP] Removing any existing motor installation..."
python3 -c "
import sys, os, shutil
for base in sys.path:
    if not os.path.isdir(base): continue
    motor_dir = os.path.join(base, 'motor')
    if os.path.isdir(motor_dir):
        shutil.rmtree(motor_dir, ignore_errors=True)
        print(f'Removed {motor_dir}')
    for item in os.listdir(base):
        if item.startswith('motor') and (item.endswith('.dist-info') or item.endswith('.egg-info')):
            shutil.rmtree(os.path.join(base, item), ignore_errors=True)
            print(f'Removed dist-info: {item}')
"

echo "[STARTUP] Installing motor==3.5.1 (direct PyPI, no proxy)..."
pip install --no-cache-dir --index-url https://pypi.org/simple/ "motor==3.5.1" "pymongo>=4.5.0,<5.0.0"

echo "[STARTUP] Verifying motor/core.py content (checking for 2.x contamination)..."
python3 -c "
import pathlib, sys
for p in sys.path:
    core = pathlib.Path(p) / 'motor' / 'core.py'
    if core.exists():
        content = core.read_text()
        if '_QUERY_OPTIONS' in content:
            print(f'[FAIL] Motor 2.x code still in {core} — trying GitHub source install')
            sys.exit(1)
        else:
            print(f'[OK] Motor 3.x code confirmed at {core}')
        break
else:
    print('[FAIL] motor/core.py not found anywhere in sys.path')
    sys.exit(1)
"

echo "[STARTUP] Verifying motor import..."
python3 -c "
from motor.motor_asyncio import AsyncIOMotorClient
import motor
print('[STARTUP] Motor OK! Version:', motor.version, 'at', motor.__file__)
"

echo "[STARTUP] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers 1
