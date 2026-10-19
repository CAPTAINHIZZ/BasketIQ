
const $ = (id) => document.getElementById(id);

let toastTimer;

function showToast(message) {
    const toast = $("toast");
    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Something went wrong.");
    }

    return data;
}

function setMessage(message) {
    $("analysisMessage").querySelector("p").textContent = message;
}

async function refreshDashboard() {
    try {
        const transactions = await api("/api/transactions");

        $("totalTransactions").textContent = transactions.length;

        const products = new Set();
        transactions.forEach(transaction => {
            transaction.items.forEach(item => products.add(item));
        });

        $("uniqueProducts").textContent = products.size;

        const list = $("transactionList");
        list.replaceChildren();

        if (transactions.length === 0) {
            const empty = document.createElement("p");
            empty.className = "empty-state";
            empty.textContent = "No transactions yet. Add one above!";
            list.appendChild(empty);
        } else {
            transactions.slice(0, 8).forEach(transaction => {
                const card = document.createElement("div");
                card.className = "transaction-item";

                const info = document.createElement("div");
                info.className = "transaction-info";

                const id = document.createElement("div");
                id.className = "transaction-id";
                id.textContent = `TRANSACTION #${transaction.id}`;

                const tags = document.createElement("div");
                tags.className = "product-tags";

                transaction.items.forEach(item => {
                    const tag = document.createElement("span");
                    tag.className = "product-tag";
                    tag.textContent = item;
                    tags.appendChild(tag);
                });

                info.append(id, tags);
                card.appendChild(info);
                list.appendChild(card);
            });
        }
    } catch (error) {
        showToast(error.message);
    }
}

$("transactionForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const input = $("itemsInput");
    const items = input.value
        .split(",")
        .map(item => item.trim())
        .filter(Boolean);

    if (items.length === 0) {
        showToast("Enter at least one product.");
        return;
    }

    try {
        await api("/api/transactions", {
            method: "POST",
            body: JSON.stringify({ items })
        });

        input.value = "";
        showToast("Transaction saved successfully!");
        await refreshDashboard();
        $("totalRules").textContent = "0";
        $("rulesContainer").innerHTML = "";
        setMessage("Transaction data updated. Run the analysis again.");
    } catch (error) {
        showToast(error.message);
    }
});

async function loadSampleData() {
    try {
        const result = await api("/api/sample-data", {
            method: "POST",
            body: JSON.stringify({})
        });

        showToast(result.message);
        await refreshDashboard();
        $("totalRules").textContent = "0";
        $("rulesContainer").innerHTML = "";
        setMessage("Sample data loaded. Run Apriori analysis to find rules.");
    } catch (error) {
        showToast(error.message);
    }
}

async function clearTransactions() {
    const confirmed = confirm(
        "Are you sure you want to delete all saved transactions?"
    );

    if (!confirmed) return;

    try {
        const result = await api("/api/transactions", {
            method: "DELETE"
        });

        showToast(result.message);
        await refreshDashboard();
        $("totalRules").textContent = "0";
        $("rulesContainer").innerHTML = "";
        setMessage("All transactions cleared. Add data to begin again.");
    } catch (error) {
        showToast(error.message);
    }
}

async function runAnalysis() {
    const support = Number($("supportInput").value);
    const confidence = Number($("confidenceInput").value);

    if (support < 1 || support > 100 ||
        confidence < 1 || confidence > 100) {
        showToast("Support and confidence must be between 1 and 100.");
        return;
    }

    const button = document.querySelector(".analyze-btn");
    button.disabled = true;
    button.textContent = "Analyzing...";

    try {
        const result = await api("/api/analyze", {
            method: "POST",
            body: JSON.stringify({
                min_support: support / 100,
                min_confidence: confidence / 100
            })
        });

        $("totalRules").textContent = result.rules.length;
        renderRules(result.rules);

        setMessage(
            `Analysis complete: ${result.transaction_count} transactions examined.`
        );

        showToast(`Found ${result.rules.length} association rules!`);
    } catch (error) {
        showToast(error.message);
        setMessage(error.message);
    } finally {
        button.disabled = false;
        button.textContent = "✦ Run Apriori Analysis";
    }
}

function renderRules(rules) {
    const container = $("rulesContainer");
    container.replaceChildren();

    if (rules.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-analysis";

        const title = document.createElement("h4");
        title.textContent = "No rules found";

        const message = document.createElement("p");
        message.textContent =
            "Try lowering minimum support or confidence.";

        empty.append(title, message);
        container.appendChild(empty);
        return;
    }

    rules.forEach(rule => {
        const card = document.createElement("div");
        card.className = "rule-card";

        const equation = document.createElement("div");
        equation.className = "rule-equation";

        const left = document.createElement("span");
        left.textContent = rule.antecedent.join(", ");

        const arrow = document.createElement("span");
        arrow.className = "rule-arrow";
        arrow.textContent = "→";

        const right = document.createElement("span");
        right.textContent = rule.consequent.join(", ");

        equation.append(left, arrow, right);

        const metrics = document.createElement("div");
        metrics.className = "rule-metrics";

        [
            ["Support", `${(rule.support * 100).toFixed(1)}%`],
            ["Confidence", `${(rule.confidence * 100).toFixed(1)}%`],
            ["Lift", rule.lift.toFixed(2)]
        ].forEach(([label, value]) => {
            const metric = document.createElement("div");
            metric.className = "metric";

            const strong = document.createElement("strong");
            strong.textContent = value;

            const caption = document.createElement("span");
            caption.textContent = label;

            metric.append(strong, caption);
            metrics.appendChild(metric);
        });

        card.append(equation, metrics);
        container.appendChild(card);
    });
}

refreshDashboard();
