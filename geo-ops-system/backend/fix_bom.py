# -*- coding: utf-8 -*-
"""Remove BOM from app.py"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'rb') as f:
    data = f.read()

# Check for BOM
if data.startswith(b'\xef\xbb\xbf'):
    print("Found UTF-8 BOM, removing...")
    data = data[3:]  # Remove BOM
    with open(filepath, 'wb') as f:
        f.write(data)
    print("BOM removed!")
else:
    print(f"No BOM found. First bytes: {data[:10].hex()}")

# Verify syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"\n✗ Syntax Error at line {e.lineno}: {e.msg}")
