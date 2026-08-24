# -*- coding: utf-8 -*-
"""Fix line 158 - remove embedded newline in docstring"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'rb') as f:
    data = f.read()

# Find the problematic area around line 158
# Look for the pattern with embedded newline
pattern = b'"""\xe6\xa0\xb9\xe6\x8d\xae IP \xe8\xbf\x87\xe5\xbb\xba'
idx = data.find(pattern)
if idx >= 0:
    print(f"Found pattern at byte {idx}")
    # Show surrounding bytes
    chunk = data[idx:idx+200]
    print(f"Chunk: {chunk}")
    
    # Check for embedded newline
    if b'\n' in chunk[:150]:
        print("Found embedded newline!")
        
# Replace the entire line 158 properly
# Read as lines, fix, write back
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\nLine 158 has {len(lines[157])} chars")
print(f"Contains newline: {chr(10) in lines[157]}")

# Fix: replace with single-line version (no embedded newlines)
lines[157] = '    """根据IP过去24h锁定次数决定本次冷却时长(秒)。include_current=1表示即将触发的这一次也算进去。用于record_lockout后回扣。"""\n'

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\nFixed!")

# Verify
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"✗ Error at line {e.lineno}: {e.msg}")
