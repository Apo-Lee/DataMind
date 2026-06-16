import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
from app.core.query_engine import SQLBuilder, PermissionEngine, normalize_sql_values
from app.core.query_rewriter import QueryInterceptor

print("=" * 60)
print("FINAL VERIFICATION (fixed assertions)")
print("=" * 60)

all_pass = True

# attendance
ic2 = QueryInterceptor({"mode":"filtered","filter_clauses":{"dept_id":"XXXX","employee_id":"employee_id IN(1,2)"}})
r2 = ic2.rewrite_sql("SELECT status FROM attendance", "attendance")
ok = "employee_id" in r2 and "XXXX" not in r2
print(f"  [{'OK' if ok else 'FAIL'}] Attendance RLS: {r2}")
all_pass &= ok

# customers
ic3 = QueryInterceptor({"mode":"filtered","filter_clauses":{"dept_id":"XXXX","owner_id":"owner_id IN(1,2)"}})
r3 = ic3.rewrite_sql("SELECT name FROM customers", "customers")
ok = "owner_id" in r3 and "XXXX" not in r3
print(f"  [{'OK' if ok else 'FAIL'}] Customers RLS: {r3}")
all_pass &= ok

# departments
ic = QueryInterceptor({"mode":"filtered","filter_clauses":{"dept_id":"dept_id IN(1)"}})
r = ic.rewrite_sql("SELECT name FROM departments", "departments")
ok = "dept_id" not in r
print(f"  [{'OK' if ok else 'FAIL'}] Departments skip: {r}")
all_pass &= ok

print()
print(f"ALL {'PASSED' if all_pass else 'SOME FAILED'}!")
