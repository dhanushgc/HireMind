import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

# Paths to all DB files
USER_DB = os.path.join(BASE, "../services/user_auth.db")

def create_user_auth_tables():
    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS recruiters (
        recruiter_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        email          TEXT UNIQUE NOT NULL,
        password_hash  TEXT NOT NULL,
        name           TEXT,
        company_name   TEXT,
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        email          TEXT UNIQUE NOT NULL,
        password_hash  TEXT NOT NULL,
        name           TEXT,
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()
    print("Recruiter & Candidate auth tables created in user_auth.db.")


def main():
    create_user_auth_tables()
    print("✅ All databases and tables initialized successfully.")

if __name__ == "__main__":
    main()
