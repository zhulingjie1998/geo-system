# -*- coding: utf-8 -*-
"""Fix multiple issues: tuple definition, f-strings, etc."""

import re

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Issue 1: Line 105-106 should be: # comment\n_PUBLIC_API_PREFIXES = (
# Currently line 105 is just a comment, line 106 is another comment
# Need to add the tuple assignment
print("\n--- Fix 1: _PUBLIC_API_PREFIXES ---")
print(f"Line 105: {lines[104][:80].rstrip()}")
print(f"Line 106: {lines[105][:80].rstrip()}")

# Insert _PUBLIC_API_PREFIXES = ( after line 105
lines[105] = '_PUBLIC_API_PREFIXES = (\n'

# Add closing ) after line 119 (the last element of the tuple)
# Find the line after "/api/share/kb-review/",  # KB review share with token auth
for i in range(116, 125):
    if 'KB review share with token auth' in lines[i]:
        print(f"Found tuple end at line {i+1}")
        # Insert ) after this line
        lines.insert(i+1, ')\n')
        break

# Issue 2: Fix f-strings with mojibake
print("\n--- Fix 2: F-strings with mojibake ---")
for i, line in enumerate(lines):
    # Look for f-strings with Chinese mojibake
    if 'f"' in line or "f'" in line:
        if any(ord(c) > 127 for c in line):
            # Check for unbalanced braces in f-string
            if '{' in line and '}' not in line[line.index('{'):]:
                print(f"Line {i+1}: Unbalanced f-string")
                print(f"  {line[:100].rstrip()}")
                # Try to fix by adding missing }
                # Find the last " before end of string
                # Simple approach: replace entire line with English version
                import re
                match = re.search(r'\{([^}]+)$', line.rstrip())
                if match:
                    var_name = match.group(1)
                    # Reconstruct with English text
                    new_line = re.sub(r'f"[^"]*"', f'"Too many attempts, try again in {{{var_name}} min"', line)
                    new_line = new_line.replace('"Too many', 'f"Too many')  # Make it f-string again
                    lines[i] = new_line + '\n'
                    print(f"  Fixed!")

# Issue 3: Remove remaining standalone mojibake comments
print("\n--- Fix 3: Remaining mojibake comments ---")
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('#') and any(ord(c) > 127 for c in line):
        print(f"Line {i+1}: Removing mojibake comment")
        lines[i] = '\n'

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\n--- Verifying syntax ---")
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"✗ Error at line {e.lineno}: {e.msg}")
    error_lines = content.split('\n')[max(0, e.lineno-3):e.lineno+3]
    for j, ln in enumerate(error_lines):
        marker = ">>>" if j == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+j}: {ln[:100]}")
