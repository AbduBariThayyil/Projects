#!/usr/bin/env python3
"""
Populate complete Johto Wild Encounters and Special Trainers in quetzal_database.db
"""

import sqlite3

DB_PATH = "/home/vibecoder/Projects/quetzal_database.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Get species lookup dictionary
cur.execute("SELECT id, name FROM pokemon")
rows = cur.fetchall()
sp_by_name = {}
for pid, name in rows:
    key = name.strip().lower()
    if key not in sp_by_name:
        sp_by_name[key] = (pid, name)

def find_sp(name):
    clean = name.strip().lower()
    if clean in sp_by_name:
        return sp_by_name[clean]
    # Check partial
    for k, v in sp_by_name.items():
        if clean in k or k in clean:
            return v
    raise ValueError(f"Species not found: {name}")

print("Setting up encounters and trainers tables...")

# Ensure trainers table exists
cur.execute("""
CREATE TABLE IF NOT EXISTS trainers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,          -- 'Battle Frontier Brain', 'Gym Leader Rematch', 'Champion', 'Evil Team Boss', 'Special NPC'
    name TEXT,              -- e.g. 'Anabel', 'Tucker', 'Red', 'Cynthia', 'Norman', 'Steven'
    title TEXT,             -- e.g. 'Salon Maiden', 'Dome Ace', 'Pokémon Trainer', 'Sinnoh Champion'
    region TEXT,            -- 'Hoenn', 'Johto', 'Kanto', 'Battle Frontier'
    location TEXT,          -- e.g. 'Battle Tower', 'Battle Dome', 'Mt. Silver Peak', 'Petalburg Gym'
    unlock_condition TEXT,  -- e.g. 'Post-HoF: Reach 35 consecutive wins for Silver Symbol, 70 for Gold Symbol'
    team_preview TEXT,      -- Formatted string of Pokemon, moves, and levels
    reward TEXT             -- e.g. 'Ability Patch, Gold Frontier Symbol, $15,000'
);
""")

# Delete any existing Johto encounters to ensure clean population
cur.execute("DELETE FROM encounters WHERE region = 'Johto'")
cur.execute("DELETE FROM trainers")

# ==========================================
# 1. JOHTO WILD ENCOUNTERS
# ==========================================
# Routes 29-46, 26-28, Caves, Waters, Towers
# Standard chances:
# Tall grass: [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
# Surfing: [60, 30, 5, 4, 1]
# Old Rod: [70, 30]
# Good Rod: [60, 20, 20]
# Super Rod: [40, 40, 15, 4, 1]
# Rock Smash: [60, 30, 5, 4, 1]

GRASS_CHANCES = [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
WATER_CHANCES = [60, 30, 5, 4, 1]
SMASH_CHANCES = [60, 30, 5, 4, 1]

JOHTO_DATA = [
    # ROUTE 29 (Tall grass, Day/Night mix, Wooloo/Lechonk additions)
    ("ROUTE 29", "Tall Grass", 2, 4, [
        "Sentret", "Pidgey", "Rattata", "Hoothoot", "Wooloo", "Lechonk",
        "Lillipup", "Bunnelby", "Yungoos", "Spearow", "Pawmi", "Eevee"
    ]),
    ("ROUTE 29", "Surfing", 15, 25, ["Poliwag", "Wooper", "Marill", "Psyduck", "Slowpoke"]),
    ("ROUTE 29", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Poliwag"]),
    ("ROUTE 29", "Fishing (Good Rod)", 15, 20, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ROUTE 29", "Fishing (Super Rod)", 25, 35, ["Poliwhirl", "Gyarados", "Seaking", "Chewtle", "Dratini"]),
    ("ROUTE 29", "Hidden Rare", 5, 6, ["Eevee"]),

    # ROUTE 30
    ("ROUTE 30", "Tall Grass", 2, 5, [
        "Pidgey", "Caterpie", "Weedle", "Ledyba", "Spinarak", "Hoothoot",
        "Rattata", "Zubat", "Blipbug", "Scatterbug", "Grubbin", "Rookidee"
    ]),
    ("ROUTE 30", "Surfing", 15, 25, ["Poliwag", "Wooper", "Marill", "Psyduck", "Ducklett"]),
    ("ROUTE 30", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Poliwag"]),
    ("ROUTE 30", "Fishing (Good Rod)", 15, 20, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ROUTE 30", "Fishing (Super Rod)", 25, 35, ["Poliwhirl", "Gyarados", "Seaking", "Corphish", "Dratini"]),
    ("ROUTE 30", "Hidden Rare", 5, 7, ["Rookidee"]),

    # ROUTE 31
    ("ROUTE 31", "Tall Grass", 3, 6, [
        "Bellsprout", "Pidgey", "Caterpie", "Weedle", "Ledyba", "Spinarak",
        "Hoothoot", "Rattata", "Gastly", "Zubat", "Mareep", "Budew"
    ]),
    ("ROUTE 31", "Surfing", 15, 25, ["Poliwag", "Wooper", "Marill", "Psyduck", "Slowpoke"]),
    ("ROUTE 31", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Poliwag"]),
    ("ROUTE 31", "Fishing (Good Rod)", 15, 20, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ROUTE 31", "Fishing (Super Rod)", 25, 35, ["Poliwhirl", "Gyarados", "Seaking", "Barboach", "Dratini"]),
    ("ROUTE 31", "Hidden Rare", 6, 8, ["Mareep"]),

    # DARK CAVE (Violet Entrance & Blackthorn Entrance) - DUNSPARCE WITH NUGGETS!
    ("DARK CAVE", "Tall Grass", 3, 6, [
        "Zubat", "Geodude", "Dunsparce", "Teddiursa", "Nacli", "Roggenrola",
        "Wobbuffet", "Grimer", "Carbink", "Sableye", "Onix", "Rolycoly"
    ]),
    ("DARK CAVE", "Rock Smash", 5, 15, ["Geodude", "Graveler", "Shuckle", "Nacli", "Dunsparce"]),
    ("DARK CAVE", "Surfing", 20, 30, ["Golbat", "Quagsire", "Slowpoke", "Slowbro", "Graveler"]),
    ("DARK CAVE", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Goldeen"]),
    ("DARK CAVE", "Fishing (Good Rod)", 20, 25, ["Magikarp", "Goldeen", "Seaking"]),
    ("DARK CAVE", "Fishing (Super Rod)", 30, 40, ["Gyarados", "Seaking", "Whiscash", "Qwilfish", "Dratini"]),
    ("DARK CAVE", "Hidden Rare", 10, 12, ["Dunsparce"]),

    # SPROUT TOWER
    ("SPROUT TOWER", "Tall Grass", 3, 6, [
        "Rattata", "Gastly", "Bellsprout", "Hoothoot", "Sinistea", "Phantump",
        "Litwick", "Drifloon", "Shuppet", "Duskull", "Greavard", "Chimecho"
    ]),
    ("SPROUT TOWER", "Hidden Rare", 8, 10, ["Sinistea"]),

    # ROUTE 32
    ("ROUTE 32", "Tall Grass", 4, 7, [
        "Mareep", "Bellsprout", "Ekans", "Zubat", "Rattata", "Hoothoot",
        "Wooper", "Pidgey", "Pawmi", "Yamper", "Shinx", "Electrike"
    ]),
    ("ROUTE 32", "Surfing", 15, 25, ["Tentacool", "Tentacruel", "Wooper", "Quagsire", "Qwilfish"]),
    ("ROUTE 32", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Tentacool"]),
    ("ROUTE 32", "Fishing (Good Rod)", 15, 20, ["Tentacool", "Magikarp", "Qwilfish"]),
    ("ROUTE 32", "Fishing (Super Rod)", 25, 35, ["Tentacruel", "Qwilfish", "Gyarados", "Chinchou", "Corsola"]),
    ("ROUTE 32", "Rock Smash", 6, 12, ["Geodude", "Shuckle", "Nacli", "Graveler", "Roggenrola"]),
    ("ROUTE 32", "Hidden Rare", 8, 10, ["Pawmi"]),

    # RUINS OF ALPH
    ("RUINS OF ALPH", "Tall Grass", 5, 8, [
        "Natu", "Smeargle", "Wooper", "Quagsire", "Baltoy", "Bronzor",
        "Sigilyph", "Elgyem", "Yamask", "Claydol", "Unown", "Unown"
    ]),
    ("RUINS OF ALPH", "Surfing", 15, 25, ["Wooper", "Quagsire", "Poliwag", "Poliwhirl", "Marill"]),
    ("RUINS OF ALPH", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Poliwag"]),
    ("RUINS OF ALPH", "Fishing (Good Rod)", 15, 20, ["Poliwag", "Magikarp", "Goldeen"]),
    ("RUINS OF ALPH", "Fishing (Super Rod)", 25, 35, ["Poliwhirl", "Gyarados", "Seaking", "Corphish", "Slowpoke"]),
    ("RUINS OF ALPH", "Rock Smash", 5, 15, ["Geodude", "Nacli", "Nosepass", "Graveler", "Shuckle"]),
    ("RUINS OF ALPH", "Hidden Rare", 10, 12, ["Sigilyph"]),

    # UNION CAVE
    ("UNION CAVE", "Tall Grass", 6, 9, [
        "Geodude", "Zubat", "Rattata", "Sandshrew", "Wooper", "Onix",
        "Drilbur", "Axew", "Gible", "Riolu", "Gligar", "Roggenrola"
    ]),
    ("UNION CAVE", "Surfing", 15, 25, ["Wooper", "Quagsire", "Lapras", "Tentacool", "Slowpoke"]),
    ("UNION CAVE", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Goldeen"]),
    ("UNION CAVE", "Fishing (Good Rod)", 15, 20, ["Goldeen", "Magikarp", "Poliwag"]),
    ("UNION CAVE", "Fishing (Super Rod)", 25, 35, ["Seaking", "Gyarados", "Poliwhirl", "Qwilfish", "Dratini"]),
    ("UNION CAVE", "Rock Smash", 8, 15, ["Geodude", "Graveler", "Onix", "Shuckle", "Nacli"]),
    ("UNION CAVE", "Hidden Rare", 15, 20, ["Lapras"]),

    # ROUTE 33
    ("ROUTE 33", "Tall Grass", 6, 8, [
        "Rattata", "Spearow", "Ekans", "Zubat", "Hoppip", "Aipom",
        "Mankey", "Scraggy", "Skiddo", "Houndour", "Geodude", "Heracross"
    ]),
    ("ROUTE 33", "Hidden Rare", 10, 12, ["Heracross"]),

    # SLOWPOKE WELL
    ("SLOWPOKE WELL", "Tall Grass", 6, 9, [
        "Zubat", "Slowpoke", "Golbat", "Slowbro", "Grimer", "Wooper",
        "Shellder", "Psyduck", "Mareanie", "Tadbulb", "Clamperl", "Wimpod"
    ]),
    ("SLOWPOKE WELL", "Surfing", 15, 25, ["Slowpoke", "Slowbro", "Golbat", "Quagsire", "Dewpider"]),
    ("SLOWPOKE WELL", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Goldeen"]),
    ("SLOWPOKE WELL", "Fishing (Good Rod)", 15, 20, ["Goldeen", "Magikarp", "Slowpoke"]),
    ("SLOWPOKE WELL", "Fishing (Super Rod)", 25, 35, ["Slowbro", "Gyarados", "Seaking", "Shellder", "Dratini"]),
    ("SLOWPOKE WELL", "Hidden Rare", 12, 15, ["Shellder"]),

    # ILEX FOREST
    ("ILEX FOREST", "Tall Grass", 6, 10, [
        "Caterpie", "Weedle", "Metapod", "Kakuna", "Zubat", "Paras",
        "Venonat", "Oddish", "Applin", "Grubbin", "Sewaddle", "Phantump"
    ]),
    ("ILEX FOREST", "Surfing", 15, 25, ["Psyduck", "Golduck", "Poliwag", "Poliwhirl", "Wooper"]),
    ("ILEX FOREST", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Poliwag"]),
    ("ILEX FOREST", "Fishing (Good Rod)", 15, 20, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ILEX FOREST", "Fishing (Super Rod)", 25, 35, ["Poliwhirl", "Gyarados", "Seaking", "Corphish", "Dratini"]),
    ("ILEX FOREST", "Hidden Rare", 12, 14, ["Applin"]),

    # ROUTE 34
    ("ROUTE 34", "Tall Grass", 10, 13, [
        "Pidgey", "Rattata", "Drowzee", "Abra", "Ditto", "Snubbull",
        "Ralts", "Espurr", "Hatenna", "Fidough", "Tandemaus", "Eevee"
    ]),
    ("ROUTE 34", "Surfing", 15, 25, ["Tentacool", "Tentacruel", "Staryu", "Corsola", "Wingull"]),
    ("ROUTE 34", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Tentacool"]),
    ("ROUTE 34", "Fishing (Good Rod)", 15, 20, ["Tentacool", "Magikarp", "Staryu"]),
    ("ROUTE 34", "Fishing (Super Rod)", 25, 35, ["Tentacruel", "Staryu", "Gyarados", "Corsola", "Kingler"]),
    ("ROUTE 34", "Hidden Rare", 12, 15, ["Ditto"]),

    # ROUTE 35
    ("ROUTE 35", "Tall Grass", 10, 14, [
        "Pidgey", "Nidoran♀", "Nidoran♂", "Drowzee", "Abra", "Ditto",
        "Yanma", "Growlithe", "Vulpix", "Morpeko", "Deerling", "Pikachu"
    ]),
    ("ROUTE 35", "Surfing", 15, 25, ["Psyduck", "Golduck", "Poliwag", "Marill", "Ducklett"]),
    ("ROUTE 35", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Poliwag"]),
    ("ROUTE 35", "Fishing (Good Rod)", 15, 20, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ROUTE 35", "Fishing (Super Rod)", 25, 35, ["Poliwhirl", "Gyarados", "Seaking", "Arrokuda", "Dratini"]),
    ("ROUTE 35", "Hidden Rare", 14, 16, ["Yanma"]),

    # NATIONAL PARK
    ("NATIONAL PARK", "Tall Grass", 10, 15, [
        "Caterpie", "Weedle", "Metapod", "Kakuna", "Butterfree", "Beedrill",
        "Pinsir", "Scyther", "Heracross", "Venonat", "Ledyba", "Spinarak"
    ]),
    ("NATIONAL PARK", "Hidden Rare", 15, 18, ["Scyther"]),

    # ROUTE 36
    ("ROUTE 36", "Tall Grass", 11, 15, [
        "Pidgey", "Nidoran♀", "Nidoran♂", "Growlithe", "Vulpix", "Stantler",
        "Sudowoodo", "Houndour", "Deerling", "Rolycoly", "Shinx", "Mareep"
    ]),
    ("ROUTE 36", "Hidden Rare", 15, 18, ["Sudowoodo"]),

    # ROUTE 37
    ("ROUTE 37", "Tall Grass", 12, 16, [
        "Pidgeotto", "Growlithe", "Vulpix", "Stantler", "Ledian", "Ariados",
        "Spinarak", "Ledyba", "Pidgey", "Houndour", "Litleo", "Maschiff"
    ]),
    ("ROUTE 37", "Hidden Rare", 15, 18, ["Growlithe"]),

    # BURNED TOWER
    ("BURNED TOWER", "Tall Grass", 13, 17, [
        "Rattata", "Zubat", "Koffing", "Magmar", "Gastly", "Raticate",
        "Weezing", "Golbat", "Houndour", "Salandit", "Charcadet", "Litwick"
    ]),
    ("BURNED TOWER", "Rock Smash", 12, 18, ["Geodude", "Graveler", "Magcargo", "Slugma", "Rolycoly"]),
    ("BURNED TOWER", "Hidden Rare", 16, 20, ["Charcadet"]),

    # BELL TOWER / TIN TOWER
    ("BELL TOWER", "Tall Grass", 20, 25, [
        "Rattata", "Raticate", "Gastly", "Haunter", "Chimecho", "Bronzong",
        "Misdreavus", "Mismagius", "Ninetales", "Arcanine", "Hoothoot", "Noctowl"
    ]),
    ("BELL TOWER", "Hidden Rare", 25, 30, ["Misdreavus"]),

    # ROUTE 38
    ("ROUTE 38", "Tall Grass", 13, 17, [
        "Pidgeotto", "Raticate", "Magnemite", "Farfetch'd", "Meowth", "Tauros",
        "Miltank", "Bouffalant", "Dubwool", "Electrike", "Yamper", "Flaaffy"
    ]),
    ("ROUTE 38", "Hidden Rare", 16, 18, ["Miltank"]),

    # ROUTE 39
    ("ROUTE 39", "Tall Grass", 14, 18, [
        "Pidgeotto", "Raticate", "Magnemite", "Farfetch'd", "Meowth", "Tauros",
        "Miltank", "Bouffalant", "Dubwool", "Oinkologne", "Flaaffy", "Electrike"
    ]),
    ("ROUTE 39", "Hidden Rare", 16, 19, ["Tauros"]),

    # ROUTE 40 (Coastal Surfing & Fishing) - SHELLDER PEARL FARM
    ("ROUTE 40", "Surfing", 15, 25, ["Tentacool", "Tentacruel", "Shellder", "Wingull", "Pelipper"]),
    ("ROUTE 40", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Tentacool"]),
    ("ROUTE 40", "Fishing (Good Rod)", 20, 25, ["Tentacool", "Magikarp", "Shellder"]),
    ("ROUTE 40", "Fishing (Super Rod)", 30, 40, ["Tentacruel", "Shellder", "Cloyster", "Gyarados", "Corsola"]),
    ("ROUTE 40", "Rock Smash", 15, 25, ["Krabby", "Kingler", "Shuckle", "Nacli", "Dwebble"]),
    ("ROUTE 40", "Hidden Rare", 22, 26, ["Shellder"]),

    # ROUTE 41 (Whirlpool Ocean)
    ("ROUTE 41", "Surfing", 20, 30, ["Tentacool", "Tentacruel", "Mantine", "Wingull", "Pelipper"]),
    ("ROUTE 41", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Tentacool"]),
    ("ROUTE 41", "Fishing (Good Rod)", 20, 25, ["Tentacool", "Magikarp", "Chinchou"]),
    ("ROUTE 41", "Fishing (Super Rod)", 30, 40, ["Tentacruel", "Lanturn", "Gyarados", "Qwilfish", "Corsola"]),
    ("ROUTE 41", "Hidden Rare", 25, 30, ["Mantine"]),

    # WHIRL ISLANDS
    ("WHIRL ISLANDS", "Tall Grass", 22, 28, [
        "Zubat", "Golbat", "Seel", "Dewgong", "Krabby", "Kingler",
        "Shellder", "Cloyster", "Slowpoke", "Slowbro", "Spheal", "Sealeo"
    ]),
    ("WHIRL ISLANDS", "Surfing", 20, 30, ["Tentacruel", "Seel", "Dewgong", "Horsea", "Seadra"]),
    ("WHIRL ISLANDS", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Krabby"]),
    ("WHIRL ISLANDS", "Fishing (Good Rod)", 20, 25, ["Krabby", "Magikarp", "Horsea"]),
    ("WHIRL ISLANDS", "Fishing (Super Rod)", 30, 40, ["Kingler", "Seadra", "Gyarados", "Corsola", "Dratini"]),
    ("WHIRL ISLANDS", "Rock Smash", 20, 30, ["Krabby", "Kingler", "Graveler", "Shuckle", "Dwebble"]),
    ("WHIRL ISLANDS", "Hidden Rare", 28, 32, ["Dewgong"]),

    # ROUTE 42
    ("ROUTE 42", "Tall Grass", 13, 17, [
        "Spearow", "Zubat", "Mankey", "Mareep", "Flaaffy", "Marill",
        "Primeape", "Golbat", "Arbok", "Nacli", "Pawmo", "Gligar"
    ]),
    ("ROUTE 42", "Surfing", 15, 25, ["Goldeen", "Seaking", "Marill", "Poliwhirl", "Ducklett"]),
    ("ROUTE 42", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Goldeen"]),
    ("ROUTE 42", "Fishing (Good Rod)", 15, 20, ["Goldeen", "Magikarp", "Seaking"]),
    ("ROUTE 42", "Fishing (Super Rod)", 25, 35, ["Seaking", "Gyarados", "Poliwhirl", "Barboach", "Dratini"]),
    ("ROUTE 42", "Rock Smash", 12, 18, ["Geodude", "Graveler", "Shuckle", "Nacli", "Onix"]),
    ("ROUTE 42", "Hidden Rare", 16, 20, ["Marill"]),

    # MT. MORTAR
    ("MT. MORTAR", "Tall Grass", 14, 18, [
        "Rattata", "Raticate", "Zubat", "Golbat", "Geodude", "Graveler",
        "Marill", "Machop", "Machoke", "Tyrogue", "Hitmonlee", "Hitmonchan"
    ]),
    ("MT. MORTAR", "Surfing", 15, 25, ["Goldeen", "Seaking", "Marill", "Slowpoke", "Slowbro"]),
    ("MT. MORTAR", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Goldeen"]),
    ("MT. MORTAR", "Fishing (Good Rod)", 15, 20, ["Goldeen", "Magikarp", "Seaking"]),
    ("MT. MORTAR", "Fishing (Super Rod)", 25, 35, ["Seaking", "Gyarados", "Poliwhirl", "Whiscash", "Dragonair"]),
    ("MT. MORTAR", "Rock Smash", 14, 20, ["Geodude", "Graveler", "Onix", "Shuckle", "Gurdurr"]),
    ("MT. MORTAR", "Hidden Rare", 18, 22, ["Tyrogue"]),

    # ROUTE 43
    ("ROUTE 43", "Tall Grass", 15, 19, [
        "Pidgeotto", "Raticate", "Sentret", "Furret", "Venonat", "Venomoth",
        "Girafarig", "Farigiraf", "Flaaffy", "Mareep", "Greavard", "Morpeko"
    ]),
    ("ROUTE 43", "Surfing", 15, 25, ["Magikarp", "Poliwag", "Poliwhirl", "Marill", "Goldeen"]),
    ("ROUTE 43", "Fishing (Old Rod)", 5, 10, ["Magikarp", "Poliwag"]),
    ("ROUTE 43", "Fishing (Good Rod)", 15, 20, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ROUTE 43", "Fishing (Super Rod)", 25, 35, ["Poliwhirl", "Gyarados", "Seaking", "Arrokuda", "Dratini"]),
    ("ROUTE 43", "Hidden Rare", 18, 22, ["Girafarig"]),

    # LAKE OF RAGE
    ("LAKE OF RAGE", "Tall Grass", 15, 20, [
        "Pidgeotto", "Raticate", "Venonat", "Venomoth", "Girafarig", "Flaaffy",
        "Furret", "Noctowl", "Morpeko", "Greavard", "Farigiraf", "Heracross"
    ]),
    ("LAKE OF RAGE", "Surfing", 15, 25, ["Magikarp", "Gyarados", "Poliwag", "Poliwhirl", "Seaking"]),
    ("LAKE OF RAGE", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Poliwag"]),
    ("LAKE OF RAGE", "Fishing (Good Rod)", 20, 25, ["Magikarp", "Gyarados", "Poliwhirl"]),
    ("LAKE OF RAGE", "Fishing (Super Rod)", 30, 45, ["Gyarados", "Poliwhirl", "Seaking", "Barraskewda", "Dragonair"]),
    ("LAKE OF RAGE", "Hidden Rare", 30, 35, ["Gyarados"]),

    # ROUTE 44
    ("ROUTE 44", "Tall Grass", 22, 26, [
        "Bellsprout", "Weepinbell", "Poliwag", "Poliwhirl", "Tangela", "Lickitung",
        "Applin", "Carnivine", "Chewtle", "Drednaw", "Smoliv", "Tsareena"
    ]),
    ("ROUTE 44", "Surfing", 20, 30, ["Poliwag", "Poliwhirl", "Slowpoke", "Slowbro", "Marill"]),
    ("ROUTE 44", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Poliwag"]),
    ("ROUTE 44", "Fishing (Good Rod)", 20, 25, ["Poliwag", "Magikarp", "Remoraid"]),
    ("ROUTE 44", "Fishing (Super Rod)", 30, 40, ["Poliwhirl", "Octillery", "Gyarados", "Remoraid", "Dratini"]),
    ("ROUTE 44", "Hidden Rare", 26, 30, ["Tangela"]),

    # ICE PATH
    ("ICE PATH", "Tall Grass", 21, 25, [
        "Zubat", "Golbat", "Swinub", "Piloswine", "Jynx", "Delibird",
        "Sneasel", "Snom", "Frosmoth", "Bergmite", "Cetoddle", "Frigibax"
    ]),
    ("ICE PATH", "Rock Smash", 20, 28, ["Geodude", "Graveler", "Bergmite", "Crabrawler", "Gurdurr"]),
    ("ICE PATH", "Hidden Rare", 26, 30, ["Frigibax"]),

    # DRAGON'S DEN
    ("DRAGON'S DEN", "Surfing", 15, 25, ["Magikarp", "Dratini", "Dragonair", "Gyarados", "Horsea"]),
    ("DRAGON'S DEN", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Dratini"]),
    ("DRAGON'S DEN", "Fishing (Good Rod)", 20, 25, ["Magikarp", "Dratini", "Dragonair"]),
    ("DRAGON'S DEN", "Fishing (Super Rod)", 30, 45, ["Dragonair", "Dratini", "Gyarados", "Kingdra", "Duraludon"]),
    ("DRAGON'S DEN", "Hidden Rare", 35, 40, ["Dragonair"]),

    # ROUTE 45
    ("ROUTE 45", "Tall Grass", 23, 27, [
        "Geodude", "Graveler", "Gligar", "Teddiursa", "Ursaring", "Skarmory",
        "Phanpy", "Donphan", "Corvisquire", "Nacli", "Garganacl", "Pupitar"
    ]),
    ("ROUTE 45", "Surfing", 20, 30, ["Magikarp", "Poliwag", "Poliwhirl", "Goldeen", "Seaking"]),
    ("ROUTE 45", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Poliwag"]),
    ("ROUTE 45", "Fishing (Good Rod)", 20, 25, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ROUTE 45", "Fishing (Super Rod)", 30, 40, ["Poliwhirl", "Gyarados", "Seaking", "Barboach", "Dratini"]),
    ("ROUTE 45", "Rock Smash", 22, 28, ["Geodude", "Graveler", "Nacli", "Garganacl", "Shuckle"]),
    ("ROUTE 45", "Hidden Rare", 27, 30, ["Skarmory"]),

    # ROUTE 46
    ("ROUTE 46", "Tall Grass", 2, 5, [
        "Geodude", "Spearow", "Rattata", "Rookidee", "Pawmi", "Nacli",
        "Phanpy", "Teddiursa", "Pidgey", "Sentret", "Lillipup", "Wooloo"
    ]),
    ("ROUTE 46", "Hidden Rare", 5, 7, ["Phanpy"]),

    # ROUTE 26
    ("ROUTE 26", "Tall Grass", 28, 32, [
        "Raticate", "Arbok", "Sandslash", "Ponyta", "Rapidash", "Doduo",
        "Dodrio", "Noctowl", "Quagsire", "Mudsdale", "Corviknight", "Tauros"
    ]),
    ("ROUTE 26", "Surfing", 25, 35, ["Tentacruel", "Quagsire", "Slowbro", "Gyarados", "Pelipper"]),
    ("ROUTE 26", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Tentacool"]),
    ("ROUTE 26", "Fishing (Good Rod)", 20, 25, ["Tentacool", "Magikarp", "Shellder"]),
    ("ROUTE 26", "Fishing (Super Rod)", 30, 45, ["Tentacruel", "Shellder", "Gyarados", "Qwilfish", "Corsola"]),
    ("ROUTE 26", "Hidden Rare", 32, 36, ["Rapidash"]),

    # ROUTE 27
    ("ROUTE 27", "Tall Grass", 28, 32, [
        "Raticate", "Arbok", "Sandslash", "Ponyta", "Doduo", "Dodrio",
        "Noctowl", "Quagsire", "Mudsdale", "Corviknight", "Tauros", "Farfetch'd"
    ]),
    ("ROUTE 27", "Surfing", 25, 35, ["Tentacruel", "Quagsire", "Slowbro", "Gyarados", "Pelipper"]),
    ("ROUTE 27", "Fishing (Old Rod)", 10, 15, ["Magikarp", "Tentacool"]),
    ("ROUTE 27", "Fishing (Good Rod)", 20, 25, ["Tentacool", "Magikarp", "Chinchou"]),
    ("ROUTE 27", "Fishing (Super Rod)", 30, 45, ["Tentacruel", "Lanturn", "Gyarados", "Qwilfish", "Corsola"]),
    ("ROUTE 27", "Hidden Rare", 32, 36, ["Corviknight"]),

    # ROUTE 28
    ("ROUTE 28", "Tall Grass", 38, 43, [
        "Ponyta", "Rapidash", "Doduo", "Dodrio", "Tangela", "Donphan",
        "Ursaring", "Sneasel", "Houndoom", "Corviknight", "Mudsdale", "Tyranitar"
    ]),
    ("ROUTE 28", "Surfing", 30, 40, ["Poliwhirl", "Golduck", "Slowbro", "Gyarados", "Quagsire"]),
    ("ROUTE 28", "Fishing (Old Rod)", 15, 20, ["Magikarp", "Poliwag"]),
    ("ROUTE 28", "Fishing (Good Rod)", 25, 30, ["Poliwag", "Magikarp", "Goldeen"]),
    ("ROUTE 28", "Fishing (Super Rod)", 35, 50, ["Poliwhirl", "Gyarados", "Seaking", "Dratini", "Dragonair"]),
    ("ROUTE 28", "Hidden Rare", 42, 46, ["Tyranitar"]),

    # MT. SILVER (Base, Cave & Peak)
    ("MT. SILVER", "Tall Grass", 42, 48, [
        "Ursaring", "Donphan", "Golbat", "Graveler", "Onix", "Steelix",
        "Larvitar", "Pupitar", "Tyranitar", "Sneasel", "Weavile", "Garganacl"
    ]),
    ("MT. SILVER", "Surfing", 35, 45, ["Seaking", "Gyarados", "Golduck", "Poliwrath", "Slowbro"]),
    ("MT. SILVER", "Fishing (Old Rod)", 15, 20, ["Magikarp", "Goldeen"]),
    ("MT. SILVER", "Fishing (Good Rod)", 25, 35, ["Goldeen", "Magikarp", "Seaking"]),
    ("MT. SILVER", "Fishing (Super Rod)", 40, 55, ["Seaking", "Gyarados", "Dratini", "Dragonair", "Dragonite"]),
    ("MT. SILVER", "Rock Smash", 40, 50, ["Graveler", "Steelix", "Garganacl", "Onix", "Shuckle"]),
    ("MT. SILVER", "Hidden Rare", 48, 52, ["Larvitar"]),
]

enc_records = []
for loc_name, method, min_l, max_l, species_list in JOHTO_DATA:
    if method == "Tall Grass":
        chances = GRASS_CHANCES
    elif method == "Surfing":
        chances = WATER_CHANCES
    elif method == "Rock Smash":
        chances = SMASH_CHANCES
    elif method == "Fishing (Old Rod)":
        chances = [70, 30]
    elif method == "Fishing (Good Rod)":
        chances = [60, 20, 20]
    elif method == "Fishing (Super Rod)":
        chances = [40, 40, 15, 4, 1]
    elif method == "Hidden Rare":
        chances = [100]
    else:
        chances = [100]

    for idx, sp_name in enumerate(species_list):
        sp_id, official_name = find_sp(sp_name)
        ch = chances[idx] if idx < len(chances) else 1
        slot = idx + 1
        enc_records.append((
            "Johto", 40, 0, loc_name, method, slot, ch, min_l, max_l, sp_id, official_name
        ))

cur.executemany("INSERT INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?)", enc_records)
print(f"Inserted {len(enc_records)} Johto encounter rows across {len(set(r[3] for r in enc_records))} locations!")

# ==========================================
# 2. SPECIAL TRAINERS & BATTLE FRONTIER
# ==========================================
trainers_data = [
    # 7 BATTLE FRONTIER BRAINS (Silver & Gold Symbols)
    (
        "Battle Frontier Brain", "Noland", "Factory Head", "Battle Frontier", "Battle Factory",
        "Post-HoF: Win 20 consecutive battles for Silver, 41 for Gold.",
        "Silver: Random Rental Pool (Lv. 50/100, 31 IVs)\nGold: Random Rental Pool (Lv. 50/100, 31 IVs)",
        "Knowledge Symbol (Silver / Gold), 30 Battle Points, Ability Patch"
    ),
    (
        "Battle Frontier Brain", "Greta", "Arena Tycoon", "Battle Frontier", "Battle Arena",
        "Post-HoF: Win 27 consecutive battles for Silver, 55 for Gold.",
        "Silver: Heracross (Lv. 100), Umbreon (Lv. 100), Shedinja (Lv. 100)\nGold: Umbreon (Lv. 100), Gengar (Lv. 100), Breloom (Lv. 100)",
        "Guts Symbol (Silver / Gold), 30 Battle Points, Focus Sash"
    ),
    (
        "Battle Frontier Brain", "Tucker", "Dome Ace", "Battle Frontier", "Battle Dome",
        "Post-HoF: Win 4 consecutive tournaments (19 battles) for Silver, 9 tournaments for Gold.",
        "Silver: Swampert (Lv. 100), Salamence (Lv. 100), Charizard (Lv. 100)\nGold: Swampert (Lv. 100), Salamence (Lv. 100), Metagross (Lv. 100)",
        "Tactics Symbol (Silver / Gold), 30 Battle Points, Choice Band"
    ),
    (
        "Battle Frontier Brain", "Lucy", "Pike Queen", "Battle Frontier", "Battle Pike",
        "Post-HoF: Complete 28 rooms (2 runs) for Silver, 140 rooms (10 runs) for Gold.",
        "Silver: Seviper (Lv. 100), Milotic (Lv. 100), Shuckle (Lv. 100)\nGold: Seviper (Lv. 100), Milotic (Lv. 100), Steelix (Lv. 100)",
        "Luck Symbol (Silver / Gold), 30 Battle Points, Leftovers"
    ),
    (
        "Battle Frontier Brain", "Spenser", "Palace Maven", "Battle Frontier", "Battle Palace",
        "Post-HoF: Win 20 consecutive battles for Silver, 41 for Gold.",
        "Silver: Crobat (Lv. 100), Slaking (Lv. 100), Lapras (Lv. 100)\nGold: Arcanine (Lv. 100), Slaking (Lv. 100), Suicune (Lv. 100)",
        "Spirits Symbol (Silver / Gold), 30 Battle Points, Life Orb"
    ),
    (
        "Battle Frontier Brain", "Anabel", "Salon Maiden", "Battle Frontier", "Battle Tower",
        "Post-HoF: Win 34 consecutive battles for Silver, 69 for Gold.",
        "Silver: Alakazam (Lv. 100), Entei (Lv. 100), Snorlax (Lv. 100)\nGold: Raikou (Lv. 100), Latios (Lv. 100), Snorlax (Lv. 100)",
        "Ability Symbol (Silver / Gold), 30 Battle Points, Master Ball"
    ),
    (
        "Battle Frontier Brain", "Brandon", "Pyramid King", "Battle Frontier", "Battle Pyramid",
        "Post-HoF: Clear 21 floors (3 rounds) for Silver, 70 floors (10 rounds) for Gold.",
        "Silver: Regirock (Lv. 100), Regice (Lv. 100), Registeel (Lv. 100)\nGold: Articuno (Lv. 100), Zapdos (Lv. 100), Moltres (Lv. 100)",
        "Brave Symbol (Silver / Gold), 30 Battle Points, Gold Bottle Cap"
    ),

    # 8 HOENN GYM LEADER REMATCHES
    (
        "Gym Leader Rematch", "Roxanne", "Rustboro Gym Leader", "Hoenn", "Rustboro Gym",
        "Post-HoF: Talk to Roxanne in Rustboro Gym after registering in PokéNav.",
        "Golem (Lv. 67), Probopass (Lv. 68), Armaldo (Lv. 67), Cradily (Lv. 67), Gigalith (Lv. 68), Diancie (Lv. 70)",
        "$10,800, Hard Stone, Rock Gem"
    ),
    (
        "Gym Leader Rematch", "Brawly", "Dewford Gym Leader", "Hoenn", "Dewford Gym",
        "Post-HoF: Talk to Brawly in Dewford Gym.",
        "Hariyama (Lv. 67), Hitmonlee (Lv. 68), Hitmonchan (Lv. 68), Breloom (Lv. 68), Machamp (Lv. 69), Lucario (Lv. 70)",
        "$11,200, Black Belt, Muscle Band"
    ),
    (
        "Gym Leader Rematch", "Wattson", "Mauville Gym Leader", "Hoenn", "Mauville Gym",
        "Post-HoF: Talk to Wattson in Mauville Gym.",
        "Manectric (Lv. 68), Magnezone (Lv. 69), Electivire (Lv. 69), Ampharos (Lv. 68), Raichu (Lv. 68), Zapdos (Lv. 72)",
        "$11,520, Magnet, Cell Battery"
    ),
    (
        "Gym Leader Rematch", "Flannery", "Lavaridge Gym Leader", "Hoenn", "Lavaridge Gym",
        "Post-HoF: Talk to Flannery in Lavaridge Gym.",
        "Torkoal (Lv. 68), Magcargo (Lv. 68), Houndoom (Lv. 69), Arcanine (Lv. 69), Blaziken (Lv. 70), Heatran (Lv. 72)",
        "$11,520, Charcoal, Flame Orb"
    ),
    (
        "Gym Leader Rematch", "Norman", "Petalburg Gym Leader", "Hoenn", "Petalburg Gym",
        "Post-HoF: Talk to your father Norman in Petalburg Gym.",
        "Slaking (Lv. 70), Snorlax (Lv. 69), Kangaskhan (Lv. 69), Bouffalant (Lv. 68), Ursaluna (Lv. 71), Regigigas (Lv. 72)",
        "$12,000, Silk Scarf, Normal Gem"
    ),
    (
        "Gym Leader Rematch", "Winona", "Fortree Gym Leader", "Hoenn", "Fortree Gym",
        "Post-HoF: Talk to Winona in Fortree Gym.",
        "Altaria (Lv. 70), Skarmory (Lv. 69), Corviknight (Lv. 69), Swellow (Lv. 68), Dragonite (Lv. 71), Tornadus (Lv. 72)",
        "$12,000, Sharp Beak, Flying Gem"
    ),
    (
        "Gym Leader Rematch", "Tate & Liza", "Mossdeep Gym Leaders", "Hoenn", "Mossdeep Gym",
        "Post-HoF: Talk to Tate & Liza in Mossdeep Gym.",
        "Lunatone (Lv. 70), Solrock (Lv. 70), Claydol (Lv. 70), Xatu (Lv. 70), Gardevoir (Lv. 71), Gallade (Lv. 71)",
        "$13,000, Twisted Spoon, Light Clay"
    ),
    (
        "Gym Leader Rematch", "Juan", "Sootopolis Gym Leader", "Hoenn", "Sootopolis Gym",
        "Post-HoF: Talk to Juan in Sootopolis Gym.",
        "Kingdra (Lv. 71), Milotic (Lv. 70), Walrein (Lv. 70), Gyarados (Lv. 70), Crawdaunt (Lv. 70), Kyogre (Lv. 73)",
        "$13,500, Mystic Water, Damp Rock"
    ),

    # 8 JOHTO GYM LEADER REMATCHES
    (
        "Gym Leader Rematch", "Falkner", "Violet Gym Leader", "Johto", "Violet Gym",
        "Post-HoF: Talk to Falkner in Violet Gym.",
        "Pidgeot (Lv. 66), Noctowl (Lv. 67), Swellow (Lv. 67), Staraptor (Lv. 68), Corviknight (Lv. 69), Lugia (Lv. 72)",
        "$10,800, Sharp Beak, Flying Gem"
    ),
    (
        "Gym Leader Rematch", "Bugsy", "Azalea Gym Leader", "Johto", "Azalea Gym",
        "Post-HoF: Talk to Bugsy in Azalea Gym.",
        "Scizor (Lv. 68), Heracross (Lv. 68), Pinsir (Lv. 67), Forretress (Lv. 67), Volcarona (Lv. 70), Genesect (Lv. 72)",
        "$11,000, Silver Powder, Bug Gem"
    ),
    (
        "Gym Leader Rematch", "Whitney", "Goldenrod Gym Leader", "Johto", "Goldenrod Gym",
        "Post-HoF: Talk to Whitney in Goldenrod Gym.",
        "Miltank (Lv. 69), Blissey (Lv. 68), Clefable (Lv. 68), Wigglytuff (Lv. 67), Ursaring (Lv. 69), Slaking (Lv. 71)",
        "$11,500, Silk Scarf, Lucky Egg"
    ),
    (
        "Gym Leader Rematch", "Morty", "Ecruteak Gym Leader", "Johto", "Ecruteak Gym",
        "Post-HoF: Talk to Morty in Ecruteak Gym.",
        "Gengar (Lv. 70), Mismagius (Lv. 69), Drifblim (Lv. 68), Chandelure (Lv. 69), Dragapult (Lv. 71), Marshadow (Lv. 72)",
        "$12,000, Spell Tag, Dusk Stone"
    ),
    (
        "Gym Leader Rematch", "Chuck", "Cianwood Gym Leader", "Johto", "Cianwood Gym",
        "Post-HoF: Talk to Chuck in Cianwood Gym.",
        "Poliwrath (Lv. 69), Primeape (Lv. 68), Machamp (Lv. 69), Annihilape (Lv. 71), Conkeldurr (Lv. 70), Urshifu (Lv. 72)",
        "$12,000, Black Belt, Focus Band"
    ),
    (
        "Gym Leader Rematch", "Jasmine", "Olivine Gym Leader", "Johto", "Olivine Gym",
        "Post-HoF: Talk to Jasmine in Olivine Gym.",
        "Steelix (Lv. 71), Skarmory (Lv. 69), Magnezone (Lv. 69), Metagross (Lv. 70), Lucario (Lv. 70), Dialga (Lv. 73)",
        "$12,500, Metal Coat, Heavy-Duty Boots"
    ),
    (
        "Gym Leader Rematch", "Pryce", "Mahogany Gym Leader", "Johto", "Mahogany Gym",
        "Post-HoF: Talk to Pryce in Mahogany Gym.",
        "Mamoswine (Lv. 71), Weavile (Lv. 70), Dewgong (Lv. 69), Glaceon (Lv. 69), Baxcalibur (Lv. 72), Articuno (Lv. 72)",
        "$12,800, Never-Melt Ice, Icy Rock"
    ),
    (
        "Gym Leader Rematch", "Clair", "Blackthorn Gym Leader", "Johto", "Blackthorn Gym",
        "Post-HoF: Talk to Clair in Blackthorn Gym.",
        "Kingdra (Lv. 72), Dragonite (Lv. 72), Garchomp (Lv. 71), Salamence (Lv. 71), Dragapult (Lv. 72), Rayquaza (Lv. 74)",
        "$13,500, Dragon Fang, Dragon Gem"
    ),

    # LEGENDARY CHAMPIONS & MASTER BOSS TRAINERS
    (
        "Champion", "Red", "Living Legend", "Kanto", "Mt. Silver Peak",
        "Post-HoF & 16 Badges: Climb to the highest snow-covered peak of Mt. Silver.",
        "Pikachu (Lv. 88), Charizard (Lv. 84), Blastoise (Lv. 84), Venusaur (Lv. 84), Snorlax (Lv. 82), Lapras (Lv. 80)",
        "$17,600, Master Ball, Legend Ribbon"
    ),
    (
        "Champion", "Cynthia", "Sinnoh Champion", "Hoenn", "Meteor Falls Inner Sanctum",
        "Post-HoF: Defeat Steven Stone, then find Cynthia in the Waterfall Chamber.",
        "Spiritomb (Lv. 78), Garchomp (Lv. 82), Lucario (Lv. 78), Togekiss (Lv. 78), Milotic (Lv. 79), Roserade (Lv. 78)",
        "$16,400, Garchompite, Ability Patch"
    ),
    (
        "Champion", "Steven Stone", "Former Hoenn Champion", "Hoenn", "Meteor Falls Deep Cave",
        "Post-HoF: Surf and Waterfall to the deepest cavern of Meteor Falls.",
        "Skarmory (Lv. 77), Claydol (Lv. 75), Aggron (Lv. 76), Cradily (Lv. 76), Armaldo (Lv. 76), Metagross (Lv. 78)",
        "$15,600, Metagrossite, Beldum Egg"
    ),
    (
        "Champion", "Wallace", "Hoenn Champion", "Hoenn", "Ever Grande Pokémon League",
        "Hall of Fame: Reach the Champion chamber at Ever Grande City.",
        "Wailord (Lv. 76), Tentacruel (Lv. 76), Ludicolo (Lv. 76), Whiscash (Lv. 76), Gyarados (Lv. 77), Milotic (Lv. 79)",
        "$15,800, Champion Ribbon, Water Memory"
    ),
    (
        "Champion", "Leon", "Galar Champion", "Battle Frontier", "Battle Tower Pinnacle",
        "Post-HoF: Reach 50 wins in Master Class Battle Tower.",
        "Charizard (Lv. 80), Dragapult (Lv. 78), Aegislash (Lv. 78), Haxorus (Lv. 78), Seismitoad (Lv. 78), Rillaboom (Lv. 78)",
        "$16,000, Charizardite X, Gold Bottle Cap"
    ),
    (
        "Champion", "Nemona", "Paldea Champion", "Johto", "National Park Battle Pavilion",
        "Post-HoF: Win 5 Bug Catching Contests and challenge the Pavilion Ace.",
        "Meowscarada (Lv. 78), Pawmot (Lv. 76), Lycanroc (Lv. 76), Goodra (Lv. 76), Orthworm (Lv. 76), Kommo-o (Lv. 77)",
        "$15,500, Booster Energy, Loaded Dice"
    ),
    (
        "Champion", "Blue", "Former Kanto Champion", "Kanto", "Viridian Gym",
        "Post-HoF: Challenge the Viridian Gym Leader position.",
        "Pidgeot (Lv. 80), Alakazam (Lv. 78), Rhydon (Lv. 78), Gyarados (Lv. 78), Exeggutor (Lv. 78), Arcanine (Lv. 80)",
        "$16,000, Life Orb, Choice Scarf"
    ),

    # EVIL TEAM BOSSES
    (
        "Evil Team Boss", "Giovanni", "Team Rocket Boss", "Kanto", "Rocket Hideout Basement B4F",
        "Post-HoF: Infiltrate Rocket Hideout in Celadon / Mahogany.",
        "Nidoking (Lv. 75), Nidoqueen (Lv. 75), Kangaskhan (Lv. 76), Rhyperior (Lv. 76), Persian (Lv. 74), Garchomp (Lv. 77)",
        "$15,000, Kangaskhanite, Master Ball"
    ),
    (
        "Evil Team Boss", "Maxie", "Team Magma Leader", "Hoenn", "Magma Hideout (Mt. Chimney)",
        "Post-HoF: Return to Magma Hideout inside Jagged Pass.",
        "Camerupt (Lv. 76), Crobat (Lv. 74), Mightyena (Lv. 74), Weavile (Lv. 75), Houndoom (Lv. 75), Groudon (Lv. 78)",
        "$15,000, Cameruptite, Red Orb"
    ),
    (
        "Evil Team Boss", "Archie", "Team Aqua Leader", "Hoenn", "Aqua Hideout (Lilycove City)",
        "Post-HoF: Return to Aqua Hideout in Lilycove Cove.",
        "Sharpedo (Lv. 76), Crobat (Lv. 74), Mightyena (Lv. 74), Muk (Lv. 75), Ludicolo (Lv. 75), Kyogre (Lv. 78)",
        "$15,000, Sharpedonite, Blue Orb"
    ),
    (
        "Evil Team Boss", "Cyrus", "Team Galactic Boss", "Hoenn", "Cave of Origin Nether Region",
        "Post-HoF: Deepest floor of Cave of Origin after catching Rayquaza.",
        "Weavile (Lv. 78), Honchkrow (Lv. 76), Crobat (Lv. 76), Gyarados (Lv. 77), Houndoom (Lv. 77), Dialga (Lv. 80)",
        "$16,000, Adamant Crystal, Griseous Core"
    ),
    (
        "Evil Team Boss", "Ghetsis", "Team Plasma Boss", "Battle Frontier", "Abandoned Ship Sub-Level",
        "Post-HoF: Dive to the engine room of Abandoned Ship.",
        "Hydreigon (Lv. 78), Cofagrigus (Lv. 76), Seismitoad (Lv. 76), Eelektross (Lv. 76), Drapion (Lv. 76), Kyurem (Lv. 80)",
        "$16,000, DNA Splicers, Dark Memory"
    )
]

cur.executemany("""
INSERT INTO trainers (category, name, title, region, location, unlock_condition, team_preview, reward)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", trainers_data)
print(f"Inserted {len(trainers_data)} legendary trainers & Frontier Brains into trainers table!")

conn.commit()
conn.close()
print("Populate Johto & Trainers script complete!")
