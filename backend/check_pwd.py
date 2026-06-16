import os; os.chdir("E:\\Python_Code_Project\\DataMind\\backend")
import sys; sys.path.insert(0, ".")
from app.core.auth import hash_password

for pwd in ["admin123", "password123", "123456", "password"]:
    h = hash_password(pwd)
    print(f"{pwd}: {h}")
