# Safe to Spend

An affordability check that runs before the money is gone.


## The problem

The bank checks every transaction to see whether it is really the customer.
It never checks whether the customer can survive it.

In the month provided, a R2 500 card payment cleared at 03:12 on 29 August and
took the account from R381 to minus R2 119. The bank's own system had already
classified that payment as uncategorised and unusual. It classified it, let it
through, and charged a R60 notice fee the following morning.

Nothing warned the customer at any point.

## What it does

Works out how much of the salary is genuinely free to spend once commitments
are set aside, then replays the month and reports where the customer would
have been warned.

For August 2026:

| | |
|---|---|
| Salary | R48 200.00 |
| Fixed commitments and debit orders | R18 298.00 |
| **Spendable** | **R29 902.00** |

Notifications fire at 50, 75, 90 and 95 percent of spendable, once each per
salary cycle:

| Date | Level | Left |
|---|---|---|
| 12 August | 50% | R14 615.01 |
| 20 August | 75% | R6 421.81 |
| 26 August | 90% | R2 904.16 |
| 28 August | 95% | R620.86 |

The account went overdrawn on 29 August, one day after the final notification,
while the balance was still R496 in credit.

## Running it

```
python3 safe_to_spend.py
```

One import from the Python standard library (`json`). No external
dependencies. It prints the month to the console and writes `index.html`, a
phone-styled view of the same results.

`index.html` is generated output but is committed so the page can be served
directly. Re-running the script overwrites it.

## The rules

**Budget.** Salary minus all fixed commitments and debit orders due in the
cycle. Fixed at the start, resets on the next salary deposit.

**Counts as spending.** Card purchases, groceries, transport, subscriptions,
online purchases, discretionary spending, cash withdrawals, transfers to other
people, bank fees. Refunds and reversals reduce it.

**Does not count.** Commitments, because they were already removed when the
budget was set. Transfers to the customer's own savings, because that money is
still theirs.

**It warns, it never blocks.** The customer's money is theirs to spend. The
bank's job is to make sure the decision is informed, not to make it for them.

## Assumptions

- **Cash counts as spent.** Once it is cash the bank cannot see what happens to
  it, and treating it as available would tell the customer they have money they
  have probably already used. A deliberate, conservative choice.
- **Savings transfers are identified by the word "savings" in the narrative.**
  This is fragile. A production system would check whether the destination
  account belongs to the same customer, which the bank already knows. That
  field is not in the supplied data.
- **The overdraft notice fee is found by matching "OVERDRAWN" in the
  narrative.** Same limitation. In production the fee would carry its own
  transaction code.
- **No arranged overdraft facility is assumed.** The data does not say either
  way.
- Dates are compared as text. The ISO format sorts correctly, so no date
  parsing is required.

## Data validation

Opening balance plus the sum of all 59 transactions equals the closing balance
exactly:

```
R1 875.40 + (-R4 146.14) = -R2 270.74
```

This was checked before any logic was built on the figures.

## What changed for the change request

At 95 percent the customer is offered a **free affordability check** rather
than a credit card or a limit increase.

The National Credit Act 34 of 2005 requires an affordability assessment before
credit is granted, and granting it without one is reckless lending, where a
court can suspend the agreement and the lender can lose the right to recover.
Offering credit at the exact moment someone has nearly run out of money is
offering it when affordability is least established.

Refusing outright is not right either. Running low is sometimes a real and
temporary need. So the answer is timing and consent: the assessment at the
moment of stress, the product afterwards, once affordability is established.

The bank already extended this customer credit at 3am, at penalty rates, with
no assessment at all. This makes that lending deliberate and checked rather
than accidental.

## What was deliberately deferred

- Customer-set thresholds. Fixed levels prove the mechanism.
- Learning each customer's own spending pattern. Needs more than one month.
- Multiple accounts. The brief specified one customer.
- Real delivery by push or SMS. The logic is the part being assessed.
- A production interface. The generated page shows the screens it would
  produce.

All four notification levels were delivered, including the commitments detail
at 75 percent.

## Use of AI

I designed the solution myself: the problem, the budget rule, the spending
classification, the thresholds and what happens at each one. I wrote the
specification, including the function names and signatures, before any code
existed.

I then used Claude Code to write the Python from that specification, and to
help with loading the bank's statement directly from its original JSON file,
and with the styling of the generated page.

I verified the output against figures I had calculated independently from the
data. That caught something the generated code got wrong: a notification that
read "R0.00 is still due for commitments" because every commitment in this
month debits in the first six days. 

I also rejected an earlier Java version. It had more structure than the problem
needed, and simplicity mattered more to me than showing off a class hierarchy I
would then have to justify.

I also used AI to create this README as it can format it to my liking very easily

## Files

| File | |
|---|---|
| `safe_to_spend.py` | The whole program |
| `transactions.json` | The bank's statement data in its original JSON format |
| `index.html` | Generated output, committed so it can be served |
