import sqlite3
import os
import csv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "toy_inventory.db")
CLASSIFICATION_CSV = os.path.join(DB_DIR, "categorization.csv")

os.makedirs(DB_DIR, exist_ok=True)  # Ensure the database directory exists
os.makedirs(os.path.join(BASE_DIR, "static/uploads"), exist_ok=True)  # Uploads directory


def create_tables():
    """Create the database schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS Users (
        UserID INTEGER PRIMARY KEY AUTOINCREMENT,
        Username TEXT NOT NULL UNIQUE,
        Email TEXT NOT NULL UNIQUE,
        Password TEXT NOT NULL,
        ProfilePicture TEXT DEFAULT NULL,
        CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS Categories (
        CategoryID INTEGER PRIMARY KEY AUTOINCREMENT,
        CategoryName TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS Subcategories (
        SubcategoryID INTEGER PRIMARY KEY AUTOINCREMENT,
        SubcategoryName TEXT NOT NULL,
        CategoryID INTEGER NOT NULL,
        FOREIGN KEY (CategoryID) REFERENCES Categories(CategoryID)
    );

    CREATE TABLE IF NOT EXISTS Types (
        TypeID INTEGER PRIMARY KEY AUTOINCREMENT,
        TypeName TEXT NOT NULL,
        SubcategoryID INTEGER NOT NULL,
        FOREIGN KEY (SubcategoryID) REFERENCES Subcategories(SubcategoryID)
    );

    CREATE TABLE IF NOT EXISTS Toys (
        ToyID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Year INTEGER,
        CategoryID INTEGER NOT NULL,
        SubcategoryID INTEGER NOT NULL,
        TypeID INTEGER NOT NULL,
        Photo TEXT DEFAULT NULL,
        Description TEXT DEFAULT NULL,
        UserID INTEGER NOT NULL,
        FOREIGN KEY (CategoryID) REFERENCES Categories(CategoryID),
        FOREIGN KEY (SubcategoryID) REFERENCES Subcategories(SubcategoryID),
        FOREIGN KEY (TypeID) REFERENCES Types(TypeID),
        FOREIGN KEY (UserID) REFERENCES Users(UserID)
    );
    """)

    conn.commit()
    conn.close()
    print("Tables created successfully.")


def load_classification_data():
    """Load categories, subcategories, and types from classification.csv."""
    if not os.path.exists(CLASSIFICATION_CSV):
        print(f"Classification CSV file not found at: {CLASSIFICATION_CSV}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(CLASSIFICATION_CSV, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            category = row["Category"]
            sub_category = row["Sub-Category"]
            type_name = row["Type"]

            # Insert category
            cursor.execute("INSERT OR IGNORE INTO Categories (CategoryName) VALUES (?)", (category,))
            cursor.execute("SELECT CategoryID FROM Categories WHERE CategoryName = ?", (category,))
            category_id = cursor.fetchone()[0]

            # Insert subcategory
            cursor.execute("""
                INSERT OR IGNORE INTO Subcategories (SubcategoryName, CategoryID) VALUES (?, ?)
            """, (sub_category, category_id))
            cursor.execute("""
                SELECT SubcategoryID FROM Subcategories WHERE SubcategoryName = ? AND CategoryID = ?
            """, (sub_category, category_id))
            subcategory_id = cursor.fetchone()[0]

            # Insert type
            cursor.execute("""
                INSERT OR IGNORE INTO Types (TypeName, SubcategoryID) VALUES (?, ?)
            """, (type_name, subcategory_id))

    conn.commit()
    conn.close()
    print("Classification data loaded successfully.")


def main():
    """Main function to set up the database."""
    print("Setting up the database...")
    create_tables()
    load_classification_data()
    print("Database setup complete.")


if __name__ == "__main__":
    main()
