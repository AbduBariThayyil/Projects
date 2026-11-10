#!/usr/bin/env bash
# Quick launcher for Pokémon Quetzal Master Pokédex & Encounter Explorer
cd /home/vibecoder/Projects
python3 quetzal_dex_gui.py "$@" > /dev/null 2>&1 &
