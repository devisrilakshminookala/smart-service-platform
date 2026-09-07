from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Secret key
app.secret_key = os.getenv("SECRET_KEY", "smart-service-local-key")


# ---------------- DATABASE CONNECTION ----------------

db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("home.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # Hash password before storing it
        hashed_password = generate_password_hash(password)

        cursor = db.cursor()

        query = """
        INSERT INTO users (name, email, password)
        VALUES (%s, %s, %s)
        """

        try:
            cursor.execute(
                query,
                (name, email, hashed_password)
            )

            db.commit()
            cursor.close()

            return "Registration successful! <a href='/login'>Login here</a>"

        except mysql.connector.Error as e:

            cursor.close()

            return f"Registration failed: {e}"

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cursor = db.cursor()

        query = """
        SELECT id, name, email, password, role
        FROM users
        WHERE email = %s
        """

        cursor.execute(query, (email,))
        user = cursor.fetchone()

        if user:

            user_id = user[0]
            name = user[1]
            stored_password = user[3]
            role = user[4]

            password_valid = False

            # Check hashed password
            try:
                password_valid = check_password_hash(
                    stored_password,
                    password
                )
            except ValueError:
                password_valid = False

            # Convert old plaintext password to hashed password
            if not password_valid and stored_password == password:

                new_password = generate_password_hash(password)

                cursor.execute(
                    """
                    UPDATE users
                    SET password = %s
                    WHERE id = %s
                    """,
                    (new_password, user_id)
                )

                db.commit()

                password_valid = True

            if password_valid:

                session["user_id"] = user_id
                session["name"] = name
                session["role"] = role

                cursor.close()

                if role == "admin":
                    return redirect("/admin-dashboard")

                elif role == "staff":
                    return redirect("/staff-dashboard")

                else:
                    return redirect("/dashboard")

        cursor.close()

        return "Invalid email or password."

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ---------------- USER DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "user":
        return redirect("/login")

    return render_template("dashboard.html")


# ---------------- RAISE SERVICE REQUEST ----------------

@app.route("/request", methods=["GET", "POST"])
def service_request():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "user":
        return redirect("/login")

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        priority = request.form["priority"]

        # Use logged-in user's ID
        user_id = session["user_id"]

        cursor = db.cursor()

        query = """
        INSERT INTO service_requests
        (user_id, title, description, category, priority)
        VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                user_id,
                title,
                description,
                category,
                priority
            )
        )

        db.commit()
        cursor.close()

        return redirect("/my-requests")

    return render_template("request.html")


# ---------------- MY REQUESTS ----------------

@app.route("/my-requests")
def my_requests():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "user":
        return redirect("/login")

    user_id = session["user_id"]

    cursor = db.cursor()

    query = """
    SELECT *
    FROM service_requests
    WHERE user_id = %s
    ORDER BY created_at DESC
    """

    cursor.execute(query, (user_id,))

    requests = cursor.fetchall()

    cursor.close()

    return render_template(
        "my_requests.html",
        requests=requests
    )


# ---------------- STAFF DASHBOARD ----------------

@app.route("/staff-dashboard")
def staff_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "staff":
        return redirect("/login")

    staff_id = session["user_id"]

    cursor = db.cursor()

    query = """
    SELECT *
    FROM service_requests
    WHERE assigned_staff_id = %s
    ORDER BY created_at DESC
    """

    cursor.execute(query, (staff_id,))

    requests = cursor.fetchall()

    cursor.close()

    return render_template(
        "staff_dashboard.html",
        requests=requests
    )


# ---------------- UPDATE REQUEST STATUS ----------------

@app.route("/update-status/<int:request_id>", methods=["POST"])
def update_status(request_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "staff":
        return redirect("/login")

    status = request.form["status"]

    staff_id = session["user_id"]

    cursor = db.cursor()

    query = """
    UPDATE service_requests
    SET status = %s
    WHERE id = %s
    AND assigned_staff_id = %s
    """

    cursor.execute(
        query,
        (
            status,
            request_id,
            staff_id
        )
    )

    db.commit()
    cursor.close()

    return redirect("/staff-dashboard")


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin-dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    cursor = db.cursor()

    # Total users
    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    total_users = cursor.fetchone()[0]

    # Total requests
    cursor.execute(
        "SELECT COUNT(*) FROM service_requests"
    )

    total_requests = cursor.fetchone()[0]

    # Submitted
    cursor.execute("""
        SELECT COUNT(*)
        FROM service_requests
        WHERE status = 'Submitted'
    """)

    submitted = cursor.fetchone()[0]

    # In Progress
    cursor.execute("""
        SELECT COUNT(*)
        FROM service_requests
        WHERE status = 'In Progress'
    """)

    in_progress = cursor.fetchone()[0]

    # Resolved
    cursor.execute("""
        SELECT COUNT(*)
        FROM service_requests
        WHERE status = 'Resolved'
    """)

    resolved = cursor.fetchone()[0]

    # All requests
    cursor.execute("""
        SELECT *
        FROM service_requests
        ORDER BY created_at DESC
    """)

    requests = cursor.fetchall()

    # Staff users
    cursor.execute("""
        SELECT id, name, email
        FROM users
        WHERE role = 'staff'
    """)

    staff_users = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_requests=total_requests,
        submitted=submitted,
        in_progress=in_progress,
        resolved=resolved,
        requests=requests,
        staff_users=staff_users
    )


# ---------------- ASSIGN STAFF ----------------

@app.route("/assign-staff/<int:request_id>", methods=["POST"])
def assign_staff(request_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    staff_id = request.form["staff_id"]

    cursor = db.cursor()

    query = """
    UPDATE service_requests
    SET assigned_staff_id = %s
    WHERE id = %s
    """

    cursor.execute(
        query,
        (
            staff_id,
            request_id
        )
    )

    db.commit()
    cursor.close()

    return redirect("/admin-dashboard")


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True)