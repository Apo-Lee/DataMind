import os, sqlite3

os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

conn = sqlite3.connect("datamind.db")
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print("系统数据库表:")
for (t,) in tables:
    cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
    count = cursor.fetchone()[0]
    print(f"  {t}: {count} 条记录")

table_names = [t[0] for t in tables]

if "users" in table_names:
    cursor.execute("SELECT id, username, display_name, role, data_scope, dept_id, employee_id FROM users")
    print("\n用户列表:")
    for row in cursor.fetchall():
        print(f"  {row}")

if "datasources" in table_names:
    cursor.execute("SELECT id, name, db_type, host, business_tag, is_active, is_system FROM datasources")
    print("\n数据源列表:")
    for row in cursor.fetchall():
        print(f"  {row}")

if "datasource_permissions" in table_names:
    cursor.execute("SELECT * FROM datasource_permissions")
    print("\n数据源权限:")
    for row in cursor.fetchall():
        print(f"  {row}")

conn.close()
