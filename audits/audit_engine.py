from statements.models import Transaction, Statement
from django.db.models import Max, Min, Sum


MIN_SUBSCRIPTION_DURATION_DAYS = 60
MIN_ANOMALY_SAMPLE_SIZE = 10
ANOMALY_STD_MULTIPLIER = 2


def get_audit_context(statement_id):
    """
    Build audit context metadata for a statement.

    This function gathers high-level information about the uploaded statement,
    such as total transaction count and statement duration.

    Purpose:
    - Helps detectors decide whether enough data exists
    - Subscription detection uses duration_days
    - AI audit can use context for confidence-aware reasoning

    Returns:
    dict containing:
    - transaction_count
    - start_date
    - end_date
    - duration_days
    """
    transactions = Transaction.objects.filter(statement_id=statement_id)
    transaction_count = transactions.count()

    date_info = transactions.aggregate(
        start_date=Min("date"),
        end_date=Max("date")
    )

    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    if start_date and end_date:
        duration_days = (end_date - start_date).days + 1
    else:
        duration_days = 0

    return {
        "transaction_count": transaction_count,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
        "duration_days": duration_days,
    }


def calculate_cashflow(statement_id):
    """
    Calculate core cashflow metrics.

    Computes:
    - total_credit
    - total_debit
    - net_savings
    - savings_rate
    """
    total_credit = Transaction.objects.filter(
        statement_id=statement_id,
        transaction_type="credit"
    ).aggregate(total=Sum("amount"))["total"] or 0

    total_debit = Transaction.objects.filter(
        statement_id=statement_id,
        transaction_type="debit"
    ).aggregate(total=Sum("amount"))["total"] or 0

    net_savings = total_credit - total_debit

    if total_credit > 0:
        savings_rate = (net_savings / total_credit) * 100
    else:
        savings_rate = 0

    return {
        "total_credit": float(total_credit),
        "total_debit": float(total_debit),
        "net_savings": float(net_savings),
        "savings_rate": round(float(savings_rate), 2),
    }


def calculate_category_breakdown(statement_id):
    """
    Calculate spending distribution by category.

    Groups debit transactions by category and sums transaction amounts.

    Example output:
    {
        "Food": 3200,
        "Shopping": 8700
    }
    """
    category_data = (
        Transaction.objects.filter(
            statement_id=statement_id,
            transaction_type="debit"
        )
        .values("category")
        .annotate(total=Sum("amount"))
    )

    breakdown = {}

    for item in category_data:
        category = item["category"] or "Uncategorized"
        breakdown[category] = float(item["total"])

    return breakdown


def detect_duplicates(statement_id):
    """
    Detect possible duplicate charges.

    A transaction is flagged as a possible duplicate if:
    - transaction_type is debit
    - same date
    - same vendor
    - same amount

    Important:
    This detects suspicious repeated charges,
    not confirmed fraud.

    Purpose:
    Helps identify accidental double charges or suspicious billing.
    """
    transactions = Transaction.objects.filter(
        statement_id=statement_id,
        transaction_type="debit"
    )

    groups = {}

    for tx in transactions:
        normalized_vendor = tx.vendor.lower().strip()
        key = (tx.date, normalized_vendor, tx.amount)

        if key in groups:
            groups[key].append(tx)
        else:
            groups[key] = [tx]

    duplicates = []

    for group in groups.values():
        if len(group) > 1:
            group_data = []

            for tx in group:
                group_data.append({
                    "date": str(tx.date),
                    "vendor": tx.vendor,
                    "amount": float(tx.amount),
                    "category": tx.category,
                    "raw_description": tx.raw_description,
                })

            duplicates.append(group_data)

    return duplicates


def detect_subscriptions(statement_id, context):
    """
    Detect recurring subscription-like payments.

    Conditions:
    - Statement duration must be at least 60 days
    - Same vendor
    - Same amount
    - Appears in at least 2 unique months

    Example:
    Netflix ₹499 in Jan and Feb -> likely subscription

    Purpose:
    Identifies recurring monthly expenses such as
    streaming, SaaS, or membership payments.
    """
    if context["duration_days"] < MIN_SUBSCRIPTION_DURATION_DAYS:
        return []

    transactions = Transaction.objects.filter(
        statement_id=statement_id,
        transaction_type="debit"
    )

    groups = {}

    for tx in transactions:
        normalized_vendor = tx.vendor.lower().strip()
        key = (normalized_vendor, tx.amount)

        if key in groups:
            groups[key].append(tx)
        else:
            groups[key] = [tx]

    subscriptions = []

    for group in groups.values():
        if len(group) >= 2:
            unique_months = set()

            for tx in group:
                unique_months.add((tx.date.year, tx.date.month))

            if len(unique_months) >= 2:
                sample = group[0]

                subscriptions.append({
                    "vendor": sample.vendor,
                    "amount": float(sample.amount),
                    "occurrences": len(group),
                    "months_detected": len(unique_months),
                    "category": sample.category
                })

    return subscriptions


def detect_anomalies(statement_id):
    """
    Detect unusually high spending transactions.

    Uses statistical anomaly detection:
        threshold = mean + (2 * standard deviation)

    A transaction is flagged if:
        amount > threshold

    Notes:
    - Only debit transactions are analyzed
    - Detects unusual spending, not fraud

    Purpose:
    Highlights large transactions that may need attention.
    """
    transactions = list(
        Transaction.objects.filter(
            statement_id=statement_id,
            transaction_type="debit"
        )
    )

    if len(transactions) < MIN_ANOMALY_SAMPLE_SIZE:
        return []

    amounts = [float(tx.amount) for tx in transactions]

    if not amounts:
        return []

    mean = sum(amounts) / len(amounts)

    variance = sum((x - mean) ** 2 for x in amounts) / len(amounts)

    std_dev = variance ** 0.5

    threshold = mean + (ANOMALY_STD_MULTIPLIER * std_dev)

    anomalies = []

    for tx in transactions:
        if float(tx.amount) > threshold:
            anomalies.append({
                "date": str(tx.date),
                "vendor": tx.vendor,
                "amount": float(tx.amount),
                "category": tx.category,
                "threshold": round(threshold, 2)
            })

    return anomalies


def run_audit(statement_id):
    """
    Main Layer A audit orchestrator.

    Runs all feature extraction modules:
    - audit context
    - cashflow analysis
    - spending analysis
    - risk detectors

    Combines all outputs into a structured audit JSON.

    Purpose:
    Produces deterministic financial intelligence for Layer B (Gemini).
    """
    context = get_audit_context(statement_id)

    cashflow = calculate_cashflow(statement_id)

    spending = {
        "category_breakdown": calculate_category_breakdown(statement_id)
    }

    risks = {
        "duplicates": detect_duplicates(statement_id),
        "subscriptions": detect_subscriptions(statement_id, context),
        "anomalies": detect_anomalies(statement_id)
    }

    audit_result = {
        "audit_context": context,
        "cashflow": cashflow,
        "spending": spending,
        "risks": risks
    }

    statement = Statement.objects.get(id=statement_id)
    statement.audit_result = audit_result
    statement.audit_status = True
    statement.save()

    return audit_result