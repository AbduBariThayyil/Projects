#!/usr/bin/env python3
"""
Pokémon Quetzal Complete Database Extractor
Dumps ROM data directly into an offline SQLite database:
- 1,499 Pokémon (All 9 Gens + Megas + Forms) with Base Stats, Types, Catch Rates
- 986 Moves with Power, Accuracy, Types, PP
- Full Level-Up Learnsets for every species
- Full Evolution trees with exact stone/level/trade parameters
- 938 Items
- All Wild Encounters across HOENN, KANTO, SEVII ISLANDS
- All 104 Legendary & Mythical locations & requirements
"""

import os
import sys
import struct
import sqlite3
import re

ROM_PATH = "/home/vibecoder/Games/Console Games/GBA/Moemon Quetzal.gba"
DB_PATH = "/home/vibecoder/Projects/quetzal_database.db"

with open(ROM_PATH, "rb") as f:
    rom = f.read()

# Character map
CHARMAP = {}
for i in range(26): CHARMAP[0xBB + i] = chr(ord("A") + i)
for i in range(26): CHARMAP[0xD5 + i] = chr(ord("a") + i)
for i in range(10): CHARMAP[0xA1 + i] = str(i)
CHARMAP[0x00] = " "
CHARMAP[0xAC] = "?"
CHARMAP[0xAD] = "."
CHARMAP[0xAE] = "-"
CHARMAP[0xB4] = "'"
CHARMAP[0xB5] = "♀"
CHARMAP[0xB6] = "♂"
CHARMAP[0xB7] = "'"
CHARMAP[0xB8] = ","
CHARMAP[0xBA] = "-"
CHARMAP[0x1B] = "é"
CHARMAP[0xF0] = ":"
CHARMAP[0xFF] = ""

TYPE_NAMES = [
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost",
    "Steel", "Mystery", "Fire", "Water", "Grass", "Electric", "Psychic", "Ice",
    "Dragon", "Dark", "Fairy", "Stellar"
]

EVO_METHODS = {
    1: "High Friendship",
    2: "Friendship (Day)",
    3: "Friendship (Night)",
    4: "Level {param}",
    5: "Trade",
    6: "Trade holding {item}",
    7: "Use {item}",
    8: "Level Up (Atk > Def)",
    9: "Level Up (Atk = Def)",
    10: "Level Up (Atk < Def)",
    11: "Level Up (Personality A)",
    12: "Level Up (Personality B)",
    13: "Level Up (Create Ninjask)",
    14: "Level Up (Create Shedinja)",
    15: "High Beauty",
    16: "Level Up (Hold Item, Day)",
    17: "Level Up (Hold Item, Night)",
    18: "Level Up (Knowing Move)",
    19: "Level Up (With Pokémon in Party)",
    20: "Level Up (Male)",
    21: "Level Up (Female)",
    22: "Level Up (Specific Location)",
    23: "Use {item}",
    24: "Level Up (Rain)",
    25: "Level Up (Affection + Fairy Move)",
}

def decode_gen3(data):
    res = []
    for b in data:
        if b == 0xFF: break
        res.append(CHARMAP.get(b, chr(b) if 32 <= b < 127 else ""))
    return "".join(res).strip()

def get_species_name(species_id):
    if species_id == 0 or species_id > 2000: return "None"
    off = 0x516b48 + species_id * 13
    if off + 13 > len(rom): return f"Species_{species_id}"
    raw = rom[off:off+13]
    name = decode_gen3(raw)
    return name if name else f"Species_{species_id}"

def get_move_name(move_id):
    if move_id == 0 or move_id > 1500: return "None"
    off = 0x5206a3 + (move_id - 1) * 17
    if off + 17 > len(rom): return f"Move_{move_id}"
    raw = rom[off:off+17]
    name = decode_gen3(raw)
    return name if name else f"Move_{move_id}"

def get_item_name(item_id):
    if item_id == 0 or item_id > 1500: return "None"
    off = 0x11eece8 + item_id * 20
    if off + 20 > len(rom): return f"Item_{item_id}"
    raw = rom[off:off+20]
    name = decode_gen3(raw)
    return name if name else f"Item_{item_id}"

def ptr_to_off(p):
    if p == 0: return None
    if 0x08000000 <= p < 0x08000000 + len(rom):
        return p - 0x08000000
    if 0x09000000 <= p < 0x09000000 + len(rom):
        return p - 0x09000000
    return None

def get_mapsec_name(mapsec_id):
    if mapsec_id >= 213: return f"MAPSEC_{mapsec_id}"
    ptr = struct.unpack_from("<I", rom, 0x1232a04 + mapsec_id * 8)[0]
    p_off = ptr - 0x08000000
    if 0 <= p_off < len(rom):
        str_ptr = struct.unpack_from("<I", rom, p_off)[0]
        str_off = str_ptr - 0x08000000
        if 0 <= str_off < len(rom):
            return decode_gen3(rom[str_off:str_off+30])
    return f"MAPSEC_{mapsec_id}"

def get_map_info(grp, num):
    try:
        grp_ptr = struct.unpack_from("<I", rom, 0x93adcc + grp * 4)[0]
        grp_off = grp_ptr - 0x08000000
        hdr_ptr = struct.unpack_from("<I", rom, grp_off + num * 4)[0]
        hdr_off = hdr_ptr - 0x08000000
        mapsec = rom[hdr_off + 0x14]
        layout_id = struct.unpack_from("<H", rom, hdr_off + 0x12)[0]
        return get_mapsec_name(mapsec), mapsec, layout_id
    except Exception:
        return f"Group_{grp}_Map_{num}", 0, 0

def main():
    print(f"Connecting to SQLite: {DB_PATH}")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE pokemon (
        id INTEGER PRIMARY KEY,
        name TEXT,
        hp INTEGER,
        atk INTEGER,
        def INTEGER,
        spa INTEGER,
        spd INTEGER,
        spe INTEGER,
        bst INTEGER,
        type1 TEXT,
        type2 TEXT,
        catch_rate INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE moves (
        id INTEGER PRIMARY KEY,
        name TEXT,
        power INTEGER,
        type TEXT,
        accuracy INTEGER,
        pp INTEGER,
        effect INTEGER,
        priority INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE learnsets (
        pokemon_id INTEGER,
        pokemon_name TEXT,
        level INTEGER,
        move_id INTEGER,
        move_name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE evolutions (
        pokemon_id INTEGER,
        pokemon_name TEXT,
        target_id INTEGER,
        target_name TEXT,
        method_desc TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE items (
        id INTEGER PRIMARY KEY,
        name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE encounters (
        region TEXT,
        map_group INTEGER,
        map_num INTEGER,
        location_name TEXT,
        method TEXT,
        slot INTEGER,
        chance INTEGER,
        min_level INTEGER,
        max_level INTEGER,
        species_id INTEGER,
        species_name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE legendaries (
        name TEXT PRIMARY KEY,
        generation TEXT,
        location TEXT,
        requirements TEXT,
        notes TEXT
    )
    """)

    print("Extracting 1,499 Pokémon species and base stats...")
    pokemon_records = []
    for i in range(1, 1500):
        name = get_species_name(i)
        stat_off = 0x550a34 + i * 36
        if stat_off + 36 <= len(rom):
            hp, atk, df, spe, spa, spd = struct.unpack_from("<6B", rom, stat_off)
            t1, t2 = rom[stat_off + 6], rom[stat_off + 7]
            catch_rate = rom[stat_off + 8]
            type1 = TYPE_NAMES[t1] if t1 < len(TYPE_NAMES) else f"Type_{t1}"
            type2 = TYPE_NAMES[t2] if t2 < len(TYPE_NAMES) else f"Type_{t2}"
            bst = hp + atk + df + spa + spd + spe
            pokemon_records.append((i, name, hp, atk, df, spa, spd, spe, bst, type1, type2, catch_rate))
    cur.executemany("INSERT INTO pokemon VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", pokemon_records)

    print("Extracting 986 moves...")
    move_records = []
    for m in range(1, 987):
        m_name = get_move_name(m)
        m_off = 0x542b65 + m * 24
        if m_off + 24 <= len(rom):
            eff, pwr, typ, acc, pp, _, _, pri = struct.unpack_from("<8B", rom, m_off)
            pri = struct.unpack_from("<b", rom, m_off + 7)[0]
            t_name = TYPE_NAMES[typ] if typ < len(TYPE_NAMES) else f"Type_{typ}"
            move_records.append((m, m_name, pwr, t_name, acc, pp, eff, pri))
    cur.executemany("INSERT INTO moves VALUES (?,?,?,?,?,?,?,?)", move_records)

    print("Extracting level-up learnsets...")
    learn_records = []
    for spec_id in range(1, 1500):
        spec_name = get_species_name(spec_id)
        ptr = struct.unpack_from("<I", rom, 0x5bc3b4 + spec_id * 4)[0]
        off = ptr_to_off(ptr)
        if off:
            while off + 4 <= len(rom):
                val = struct.unpack_from("<H", rom, off)[0]
                if val == 0xFFFF: break
                move = val
                level = struct.unpack_from("<H", rom, off + 2)[0]
                m_name = get_move_name(move)
                learn_records.append((spec_id, spec_name, level, move, m_name))
                off += 4
    cur.executemany("INSERT INTO learnsets VALUES (?,?,?,?,?)", learn_records)

    print("Extracting evolutions...")
    evo_records = []
    for spec_id in range(1, 1500):
        spec_name = get_species_name(spec_id)
        for slot in range(11):
            off = 0x59b61c + spec_id * 88 + slot * 8
            meth, param, target, _ = struct.unpack_from("<4H", rom, off)
            if meth != 0 and target != 0:
                target_name = get_species_name(target)
                tmpl = EVO_METHODS.get(meth, f"Method {meth}")
                if "{item}" in tmpl:
                    desc = tmpl.format(item=get_item_name(param))
                elif "{param}" in tmpl:
                    desc = tmpl.format(param=param)
                else:
                    desc = tmpl
                evo_records.append((spec_id, spec_name, target, target_name, desc))
    cur.executemany("INSERT INTO evolutions VALUES (?,?,?,?,?)", evo_records)

    print("Extracting 938 items...")
    item_records = []
    for it in range(1, 939):
        it_name = get_item_name(it)
        item_records.append((it, it_name))
    cur.executemany("INSERT INTO items VALUES (?,?)", item_records)

    print("Extracting wild encounters across all regions (Hoenn, Kanto, Sevii)...")
    enc_records = []

    GRASS_CHANCES = [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
    WATER_CHANCES = [60, 30, 5, 4, 1]
    SMASH_CHANCES = [60, 30, 5, 4, 1]
    FISH_CHANCES = {
        "Old Rod": [70, 30],
        "Good Rod": [60, 20, 20],
        "Super Rod": [40, 40, 15, 4, 1]
    }

    def parse_slots(info_ptr, count):
        if info_ptr == 0: return []
        off = ptr_to_off(info_ptr)
        if off is None: return []
        m_ptr = struct.unpack_from("<I", rom, off + 4)[0]
        m_off = ptr_to_off(m_ptr)
        if m_off is None: return []
        slots = []
        for i in range(count):
            if m_off + i*4 + 4 > len(rom): break
            min_l, max_l, sp = struct.unpack_from("<BBH", rom, m_off + i*4)
            if min_l == 0 or min_l > 100 or sp == 0 or sp > 2000: break
            slots.append((min_l, max_l, sp, get_species_name(sp)))
        return slots

    for curr in range(0x118955c, 0x118bbf8, 28):
        grp, num = rom[curr], rom[curr+1]
        if grp == 0xFF: break
        land_p, water_p, smash_p, fish_p = struct.unpack_from("<4I", rom, curr + 4)
        loc_name, sec, lay = get_map_info(grp, num)

        region = "Hoenn"
        if grp in (36, 37):
            if sec in range(143, 195) or sec in range(150, 185):
                region = "Sevii Islands"
            elif sec in range(88, 143):
                region = "Kanto"
            else:
                region = "Kanto"
        elif grp in (34, 35):
            if sec in range(88, 143):
                region = "Kanto"
            else:
                region = "Hoenn"

        # Tall grass
        if land_p:
            slots = parse_slots(land_p, 12)
            for idx, (min_l, max_l, sp, sp_name) in enumerate(slots):
                ch = GRASS_CHANCES[idx] if idx < len(GRASS_CHANCES) else 1
                enc_records.append((region, grp, num, loc_name, "Tall Grass", idx + 1, ch, min_l, max_l, sp, sp_name))

        # Water
        if water_p:
            slots = parse_slots(water_p, 5)
            for idx, (min_l, max_l, sp, sp_name) in enumerate(slots):
                ch = WATER_CHANCES[idx] if idx < len(WATER_CHANCES) else 1
                enc_records.append((region, grp, num, loc_name, "Surfing", idx + 1, ch, min_l, max_l, sp, sp_name))

        # Rock smash
        if smash_p:
            slots = parse_slots(smash_p, 5)
            for idx, (min_l, max_l, sp, sp_name) in enumerate(slots):
                ch = SMASH_CHANCES[idx] if idx < len(SMASH_CHANCES) else 1
                enc_records.append((region, grp, num, loc_name, "Rock Smash", idx + 1, ch, min_l, max_l, sp, sp_name))

        # Fishing
        if fish_p:
            slots = parse_slots(fish_p, 10)
            # Old Rod: slots 0-1
            for idx in range(min(2, len(slots))):
                min_l, max_l, sp, sp_name = slots[idx]
                ch = FISH_CHANCES["Old Rod"][idx]
                enc_records.append((region, grp, num, loc_name, "Fishing (Old Rod)", idx + 1, ch, min_l, max_l, sp, sp_name))
            # Good Rod: slots 2-4
            for idx in range(2, min(5, len(slots))):
                min_l, max_l, sp, sp_name = slots[idx]
                ch = FISH_CHANCES["Good Rod"][idx - 2]
                enc_records.append((region, grp, num, loc_name, "Fishing (Good Rod)", idx - 1, ch, min_l, max_l, sp, sp_name))
            # Super Rod: slots 5-9
            for idx in range(5, min(10, len(slots))):
                min_l, max_l, sp, sp_name = slots[idx]
                ch = FISH_CHANCES["Super Rod"][idx - 5]
                enc_records.append((region, grp, num, loc_name, "Fishing (Super Rod)", idx - 4, ch, min_l, max_l, sp, sp_name))

    cur.executemany("INSERT INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?)", enc_records)

    # Populate Legendaries from Legendary_Encounter_Master_Plan.md
    print("Populating Legendaries & Mythicals...")
    plan_path = "/home/vibecoder/Projects/Legendary_Encounter_Master_Plan.md"
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as pf:
            lines = pf.readlines()

        current_gen = "Hoenn"
        leg_records = []
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("### Generation"):
                current_gen = line_str.replace("###", "").strip()
            elif line_str.startswith("### 3."):
                current_gen = "Hoenn Native"

            # Parse bullet: * **Name (Lv X)**: description
            if line_str.startswith("* **") and "**:" in line_str:
                head, body = line_str[4:].split("**:", 1)
                m = re.search(r"^(.*?)\s*\((?:Lv|Level)\s*(\d+)[^\)]*\)", head)
                if m:
                    name = m.group(1).strip()
                    lv = m.group(2).strip()
                    loc_part = body.strip().split(".")[0]
                    leg_records.append((name, current_gen, f"Lv {lv} | {loc_part}", body.strip(), ""))
                else:
                    name = head.strip()
                    leg_records.append((name, current_gen, "Special", body.strip(), ""))
            # Table rows: | **Rayquaza** | 70 | **Sky Pillar** (Route 131) | ...
            elif line_str.startswith("| **") and "|" in line_str:
                cols = [c.strip() for c in line_str.split("|")[1:-1]]
                if len(cols) >= 4 and not cols[0].startswith("---") and cols[0] != "Pokémon":
                    name = cols[0].replace("**", "").strip()
                    lv = cols[1].strip()
                    loc = cols[2].replace("**", "").strip()
                    req = cols[3].strip()
                    leg_records.append((name, "Hoenn Native", f"Lv {lv} | {loc}", req, ""))

        print(f"Extracted {len(leg_records)} Legendary / Mythical encounter records.")
        cur.executemany("INSERT OR REPLACE INTO legendaries VALUES (?,?,?,?,?)", leg_records)

    # Indices for blazing speed
    cur.execute("CREATE INDEX idx_pokemon_name ON pokemon(name);")
    cur.execute("CREATE INDEX idx_learnsets_pid ON learnsets(pokemon_id);")
    cur.execute("CREATE INDEX idx_evolutions_pid ON evolutions(pokemon_id);")
    cur.execute("CREATE INDEX idx_encounters_spname ON encounters(species_name);")
    cur.execute("CREATE INDEX idx_encounters_loc ON encounters(location_name);")
    cur.execute("CREATE INDEX idx_encounters_region ON encounters(region);")

    conn.commit()
    conn.close()
    print("Database build complete!")

if __name__ == "__main__":
    main()
