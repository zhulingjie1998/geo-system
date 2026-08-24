"""Nuclear option: rebuild archive API section from scratch"""
fp = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the archive section by looking for unique markers
# Strategy: find everything between "# Archive (归档) API" and "@app.post...transfer"

import re

# Pattern to match the entire broken archive section
pattern = r'(# ═+.*?Archive.*?API.*?═+\s*)@app\.post\("/api/accounts/<int:account_id>/archive"\).*?return jsonify\(\{"ok": True, "purged": stats\}\)\s*\)'

# Build the replacement text
replacement = '''# ═══════════════════════════════════════════
# Archive (归档) API
# ═══════════════════════════════════════════

@app.post("/api/accounts/<int:account_id>/archive")
def api_account_archive(account_id):
    """Archive account: keep data but hide from list"""
    acc = db.get_account(account_id)
    if not acc:
        return jsonify({"error": "客户不存在"}), 404
    if not _is_full_view_role():
        if acc.get("ownerId") != session.get("user_id"):
            return jsonify({"error": "无权操作"}), 403
    result = db.archive_account(account_id)
    return jsonify({"ok": True, **result})


@app.post("/api/accounts/<int:account_id>/unarchive")
def api_account_unarchive(account_id):
    """Restore from archive to active list"""
    acc = db.get_account(account_id, include_deleted=True)
    if not acc:
        return jsonify({"error": "客户不存在"}), 404
    if not _is_full_view_role():
        if acc.get("ownerId") != session.get("user_id"):
            return jsonify({"error": "无权操作"}), 403
    restored = db.unarchive_account(account_id)
    if not restored:
        return jsonify({"error": "恢复失败"}), 500
    return jsonify({"ok": True, "account": restored})


@app.get("/api/accounts/archived")
def api_archived_list():
    """Get archived accounts list"""
    rows = db.list_archived_accounts(**_account_scope_kwargs())
    return jsonify(rows)


@app.delete("/api/accounts/<int:account_id>/purge-archived")
def api_purge_archived_account(account_id):
    """Permanently delete archived account"""
    acc = db.get_account(account_id, include_deleted=True)
    if not acc:
        return jsonify({"error": "客户不存在"}), 404
    if not _is_full_view_role():
        if acc.get("ownerId") != session.get("user_id"):
            return jsonify({"error": "无权操作"}), 403
    stats = db.purge_archived_account(account_id)
    return jsonify({"ok": True, "purged": stats})'''

new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

if count > 0:
    print(f'Replaced {count} occurrence(s)')
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('File saved')
else:
    print('Pattern not found. Trying simpler approach...')
    
    # Simpler: just replace each garbled string individually
    garbled_strings = [
        ('鎭㈠澶辫触', '恢复失败'),
        ('鑾峰彇褰掓。瀹㈡埛鍒楄〃', '获取归档客户列表'),
        ('姘镐箙鍒犻櫎宸插綊妗ｇ殑瀹㈡埛', '永久删除已归档的客户'),
        ('瀹㈡埛涓嶅瓨鍦?', '客户不存在'),
    ]
    
    total = 0
    for old, new in garbled_strings:
        if old in new_content:
            c = new_content.count(old)
            new_content = new_content.replace(old, new)
            total += c
            print(f'Fixed {c}x: {old}')
    
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'Total fixes: {total}')
