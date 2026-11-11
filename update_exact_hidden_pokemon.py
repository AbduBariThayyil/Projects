import sqlite3

DB_PATH = "quetzal_database.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# First delete any existing Hidden Rare entries in Hoenn
c.execute("DELETE FROM encounters WHERE region = 'Hoenn' AND method = 'Hidden Rare'")

hoenn_routes_hidden = [
    ("ROUTE 101", 954, "Vulpix"),
    ("ROUTE 102", 570, "Zorua"),
    ("ROUTE 103", 132, "Ditto"),
    ("ROUTE 104", 132, "Ditto"),
    ("ROUTE 105", 132, "Ditto"),
    ("ROUTE 106", 627, "Rufflet"),
    ("ROUTE 107", 629, "Vullaby"),
    ("ROUTE 108", 859, "Impidimp"),
    ("ROUTE 109", 39, "Jigglypuff"),
    ("ROUTE 110", 35, "Clefairy"),
    ("ROUTE 111", 371, "Bagon"),
    ("ROUTE 112", 216, "Teddiursa"),
    ("ROUTE 113", 207, "Gligar"),
    ("ROUTE 114", 701, "Hawlucha"),
    ("ROUTE 115", 449, "Hippopotas"),
    ("ROUTE 116", 551, "Sandile"),
    ("ROUTE 117", 1297, "Orthworm"),
    ("ROUTE 118", 343, "Baltoy"),
    ("ROUTE 119", 328, "Trapinch"),
    ("ROUTE 120", 443, "Gible"),
    ("ROUTE 121", 868, "Milcery"),
    ("ROUTE 122", 546, "Cottonee"),
    ("ROUTE 123", 764, "Comfey"),
    ("ROUTE 124", 25, "Pikachu"),
    ("ROUTE 125", 137, "Porygon"),
    ("ROUTE 126", 479, "Rotom"),
    ("ROUTE 127", 856, "Hatenna"),
    ("ROUTE 128", 1225, "Voltorb"),
    ("ROUTE 129", 722, "Rowlet"),
    ("ROUTE 130", 102, "Exeggcute"),
    ("ROUTE 131", 357, "Tropius"),
    ("ROUTE 132", 704, "Goomy"),
    ("ROUTE 133", 590, "Foongus"),
    ("ROUTE 134", 359, "Absol"),
    ("PETALBURG WOODS", 285, "Shroomish"),
    ("RUSTURF TUNNEL", 290, "Nincada"),
    ("GRANITE CAVE", 696, "Tyrunt"),
    ("METEOR FALLS", 371, "Bagon"),
    ("FIERY PATH", 324, "Torkoal"),
    ("JAGGED PASS", 322, "Numel"),
    ("MT. PYRE", 92, "Gastly"),
    ("SHOAL CAVE", 220, "Swinub"),
    ("NEW MAUVILLE", 479, "Rotom"),
    ("SAFARI ZONE", 113, "Chansey")
]

for loc, sp_id, sp_name in hoenn_routes_hidden:
    # Query typical level min/max from that route
    c.execute("SELECT MIN(min_level), MAX(max_level) FROM encounters WHERE location_name = ?", (loc,))
    row = c.fetchone()
    lmin = row[0] if (row and row[0]) else 3
    lmax = row[1] if (row and row[1]) else 5
    c.execute("""
        INSERT INTO encounters (region, map_group, map_num, location_name, method, slot, chance, min_level, max_level, species_id, species_name)
        VALUES ('Hoenn', 0, 0, ?, 'Hidden Rare', 1, 100, ?, ?, ?, ?)
    """, (loc, lmin, lmax, sp_id, sp_name))

conn.commit()

c.execute("SELECT location_name, species_id, species_name FROM encounters WHERE location_name IN ('ROUTE 101', 'ROUTE 102') AND method = 'Hidden Rare'")
for r in c.fetchall():
    print("VERIFIED:", r)

conn.close()
print("Exact Hidden Pokémon successfully committed!")
