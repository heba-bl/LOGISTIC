# Demonstration script

The point of the demo is to show one coherent chain: a truck arrives and, a few
minutes later, the parts have been consumed by production — with the stock, the
traceability, the analytics and the AI all reflecting each step.

**Duration:** 8–12 minutes.

---

## Before you start

```bash
# terminal 1
cd backend
python scripts/seed.py --reset      # clean, coherent dataset
uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
npm run dev
```

Open <http://localhost:5173>. In **Settings → Acting as**, pick *Amine Sahli
(Logistics Manager)*.

---

## Act 1 — The control room (2 min)

**Mission Control.**

- The six KPIs are computed live: total stock, active lots, pending inspections,
  open production requests, warehouse occupancy, critical alerts.
- The **Live Logistics Flow** shows the six stages with the lots actually sitting
  at each one. Click a lot chip → its complete history opens.
- **Smart Alerts** are derived from the real state: lots blocked in the Red Cage,
  a production request not covered by stock, an address filling up.
- **Recent Activity** is the audit trail, with the operator who did each action.

> Point out the system badge: it reads **Degraded** because critical alerts exist —
> it is not decorative, it is computed.

---

## Act 2 — The chain, step by step (4 min)

Still in Mission Control: **Run simulation**.

Set *Stop after* to run one step at a time and narrate:

| Step | What to say | Stock |
|------|-------------|-------|
| **Reception** | "The truck arrives. We check the quantity against the tolerance." | unchanged |
| **Inspection** | "Quality samples the lot — not every part." | unchanged |
| **Quality** | "The lot is approved. It still is not stock." | **unchanged** |
| **Storage** | "The warehouse confirms the address. *Now* stock increases." | **+** |
| **Request** | "Station 02 asks for parts." | unchanged |
| **Approval** | "The production manager validates. Quantity reserved." | unchanged |
| **Preparation** | "The warehouse picks the parts." | unchanged |
| **Issue** | "Physical issue confirmed. *Now* stock decreases." | **−** |

> The key line for the jury: **only steps 4 and 8 move the stock.** Everything
> else is workflow. The report shows the before/after balance for each step.

Run the full chain once to finish, then close the dialog — Mission Control has
already refreshed.

---

## Act 3 — Do it by hand (3 min)

Show that the simulation is not a special path: the same operations exist as real
screens.

1. **Receiving → New reception.** Choose a *large* part (CB-220) and enter a
   quantity 3 units below the expectation. The tolerance panel updates live and
   warns: *outside tolerance → Red Cage*. Confirm.
2. **Quality → Red Cage.** The lot is there, with the recorded reason. Try to
   store it — impossible. Release it with a justification.
3. **Warehouse.** The lot now appears under *Approved lots awaiting storage*.
   Click **Confirm storage**: the backend proposes the primary address, then
   secondary ones if needed. Confirm → stock increases, the map updates.
4. **Production → New request** → approve → prepare → mark ready → **confirm
   issue**. The toast shows the exact before/after balance.

---

## Act 3b — Excel import and double validation (3 min)

This is the answer to "the operators fill Excel files and nobody knows who did
what".

1. **Data Import → Import a file.** Pick *Receptions*, the operator
   **OP-1042 Karim Moreau (Receptionist)**, and download the **.xlsx template**
   if you want to show it. Upload a small file with 2 good rows and 1 bad one
   (an unknown part reference).
2. The batch lands as **PENDING_REVIEW**. Say the key line:
   > *"The file is in the system, but the data is not. No lot, no stock — it is
   > waiting for a responsible."*
   Show the row list: the bad line is flagged INVALID with the reason.
3. Click **Review**. Try to validate as **OP-1042** — the system refuses:
   *"OP-1042 entered this data and cannot validate it."*
4. Note the checker dropdown: **the maker is not in it**. Only the Reception
   Manager and the Logistics Manager are.
5. Validate as **RM-004 Fatima Chaoui (Reception Manager)** with a comment.
   The valid rows are applied and produce real receptions; the invalid one is not.
6. Go to **Traceability**: the audit trail now shows *who entered* (OP-1042) and
   *who validated* (RM-004), the decision, the file name and its SHA-256 hash.

> Optional, if the jury asks about separation of duties: the same rule applies to
> inspections — a Quality Inspector may enter one, but only a Quality Manager can
> validate it. Never their own.

---

## Act 4 — Traceability (1 min)

**Traceability.** Search the lot number. Its full history answers the ten
questions: who, what, when, how much, which lot, which reference, which location,
status before, status after, why — plus, for imported data, **who entered it and
who validated it**, with both matricules and the source file.

Then pick a reference in *Stock history*: every increment and decrement, with its
justification. This is the answer to "why is this stock dropping?".

---

## Act 5 — Analytics and Power BI (1 min)

**Analytics.**

- Conformity rate, service rate, Red Cage count, pending requests.
- Stock by category / reference / address, and the signed daily evolution.
- **Lead time per stage** with the bottleneck highlighted.
- Defects by reference and by supplier.

Click **Power BI datasets**: six flat tables and five ready-made DAX measures,
with the endpoint to paste into Power BI Desktop. The application does not depend
on Power BI being connected.

---

## Act 6 — Decision support (2 min)

**AI Assistant.**

- The headline states the situation in one sentence.
- Each recommendation carries a **WHY** block with the actual figures, a concrete
  recommended action, and the metrics behind it. Priority 1 = production at risk,
  2 = lot blocked too long, 3 = saturation and optimisation.
- Shortage risk per reference: stock, confirmed demand, days of cover, and what is
  already received but not yet stock.

Then use the **Logistics Copilot**:

- *"What are today's priorities?"*
- *"Which lots are blocked?"*
- *"Why is BR-145 stock decreasing?"*
- *"Which racks are nearly full?"*

Every answer is computed from the database and shows its sources. Ask something
out of scope to show it declines rather than inventing an answer.

---

## Closing line

> Nothing on these screens is hardcoded. The tolerance is a setting, the stock is a
> ledger, the alerts are computed, the recommendations are explained, and every
> action is traceable to an operator.
