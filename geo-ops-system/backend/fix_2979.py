# -*- coding: utf-8 -*-
"""Fix orphaned except at line 2979"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 2975-2980 have orphaned code without try
# Need to add try: before import knowledge_routes
print("Lines 2974-2981:")
for i in range(2973, 2981):
    print(f"  {i+1}: {lines[i][:80].rstrip()}")

# Find "import knowledge_routes" and add try before it
for i in range(2970, 2980):
    if 'import knowledge_routes' in lines[i]:
        # Insert try: before this line with proper indentation
        lines.insert(i, 'try:\n')
        print(f"\nInserted 'try:' before line {i+1}")
        break

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# Verify syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"\n✗ Error at line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno-3), min(e.lineno+3, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:100]}")
