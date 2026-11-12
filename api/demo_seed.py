"""Seed a fictional, connected alumni community for demos and local testing.

The script is safe to repeat: it only creates records with the ``demo.alumni``
email domain and student numbers beginning with ``DEMO-``.  It never changes
existing non-demo accounts.  Passwords are random and intentionally not
printed, so these profiles cannot be used to sign in.

Examples:
    # Seed the database from api/.env (for example a Neon DATABASE_URL)
    python api/demo_seed.py

    # Export the portable, non-sensitive data catalog for local testing
    python api/demo_seed.py --export demo-alumni.json

    # Use a separate local database
    $env:DATABASE_URL = "sqlite:///./alumni_demo.db"  # PowerShell
    python api/demo_seed.py
"""
from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

YEARS = range(2015, 2026)
PEOPLE = (
    ("Avery", "Sample", "BS Information Technology", "Systems Analyst", "Vigan City"),
    ("Bela", "Sample", "BS Accountancy", "Finance Associate", "Baguio City"),
    ("Cian", "Sample", "BS Agriculture", "Program Coordinator", "Ilocos Sur"),
)


def catalog() -> list[dict[str, object]]:
    """Return 33 fictional profiles: three for every graduating batch."""
    profiles: list[dict[str, object]] = []
    for year in YEARS:
        for position, (first, last, degree, title, location) in enumerate(PEOPLE, start=1):
            slug = f"{year}-{position}"
            profiles.append(
                {
                    "name": f"{first} {last} {year}",
                    "email": f"{first.lower()}.{year}.{position}@demo.alumni",
                    "student_number": f"DEMO-{year}-{position:02d}",
                    "degree": degree,
                    "major": degree.removeprefix("BS "),
                    "batch_year": year,
                    "job_title": title,
                    "company": "Sample Organization",
                    "location": location,
                    "bio": "Fictional profile generated for the ISPSC Alumni Connect demonstration.",
                    "directory_visible": "alumni",
                    "catalog_key": slug,
                }
            )
    return profiles


def connection_pairs(keys: list[str]) -> set[tuple[str, str]]:
    """Build a small, LinkedIn-style network within and across batches."""
    pairs: set[tuple[str, str]] = set()
    for offset in range(0, len(keys), 3):
        group = keys[offset : offset + 3]
        if len(group) == 3:
            pairs.update(((group[0], group[1]), (group[1], group[2]), (group[2], group[0])))
    # Join each batch to the next one so the directory is one community.
    for offset in range(0, len(keys) - 3, 3):
        pairs.add((keys[offset], keys[offset + 3]))
    return pairs


def export_catalog(destination: Path) -> None:
    profiles = catalog()
    keys = [str(item.pop("catalog_key")) for item in profiles]
    document = {
        "description": "Fictional, non-login alumni profiles for local testing.",
        "profiles": profiles,
        "accepted_connections": [list(pair) for pair in sorted(connection_pairs(keys))],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(profiles)} fictional profiles to {destination}")


def seed() -> tuple[int, int]:
    # Keep this import here so --export works on any machine with Python,
    # even before the FastAPI requirements have been installed.
    from sqlalchemy import or_, select
    from main import Alumni, Connection, SessionLocal, hash_password

    entries = catalog()
    db = SessionLocal()
    try:
        profiles: dict[str, Alumni] = {}
        added_profiles = 0
        for item in entries:
            key = str(item.pop("catalog_key"))
            person = db.scalar(select(Alumni).where(Alumni.email == item["email"]))
            if person is None:
                person = Alumni(
                    **item,
                    role="user",
                    consent_at=datetime.now(timezone.utc),
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                )
                db.add(person)
                db.flush()
                added_profiles += 1
            profiles[key] = person

        added_connections = 0
        for requester_key, recipient_key in connection_pairs(list(profiles)):
            requester, recipient = profiles[requester_key], profiles[recipient_key]
            existing = db.scalar(
                select(Connection).where(
                    or_(
                        (Connection.requester_id == requester.id) & (Connection.recipient_id == recipient.id),
                        (Connection.requester_id == recipient.id) & (Connection.recipient_id == requester.id),
                    )
                )
            )
            if existing is None:
                db.add(Connection(requester_id=requester.id, recipient_id=recipient.id, status="accepted"))
                added_connections += 1
        db.commit()
        return added_profiles, added_connections
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, metavar="FILE", help="write a portable JSON demo-data catalog")
    args = parser.parse_args()
    if args.export:
        export_catalog(args.export)
        return
    profiles, connections = seed()
    print(f"Demo database ready: {profiles} profile(s) and {connections} accepted connection(s) added.")


if __name__ == "__main__":
    main()
