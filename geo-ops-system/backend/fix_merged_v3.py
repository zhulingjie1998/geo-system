# -*- coding: utf-8 -*-
"""Fix remaining merged comment+code lines starting with #"""

import re

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = 0
for i, line in enumerate(lines):
    # Lines that start with # (comment) but have code after the corrupted part
    # Pattern: "    # [mojibake]    resp.headers..." or similar
    if line.strip().startswith('#') and any(ord(c) > 127 for c in line):
        # Look for code patterns after the comment
        patterns = [
            r'#.*?\s{4,}(resp|return|db\.|logger|if |for |with |import )',
            r'#.*?    (resp|return|db\.|logger)',
        ]
        
        for pat in patterns:
            match = re.search(pat, line)
            if match:
                # Find where the actual code keyword starts
                kw_match = re.search(r'(resp|return|db\.|logger|if |for |with |import )', line[match.start():])
                if kw_match:
                    # Extract from the keyword position
                    abs_pos = match.start() + kw_match.start()
                    code_part = line[abs_pos:]
                    # Ensure proper indentation
                    if not code_part.startswith('    '):
                        code_part = '    ' + code_part.lstrip()
                    
                    print(f"Line {i+1}: Extracted code from comment")
                    lines[i] = code_part
                    fixed += 1
                    break

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print(f"\nFixed {fix} more lines")

# Verify syntax
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
