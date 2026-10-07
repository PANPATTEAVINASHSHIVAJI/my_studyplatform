from flask import Flask, request, jsonify, g
from flask import send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)

# ✅ Create instance folder and DB path
instance_path = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(instance_path, exist_ok=True)
db_path = os.path.join(instance_path, 'users.db')

# ✅ Create DB
def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """)
    # ✅ Books table
    c.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT,
            description TEXT,
            cover_icon TEXT
        )
    """)
    # ✅ Orders table
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            order_date TEXT NOT NULL,
            total_price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            delivery_address TEXT,
            phone TEXT
        )
    """)
    # ✅ Order items table
    c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_at_purchase REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
    """)
    conn.commit()
    
    # ✅ Insert sample books
    c.execute("SELECT COUNT(*) FROM books")
    if c.fetchone()[0] == 0:
        sample_books = [
            ("Data Structures & Algorithms", "Robert Sedgewick", 45.99, "Computer Science", "Master data structures with comprehensive examples", "💾"),
            ("Database Design Guide", "C.J. Date", 52.50, "Computer Science", "Learn database design principles and SQL optimization", "🗄️"),
            ("Operating Systems Explained", "Andrew Tanenbaum", 58.75, "Computer Science", "Deep dive into OS concepts, scheduling, and memory management", "⚙️"),
            ("Software Engineering Best Practices", "Ian Sommerville", 65.00, "Computer Science", "SDLC, design patterns, and software architecture", "🏗️"),
            ("Constitutional Law Handbook", "H.M. Seervai", 48.99, "Law", "Comprehensive guide to constitutional law and rights", "📘"),
            ("Contract Law Essentials", "G.H. Treitel", 42.50, "Law", "Master contract formation, terms, and remedies", "📝"),
            ("Criminal Procedure Manual", "K.N. Chandrasekharan", 55.00, "Law", "Complete criminal law and procedural guide", "⚖️"),
            ("Jurisprudence Theory", "H.L.A. Hart", 49.99, "Law", "Philosophy of law and legal theory fundamentals", "📚")
        ]
        for book in sample_books:
            c.execute(
                "INSERT INTO books (title, author, price, category, description, cover_icon) VALUES (?, ?, ?, ?, ?, ?)",
                book
            )
        conn.commit()
        print("✅ Sample books inserted", flush=True)
    
    conn.close()

init_db()

def log_auth_event(action, username, status):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    client_port = request.environ.get("REMOTE_PORT", "-")
    client_id = request.headers.get("X-Client-Id", "-")
    print(
        f"[{timestamp}] {action} | user={username} | status={status} | ip={client_ip}:{client_port} | client_id={client_id}",
        flush=True,
    )

def print_users(label):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, username, password FROM users ORDER BY id")
    users = c.fetchall()
    conn.close()

    print(f"\n📦 {label} - users in database:", flush=True)
    if users:
        for user in users:
            print(f"   ID={user[0]}, Username={user[1]}, Password={user[2]}", flush=True)
    else:
        print("   (no users found)", flush=True)

print_users("Startup")

@app.before_request
def capture_request_username():
    g.request_username = "-"
    if request.method == "POST" and request.path in {"/login", "/signup"}:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        if username:
            g.request_username = username

@app.after_request
def custom_access_log(response):
    timestamp = datetime.now().strftime("%d/%b/%Y %H:%M:%S")
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    client_port = request.environ.get("REMOTE_PORT", "-")
    protocol = request.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
    username = getattr(g, "request_username", "-")
    client_id = request.headers.get("X-Client-Id", "-")
    print(
        f'{client_ip}:{client_port} - user={username} - client_id={client_id} - [{timestamp}] "{request.method} {request.path} {protocol}" {response.status_code} -',
        flush=True,
    )
    return response

@app.route("/")
def home():
    return send_from_directory(os.path.dirname(__file__), "index.html")

@app.route("/<path:filename>")
def files(filename):
    allowed_extensions = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg"}
    _, extension = os.path.splitext(filename)

    if extension not in allowed_extensions:
        return jsonify({"message": "Not found"}), 404

    return send_from_directory(os.path.dirname(__file__), filename)

# ✅ REGISTER
@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        log_auth_event("SIGNUP_ATTEMPT", username, "received")

        if not username or not password:
            return jsonify({"message": "Username and password required"}), 400

        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if c.fetchone():
            conn.close()
            log_auth_event("SIGNUP", username, "failed_user_exists")
            return jsonify({"message": "User already exists"}), 400

        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()

        user_id = c.lastrowid
        conn.close()

        log_auth_event("SIGNUP", username, f"success_id_{user_id}")
        print_users("After signup")

        return jsonify({"message": "success"}), 201
    except Exception as e:
        print(f"❌ Signup Error: {str(e)}", flush=True)
        return jsonify({"message": f"Error: {str(e)}"}), 500

# ✅ LOGIN
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        log_auth_event("LOGIN_ATTEMPT", username, "received")

        if not username or not password:
            return jsonify({"message": "Username and password required"}), 400

        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute("SELECT id, username FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            log_auth_event("LOGIN", user[1], f"success_id_{user[0]}")
            print_users("After login")
            return jsonify({"message": "success"}), 200
        else:
            log_auth_event("LOGIN", username, "failed_invalid_credentials")
            return jsonify({"message": "Invalid login"}), 401
    except Exception as e:
        print(f"❌ Login Error: {str(e)}", flush=True)
        return jsonify({"message": f"Error: {str(e)}"}), 500

# ✅ GET ALL BOOKS
@app.route("/api/books", methods=["GET"])
def get_books():
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT id, title, author, price, category, description, cover_icon FROM books ORDER BY category, title")
        books = c.fetchall()
        conn.close()
        
        return jsonify({
            "books": [
                {
                    "id": book[0],
                    "title": book[1],
                    "author": book[2],
                    "price": book[3],
                    "category": book[4],
                    "description": book[5],
                    "icon": book[6]
                }
                for book in books
            ]
        }), 200
    except Exception as e:
        print(f"❌ Get Books Error: {str(e)}", flush=True)
        return jsonify({"message": f"Error: {str(e)}"}), 500

# ✅ PLACE ORDER
@app.route("/api/orders", methods=["POST"])
def place_order():
    try:
        data = request.get_json()
        username = data.get("username")
        items = data.get("items", [])  # List of {book_id, quantity}
        address = data.get("address")
        phone = data.get("phone")
        
        if not username or not items or not address or not phone:
            return jsonify({"message": "Missing required fields"}), 400
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # ✅ Calculate total price
        total_price = 0
        order_items = []
        
        for item in items:
            book_id = item.get("book_id")
            quantity = item.get("quantity", 1)
            
            c.execute("SELECT price FROM books WHERE id=?", (book_id,))
            book = c.fetchone()
            
            if not book:
                conn.close()
                return jsonify({"message": f"Book {book_id} not found"}), 404
            
            price = book[0]
            total_price += price * quantity
            order_items.append((book_id, quantity, price))
        
        # ✅ Create order
        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO orders (username, order_date, total_price, status, delivery_address, phone) VALUES (?, ?, ?, ?, ?, ?)",
            (username, order_date, total_price, "pending", address, phone)
        )
        order_id = c.lastrowid
        
        # ✅ Add order items
        for book_id, quantity, price in order_items:
            c.execute(
                "INSERT INTO order_items (order_id, book_id, quantity, price_at_purchase) VALUES (?, ?, ?, ?)",
                (order_id, book_id, quantity, price)
            )
        
        conn.commit()
        conn.close()
        
        print(f"✅ Order placed: ID={order_id}, User={username}, Total=₹{total_price}", flush=True)
        
        return jsonify({
            "message": "Order placed successfully",
            "order_id": order_id,
            "total_price": total_price
        }), 201
    except Exception as e:
        print(f"❌ Place Order Error: {str(e)}", flush=True)
        return jsonify({"message": f"Error: {str(e)}"}), 500

# ✅ GET USER ORDERS
@app.route("/api/orders/<username>", methods=["GET"])
def get_user_orders(username):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute(
            "SELECT id, order_date, total_price, status FROM orders WHERE username=? ORDER BY order_date DESC",
            (username,)
        )
        orders = c.fetchall()
        conn.close()
        
        return jsonify({
            "orders": [
                {
                    "id": order[0],
                    "date": order[1],
                    "total": order[2],
                    "status": order[3]
                }
                for order in orders
            ]
        }), 200
    except Exception as e:
        print(f"❌ Get Orders Error: {str(e)}", flush=True)
        return jsonify({"message": f"Error: {str(e)}"}), 500

# ✅ GET ORDER DETAILS
@app.route("/api/order-details/<int:order_id>", methods=["GET"])
def get_order_details(order_id):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get order info
        c.execute(
            "SELECT username, order_date, total_price, status, delivery_address, phone FROM orders WHERE id=?",
            (order_id,)
        )
        order = c.fetchone()
        
        if not order:
            conn.close()
            return jsonify({"message": "Order not found"}), 404
        
        # Get order items
        c.execute(
            """SELECT oi.book_id, b.title, b.author, oi.quantity, oi.price_at_purchase
               FROM order_items oi
               JOIN books b ON oi.book_id = b.id
               WHERE oi.order_id=?""",
            (order_id,)
        )
        items = c.fetchall()
        conn.close()
        
        return jsonify({
            "order_id": order_id,
            "username": order[0],
            "order_date": order[1],
            "total_price": order[2],
            "status": order[3],
            "delivery_address": order[4],
            "phone": order[5],
            "items": [
                {
                    "book_id": item[0],
                    "title": item[1],
                    "author": item[2],
                    "quantity": item[3],
                    "price": item[4],
                    "subtotal": item[3] * item[4]
                }
                for item in items
            ]
        }), 200
    except Exception as e:
        print(f"❌ Get Order Details Error: {str(e)}", flush=True)
        return jsonify({"message": f"Error: {str(e)}"}), 500

if __name__ == "__main__":
    logging.getLogger("werkzeug").disabled = True
    print("✅ Database initialized at:", db_path, flush=True)
    app.run(debug=True, host="127.0.0.1", port=5000)