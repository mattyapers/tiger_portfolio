STAGE 0 — FRESHNESS CHECK
Role: Triage pipeline data. No search. Deterministic logic only.
Today's date → compute ages.
Inputs (paste below):

* DATA_FRESHNESS dict
* MACRO_REGIME dict
* Last run log timestamp (optional)

Logic:

* Fresh: age ≤ cadence → ✅
* Due: 0.8*cadence < age ≤ cadence → ⚠️
* Stale: age > cadence → 🚨
* inflections: future=🟢, overdue=🔴, resolved=⚪.

Outputs (strict, keep <30 lines total):

1. Table: Item | Age(days) | Cadence | Status (✅⚠️🚨) | Action (file + var to update)
2. Inflection statuses (list with 🟢🔴⚪).
3. Verdict (choose one):
   * GREEN → skip to Stage 1.
   * YELLOW → run Stage 1, then Stage 2.
   * RED → update pipeline data first.
4. Carry‑forward block (bullet list of 🔴 entries) for Stage 1's "OPEN QUESTIONS". If none: `[None — Stage 1 starts clean]`.

Constraints:

* No portfolio/regime calls. Stage 1/2 handle those.
* No web search.
