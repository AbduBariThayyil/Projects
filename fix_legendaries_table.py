import sqlite3

conn = sqlite3.connect("quetzal_database.db")
c = conn.cursor()

# Remove stray rows
c.execute("DELETE FROM legendaries WHERE name LIKE 'Slot %'")

# Synergies mapping
synergies = {
    "Galarian Articuno": "Kantonian Articuno + 4 Psychic-types",
    "Galarian Zapdos": "Kantonian Zapdos + 4 Fighting-types",
    "Galarian Moltres": "Kantonian Moltres + 4 Dark-types",
    "Mewtwo": "Mew + 5 Psychic-types",
    "Raikou": "Zapdos + 5 Electric-types",
    "Entei": "Moltres + 5 Fire-types",
    "Suicune": "Entei + Raikou + 4 Water-types",
    "Giratina": "Dialga + Palkia + Sinnoh Avatar",
    "Phione": "Breed Manaphy + Ditto (Day Care)",
    "Keldeo": "Cobalion + Terrakion + Virizion + Water-types",
    "Cosmoem": "Level Cosmog to 43",
    "Solgaleo / Lunala": "Cosmoem + Sun/Moon Stone",
    "Nihilego": "Cosmog + Alolan Rock/Poison",
    "Buzzwole": "Cosmog + Alolan Bug/Fighting",
    "Pheromosa": "Cosmog + Alolan Bug/Fighting",
    "Xurkitree": "Cosmog + Alolan Electric",
    "Celesteela": "Cosmog + Alolan Steel/Flying",
    "Kartana": "Cosmog + Alolan Grass/Steel",
    "Guzzlord": "Cosmog + Alolan Dark/Dragon",
    "Magearna": "5 Klink in Party",
    "Urshifu": "Scroll of Waters / Darkness on Kubfu",
    "Pecharunt": "Okidogi + Munkidori + Fezandipiti + 3 Poison-types",
    "Enamorus": "Tornadus + Thundurus + Landorus (Hisui)",
    "Poipole": "6 Different Poison-type Pokémon",
    "Blacephalon": "Cosmog + 5 Explosion/Self-Destruct Pokémon",
    "Arceus": "Complete Nat. Dex + Azure Flute + HoF Team",
    "Articuno": "Shoal Cave at Low Tide (Ice/Flying)",
    "Zapdos": "New Mauville (Electric/Flying)",
    "Moltres": "Mt. Chimney / Magma Hideout (Fire/Flying)",
    "Mew": "Faraway Island (Old Sea Map)",
    "Lugia": "Navel Rock (Mystic Ticket) / Whirl Islands",
    "Ho-Oh": "Navel Rock (Mystic Ticket) / Bell Tower",
    "Celebi": "Petalburg Woods (Post-HoF Grass Team)",
    "Regigigas": "Regirock + Regice + Registeel in Party",
    "Dialga": "Spear Pillar (Adamant Orb)",
    "Palkia": "Spear Pillar (Lustrous Orb)",
    "Heatran": "Fiery Path (Magma Stone)",
    "Cresselia": "Fullmoon Island / Meteor Falls Deep Cavern",
    "Darkrai": "Newmoon Island / Member Card",
    "Manaphy": "Route 105 Dive Patch (Water-types)",
    "Shaymin": "Flower Paradise / Route 123 (Oaks Letter)",
    "Victini": "Liberty Garden (Liberty Pass)",
    "Cobalion": "Route 115 (Mach Bike slope)",
    "Terrakion": "Meteor Falls (Waterfall + Strength)",
    "Virizion": "Petalburg Woods hidden glade",
    "Tornadus": "Route 119 (Roamer / Rain)",
    "Thundurus": "Route 119 (Roamer / Thunderstorm)",
    "Landorus": "Route 111 Desert (Tornadus + Thundurus)",
    "Reshiram": "Mirage Island / Dragon's Den (Light Stone)",
    "Zekrom": "Mirage Island / Dragon's Den (Dark Stone)",
    "Kyurem": "Shoal Cave (Reshiram + Zekrom)",
    "Genesect": "Weather Institute / New Mauville (Drives)",
    "Xerneas": "Route 119 (Fairy-types)",
    "Yveltal": "Mt. Pyre (Dark/Flying-types)",
    "Zygarde": "Granite Cave Deep Cavern (Zygarde Cell 100%)",
    "Diancie": "Shoal Cave (Carbink in party)",
    "Hoopa": "Mirage Island (Prison Bottle)",
    "Volcanion": "Lavaridge Gym hot springs (Fire + Water)",
    "Type: Null / Silvally": "Aether Paradise / Mossdeep Space Center",
    "Tapu Koko": "Route 110 (Electric Terrain)",
    "Tapu Lele": "Route 117 (Psychic Terrain)",
    "Tapu Bulu": "Safari Zone (Grassy Terrain)",
    "Tapu Fini": "Route 105 (Misty Terrain)",
    "Necrozma": "Shoal Cave deepest chamber",
    "Meltan / Melmetal": "New Mauville (Metal Coat)",
    "Zacian": "Victory Road (Rusted Sword)",
    "Zamazenta": "Victory Road (Rusted Shield)",
    "Eternatus": "Sky Pillar Peak (Post-Delta Story)",
    "Kubfu": "Dewford Dojo (Fighting-type trainer)",
    "Zarude": "Petalburg Woods (Dada Cape)",
    "Regieleki": "New Mauville ruins (Regi Trio)",
    "Regidrago": "Meteor Falls ruins (Regi Trio)",
    "Glastrier": "Route 116 (Iceroot Carrot)",
    "Spectrier": "Mt. Pyre (Shadowroot Carrot)",
    "Calyrex": "Route 116 / Crown Shrine (Wooden Crown)",
    "Wo-Chien": "Route 119 (Ominous Purple Stakes)",
    "Chien-Pao": "Shoal Cave (Ominous Yellow Stakes)",
    "Ting-Lu": "Route 111 Desert (Ominous Green Stakes)",
    "Chi-Yu": "Magma Hideout (Ominous Blue Stakes)",
    "Koraidon": "Meteor Falls crater (Sun team)",
    "Miraidon": "New Mauville core (Electric terrain)",
    "Walking Wake": "Route 105 (Suicune / Past Paradox)",
    "Iron Leaves": "Route 115 (Virizion / Future Paradox)",
    "Gouging Fire": "Fiery Path (Entei / Past Paradox)",
    "Raging Bolt": "Route 110 (Raikou / Past Paradox)",
    "Iron Boulder": "Meteor Falls (Terrakion / Future Paradox)",
    "Iron Crown": "New Mauville (Cobalion / Future Paradox)",
    "Terapagos": "Sealed Chamber deepest cave (Stellar Tera)",
    "Ogerpon": "Route 120 (Teal/Wellspring/Hearthflame Masks)",
    "Okidogi": "Route 111 Desert (Fighting/Poison)",
    "Munkidori": "Route 114 (Psychic/Poison)",
    "Fezandipiti": "Route 119 (Fairy/Poison)"
}

for name, syn in synergies.items():
    c.execute("UPDATE legendaries SET synergy = ? WHERE name = ?", (syn, name))

# Ensure no empty synergies remain
c.execute("UPDATE legendaries SET synergy = 'Standard Battle Encounter' WHERE synergy IS NULL OR synergy = ''")

conn.commit()

c.execute("SELECT COUNT(*) FROM legendaries")
print(f"Total clean legendaries: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM legendaries WHERE synergy IS NOT NULL AND synergy != ''")
print(f"Legendaries with synergy populated: {c.fetchone()[0]}")

conn.close()
