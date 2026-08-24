import db

conn = db.get_conn()

# 删除所有角色
db._exec(conn, 'DELETE FROM role')

# 插入正确角色
db._exec(conn, """INSERT INTO role (code, name, data_scope, is_builtin, pages) VALUES 
('super_admin', '超级管理员', 'all', 1, '["home","accounts","keyword-search","knowledge","admin-users","roles","settings"]'),
('admin', '管理员', 'team', 1, '["home","accounts","keyword-search","knowledge"]'),
('operator', '运营人员', 'self', 1, '["home","keyword-search"]')""")

# 验证
role = db.get_role_by_code('super_admin')
print('super_admin role:', role)
if role:
    print('Code:', role['code'])
    print('Pages:', role['pages'])
