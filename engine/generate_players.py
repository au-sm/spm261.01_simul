"""
Generates the player pool for the SPM Owner-League soccer simulation.

Run once at the start of the season to create data/players.csv.
Re-running overwrites the pool with a new random draw (same PLAYER_POOL
config) -- don't re-run mid-season or you'll wipe drafted rosters' stat
history along with everyone else's.

N_TEAMS and ROSTER_SIZE are read from THIS FOLDER's data/league_config.json
(n_teams / roster_size) -- so a section's own player pool always matches
its own team count. Only FA_BUFFER below is a fixed constant.
"""
import csv
import json
import os
import random

random.seed(42)  # reproducible pool -- same players every run unless config changes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(BASE, "data", "league_config.json")) as _f:
    _config = json.load(_f)
N_TEAMS = _config["n_teams"]
ROSTER_SIZE = _config["roster_size"]
FA_BUFFER = 40

# position group -> squad slots per team (GK/DF/MF/FW), used to size the pool
SLOTS_PER_TEAM = {"GK": 2, "DF": 6, "MF": 6, "FW": 4}

FIRST_NAMES = [
    "Marco","Kwame","Diego","Yusuf","Lars","Tomas","Kenji","Andre","Milan","Sami",
    "Pavel","Idris","Bruno","Nico","Felix","Amara","Rafael","Jonas","Tariq","Leon",
    "Mateo","Igor","Sven","Cesar","Rui","Hassan","Emil","Dario","Kofi","Ivan",
    "Omar","Stefan","Luca","Adrian","Kai","Enzo","Youssef","Radek","Nikolai","Tobias",
]
LAST_NAMES = [
    "Reyes","Osei","Nowak","Barros","Keller","Novak","Sato","Silva","Petrov","Haddad",
    "Kovac","Diallo","Costa","Ferreira","Weber","Suarez","Almeida","Larsson","Malik","Bauer",
    "Fischer","Ivanov","Duarte","Mensah","Rossi","Berg","Krause","Toure","Vidal","Horvat",
    "Adeyemi","Lindqvist","Moreno","Sokol","Adamu","Braga","Neumann","Kucera","Santos","Wallin",
]

POSITIONS = ["GK", "DF", "MF", "FW"]

# rough per-position skew: which of ATT/DEF matters more, before noise
POSITION_BIAS = {
    "GK": {"att": (30, 45), "def": (55, 80)},
    "DF": {"att": (35, 60), "def": (60, 88)},
    "MF": {"att": (50, 78), "def": (45, 75)},
    "FW": {"att": (60, 90), "def": (25, 50)},
}


def clamp(v, lo=40, hi=99):
    return max(lo, min(hi, v))


def gen_player(pid, position, used_names):
    while True:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used_names:
            used_names.add(name)
            break

    att_lo, att_hi = POSITION_BIAS[position]["att"]
    def_lo, def_hi = POSITION_BIAS[position]["def"]
    att = random.randint(att_lo, att_hi)
    de = random.randint(def_lo, def_hi)
    pace = clamp(random.randint(45, 95))
    phy = clamp(random.randint(45, 92))
    ovr = clamp(round(att * 0.32 + de * 0.32 + pace * 0.18 + phy * 0.18))

    # Star power is a SEPARATE axis from skill on purpose -- a flashy, marketable
    # player is not always your best player, and vice versa. That gap is the
    # point: it forces the classic "win now" vs. "sell jerseys" tradeoff.
    star_base = random.randint(30, 90)
    # slight pull toward OVR so it's not pure noise, but keep real spread
    star = clamp(round(star_base * 0.7 + ovr * 0.3), 30, 99)

    age = random.randint(19, 34)
    # salary scales with OVR and star power, plus noise -- lets a savvy owner
    # find undervalued OVR-for-salary players, which is the point of a draft.
    base_salary = (ovr * 8 + star * 5) * 1000
    noise = random.uniform(0.85, 1.2)
    salary = round(base_salary * noise / 1000) * 1000

    return {
        "player_id": pid,
        "name": name,
        "position": position,
        "age": age,
        "att": att,
        "def": de,
        "pace": pace,
        "phy": phy,
        "ovr": ovr,
        "star_power": star,
        "salary": salary,
        "team_id": "",  # blank until drafted
    }


def main():
    pool_needed = {
        pos: SLOTS_PER_TEAM[pos] * N_TEAMS for pos in POSITIONS
    }
    # add free-agent buffer proportionally to slot distribution
    total_slots = sum(SLOTS_PER_TEAM.values())
    for pos in POSITIONS:
        pool_needed[pos] += round(FA_BUFFER * SLOTS_PER_TEAM[pos] / total_slots)

    used_names = set()
    players = []
    pid = 1
    for pos in POSITIONS:
        for _ in range(pool_needed[pos]):
            players.append(gen_player(pid, pos, used_names))
            pid += 1

    random.shuffle(players)
    for i, p in enumerate(players, start=1):
        p["player_id"] = i

    out_path = os.path.join(BASE, "data", "players.csv")
    fieldnames = ["player_id","name","position","age","att","def","pace","phy","ovr","star_power","salary","team_id"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(players)

    print(f"Generated {len(players)} players -> {out_path}")
    print(f"  by position: { {pos: pool_needed[pos] for pos in POSITIONS} }")
    print(f"  draft pool: {N_TEAMS} teams x {ROSTER_SIZE} = {N_TEAMS*ROSTER_SIZE}; free agents left over: {len(players) - N_TEAMS*ROSTER_SIZE}")


if __name__ == "__main__":
    main()
