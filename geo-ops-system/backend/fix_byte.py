# -*- coding: utf-8 -*-
"""Byte-level fix for app.py encoding issues"""

with open('app.py', 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes")

# Find and fix the specific problematic string
old_bytes = b'db.create_role("\xe2\x93\x92\xe5\x90\xaf\xe8\xad\x89\xe7\x90\x86\xe5\x91\x98"'
new_bytes = b'db.create_role("\xe8\xb6\x85\xe7\xba\xa7\xe7\xae\xa1\xe7\x90\x86\xe5\x91\x98"'

if old_bytes in data:
    data = data.replace(old_bytes, new_bytes)
    print("Fixed: 超级管理员")
else:
    print("Pattern 1 not found")

# Fix description field
old_desc = b'\xe7\xb3\xbb\xe7\xbb\x9f\xe5\x86\x85\xe7\xbd\xae\xe2\x93\x92\xe5\x90\xaf\xe8\xad\x89\xe7\x90\x86\xe5\x91\x98'
new_desc = b'\xe7\xb3\xbb\xe7\xbb\x9f\xe5\x86\x85\xe7\xbd\xae\xe8\xb6\x85\xe7\xba\xa7\xe7\xae\xa1\xe7\x90\x86\xe5\x91\x98'

if old_desc in data:
    data = data.replace(old_desc, new_desc)
    print("Fixed: 系统内置超级管理员")
else:
    print("Pattern 2 not found")

# Write back
with open('app.py', 'wb') as f:
    f.write(data)

print("\nDone! Testing syntax...")

# Test
import subprocess
result = subprocess.run(
    ['.venv/Scripts/python.exe', '-c', 'import ast; ast.parse(open("app.py", encoding="utf-8").read()); print("Syntax OK")'],
    capture_output=True,
    text=True
)
print(result.stdout)
if result.stderr:
    print("Error:", result.stderr)
