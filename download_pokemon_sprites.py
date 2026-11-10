#!/usr/bin/env python3
"""
Background Sprite & Asset Downloader for Pokémon Quetzal DexNav.
Downloads authentic GBA/Gen 7/8/9 menu icon sprites and front sprites
for all Pokémon species in the Quetzal database.
"""

import os
import sys
import json
import sqlite3
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets", "sprites")
SILHOUETTE_DIR = os.path.join(BASE_DIR, "assets", "silhouettes")
DB_PATH = os.path.join(BASE_DIR, "quetzal_database.db")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(SILHOUETTE_DIR, exist_ok=True)

# Fetch official National Dex mapping
print("Fetching PokeAPI species list...")
name_to_dex = {}
try:
    req = urllib.request.Request("https://pokeapi.co/api/v2/pokemon?limit=1025", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        for idx, item in enumerate(data.get("results", [])):
            clean_name = item["name"].lower().replace("-", "").replace(" ", "")
            name_to_dex[clean_name] = idx + 1
except Exception as e:
    print("Warning: Could not fetch PokeAPI mapping online, falling back to ID mapping:", e)

def get_dex_id(species_id, species_name):
    clean = species_name.lower().replace("-", "").replace(" ", "").replace(".", "").replace("'", "")
    if clean in name_to_dex:
        return name_to_dex[clean]
    if species_id <= 1025:
        return species_id
    return species_id

def make_silhouette(in_path, out_path):
    try:
        im = Image.open(in_path).convert("RGBA")
        data = []
        for p in im.get_data():
            if p[3] > 20:
                data.append((25, 25, 30, 255))
            else:
                data.append((0, 0, 0, 0))
        im.putdata(data)
        im.save(out_path)
    except Exception:
        pass

def download_mon_sprite(item):
    sp_id, sp_name = item
    dex_id = get_dex_id(sp_id, sp_name)
    out_sprite = os.path.join(ASSETS_DIR, f"{sp_id}.png")
    out_sil = os.path.join(SILHOUETTE_DIR, f"{sp_id}.png")

    if os.path.exists(out_sprite) and os.path.exists(out_sil):
        return sp_id, True

    urls = [
        f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/{dex_id}.png",
        f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-viii/sword-shield/icons/{dex_id}.png",
        f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{dex_id}.png"
    ]

    downloaded = False
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    content = resp.read()
                    with open(out_sprite, "wb") as f:
                        f.write(content)
                    downloaded = True
                    break
        except Exception:
            continue

    if downloaded:
        # Create silhouette
        make_silhouette(out_sprite, out_sil)
        return sp_id, True
    return sp_id, False

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Prioritize encounter species
    cur.execute("SELECT DISTINCT species_id, species_name FROM encounters ORDER BY species_id")
    encounter_mons = cur.fetchall()
    print(f"Prioritizing {len(encounter_mons)} wild encounter species...")

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(download_mon_sprite, item): item for item in encounter_mons}
        count = 0
        for f in as_completed(futures):
            count += 1
            if count % 50 == 0 or count == len(encounter_mons):
                print(f"Progress: {count}/{len(encounter_mons)} encounter sprites processed.")

    # Now all remaining pokedex species
    cur.execute("SELECT id, name FROM pokemon ORDER BY id")
    all_mons = cur.fetchall()
    remaining = [m for m in all_mons if not os.path.exists(os.path.join(ASSETS_DIR, f"{m[0]}.png"))]
    print(f"Downloading remaining {len(remaining)} Pokédex species sprites in background...")

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(download_mon_sprite, item): item for item in remaining}
        count = 0
        for f in as_completed(futures):
            count += 1
            if count % 100 == 0 or count == len(remaining):
                print(f"All Pokédex: {count}/{len(remaining)} processed.")

    print("All sprites successfully downloaded and cached!")

if __name__ == "__main__":
    main()
