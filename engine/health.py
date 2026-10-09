"""
Player Health Hub -- paid medical treatment, applied by auto_resolve.py.

Owners spend team cash (starting budget + revenue, the same pool trade
cash comes from) to speed up an injured player's return or to lift a
healthy player's condition for the NEXT round. Spending reduces cash on
the Budget Dashboard only; it never touches the Revenue component of the
Season Scorecard, which counts revenue earned, not cash left (instructor's
call, 2026-10-08).

Rules (instructor-approved 2026-10-08):
  - opens for Round START_ROUND onward
  - at most MAX_PER_ROUND treatments per team per round, one per player
  - a treatment always targets the next unplayed round (current_round + 1)
  - rehab is for injured players only, recovery/fitness for healthy ones

Effects feed the rest of the engine through two existing seams, so every
page that shows condition (Dashboard report, roster tab, scouting) and
resolve_round.py itself pick them up with no extra wiring:
  - rehab rewrites data/player_injuries.json (injured_until_round)
  - recovery/fitness and the elite clinic's "back at Average" write
    per-round boosts into data/health_treatments.json, which
    player_condition.conditions_for_round() reads.

The Sheet row is the request; this module is the authority. Anything
that fails a check here (cash, roster, injury status, a round already
played) is recorded as voided with a reason, never silently dropped.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE, "data", "health_treatments.json")

START_ROUND = 3
MAX_PER_ROUND = 4

# prices halved (instructor, 2026-10-09)
CATALOG = {
    "rehab_standard":    {"label": "Standard Rehab", "cost": 75_000, "kind": "injury", "rounds": 1,
                          "effect": "Returns 1 round sooner"},
    "rehab_accelerated": {"label": "Accelerated Rehab", "cost": 200_000, "kind": "injury", "rounds": 2,
                          "effect": "Returns 2 rounds sooner"},
    "rehab_elite":       {"label": "Elite Specialist Clinic", "cost": 375_000, "kind": "injury", "rounds": None,
                          "effect": "Fit for next round, at Average condition"},
    "recovery":          {"label": "Recovery Session", "cost": 50_000, "kind": "form", "levels": 1,
                          "effect": "+1 condition level next round"},
    "sports_science":    {"label": "Sports-Science Package", "cost": 125_000, "kind": "form", "levels": 2,
                          "effect": "+2 condition levels next round (max Excellent)"},
}


def load():
    if os.path.exists(PATH):
        with open(PATH) as f:
            return json.load(f)
    return {"applied": [], "voided": [], "team_spend": {}, "boosts": {}}


def save(state):
    with open(PATH, "w") as f:
        json.dump(state, f, indent=1)


def boosts_for_round(round_num, state=None):
    """{player_id: {"levels": n} | {"set": tier_label}} for one round."""
    state = state if state is not None else load()
    return state.get("boosts", {}).get(str(round_num), {})


def team_spend(team_id, state=None):
    state = state if state is not None else load()
    return state.get("team_spend", {}).get(str(team_id), 0)


def request_id(row):
    return f"{row.get('team_id')}|{row.get('round')}|{row.get('player_id')}|{row.get('submitted_at')}"


def apply_requests(rows, config, players, injuries, cash_before_medical):
    """rows: HealthTreatments rows from the admin export.
    players: list of player dicts (player_id, name, team_id as strings).
    injuries: {player_id: injured_until_round}, mutated in place.
    cash_before_medical(team_id) -> cash on hand ignoring medical spend (starting
      budget + revenue + trade cash); medical spend so far is subtracted here.
    Returns (state, actions). Caller saves injuries; this saves its own state."""
    state = load()
    seen = {r["id"] for r in state["applied"]} | {r["id"] for r in state["voided"]}
    next_round = config.get("current_round", 0) + 1
    by_id = {str(p["player_id"]): p for p in players}
    actions = []

    for row in sorted(rows, key=lambda r: str(r.get("submitted_at", ""))):
        rid = request_id(row)
        if rid in seen:
            continue
        tid = str(row.get("team_id"))
        pid = str(row.get("player_id"))
        try:
            rnd = int(row.get("round"))
        except (TypeError, ValueError):
            rnd = -1
        if rnd > next_round:
            continue  # submitted early for a later round -- leave it until that round is next

        rec = {"id": rid, "team_id": tid, "round": rnd, "player_id": pid,
               "player_name": by_id.get(pid, {}).get("name", row.get("player_name", "")),
               "treatment": row.get("treatment"), "submitted_at": row.get("submitted_at")}

        def void(reason):
            rec["void_reason"] = reason
            state["voided"].append(rec)
            seen.add(rid)
            actions.append(f"health: voided team {tid} {rec['player_name']} ({reason})")

        t = CATALOG.get(row.get("treatment"))
        if t is None:
            void("unknown treatment"); continue
        if rnd < next_round:
            void(f"Round {rnd} was already played before this was processed"); continue
        if rnd < START_ROUND:
            void(f"the Health Hub opens for Round {START_ROUND}"); continue
        p = by_id.get(pid)
        if p is None or str(p.get("team_id")) != tid:
            void("player is not on this team's roster"); continue
        same_round = [a for a in state["applied"] if a["team_id"] == tid and a["round"] == rnd]
        if len(same_round) >= MAX_PER_ROUND:
            void(f"team already used {MAX_PER_ROUND} treatments this round"); continue
        if any(a["player_id"] == pid for a in same_round):
            void("this player already has a treatment this round"); continue
        injured = injuries.get(pid) is not None and injuries[pid] >= rnd
        if t["kind"] == "injury" and not injured:
            void("rehab is only for players injured for the coming round"); continue
        if t["kind"] == "form" and injured:
            void("injured players need rehab, not a recovery treatment"); continue
        if cash_before_medical(tid) - state.get("team_spend", {}).get(tid, 0) < t["cost"]:
            void("not enough cash on hand"); continue

        boosts = state.setdefault("boosts", {}).setdefault(str(rnd), {})
        if t["kind"] == "injury":
            before = injuries[pid]
            if t["rounds"] is None:
                injuries[pid] = rnd - 1
                boosts[pid] = {"set": "Average"}
            else:
                injuries[pid] = before - t["rounds"]
            rec["injured_until_before"] = before
            rec["injured_until_after"] = injuries[pid]
        else:
            boosts[pid] = {"levels": t["levels"]}
        rec["cost"] = t["cost"]
        state["applied"].append(rec)
        state.setdefault("team_spend", {})[tid] = state["team_spend"].get(tid, 0) + t["cost"]
        seen.add(rid)
        actions.append(f"health: team {tid} {t['label']} for {rec['player_name']} (Round {rnd}, ${t['cost']:,})")

    save(state)
    return state, actions
