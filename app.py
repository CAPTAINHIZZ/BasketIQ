
from flask import Flask, render_template, request, jsonify
import sqlite3
from itertools import combinations

app = Flask(__name__)

import os

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basketiq.db")


# Initialize database
def initialize_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                items TEXT NOT NULL
            )
        """)


# Get transactions from database
def get_transactions():
    with sqlite3.connect(DATABASE) as conn:
        rows = conn.execute(
            "SELECT items FROM transactions"
        ).fetchall()

    return [
        set(item.strip() for item in row[0].split(",") if item.strip())
        for row in rows
    ]


# Apriori algorithm
def apriori(transactions, min_support, min_confidence):
    total = len(transactions)

    if total == 0:
        return []

    # Count individual items
    item_counts = {}

    for transaction in transactions:
        for item in transaction:
            itemset = frozenset([item])
            item_counts[itemset] = item_counts.get(itemset, 0) + 1

    # Find frequent single items
    frequent = {
        itemset: count / total
        for itemset, count in item_counts.items()
        if count / total >= min_support
    }

    all_frequent = dict(frequent)
    k = 2

    # Find frequent item combinations
    while True:
        items = sorted({
            item
            for itemset in frequent
            for item in itemset
        })

        candidates = [
            frozenset(combo)
            for combo in combinations(items, k)
        ]

        new_frequent = {}

        for candidate in candidates:
            count = sum(
                candidate.issubset(transaction)
                for transaction in transactions
            )

            support = count / total

            if support >= min_support:
                new_frequent[candidate] = support

        if not new_frequent:
            break

        all_frequent.update(new_frequent)
        frequent = new_frequent
        k += 1

    # Generate association rules
    rules = []

    for itemset, support in all_frequent.items():
        if len(itemset) < 2:
            continue

        items = list(itemset)

        for size in range(1, len(items)):
            for combo in combinations(items, size):
                antecedent = frozenset(combo)
                consequent = itemset - antecedent

                antecedent_support = all_frequent.get(
                    antecedent, 0
                )
                consequent_support = all_frequent.get(
                    consequent, 0
                )

                if antecedent_support == 0 or consequent_support == 0:
                    continue

                confidence = support / antecedent_support

                if confidence >= min_confidence:
                    lift = confidence / consequent_support

                    rules.append({
                        "antecedent": sorted(antecedent),
                        "consequent": sorted(consequent),
                        "support": round(support, 3),
                        "confidence": round(confidence, 3),
                        "lift": round(lift, 3)
                    })

    rules.sort(
        key=lambda rule: (
            rule["confidence"],
            rule["lift"]
        ),
        reverse=True
    )

    return rules


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# Display transactions
@app.route("/api/transactions", methods=["GET"])
def list_transactions():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT id, items FROM transactions ORDER BY id DESC"
        ).fetchall()

    return jsonify([dict(row) for row in rows])


# Add a transaction
@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])

    if not isinstance(items, list):
        return jsonify({
            "error": "Items must be a list."
        }), 400

    cleaned_items = list(dict.fromkeys(
        str(item).strip()
        for item in items
        if str(item).strip()
    ))

    if not cleaned_items:
        return jsonify({
            "error": "Enter at least one product."
        }), 400

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (items) VALUES (?)",
            (",".join(cleaned_items),)
        )

        transaction_id = cursor.lastrowid

    return jsonify({
        "message": "Transaction added successfully.",
        "id": transaction_id,
        "items": cleaned_items
    }), 201


# Delete all transactions
@app.route("/api/transactions", methods=["DELETE"])
def delete_transactions():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("DELETE FROM transactions")

    return jsonify({
        "message": "All transactions cleared."
    })


# Add sample transactions
@app.route("/api/sample-data", methods=["POST"])
def add_sample_data():
    samples = [
        ["Milk", "Bread", "Butter"],
        ["Bread", "Butter"],
        ["Milk", "Bread"],
        ["Milk", "Bread", "Butter", "Eggs"],
        ["Bread", "Eggs"],
        ["Milk", "Butter"],
        ["Milk", "Bread", "Eggs"],
        ["Bread", "Butter", "Eggs"]
    ]

    with sqlite3.connect(DATABASE) as conn:
        conn.executemany(
            "INSERT INTO transactions (items) VALUES (?)",
            [(",".join(items),) for items in samples]
        )

    return jsonify({
        "message": "Sample transactions added successfully.",
        "count": len(samples)
    })


# Run Apriori analysis
@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}

    try:
        min_support = float(
            data.get("min_support", 0.25)
        )
        min_confidence = float(
            data.get("min_confidence", 0.50)
        )
    except (TypeError, ValueError):
        return jsonify({
            "error": "Support and confidence must be numbers."
        }), 400

    if not (
        0 < min_support <= 1
        and 0 < min_confidence <= 1
    ):
        return jsonify({
            "error": "Support and confidence must be between 0 and 1."
        }), 400

    transactions = get_transactions()

    rules = apriori(
        transactions,
        min_support,
        min_confidence
    )

    return jsonify({
        "transaction_count": len(transactions),
        "rules": rules
    })


# Start application
initialize_db()

if __name__ == "__main__":
    app.run(debug=True)
