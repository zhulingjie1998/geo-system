# -*- coding: utf-8 -*-
"""Fix missing _DefaultJSONProvider import"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add import for DefaultJSONProvider from flask
old_import = 'from flask import Flask, Response, jsonify, redirect, render_template_string, request, send_from_directory, session'
new_import = 'from flask import Flask, Response, jsonify, redirect, render_template_string, request, send_from_directory, session\nfrom flask.json.provider import DefaultJSONProvider as _DefaultJSONProvider'

if '_DefaultJSONProvider' not in content.split('from flask import')[0] if 'from flask import' in content else True:
    if old_import in content:
        content = content.replace(old_import, new_import)
        print("Added DefaultJSONProvider import")
    else:
        # Try to find and add after existing flask import
        for line in content.split('\n'):
            if 'from flask import' in line and '_DefaultJSONProvider' not in line:
                content = content.replace(line, line + '\nfrom flask.json.provider import DefaultJSONProvider as _DefaultJSONProvider')
                print(f"Added import after: {line[:60]}...")
                break

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("\nDone!")
