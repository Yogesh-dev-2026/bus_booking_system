import sqlite3
from datetime import date, timedelta
from flask import g
from werkzeug.security import generate_password_hash

DATABASE = "bus.db"


def get_db():
    """Open one database connection per request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables and add sample data."""
    db = sqlite3.connect(DATABASE)
    with open("schema.sql") as f:
        db.executescript(f.read())

    db.execute(
        "INSERT INTO users (name, email, password_hash, is_admin) VALUES (?, ?, ?, 1)",
        ("Admin", "admin@busgo.com", generate_password_hash("admin123")),
    )
    db.executemany(
        "INSERT INTO buses (name, bus_type, total_seats) VALUES (?, ?, ?)",
        [("KPN Travels", "AC Sleeper", 20), ("SRS Express", "Non-AC Seater", 16)],
    )
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    db.executemany(
        """INSERT INTO schedules
           (bus_id, source, destination, travel_date, departure_time, price)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (1, "Chennai", "Bangalore", tomorrow, "21:30", 850),
            (2, "Chennai", "Bangalore", tomorrow, "06:00", 450),
            (1, "Chennai", "Coimbatore", tomorrow, "22:00", 900),
        ],
    )
    db.commit()
    db.close()


if __name__ == "__main__":
    init_db()
    print("Database ready: bus.db created")