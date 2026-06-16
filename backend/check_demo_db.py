import os, sqlite3

os.chdir("E:\\Python_Code_Project\\DataMind\\backend")

dbs = [
    "../demo_data/hr_demo.sqlite",
    "../demo_data/crm_demo.sqlite",
    "../demo_data/finance_demo.sqlite",
    "../demo_data/erp_demo.sqlite",
]

for db_path in dbs:
    full_path = os.path.abspath(os.path.join(os.getcwd(), db_path))
    if not os.path.exists(full_path):
        print(f"{db_path}: 不存在")
        continue

    conn = sqlite3.connect(full_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()

    print(f"\n{'='*60}")
    print(f"数据库: {db_path}")
    print(f"表数量: {len(tables)}")

    for (table_name,) in tables:
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = cursor.fetchall()
        print(f"\n  \u8868: {table_name} ({len(columns)} \u5217)")
        for col in columns:
            print(f"    {col[1]:25s} {col[2]:15s} nullable={col[3]}  pk={col[5]}")

        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
        rows = cursor.fetchall()
        if rows:
            col_names = [c[1] for c in columns]
            print(f"  样本数据:")
            for row in rows:
                d = dict(zip(col_names, row))
                print(f"    {d}")

    conn.close()

print("\nDone checking demo databases.")
