import os
from datetime import date 
from functools import wraps 
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash,check_password_hash
from db import get_db, close_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.teardown_appcontext(close_db)


if not os.path.exists("bus.db"):
    init_db()


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
        if not session.get("is_Admin"):
           flash("Admin access only")
           return redirect("/")
        return f(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    return render_template(
        "index.html",
        today=date.today().isoformat()
    )

# ---- pasted new routes 
if __name__ == "__main__":
    app.run(debug=True, port=5001)
