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


# ---- new routes for the next days go ABOVE this line ----
if __name__ == "__main__":
    app.run(debug=True, port=5001)