STAGE 0 — FRESHNESS CHECK
Role: Triage pipeline data. No search. Deterministic logic only.
Today's date → compute ages.

Two books share this pipeline (`config/settings.py` = Core/Core-Plus, `config/settings_satellite.py` = Satellite). Run this check against **both**.

Inputs (paste below):

* DATA_FRESHNESS dict — from `config/settings.py`
* DATA_FRESHNESS dict — from `config/settings_satellite.py`
* MACRO_REGIME dict — from `config/settings.py`
* MACRO_REGIME dict — from `config/settings_satellite.py`
* Last run log timestamp (optional, per book — `run_core_*.log` / `run_satellite_*.log`)

Logic:

* Fresh: age ≤ cadence → ✅
* Due: 0.8*cadence < age ≤ cadence → ⚠️
* Stale: age > cadence → 🚨
* inflections: future=🟢, overdue=🔴, resolved=⚪.
* **Desync check**: the two MACRO_REGIME dicts are supposed to be identical (CLAUDE.md's Manual Update Checklist requires updating both together every cycle). If any field differs between them → 🚨 DESYNC, regardless of either dict's own age. This is a distinct failure mode from staleness — one copy can be "fresh" by date and still wrong if the other was updated and this one wasn't.

Outputs (strict, keep <40 lines total):

1. Table: Item | Book | Age(days) | Cadence | Status (✅⚠️🚨) | Action (file + var to update)
2. Desync check result: ✅ in sync / 🚨 DESYNC (list the differing fields).
3. Inflection statuses (list with 🟢🔴⚪) — evaluate once; both books share the same macro read.
4. Verdict (choose one):
   * GREEN → skip to Stage 1.
   * YELLOW → run Stage 1, then Stage 2.
   * RED → update pipeline data first (stale item or desync found).
5. Carry‑forward block (bullet list of 🔴 entries + any desync) for Stage 1's "OPEN QUESTIONS". If none: `[None — Stage 1 starts clean]`.

Constraints:

* No portfolio/regime calls. Stage 1/2 handle those.
* No web search.
* This stage never edits files — it only decides what Stage 1/2 must refresh, and whether both books' copies already agree.
