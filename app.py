import os
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, close_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.teardown_appcontext(close_db)

# create the database automatically if it does not exist
if not os.path.exists("bus.db"):
    init_db()


# ---------- helpers: protect pages ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first")
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access only")
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper


# ---------- DAY 1: home ----------
@app.route("/")
def home():
    return render_template("index.html", today=date.today().isoformat())


# ---------- DAY 2: register, login, logout ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or len(password) < 6:
            flash("Fill all fields. Password must be 6+ characters")
            return render_template("register.html")

        db = get_db()
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            flash("Email already registered")
            return render_template("register.html")

        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
        flash("Registered! Please login")
        return redirect("/login")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["is_admin"] = user["is_admin"]
            flash("Login successful")
            return redirect("/")
        flash("Wrong email or password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect("/")


# ---------- DAY 3: search ----------
@app.route("/search")
def search():
    source = request.args.get("source", "").strip()
    destination = request.args.get("destination", "").strip()
    travel_date = request.args.get("travel_date", "")

    if travel_date < date.today().isoformat():
        flash("Please pick today or a future date")
        return redirect("/")

    buses = get_db().execute(
        """
        SELECT s.*, b.name AS bus_name, b.bus_type, b.total_seats,
               (b.total_seats - (SELECT COUNT(*) FROM bookings k
                                 WHERE k.schedule_id = s.id
                                 AND k.status = 'CONFIRMED')) AS available
        FROM schedules s
        JOIN buses b ON b.id = s.bus_id
        WHERE LOWER(s.source) = LOWER(?) AND LOWER(s.destination) = LOWER(?)
              AND s.travel_date = ?
        ORDER BY s.departure_time
        """,
        (source, destination, travel_date),
    ).fetchall()

    return render_template("search.html", buses=buses, source=source,
                           destination=destination, travel_date=travel_date)


# ---------- DAY 4: seat selection and booking ----------
@app.route("/book/<int:schedule_id>", methods=["GET", "POST"])
@login_required
def book(schedule_id):
    db = get_db()
    schedule = db.execute(
        """SELECT s.*, b.name AS bus_name, b.bus_type, b.total_seats
           FROM schedules s JOIN buses b ON b.id = s.bus_id
           WHERE s.id = ?""",
        (schedule_id,),
    ).fetchone()
    if schedule is None:
        flash("Schedule not found")
        return redirect("/")

    rows = db.execute(
        "SELECT seat_number FROM bookings WHERE schedule_id = ? AND status = 'CONFIRMED'",
        (schedule_id,),
    ).fetchall()
    booked = [r["seat_number"] for r in rows]

    if request.method == "POST":
        seats = [int(x) for x in request.form.getlist("seats")]
        name = request.form["passenger_name"].strip()
        age = request.form["passenger_age"]
        phone = request.form["passenger_phone"].strip()

        if not seats:
            flash("Select at least one seat")
        elif not name or not age.isdigit() or len(phone) < 10:
            flash("Enter valid passenger details")
        elif any(s in booked or s < 1 or s > schedule["total_seats"] for s in seats):
            flash("A seat is not available. Pick another")
        else:
            for seat in seats:
                db.execute(
                    """INSERT INTO bookings
                       (user_id, schedule_id, passenger_name, passenger_age,
                        passenger_phone, seat_number)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session["user_id"], schedule_id, name, int(age), phone, seat),
                )
            db.commit()
            total = schedule["price"] * len(seats)
            flash(f"Booked seats {', '.join(map(str, seats))}. Total: ₹{total}")
            # Day 5 will change this to redirect("/my-bookings")
            return redirect("/my-bookings")

    return render_template("seats.html", schedule=schedule, booked=booked)

# ---------- DAY 5: my bookings and cancel ----------
@app.route("/my-bookings")
@login_required
def my_bookings():
    bookings = get_db().execute(
        """SELECT k.*, s.source, s.destination, s.travel_date, s.departure_time,
                  s.price, b.name AS bus_name
           FROM bookings k
           JOIN schedules s ON s.id = k.schedule_id
           JOIN buses b ON b.id = s.bus_id
           WHERE k.user_id = ?
           ORDER BY k.id DESC""",
        (session["user_id"],),
    ).fetchall()
    return render_template("my_bookings.html", bookings=bookings)


@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if booking and (booking["user_id"] == session["user_id"] or session.get("is_admin")):
        db.execute("UPDATE bookings SET status = 'CANCELLED' WHERE id = ?", (booking_id,))
        db.commit()
        flash("Booking cancelled")
    else:
        flash("Not allowed")
    return redirect(request.referrer or "/my-bookings")

# ---------- DAY 5: admin dashboard ----------
@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        "buses": db.execute("SELECT COUNT(*) FROM buses").fetchone()[0],
        "schedules": db.execute("SELECT COUNT(*) FROM schedules").fetchone()[0],
        "bookings": db.execute(
            "SELECT COUNT(*) FROM bookings WHERE status = 'CONFIRMED'").fetchone()[0],
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
    }
    return render_template("admin/dashboard.html", stats=stats)


@app.route("/admin/buses", methods=["GET", "POST"])
@admin_required
def admin_buses():
    db = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        bus_type = request.form["bus_type"].strip()
        seats = int(request.form["total_seats"])
        if not name or not bus_type or seats < 1 or seats > 60:
            flash("Fill all fields. Seats must be between 1 and 60")
        else:
            db.execute(
                "INSERT INTO buses (name, bus_type, total_seats) VALUES (?, ?, ?)",
                (name, bus_type, seats),
            )
            db.commit()
            flash("Bus added")
        return redirect("/admin/buses")
    buses = db.execute("SELECT * FROM buses ORDER BY id").fetchall()
    return render_template("admin/buses.html", buses=buses)


@app.route("/admin/buses/<int:bus_id>/delete", methods=["POST"])
@admin_required
def delete_bus(bus_id):
    db = get_db()
    used = db.execute(
        "SELECT COUNT(*) FROM schedules WHERE bus_id = ?", (bus_id,)).fetchone()[0]
    if used:
        flash("Cannot delete: this bus has schedules")
    else:
        db.execute("DELETE FROM buses WHERE id = ?", (bus_id,))
        db.commit()
        flash("Bus deleted")
    return redirect("/admin/buses")


# ---------- DAY 6: manage schedules ----------
@app.route("/admin/schedules", methods=["GET", "POST"])
@admin_required
def admin_schedules():
    db = get_db()
    if request.method == "POST":
        source = request.form["source"].strip()
        destination = request.form["destination"].strip()
        price = float(request.form["price"])
        if not source or not destination or price <= 0:
            flash("Fill all fields. Price must be more than 0")
        else:
            db.execute(
                """INSERT INTO schedules
                   (bus_id, source, destination, travel_date, departure_time, price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (int(request.form["bus_id"]), source, destination,
                 request.form["travel_date"], request.form["departure_time"], price),
            )
            db.commit()
            flash("Schedule added")
        return redirect("/admin/schedules")

    buses = db.execute("SELECT * FROM buses").fetchall()
    schedules = db.execute(
        """SELECT s.*, b.name AS bus_name
           FROM schedules s JOIN buses b ON b.id = s.bus_id
           ORDER BY s.travel_date, s.departure_time"""
    ).fetchall()
    return render_template("admin/schedules.html", buses=buses, schedules=schedules)


@app.route("/admin/schedules/<int:schedule_id>/delete", methods=["POST"])
@admin_required
def delete_schedule(schedule_id):
    db = get_db()
    used = db.execute(
        "SELECT COUNT(*) FROM bookings WHERE schedule_id = ? AND status = 'CONFIRMED'",
        (schedule_id,),
    ).fetchone()[0]
    if used:
        flash("Cannot delete: schedule has confirmed bookings")
    else:
        db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        db.commit()
        flash("Schedule deleted")
    return redirect("/admin/schedules")


# ---------- DAY 6: all bookings ----------
@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    bookings = get_db().execute(
        """SELECT k.*, u.name AS user_name, s.source, s.destination,
                  s.travel_date, b.name AS bus_name
           FROM bookings k
           JOIN users u ON u.id = k.user_id
           JOIN schedules s ON s.id = k.schedule_id
           JOIN buses b ON b.id = s.bus_id
           ORDER BY k.id DESC"""
    ).fetchall()
    return render_template("admin/bookings.html", bookings=bookings)

# ---------- DAY 7: custom 404 page ----------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

# ---- new routes for the next days go ABOVE this line ----
if __name__ == "__main__":
    app.run(debug=True, port=5001)