"""
generate_hashes.py — Run this ONCE to create correct bcrypt hashes
then update your seed.sql or run the UPDATE queries it prints.

Usage:
    python generate_hashes.py
"""
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


passwords = {
    'admin':      'Admin@123',
    'dr_ahmed':   'DrAhmed@123',
    'dr_fatima':  'DrFatima@123',
    'dr_omar':    'DrOmar@123',
    'nurse_sara': 'NurseSara@123',
    'nurse_ali':  'NurseAli@123',
    'billing1':   'Billing@123',
    'pt_mkhan':   'PtKhan@123',
    'pt_ayesha':  'PtAyesha@123',
    'pt_zainab':  'PtZainab@123',
}

print("-- Run these UPDATE statements in SSMS after running seed.sql:\n")
for username, password in passwords.items():
    h = hash_password(password)
    print(f"UPDATE Users SET password_hash = '{h}' WHERE username = '{username}';")

print("\nGO")
print("\n-- Done!")
