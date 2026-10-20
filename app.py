
import os
import json
import sqlite3
from collections import Counter

from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

# Database path
DATABASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "basketiq.db"
)


# ---------------- DATABASE ----------------

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


# ---------------- HELPER FUNCTION ----------------

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


# ---------------- HOMEPAGE ----------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------- TRANSACTIONS ----------------

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, items
            FROM transactions
            ORDER BY id DESC
        """).fetchall()

    return jsonify([
        {
            "id": row["id"],
            "items": parse_items(row["items"])
        }
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
        return jsonify({
            "error": "Enter at least one product."
        }), 400

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

    return jsonify({
        "message": "All transactions cleared."
    })


# ---------------- SAMPLE DATA ----------------

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
            [
                (json.dumps(items),)
                for items in samples
            ]
        )

    return jsonify({
        "message": "Sample data loaded successfully!"
    })


# ---------------- FREQUENTLY BOUGHT ITEMS ----------------

@app.route("/api/frequent-items", methods=["GET"])
def frequent_items():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT items FROM transactions"
        ).fetchall()

    counts = Counter()
    total_transactions = len(rows)

    for row in rows:
        # Count each product only once per transaction.
        items = set(parse_items(row["items"]))
        counts.update(items)

    results = [
        {
            "item": item,
            "count": count,
            "percentage": round(
                (count / total_transactions) * 100, 1
            ) if total_transactions else 0
        }
        for item, count in counts.most_common()
    ]

    return jsonify({
        "total_transactions": total_transactions,
        "items": results
    })


# ---------------- APRIORI ANALYSIS ----------------

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}

    try:
        min_support = float(data.get("min_support", 0.2))
        min_confidence = float(data.get("min_confidence", 0.5))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Support and confidence must be numbers."
        }), 400

    if not 0 < min_support <= 1:
        return jsonify({
            "error": "Minimum support must be greater than 0 and at most 1."
        }), 400

    if not 0 < min_confidence <= 1:
        return jsonify({
            "error": "Minimum confidence must be greater than 0 and at most 1."
        }), 400

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT items FROM transactions"
        ).fetchall()

    transactions = [
        set(parse_items(row["items"]))
        for row in rows
    ]

    total = len(transactions)

    if total == 0:
        return jsonify({
            "error": "Add transactions before running analysis."
        }), 400

    # Count individual items.
    item_counts = Counter()

    for transaction in transactions:
        item_counts.update(transaction)

    frequent = {
        frozenset([item]): count / total
        for item, count in item_counts.items()
        if count / total >= min_support
    }

    all_frequent = dict(frequent)
    k = 2

    # Generate larger frequent itemsets.
    while True:
        previous = [
            itemset
            for itemset in frequent
            if len(itemset) == k - 1
        ]

        if not previous:
            break

        candidates = set()

        for i in range(len(previous)):
            for j in range(i + 1, len(previous)):
                candidate = previous[i] | previous[j]

                if len(candidate) == k:
                    candidates.add(candidate)

        next_frequent = {}

        for candidate in candidates:
            count = sum(
                1
                for transaction in transactions
                if candidate.issubset(transaction)
            )

            support = count / total

            if support >= min_support:
                next_frequent[candidate] = support

        if not next_frequent:
            break

        all_frequent.update(next_frequent)
        frequent = next_frequent
        k += 1

    # Generate association rules.
    rules = []

    for itemset, support in all_frequent.items():
        if len(itemset) < 2:
            continue

        items = list(itemset)

        # Generate every non-empty proper antecedent.
        from itertools import combinations

        for size in range(1, len(items)):
            for combination in combinations(items, size):
                antecedent = frozenset(combination)
                consequent = itemset - antecedent

                antecedent_support = all_frequent.get(antecedent)

                if not antecedent_support:
                    continue

                confidence = support / antecedent_support

                if confidence >= min_confidence:
                    consequent_support = all_frequent.get(consequent)

                    lift = (
                        support / (antecedent_support * consequent_support)
                        if consequent_support
                        else 0
                    )

                    rules.append({
                        "antecedent": sorted(antecedent),
                        "consequent": sorted(consequent),
                        "support": round(support, 4),
                        "confidence": round(confidence, 4),
                        "lift": round(lift, 4)
                    })

    rules.sort(
        key=lambda rule: (
            rule["confidence"],
            rule["lift"]
        ),
        reverse=True
    )

    return jsonify({
        "total_transactions": total,
        "frequent_itemsets": [
            {
                "items": sorted(itemset),
                "support": round(support, 4)
            }
            for itemset, support in sorted(
                all_frequent.items(),
                key=lambda pair: (
                    len(pair[0]),
                    sorted(pair[0])
                )
            )
        ],
        "rules": rules
    })


# ---------------- STARTUP ----------------

initialize_db()


if __name__ == "__main__":
    app.run(debug=True)
