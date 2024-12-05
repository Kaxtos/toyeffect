import os
import csv  # <-- Import the CSV module
import uuid
import sqlite3
from collections import defaultdict
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from PIL import Image
import io
from rembg import remove
from flask_cors import CORS
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, Length, EqualTo
from werkzeug.utils import secure_filename
from flask import send_from_directory
from flask import Flask

app = Flask(__name__, static_folder="static")

# Initialize CSRF protection
csrf = CSRFProtect(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "database/toy_inventory.db")
CSV_PATH = "database/manufacturers.csv"

def populate_manufacturers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM Manufacturers")  # Optional: Clear table
    with open(CSV_PATH, "r") as file:
        reader = csv.reader(file)
        for row in reader:
            manufacturer = row[0].strip()
            if manufacturer:
                cursor.execute("""
                    INSERT OR IGNORE INTO Manufacturers (ManufacturerName) 
                    VALUES (?)""", (manufacturer,))
    conn.commit()
    conn.close()

populate_manufacturers()

# Configure the upload folder
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # Ensure the folder exists

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def landing():
    """Landing page."""
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User signup."""
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO Users (Username, Email, Password) VALUES (?, ?, ?)
            """, (username, email, password))
            conn.commit()
            flash("Account created successfully!", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "error")
        finally:
            conn.close()

    return render_template("signup.html")
    
@app.route("/login", methods=["GET", "POST"])
@csrf.exempt
def login():
    """User login."""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, Password FROM Users WHERE Email = ?", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "error")
        conn.close()

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    """User dashboard."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch username
    cursor.execute("SELECT Username FROM Users WHERE UserID = ?", (session["user_id"],))
    username = cursor.fetchone()[0]

    # Calculate total stats
    cursor.execute("SELECT COUNT(*) FROM Toys WHERE UserID = ?", (session["user_id"],))
    total_toys = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT CategoryID) FROM Toys WHERE UserID = ?
    """, (session["user_id"],))
    total_categories = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT SubcategoryID) FROM Toys WHERE UserID = ?
    """, (session["user_id"],))
    total_subcategories = cursor.fetchone()[0]

    cursor.execute("""
        SELECT IFNULL(SUM(Price * Quantity), 0) FROM Toys WHERE UserID = ?
    """, (session["user_id"],))
    total_value = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        username=username,
        total_toys=total_toys,
        total_categories=total_categories,
        total_subcategories=total_subcategories,
        total_value=total_value,
    )
@app.route("/add-toy", methods=["GET", "POST"])
@csrf.exempt
def add_toy():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Initialize database connection for fetching categories
    conn = sqlite3.connect(DB_PATH)
    conn.set_trace_callback(print)  # Enable SQLite debug logs
    cursor = conn.cursor()

    # Fetch categories for dropdown
    cursor.execute("SELECT CategoryID, CategoryName FROM Categories")
    categories = cursor.fetchall()

    # Load manufacturers from CSV
    manufacturers = []
    csv_path = os.path.join(os.path.dirname(__file__), "database/manufacturers.csv")
    try:
        with open(csv_path, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            manufacturers = [row[0] for row in reader if row]
    except FileNotFoundError:
        flash("Manufacturers CSV not found. Please upload it.", "danger")
    finally:
        conn.close()  # Close connection after fetching dropdown data

    if request.method == "POST":
        try:
            # Reinitialize connection for insert operation
            conn = sqlite3.connect(DB_PATH)
            conn.set_trace_callback(print)
            cursor = conn.cursor()

            # Process form data
            category = request.form.get("category")
            subcategory = request.form.get("subcategory")
            type_ = request.form.get("type")
            manufacturer = request.form.get("manufacturers")
            year = request.form.get("year")
            subject = request.form.get("subject")
            description = request.form.get("description")

            # Debugging: log form data
            print("Form Data:", category, subcategory, type_, manufacturer, year, subject)

            # Validate required fields
            if not all([category, subcategory, type_, year, subject]):
                flash("Please fill in all required fields.", "danger")
                return redirect(request.url)

            # Handle photo upload
            file = request.files.get("photo")
            photo_path = None
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                photo_path = f"uploads/{filename}"
                absolute_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(absolute_path)
            else:
                flash("Invalid or missing photo. Please upload a valid image file.", "danger")
                return redirect(request.url)

            # Insert data into database
            cursor.execute("""
                INSERT INTO Toys (
                    Name, Year, CategoryID, SubcategoryID, TypeID, Manufacturer, Description, 
                    Photo, UserID, Price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subject, year, category, subcategory, type_, manufacturer, description,
                photo_path, session["user_id"], price
            ))


            # Ensure consistent photo paths
            cursor.execute("""
                UPDATE Toys
                SET Photo = REPLACE(Photo, '\\', '/')
                WHERE Photo LIKE '%\\%'
            """)

            # Standardize relative paths
            cursor.execute("""
                UPDATE Toys
                SET Photo = SUBSTR(Photo, INSTR(Photo, 'uploads/'))
                WHERE Photo LIKE '%uploads/%'
            """)

            conn.commit()
            flash("Toy added successfully!", "success")
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            flash(f"Database error: {e}", "danger")
        finally:
            conn.close()  # Ensure connection is closed properly

        return redirect(request.url)

    return render_template("add-toy.html", categories=categories, manufacturers=manufacturers)

@app.route("/get-subcategories/<category_id>")
def get_subcategories(category_id):
    """Fetch unique subcategories for a given category."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT SubcategoryID, SubcategoryName 
        FROM Subcategories 
        WHERE CategoryID = ?
    """, (category_id,))
    subcategories = cursor.fetchall()
    conn.close()

    return jsonify(subcategories)

@app.route("/get-types/<subcategory_id>")
def get_types(subcategory_id):
    """Fetch unique types for a given subcategory."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT TypeID, TypeName 
        FROM Types 
        WHERE SubcategoryID = ?
    """, (subcategory_id,))
    types = cursor.fetchall()
    conn.close()

    return jsonify(types)

@app.route("/search-manufacturers", methods=["GET"])
def search_manufacturers():
    query = request.args.get("q", "").strip().lower()  # Get query from request
    if not query:
        return jsonify([])  # Return an empty list if no query

    try:
        # Read manufacturers from the CSV
        manufacturers = []
        csv_path = os.path.join(app.root_path, "database", "manufacturers.csv")
        with open(csv_path, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            manufacturers = [row[0] for row in reader]  # Assuming manufacturer names are in the first column

        # Filter manufacturers based on the query
        matching_manufacturers = [
            manufacturer for manufacturer in manufacturers if query in manufacturer.lower()
        ]

        return jsonify(matching_manufacturers[:10])  # Return the first 10 matches
    except Exception as e:
        print(f"Error searching manufacturers: {e}")
        return jsonify([]), 500
    

@app.route("/inventory", methods=["GET"])
def inventory():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        # Fetch categories, subcategories, and types for filters
        cursor.execute("SELECT DISTINCT CategoryID, CategoryName FROM Categories")
        categories = cursor.fetchall()

        cursor.execute("SELECT DISTINCT SubcategoryID, SubcategoryName FROM Subcategories")
        subcategories = cursor.fetchall()

        cursor.execute("SELECT DISTINCT TypeID, TypeName FROM Types")
        types = cursor.fetchall()

        # Fetch filters from the query string
        name_filter = request.args.get("name", "").strip()
        year_filter = request.args.get("year", "").strip()
        category_filter = request.args.get("category", "").strip()
        subcategory_filter = request.args.get("subcategory", "").strip()
        type_filter = request.args.get("type", "").strip()

        # Construct SQL query with filters
        query = """
            SELECT 
                t.ToyID, t.Name AS Subject, t.Year, t.Description, t.Photo, 
                t.Quantity, t.Price, c.CategoryName, sc.SubcategoryName, 
                ty.TypeName, t.CharacterAccessories 
            FROM Toys t
            LEFT JOIN Categories c ON t.CategoryID = c.CategoryID
            LEFT JOIN Subcategories sc ON t.SubcategoryID = sc.SubcategoryID
            LEFT JOIN Types ty ON t.TypeID = ty.TypeID
            WHERE t.UserID = ?
        """

        params = [session["user_id"]]

        if name_filter:
            query += " AND t.Name LIKE ?"
            params.append(f"%{name_filter}%")
        if year_filter:
            query += " AND t.Year = ?"
            params.append(year_filter)
        if category_filter:
            query += " AND t.CategoryID = ?"
            params.append(category_filter)
        if subcategory_filter:
            query += " AND t.SubcategoryID = ?"
            params.append(subcategory_filter)
        if type_filter:
            query += " AND t.TypeID = ?"
            params.append(type_filter)

        # Fetch toys with pagination
        cursor.execute("SELECT COUNT(*) FROM (" + query + ")", params)
        total_toys = cursor.fetchone()[0]

        page = int(request.args.get("page", 1))
        per_page = 10
        offset = (page - 1) * per_page
        total_pages = (total_toys + per_page - 1) // per_page

        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        cursor.execute(query, params)

        toys = cursor.fetchall()

        # Map categories, subcategories, and types for the dropdowns
        categories = [dict(id=row[0], name=row[1]) for row in categories]
        subcategories = [dict(id=row[0], name=row[1]) for row in subcategories]
        types = [dict(id=row[0], name=row[1]) for row in types]

        # Map toys for rendering
        toys = [
    dict(
        ToyID=row[0], Subject=row[1], Year=row[2], Description=row[3],
        Photo=row[4], Quantity=row[5], Price=row[6], CategoryName=row[7],
        SubcategoryName=row[8], TypeName=row[9], CharacterAccessories=row[10]
    )
    for row in toys
]


    finally:
        conn.close()  # Ensure the connection is closed after all operations

    return render_template(
        "inventory.html",
        categories=categories,
        subcategories=subcategories,
        types=types,
        toys=toys,
        current_page=page,
        total_pages=total_pages,
    )

@app.route("/profile")
def profile():
    """User profile."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT Username, Email FROM Users WHERE UserID = ?", (session["user_id"],))
    user_data = cursor.fetchone()
    conn.close()

    return render_template("profile.html", user=user_data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Use the PORT from the environment, default to 8000
    app.run(host="0.0.0.0", port=port)
