"""Development seeder for ISPSC Alumni Connect.

Run from the project root after setting DATABASE_URL:
    python api/seed.py

It is safe to run repeatedly: existing sample email addresses are skipped.
Never run this command against a live production database.
"""
from datetime import datetime, timezone

from main import Alumni, SessionLocal, hash_password

SAMPLE_PASSWORD = "ChangeMe2026!"
SAMPLE_USERS = [
    {
        "name": "Dr. Maria Santos", "email": "admin@ispsc-alumni.test", "role": "admin",
        "degree": "BS Information Technology", "batch_year": 2014,
        "job_title": "Alumni Affairs Administrator", "company": "ISPSC Alumni Affairs Office", "location": "Ilocos Sur",
    },
    {
        "name": "John Michael Dela Cruz", "email": "john.delacruz@ispsc-alumni.test", "role": "user",
        "degree": "BS Computer Science", "batch_year": 2019,
        "job_title": "Software Engineer", "company": "Arcanys", "location": "Cebu City",
    },
    {
        "name": "Anne Rivera", "email": "anne.rivera@ispsc-alumni.test", "role": "user",
        "degree": "BS Accountancy", "batch_year": 2018,
        "job_title": "Audit Associate", "company": "SGV & Co.", "location": "Baguio City",
    },
    {
        "name": "Rafael Garcia", "email": "rafael.garcia@ispsc-alumni.test", "role": "user",
        "degree": "BS Agriculture", "batch_year": 2020,
        "job_title": "Farm Operations Officer", "company": "DA Region I", "location": "Vigan City",
    },
    {
        "name": "Liza Bautista", "email": "liza.bautista@ispsc-alumni.test", "role": "user",
        "degree": "BS Nursing", "batch_year": 2019,
        "job_title": "Registered Nurse", "company": "St. Paul Hospital", "location": "Ilocos Sur",
    },
]

def main():
    db = SessionLocal()
    try:
        added = 0
        for item in SAMPLE_USERS:
            if db.query(Alumni).filter(Alumni.email == item["email"]).first():
                continue
            db.add(Alumni(
                **item,
                password_hash=hash_password(SAMPLE_PASSWORD),
                consent_at=datetime.now(timezone.utc),
                directory_visible="alumni",
            ))
            added += 1
        db.commit()
        print(f"Added {added} sample account(s). Password for all samples: {SAMPLE_PASSWORD}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
