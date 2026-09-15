import json

INCOME = "Income / Salary"
FIXED_COMMITMENTS = "Fixed Commitments"
DEBIT_ORDER = "Debit Order"
TRANSFERS = "Transfers"
THRESHOLDS = [50, 75, 90, 95]
MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def load_transactions(path):
    with open(path, "r") as file:
        data = json.load(file)
    transactions = []
    for line in data["statementLines"]:
        transaction = {
            "posting_date": line["postingDate"][:10],
            "amount": float(line["amount"]["amount"]),
            "category": line["transactionCategory"]["transactionCategoryName"],
            "narrative": line["narrative"],
            "running_balance": float(line["runningBalance"]["amount"]),
        }
        transactions.append(transaction)
    return transactions


def calculate_budget(transactions):
    salary = 0.0
    commitments = 0.0
    for transaction in transactions:
        if transaction["category"] == INCOME:
            salary += transaction["amount"]
        elif transaction["category"] == FIXED_COMMITMENTS or transaction["category"] == DEBIT_ORDER:
            commitments += transaction["amount"]
    # commitments are stored as negative amounts, so adding them to salary is the same as subtracting them from it
    total_commitments = -commitments
    budget = salary + commitments
    return salary, total_commitments, budget


def counts_as_spending(transaction):
    # commitments are already removed from the budget up front, so they
    # must not be counted again as the month's spending drains the budget
    if transaction["category"] in (INCOME, FIXED_COMMITMENTS, DEBIT_ORDER):
        return False
    # a transfer to the customer's own savings is not money leaving them
    if transaction["category"] == TRANSFERS and "SAVINGS" in transaction["narrative"]:
        return False
    return True


def commitments_still_due(transactions, date):
    total = 0.0
    posted = 0.0
    for transaction in transactions:
        if transaction["category"] in (FIXED_COMMITMENTS, DEBIT_ORDER):
            total += transaction["amount"]
            if transaction["posting_date"] <= date:
                posted += transaction["amount"]
    return posted - total


def format_rand(amount):
    # South African rand amounts use a space as the thousands separator
    return f"R{amount:,.2f}".replace(",", " ")


def build_notification_message(level, amount_left, commitments_due):
    if level == 50:
        return f"You have used half your spending money. {format_rand(amount_left)} left until payday."
    if level == 75:
        if commitments_due == 0:
            return f"{format_rand(amount_left)} left. All your commitments for this month are already paid."
        return f"{format_rand(amount_left)} left. {format_rand(commitments_due)} is still due for commitments before your next salary."
    if level == 90:
        return f"{format_rand(amount_left)} left. At this rate you will run out before payday."
    if level == 95:
        return f"{format_rand(amount_left)} left. Here is a free affordability check to see what you can safely afford."


def run_month(transactions):
    salary, total_commitments, budget = calculate_budget(transactions)

    print(f"Salary: R{salary:.2f}")
    print(f"Commitments: R{total_commitments:.2f}")
    print(f"Budget: R{budget:.2f}")
    print("")

    sent = {}
    for threshold in THRESHOLDS:
        sent[threshold] = False

    running_total = 0.0
    notifications_sent = 0
    last_notification_date = None
    last_notification_amount_left = None
    first_negative_date = None
    notifications = []
    percent_used = 0.0

    for transaction in transactions:
        if counts_as_spending(transaction):
            running_total += -transaction["amount"]

        percent_used = running_total / budget * 100

        date = transaction["posting_date"]
        narrative = transaction["narrative"]
        amount = transaction["amount"]
        print(f"{date}  {narrative:<40}  {amount:>10.2f}  {percent_used:5.1f}%")

        if transaction["running_balance"] < 0 and first_negative_date is None:
            first_negative_date = date

        newly_crossed = []
        for threshold in THRESHOLDS:
            if percent_used >= threshold and not sent[threshold]:
                newly_crossed.append(threshold)

        if len(newly_crossed) > 0:
            highest = max(newly_crossed)
            amount_left = budget - running_total
            commitments_due = commitments_still_due(transactions, date)
            message = build_notification_message(highest, amount_left, commitments_due)
            print(f"    >> {message}")
            notifications.append({"date": date, "level": highest, "message": message})

            for threshold in newly_crossed:
                sent[threshold] = True

            notifications_sent += 1
            last_notification_date = date
            last_notification_amount_left = amount_left

    print("")
    print(f"Notifications sent: {notifications_sent}")
    if last_notification_date is not None:
        print(f"Last notification: {last_notification_date} - R{last_notification_amount_left:.2f} left")
    else:
        print("Last notification: none")
    if first_negative_date is not None:
        print(f"Balance first went negative on: {first_negative_date}")
    else:
        print("Balance first went negative on: never")

    return {
        "salary": salary,
        "total_commitments": total_commitments,
        "budget": budget,
        "final_percent_used": percent_used,
        "spent_so_far": running_total,
        "notifications": notifications,
        "first_negative_date": first_negative_date,
    }


def format_date_long(date_string):
    _, month, day = date_string.split("-")
    return f"{int(day)} {MONTH_NAMES[month]}"


def format_month_year(date_string):
    year, month, day = date_string.split("-")
    return f"{MONTH_NAMES[month]} {year}"


def progress_bar_colour(percent_used):
    # traffic-light colours so the customer can tell their spending pace at a glance
    if percent_used < 75:
        return "#0A33B0"
    if percent_used < 90:
        return "#D9822B"
    return "#D0021B"


def notification_title(level):
    if level == 50:
        return "Halfway through your budget"
    if level == 75:
        return "Most of your budget used"
    if level == 90:
        return "Budget running low"
    return "Budget almost gone"


def notification_badge_colour(level):
    if level == 50:
        return "#0A33B0"
    if level == 75:
        return "#D9822B"
    if level == 90:
        return "#E67E22"
    return "#D0021B"


def find_overdraw_fee(transactions):
    # the notice fee is a real posted transaction, not a typed-in figure
    for transaction in transactions:
        if "OVERDRAWN" in transaction["narrative"]:
            return transaction
    return None


def write_html(transactions, results):
    month_label = format_month_year(transactions[0]["posting_date"])
    spendable = results["budget"]
    left_to_spend = results["budget"] - results["spent_so_far"]
    percent_used = results["final_percent_used"]
    bar_width = percent_used
    if bar_width > 100:
        bar_width = 100
    bar_colour = progress_bar_colour(percent_used)

    # only the two most recent notifications show by default, matching the app's
    # "recent transactions" pattern with a show all link to reveal the rest
    visible_count = 2
    notification_rows = ""
    for index, notification in enumerate(results["notifications"]):
        badge_colour = notification_badge_colour(notification["level"])
        row_class = "row" if index < visible_count else "row hidden-row"
        notification_rows += f"""
        <div class="{row_class}">
            <div class="row-left">
                <p class="row-date">{format_date_long(notification["date"])}</p>
                <p class="row-title">{notification_title(notification["level"])}</p>
                <p class="row-message">{notification["message"]}</p>
            </div>
            <span class="row-amount" style="color: {badge_colour};">{notification["level"]}%</span>
        </div>"""

    show_all_link = ""
    if len(results["notifications"]) > visible_count:
        show_all_link = """
        <a class="show-all" id="your-month-show-all" onclick="showAllRows('your-month'); return false;" href="#">Show all</a>"""

    overdraw_section = ""
    overdraw_fee = find_overdraw_fee(transactions)
    if results["first_negative_date"] is not None and overdraw_fee is not None:
        overdraw_date = format_date_long(results["first_negative_date"])
        fee_amount = format_rand(-overdraw_fee["amount"])
        overdraw_section = f"""
        <div class="list-section" id="impact">
            <p class="section-heading">What actually happened</p>
            <div class="row">
                <div class="row-left">
                    <p class="row-date">{overdraw_date}</p>
                    <p class="row-title">Account overdrawn</p>
                    <p class="row-description">Low-balance notice fee charged</p>
                </div>
                <span class="row-amount amount-negative">-{fee_amount}</span>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Safe to Spend</title>
<style>
    * {{
        box-sizing: border-box;
    }}
    body {{
        margin: 0;
        background: #E2E5EA;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
        display: flex;
        justify-content: center;
        padding: 40px 16px;
    }}
    .phone {{
        width: 390px;
        max-width: 100%;
        height: 844px;
        max-height: 92vh;
        background: #FFFFFF;
        border-radius: 40px;
        overflow: hidden;
        box-shadow: 0 30px 60px rgba(10, 20, 40, 0.35);
        display: flex;
        flex-direction: column;
    }}
    .phone-chrome {{
        background: #0A33B0;
        flex-shrink: 0;
    }}
    .status-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 26px 2px 26px;
        color: #FFFFFF;
        font-size: 14px;
        font-weight: 600;
    }}
    .status-icons {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .signal-dots {{
        display: flex;
        align-items: flex-end;
        gap: 2px;
    }}
    .signal-dots span {{
        width: 3px;
        background: #FFFFFF;
        border-radius: 1px;
        display: block;
    }}
    .signal-dots span:nth-child(1) {{ height: 4px; }}
    .signal-dots span:nth-child(2) {{ height: 6px; }}
    .signal-dots span:nth-child(3) {{ height: 8px; }}
    .signal-dots span:nth-child(4) {{ height: 10px; }}
    .status-network {{
        font-size: 11px;
        font-weight: 700;
    }}
    .battery {{
        width: 22px;
        height: 11px;
        border: 1px solid #FFFFFF;
        border-radius: 3px;
        padding: 1px;
        position: relative;
    }}
    .battery::after {{
        content: '';
        position: absolute;
        right: -4px;
        top: 3px;
        width: 2px;
        height: 5px;
        background: #FFFFFF;
        border-radius: 0 2px 2px 0;
    }}
    .battery-fill {{
        display: block;
        height: 100%;
        width: 75%;
        background: #FFFFFF;
        border-radius: 1px;
    }}
    .hero {{
        padding: 6px 20px 0 20px;
    }}
    .hero-top {{
        display: flex;
        align-items: center;
        gap: 14px;
    }}
    .back-arrow {{
        font-size: 20px;
        color: #FFFFFF;
        line-height: 1;
    }}
    .hero-title {{
        margin: 0;
        font-size: 20px;
        font-weight: 700;
        color: #FFFFFF;
    }}
    .hero-subtitle {{
        margin: 2px 0 0 0;
        font-size: 13px;
        color: #C7D2F0;
    }}
    .tabs {{
        display: flex;
        gap: 28px;
        margin-top: 20px;
    }}
    .tab {{
        padding-bottom: 12px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.3px;
        color: rgba(255, 255, 255, 0.55);
        border-bottom: 2px solid transparent;
    }}
    .tab-active {{
        color: #FFFFFF;
        border-bottom-color: #FFFFFF;
    }}
    .content {{
        flex: 1;
        overflow-y: auto;
        background: #FFFFFF;
        -webkit-overflow-scrolling: touch;
    }}
    .balance-section {{
        text-align: center;
        padding: 26px 20px 22px 20px;
        border-bottom: 1px solid #EDEEF2;
    }}
    .avatar {{
        width: 52px;
        height: 52px;
        border-radius: 15px;
        background: linear-gradient(135deg, #2154E8, #0A1F80);
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 14px auto;
    }}
    .balance-label {{
        margin: 0;
        font-size: 13px;
        color: #8A93A6;
    }}
    .balance-amount {{
        margin: 4px 0 0 0;
        font-size: 34px;
        font-weight: 700;
        color: #10182B;
    }}
    .balance-amount-secondary {{
        margin: 4px 0 0 0;
        font-size: 19px;
        font-weight: 700;
        color: #10182B;
    }}
    .secondary-label {{
        margin: 16px 0 0 0;
        font-size: 12px;
        color: #8A93A6;
    }}
    .button-row {{
        display: flex;
        justify-content: center;
        gap: 12px;
        margin-top: 20px;
    }}
    .pill-btn {{
        display: inline-flex;
        align-items: center;
        padding: 9px 22px;
        border: 1.5px solid #0A33B0;
        border-radius: 999px;
        color: #0A33B0;
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        text-decoration: none;
    }}
    .progress-wrap {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 22px;
    }}
    .progress-track {{
        flex: 1;
        background: #EDEEF2;
        border-radius: 8px;
        height: 10px;
        overflow: hidden;
    }}
    .progress-fill {{
        height: 100%;
        border-radius: 8px;
    }}
    .progress-percent {{
        font-size: 13px;
        font-weight: 700;
        color: #10182B;
        white-space: nowrap;
    }}
    .list-section {{
        padding: 20px;
    }}
    .section-divider {{
        height: 8px;
        background: #F5F6F8;
    }}
    .section-heading {{
        margin: 0 0 4px 0;
        font-size: 17px;
        font-weight: 700;
        color: #10182B;
    }}
    .row {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
        padding: 14px 0;
        border-top: 1px solid #EDEEF2;
    }}
    .row:first-of-type {{
        border-top: none;
        padding-top: 10px;
    }}
    .hidden-row {{
        display: none;
    }}
    .row-left {{
        min-width: 0;
    }}
    .row-date {{
        margin: 0;
        font-size: 12px;
        color: #8A93A6;
    }}
    .row-title {{
        margin: 2px 0 0 0;
        font-size: 15px;
        font-weight: 700;
        color: #10182B;
    }}
    .row-description {{
        margin: 2px 0 0 0;
        font-size: 11px;
        letter-spacing: 0.2px;
        text-transform: uppercase;
        color: #8A93A6;
    }}
    .row-message {{
        margin: 4px 0 0 0;
        font-size: 13px;
        color: #4B5563;
        line-height: 1.4;
    }}
    .row-amount {{
        flex-shrink: 0;
        font-size: 15px;
        font-weight: 700;
        text-align: right;
        white-space: nowrap;
    }}
    .amount-negative {{
        color: #D0021B;
    }}
    .show-all {{
        display: block;
        text-align: right;
        margin-top: 8px;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        color: #0A33B0;
        text-decoration: none;
    }}
    .bottom-nav {{
        flex-shrink: 0;
        display: flex;
        justify-content: space-around;
        align-items: center;
        padding: 10px 0 16px 0;
        border-top: 1px solid #EDEEF2;
        background: #FFFFFF;
    }}
    .nav-item {{
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        font-size: 10px;
        font-weight: 600;
        color: #8A93A6;
    }}
    .nav-item.active {{
        color: #0A33B0;
    }}
</style>
</head>
<body>
    <div class="phone">
        <div class="phone-chrome">
            <div class="status-bar">
                <span class="status-time">9:41</span>
                <div class="status-icons">
                    <span class="signal-dots"><span></span><span></span><span></span><span></span></span>
                    <span class="status-network">5G</span>
                    <span class="battery"><span class="battery-fill"></span></span>
                </div>
            </div>
            <div class="hero">
                <div class="hero-top">
                    <span class="back-arrow">&larr;</span>
                    <div>
                        <p class="hero-title">Safe to Spend</p>
                        <p class="hero-subtitle">Everyday Account &middot; {month_label}</p>
                    </div>
                </div>
                <div class="tabs">
                    <span class="tab tab-active">OVERVIEW</span>
                    <span class="tab">ALERTS</span>
                    <span class="tab">IMPACT</span>
                </div>
            </div>
        </div>

        <div class="content">
            <div class="balance-section">
                <div class="avatar">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="3" y="6" width="18" height="13" rx="2" stroke="#FFFFFF" stroke-width="1.6"/>
                        <path d="M3 9.5H21" stroke="#FFFFFF" stroke-width="1.6"/>
                        <circle cx="16.5" cy="14.5" r="1.3" fill="#FFFFFF"/>
                    </svg>
                </div>
                <p class="balance-label">Spendable this month</p>
                <p class="balance-amount">{format_rand(spendable)}</p>
                <p class="secondary-label">Spent so far</p>
                <p class="balance-amount-secondary">{format_rand(results["spent_so_far"])}</p>
                <p class="secondary-label">Left to spend</p>
                <p class="balance-amount-secondary{' amount-negative' if left_to_spend < 0 else ''}">{format_rand(left_to_spend)}</p>
                <div class="button-row">
                    <a class="pill-btn" href="#your-month">Alerts</a>
                    <a class="pill-btn" href="#impact">Impact</a>
                </div>
                <div class="progress-wrap">
                    <div class="progress-track">
                        <div class="progress-fill" style="width: {bar_width}%; background: {bar_colour};"></div>
                    </div>
                    <span class="progress-percent">{percent_used:.1f}%</span>
                </div>
            </div>

            <div class="list-section" id="your-month">
                <p class="section-heading">Your month</p>
                {notification_rows}
                {show_all_link}
            </div>
            <div class="section-divider"></div>
            {overdraw_section}
        </div>

        <div class="bottom-nav">
            <div class="nav-item active">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 11.5L12 5l8 6.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M6 10v8a1 1 0 0 0 1 1h3v-5h4v5h3a1 1 0 0 0 1-1v-8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>Home</span>
            </div>
            <div class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="3" y="6" width="18" height="13" rx="2" stroke="currentColor" stroke-width="1.6"/>
                    <path d="M3 10h18" stroke="currentColor" stroke-width="1.6"/>
                    <circle cx="17" cy="14.5" r="1.2" fill="currentColor"/>
                </svg>
                <span>Accounts</span>
            </div>
            <div class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 8h13m0 0l-3-3m3 3l-3 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M20 16H7m0 0l3-3m-3 3l3 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>Transact</span>
            </div>
            <div class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M3 4h2l2.4 12.2a1 1 0 0 0 1 .8h9a1 1 0 0 0 1-.8L20 8H6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="9.5" cy="20" r="1.1" fill="currentColor"/>
                    <circle cx="17.5" cy="20" r="1.1" fill="currentColor"/>
                </svg>
                <span>Buy</span>
            </div>
            <div class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                </svg>
                <span>More</span>
            </div>
        </div>
    </div>
    <script>
        function showAllRows(sectionId) {{
            var section = document.getElementById(sectionId);
            var hiddenRows = section.querySelectorAll('.hidden-row');
            for (var i = 0; i < hiddenRows.length; i++) {{
                hiddenRows[i].classList.remove('hidden-row');
            }}
            var link = document.getElementById(sectionId + '-show-all');
            if (link) {{
                link.style.display = 'none';
            }}
        }}
    </script>
</body>
</html>
"""

    with open("index.html", "w") as file:
        file.write(html)


if __name__ == "__main__":
    transactions = load_transactions("transactions.json")
    results = run_month(transactions)
    write_html(transactions, results)
