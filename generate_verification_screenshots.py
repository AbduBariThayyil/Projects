#!/usr/bin/env python3
"""
generate_verification_screenshots.py - Captures crisp verification screenshots
for Retro Pokédex Evolution Chains and How To Get views.
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from pokedex_retro_view import PokedexRetroView

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    
    view = PokedexRetroView()
    view.setWindowTitle("Authentic GBA Pokédex View - Evos & How To Get")
    view.resize(1024, 680)
    view.show()

    # 1. Capture Evolution Chains tab (Eevee branching or Charmander)
    view.select_pokemon(133) # Eevee with 8 evolution branches
    view.show_evos_tab()
    app.processEvents()

    pix_evos = view.grab()
    evos_path = os.path.join("/home/vibecoder/Projects", "verify_gba_pokedex_evos.png")
    pix_evos.save(evos_path, "PNG")
    print(f"Saved: {evos_path} ({pix_evos.width()}x{pix_evos.height()})")

    # 2. Capture How To Get tab (Pikachu with multi-region wild encounters)
    view.select_pokemon(25) # Pikachu with Hoenn, Kanto, Johto wild spawns & pre-evo note
    view.show_how_to_get_tab()
    app.processEvents()

    pix_how = view.grab()
    how_path = os.path.join("/home/vibecoder/Projects", "verify_gba_pokedex_how_to_get.png")
    pix_how.save(how_path, "PNG")
    print(f"Saved: {how_path} ({pix_how.width()}x{pix_how.height()})")

    view.close()

if __name__ == "__main__":
    main()
