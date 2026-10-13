from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "prodigy_task_4_development_key"
)
socketio = SocketIO(app, async_mode="threading")

DATABASE = "chat.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            room TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    if "username" in session:
        return redirect(url_for("chat"))

    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please fill in all fields.")
            return render_template("register.html")

        if len(username) < 3:
            flash("Username must contain at least 3 characters.")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )
            conn.commit()
            conn.close()

            flash("Account created successfully! Please log in.")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conn.close()
            flash("Username already exists.")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["username"] = user["username"]
            return redirect(url_for("chat"))

        flash("Invalid username or password.")

    return render_template("login.html")


@app.route("/chat")
def chat():
    if "username" not in session:
        return redirect(url_for("login"))

    return render_template(
        "chat.html",
        username=session["username"]
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@socketio.on("join")
def handle_join(data):
    if "username" not in session:
        return

    room = str(data.get("room", "general")).strip().lower()

    if not room or len(room) > 30:
        return

    join_room(room)

    emit(
        "system_message",
        {"message": f'{session["username"]} joined #{room}.'},
        to=room
    )

@socketio.on("send_message")
def handle_message(data):
    print("MESSAGE EVENT RECEIVED:", data)

    if "username" not in session:
        print("ERROR: User not logged in")
        return

    room = str(data.get("room", "general")).strip().lower()
    message = str(data.get("message", "")).strip()

    if not room or len(room) > 30 or not message or len(message) > 1000:
        print("ERROR: Invalid room or message")
        return

    conn = get_db()

    conn.execute(
        "INSERT INTO messages (username, room, message) VALUES (?, ?, ?)",
        (session["username"], room, message)
    )

    conn.commit()
    conn.close()

    print("MESSAGE SAVED:", message)

    emit(
        "receive_message",
        {
            "username": session["username"],
            "message": message
        },
        to=room
    )