#!/usr/bin/env python3
"""
Pokémon Quetzal Save File Reader & Reverse Engineering Library
Extracts player metadata, party Pokémon, PC boxes (supporting 38, 31, and 21 byte formats),
and Pokédex bitfields from Pokémon Quetzal GBA save files (.sav).
"""

import os
import sys
import struct
import sqlite3
from typing import Optional, Set, Dict, List, Tuple, Any

DEFAULT_SAVE_PATH = "/home/vibecoder/Games/Console Games/GBA/Moemon Quetzal.sav"
DEFAULT_DB_PATH = "/home/vibecoder/Projects/quetzal_database.db"

SIGNATURE = 0x08012025
SECTOR_SIZE = 4096
SECTOR_DATA_SIZE = 3968  # 0xF80 bytes per sector in save blocks / PC storage
SECTORS_PER_SLOT = 16

# Gen 3 Pokémon Text Character Map
GEN3_CHARMAP: Dict[int, str] = {}
for i in range(26):
    GEN3_CHARMAP[0xBB + i] = chr(ord("A") + i)
    GEN3_CHARMAP[0xD5 + i] = chr(ord("a") + i)
for i in range(10):
    GEN3_CHARMAP[0xA1 + i] = str(i)
GEN3_CHARMAP[0x00] = " "
GEN3_CHARMAP[0xAC] = "?"
GEN3_CHARMAP[0xAD] = "."
GEN3_CHARMAP[0xAE] = "-"
GEN3_CHARMAP[0xB4] = "'"
GEN3_CHARMAP[0xB5] = "♂"
GEN3_CHARMAP[0xB6] = "♀"
GEN3_CHARMAP[0xB7] = "'"
GEN3_CHARMAP[0xB8] = ","
GEN3_CHARMAP[0xBA] = "-"
GEN3_CHARMAP[0x1B] = "é"
GEN3_CHARMAP[0xF0] = ":"
GEN3_CHARMAP[0xFF] = ""

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky"
]

PC_FORMATS = [
    {"size": 38, "data_bytes": 24, "pp": 24, "nickname": 28, "boxes": 37},
    {"size": 31, "data_bytes": 21, "pp": None, "nickname": 21, "boxes": 45},
    {"size": 21, "data_bytes": 21, "pp": None, "nickname": None, "boxes": 67},
]


def decode_gen3_text(data: bytes) -> str:
    """Decode Gen 3 GBA character-encoded byte arrays."""
    res = []
    for b in data:
        if b == 0xFF:
            break
        res.append(GEN3_CHARMAP.get(b, chr(b) if 32 <= b < 127 else ""))
    return "".join(res).strip()


def calc_sector_checksum(sector_bytes: bytes) -> int:
    """Calculate 16-bit checksum of 0xFF4 bytes in a save sector."""
    s = sum(int.from_bytes(sector_bytes[i:i+4], "little") for i in range(0, 0xFF4, 4)) & 0xFFFFFFFF
    return ((s >> 16) + (s & 0xFFFF)) & 0xFFFF


def read_bits(b_arr: bytes, n_bytes: int) -> int:
    """Read first n_bytes of byte array as little-endian integer for bitfield extraction."""
    val = 0
    for k in range(n_bytes - 1, -1, -1):
        val = (val << 8) | b_arr[k]
    return val


def get_bitfield(val: int, offset: int, width: int) -> int:
    """Extract width bits at offset from integer."""
    return (val >> offset) & ((1 << width) - 1)


class QuetzalSaveParser:
    """Complete Reverse Engineering Parser for Pokémon Quetzal save files."""

    def __init__(self, save_path: str = DEFAULT_SAVE_PATH):
        if not os.path.exists(save_path):
            raise FileNotFoundError(f"Save file not found at: {save_path}")
        with open(save_path, "rb") as f:
            self.raw_data = f.read()

        if len(self.raw_data) < 131072:
            raise ValueError(f"Save file too small: {len(self.raw_data)} bytes (expected >= 128KB)")

        self.save_path = save_path
        self.active_slot = self._determine_active_slot()
        self.sector_map = self._build_sector_map(self.active_slot)

    def _determine_active_slot(self) -> int:
        """Find the active save slot (0 or 1) by evaluating save counters and checksums."""
        slots = []
        for slot in (0, 1):
            start = slot * SECTORS_PER_SLOT
            valid_count = 0
            max_counter = 0
            for i in range(SECTORS_PER_SLOT):
                sec = self.raw_data[(start + i) * SECTOR_SIZE : (start + i + 1) * SECTOR_SIZE]
                sid = int.from_bytes(sec[0xFF4:0xFF6], "little")
                chk = int.from_bytes(sec[0xFF6:0xFF8], "little")
                sig = int.from_bytes(sec[0xFF8:0xFFC], "little")
                cnt = int.from_bytes(sec[0xFFC:0x1000], "little")
                if sig == SIGNATURE and calc_sector_checksum(sec) == chk:
                    valid_count += 1
                max_counter = max(max_counter, cnt)
            slots.append({"slot": slot, "valid_count": valid_count, "counter": max_counter})

        # Sort: prefer valid completeness, then higher save counter
        slots.sort(key=lambda s: (s["valid_count"] >= 14, s["counter"]), reverse=True)
        return slots[0]["slot"]

    def _build_sector_map(self, slot: int) -> Dict[int, int]:
        """Map sector ID (0..15) to physical sector index in the save file."""
        mapping = {}
        start = slot * SECTORS_PER_SLOT
        for i in range(SECTORS_PER_SLOT):
            phys = start + i
            sec = self.raw_data[phys * SECTOR_SIZE : (phys + 1) * SECTOR_SIZE]
            sid = int.from_bytes(sec[0xFF4:0xFF6], "little")
            sig = int.from_bytes(sec[0xFF8:0xFFC], "little")
            if sig == SIGNATURE:
                mapping[sid] = phys
        return mapping

    def get_player_info(self) -> Dict[str, Any]:
        """Extract player trainer info and play time from SaveBlock2 (Sector ID 0)."""
        sec0_idx = self.sector_map.get(0)
        if sec0_idx is None:
            return {"name": "Unknown", "hours": 0, "minutes": 0, "seconds": 0}

        sec0 = self.raw_data[sec0_idx * SECTOR_SIZE : (sec0_idx + 1) * SECTOR_SIZE]
        name = decode_gen3_text(sec0[0:8])
        tid = int.from_bytes(sec0[0x0A:0x0C], "little")
        sid = int.from_bytes(sec0[0x0C:0x0E], "little")
        hours = int.from_bytes(sec0[0x10:0x12], "little")
        minutes = sec0[0x14]
        seconds = sec0[0x15]

        return {
            "name": name,
            "tid": tid,
            "sid": sid,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "play_time_str": f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        }

    def get_party_pokemon(self) -> List[Dict[str, Any]]:
        """Extract party Pokémon from SaveBlock1 (Sector ID 1)."""
        sec1_idx = self.sector_map.get(1)
        if sec1_idx is None:
            return []

        sec1 = self.raw_data[sec1_idx * SECTOR_SIZE : (sec1_idx + 1) * SECTOR_SIZE]
        party_count = min(sec1[0x6A4], 6)
        party = []

        for slot in range(party_count):
            r = 0x6A8 + slot * 104
            pdata = sec1[r : r + 104]
            pid = int.from_bytes(pdata[0x00:0x04], "little")
            ot_id = int.from_bytes(pdata[0x04:0x08], "little")
            nick = decode_gen3_text(pdata[0x08:0x12])
            ot_name = decode_gen3_text(pdata[0x14:0x1B])
            species = int.from_bytes(pdata[0x28:0x2A], "little")
            item = int.from_bytes(pdata[0x2A:0x2C], "little")
            exp = int.from_bytes(pdata[0x2C:0x30], "little")
            level = pdata[0x58]
            current_hp = int.from_bytes(pdata[0x23:0x25], "little")
            max_hp = int.from_bytes(pdata[0x5A:0x5C], "little")
            moves = [int.from_bytes(pdata[0x34 + 2 * j : 0x36 + 2 * j], "little") for j in range(4)]
            moves = [m for m in moves if m != 0]

            party.append({
                "slot": slot + 1,
                "species_id": species,
                "nickname": nick,
                "ot_name": ot_name,
                "level": level,
                "current_hp": current_hp,
                "max_hp": max_hp,
                "item_id": item,
                "exp": exp,
                "moves": moves,
                "pid": pid,
                "ot_id": ot_id
            })

        return party

    def get_box_pokemon(self) -> List[Dict[str, Any]]:
        """Extract PC box Pokémon across sectors 5..15 with automatic format detection."""
        storage = bytearray()
        for sid in range(5, 16):
            phys = self.sector_map.get(sid)
            if phys is not None:
                storage.extend(self.raw_data[phys * SECTOR_SIZE : phys * SECTOR_SIZE + SECTOR_DATA_SIZE])

        mon_start = 0x461

        # Detect best format (38, 31, or 21 bytes)
        best_fmt = PC_FORMATS[1]  # Default to 31 bytes
        best_score = -999999

        for fmt in PC_FORMATS:
            size = fmt["size"]
            db = fmt["data_bytes"]
            boxes = fmt["boxes"]
            max_slots = min(boxes * 30, (len(storage) - mon_start) // size)
            score = 0
            for slot in range(max_slots):
                off = mon_start + slot * size
                rec = storage[off : off + size]
                if not any(rec):
                    continue
                bits = read_bits(rec[:db], db)
                sp = get_bitfield(bits, 0, 11)
                if not sp:
                    continue
                exp = get_bitfield(bits, 21, 17) * 10
                nature = get_bitfield(bits, 161, 5)
                ability = get_bitfield(bits, 166, 2)
                moves = [get_bitfield(bits, 48 + 10 * j, 10) for j in range(4)]
                if sp <= 1528 and exp <= 1059860 and nature <= 24 and ability <= 2 and all(m <= 848 for m in moves):
                    score += 1
                else:
                    score -= 1
            if score > best_score:
                best_score = score
                best_fmt = fmt

        size = best_fmt["size"]
        db = best_fmt["data_bytes"]
        boxes = best_fmt["boxes"]
        max_slots = min(boxes * 30, (len(storage) - mon_start) // size)

        boxed_pokemon = []
        for slot in range(max_slots):
            off = mon_start + slot * size
            rec = storage[off : off + size]
            if not any(rec):
                continue
            bits = read_bits(rec[:db], db)
            sp = get_bitfield(bits, 0, 11)
            if not sp or sp > 1528:
                continue

            item = get_bitfield(bits, 11, 10)
            exp = get_bitfield(bits, 21, 17) * 10
            shiny = get_bitfield(bits, 44, 1) == 1
            moves = [get_bitfield(bits, 48 + 10 * j, 10) for j in range(4)]
            moves = [m for m in moves if m != 0]
            nature = get_bitfield(bits, 161, 5)
            ability = get_bitfield(bits, 166, 2)

            nick = ""
            if best_fmt["nickname"] is not None:
                nick_off = best_fmt["nickname"]
                nick = decode_gen3_text(rec[nick_off : nick_off + 10])

            b_idx = slot // 30 + 1
            s_idx = slot % 30 + 1
            boxed_pokemon.append({
                "box": b_idx,
                "slot": s_idx,
                "species_id": sp,
                "nickname": nick,
                "item_id": item,
                "exp": exp,
                "shiny": shiny,
                "nature_id": nature,
                "nature_name": NATURES[nature] if nature < len(NATURES) else "Unknown",
                "ability_num": ability,
                "moves": moves
            })

        return boxed_pokemon

    def get_pokedex_bitfield_species(self) -> Set[int]:
        """Extract caught species IDs from Pokédex bitfields in Sector 4 (ROP/National, Johto, Kanto)."""
        sec4_idx = self.sector_map.get(4)
        if sec4_idx is None:
            return set()

        sec4 = self.raw_data[sec4_idx * SECTOR_SIZE : (sec4_idx + 1) * SECTOR_SIZE]
        caught = set()

        # 1. Primary ROP / National Dex bitfield at 0x9D0 (130 bytes = 1034 bits)
        if len(sec4) >= 0x9D0 + 130:
            dex_slice = sec4[0x9D0 : 0x9D0 + 130]
            for n in range(1, 1035):
                byte_idx = (n - 1) >> 3
                bit_idx = (n - 1) & 7
                if (dex_slice[byte_idx] >> bit_idx) & 1:
                    caught.add(n)

        # 2. Johto Dex bitfield at 0x1CC (if populated)
        if len(sec4) >= 0x1CC + 130:
            johto_slice = sec4[0x1CC : 0x1CC + 130]
            if any(johto_slice):
                for n in range(1, 1035):
                    byte_idx = (n - 1) >> 3
                    bit_idx = (n - 1) & 7
                    if (johto_slice[byte_idx] >> bit_idx) & 1:
                        caught.add(n)

        # 3. Kanto Dex bitfield at 0x3D4 (if populated)
        if len(sec4) >= 0x3D4 + 130:
            kanto_slice = sec4[0x3D4 : 0x3D4 + 130]
            if any(kanto_slice):
                for n in range(1, 1035):
                    byte_idx = (n - 1) >> 3
                    bit_idx = (n - 1) & 7
                    if (kanto_slice[byte_idx] >> bit_idx) & 1:
                        caught.add(n)

        return caught

    def get_all_caught_species(self) -> Set[int]:
        """
        Extract complete union of CAUGHT species IDs from:
        - Player's 6 party Pokémon
        - All PC box Pokémon (boxes 1 to 45/67)
        - Pokédex owned bitfields in SaveBlock1 / Sector 4
        """
        caught = set(self.get_pokedex_bitfield_species())

        # Union with party Pokémon
        for mon in self.get_party_pokemon():
            if mon["species_id"] > 0:
                caught.add(mon["species_id"])

        # Union with PC box Pokémon
        for mon in self.get_box_pokemon():
            if mon["species_id"] > 0:
                caught.add(mon["species_id"])

        return caught

    def get_all_seen_species(self) -> Set[int]:
        """
        Extract complete union of SEEN species IDs.
        In Pokémon Quetzal, every caught species is registered as seen.
        """
        # In Pokémon Quetzal, seen covers all caught Pokémon plus any registered Dex entries
        return set(self.get_all_caught_species())


def get_caught_species(save_path: str = DEFAULT_SAVE_PATH) -> Set[int]:
    """Public helper returning set of all caught species IDs."""
    parser = QuetzalSaveParser(save_path)
    return parser.get_all_caught_species()


def get_seen_species(save_path: str = DEFAULT_SAVE_PATH) -> Set[int]:
    """Public helper returning set of all seen species IDs."""
    parser = QuetzalSaveParser(save_path)
    return parser.get_all_seen_species()


def update_database_user_pokedex(save_path: str = DEFAULT_SAVE_PATH, db_path: str = DEFAULT_DB_PATH, existing_conn: Optional[sqlite3.Connection] = None) -> Tuple[int, int]:
    """
    Update quetzal_database.db with user_pokedex table populated from active save file.
    Returns (caught_count, seen_count).
    """
    parser = QuetzalSaveParser(save_path)
    caught_set = parser.get_all_caught_species()
    seen_set = parser.get_all_seen_species()

    should_close = False
    if existing_conn is not None:
        conn = existing_conn
    else:
        conn = sqlite3.connect(db_path, timeout=15.0)
        should_close = True

    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout=10000;")

    # Regional form expansion mapping:
    # Query SELECT id, name FROM pokemon WHERE id IN ({}) for caught species.
    # Find all form IDs in pokemon table that share the exact same name (case-insensitive)
    # as any caught species (e.g. Vulpix ID 37 -> Alolan Vulpix ID 954; Zorua ID 570 -> Hisuian Zorua ID 1233).
    # Add those form IDs to caught_set and insert them into caught_pokemon.
    if caught_set:
        caught_list = list(caught_set)
        caught_names = set()
        chunk_size = 500
        for i in range(0, len(caught_list), chunk_size):
            chunk = caught_list[i:i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            cur.execute(f"SELECT id, name FROM pokemon WHERE id IN ({placeholders})", chunk)
            for row in cur.fetchall():
                if row[1]:
                    caught_names.add(row[1].strip().lower())

        if caught_names:
            name_list = list(caught_names)
            for i in range(0, len(name_list), chunk_size):
                chunk = name_list[i:i + chunk_size]
                name_placeholders = ",".join("?" for _ in chunk)
                cur.execute(f"SELECT id FROM pokemon WHERE LOWER(name) IN ({name_placeholders})", chunk)
                form_ids = {row[0] for row in cur.fetchall()}
                caught_set.update(form_ids)
                seen_set.update(form_ids)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_pokedex (
        species_id INTEGER PRIMARY KEY,
        caught BOOLEAN,
        seen BOOLEAN
    )
    """)

    # Get max species from pokemon table
    cur.execute("SELECT id FROM pokemon")
    db_species = [row[0] for row in cur.fetchall()]
    if not db_species:
        db_species = list(range(1, 1500))

    # Also sync caught_pokemon table used by quetzal_dex_gui.py
    cur.execute("""
    CREATE TABLE IF NOT EXISTS caught_pokemon (
        species_id INTEGER PRIMARY KEY,
        species_name TEXT,
        caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    for sp_id in db_species:
        c = 1 if sp_id in caught_set else 0
        s = 1 if sp_id in seen_set else 0
        cur.execute("""
        INSERT INTO user_pokedex (species_id, caught, seen)
        VALUES (?, ?, ?)
        ON CONFLICT(species_id) DO UPDATE SET
            caught = excluded.caught,
            seen = excluded.seen
        """, (sp_id, c, s))

    # Populate caught_pokemon with all caught species
    for sp_id in sorted(caught_set):
        cur.execute("SELECT name FROM pokemon WHERE id=?", (sp_id,))
        row = cur.fetchone()
        name = row[0] if row else f"Species_{sp_id}"
        cur.execute("""
        INSERT INTO caught_pokemon (species_id, species_name)
        VALUES (?, ?)
        ON CONFLICT(species_id) DO UPDATE SET
            species_name = excluded.species_name
        """, (sp_id, name))

    conn.commit()
    if should_close:
        conn.close()

    return len(caught_set), len(seen_set)


def main():
    save_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SAVE_PATH
    db_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DB_PATH

    print("=" * 60)
    print("  POKÉMON QUETZAL SAVE FILE REVERSE ENGINEER")
    print("=" * 60)
    print(f"Target Save: {save_path}")

    parser = QuetzalSaveParser(save_path)
    player = parser.get_player_info()
    party = parser.get_party_pokemon()
    boxes = parser.get_box_pokemon()
    caught_ids = parser.get_all_caught_species()
    seen_ids = parser.get_all_seen_species()

    # Load species names from DB if available
    names_map: Dict[int, str] = {}
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM pokemon")
            names_map = {row[0]: row[1] for row in cur.fetchall()}
            conn.close()
        except Exception:
            pass

    print(f"\n[Trainer Information]")
    print(f"  Player Name   : {player['name']}")
    print(f"  Trainer ID    : {player['tid']:05d} (Secret ID: {player['sid']:05d})")
    print(f"  Play Time     : {player['play_time_str']}")
    print(f"  Active Slot   : Slot {parser.active_slot + 1}")

    print(f"\n[Party Pokémon ({len(party)} / 6)]")
    for mon in party:
        name = names_map.get(mon["species_id"], f"Species_{mon['species_id']}")
        nick = f" (\"{mon['nickname']}\")" if mon['nickname'] and mon['nickname'] != name else ""
        print(f"  Slot {mon['slot']}: Lv.{mon['level']:<3} #{mon['species_id']:4d} {name}{nick} - HP: {mon['current_hp']}/{mon['max_hp']}")

    print(f"\n[PC Storage Pokémon ({len(boxes)} Boxed)]")
    box_counts: Dict[int, int] = {}
    for mon in boxes:
        box_counts[mon["box"]] = box_counts.get(mon["box"], 0) + 1
    for b_num in sorted(box_counts.keys()):
        print(f"  Box {b_num:2d}: {box_counts[b_num]:2d} Pokémon")

    print(f"\n[Pokédex Progress]")
    print(f"  Total Caught Pokémon : {len(caught_ids)}")
    print(f"  Total Seen Pokémon   : {len(seen_ids)}")

    print(f"\n[Sample List of Caught Pokémon (First 25)]")
    for sp_id in sorted(list(caught_ids))[:25]:
        name = names_map.get(sp_id, f"Species_{sp_id}")
        print(f"  #{sp_id:4d}: {name}")

    print(f"\n[Updating Database: {db_path}]")
    c_count, s_count = update_database_user_pokedex(save_path, db_path)
    print(f"  Successfully updated user_pokedex table ({c_count} caught, {s_count} seen).")
    print("=" * 60)


if __name__ == "__main__":
    main()
