
import os
import json
import sqlite3
from collections import Counter

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "basketiq.db"
)


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                items TEXT NOT NULL
            )
        """)


def parse_items(value):
    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    return []


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, items FROM transactions ORDER BY id DESC"
        ).fetchall()

    return jsonify([
        {"id": row["id"], "items": parse_items(row["items"])}
        for row in rows
    ])


@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    data = request.get_json(silent=True) or {}
    items = parse_items(data.get("items", []))

    items = [
        str(item).strip()
        for item in items
        if str(item).strip()
    ]

    if not items:
        return jsonify({"error": "Enter at least one product."}), 400

    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (items) VALUES (?)",
            (json.dumps(items),)
        )
        transaction_id = cursor.lastrowid

    return jsonify({
        "message": "Transaction saved successfully!",
        "id": transaction_id,
        "items": items
    }), 201


@app.route("/api/transactions", methods=["DELETE"])
def delete_transactions():
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions")

    return jsonify({"message": "All transactions cleared."})


@app.route("/api/sample-data", methods=["POST"])
def sample_data():
    samples = [
        ["Bread", "Milk"],
        ["Bread", "Diaper", "Beer", "Eggs"],
        ["Milk", "Diaper", "Beer", "Cola"],
        ["Bread", "Milk", "Diaper", "Beer"],
        ["Bread", "Milk", "Diaper", "Cola"]
    ]

    with get_connection() as conn:
        conn.execute("DELETE FROM transactions")
        conn.executemany(
            "INSERT INTO transactions (items) VALUES (?)",
            [(json.dumps(items),) for items in samples]
        )

    return jsonify({"message": "Sample data loaded successfully!"})


@app.route("/api/frequent-items", methods=["GET"])
def frequent_items():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT items FROM transactions"
        ).fetchall()

    counts = Counter()
    total_transactions = len(rows)

    for row in rows:
        # Count each product once per transaction.
        items = set(parse_items(row["items"]))
        counts.update(items)

    results = [
        {
            "item": item,
            "count": count,
            "percentage": round(
                count / total_transactions * 100, 1
            ) if total_transactions else 0
        }
        for item, count in counts.most_common()
    ]

    return jsonify({
        "total_transactions": total_transactions,
        "items": results
    })


initialize_db()


if __name__ == "__main__":
    app.run(debug=True)
