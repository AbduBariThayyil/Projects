#!/usr/bin/env python3
"""
OmniView CLI Symmetrical Terminal View
Catppuccin Mocha aesthetic with robust unicode-aware alignment.
Eliminates terminal jitter and misaligned borders across all fonts.
"""
import os
import re
import sys
import shutil
import unicodedata
from typing import List, Dict, Tuple, Optional, Any

# Catppuccin Mocha Palette (Truecolor ANSI)
MAUVE = "\033[38;2;203;166;247m"
BLUE = "\033[38;2;137;180;250m"
SAPPHIRE = "\033[38;2;116;199;236m"
GREEN = "\033[38;2;166;227;161m"
PEACH = "\033[38;2;250;179;135m"
YELLOW = "\033[38;2;249;226;175m"
RED = "\033[38;2;243;139;168m"
TEXT = "\033[38;2;205;214;244m"
SUBTEXT = "\033[38;2;166;173;200m"
SURFACE = "\033[38;2;88;91;112m"
OVERLAY = "\033[38;2;108;112;134m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def char_width(c: str) -> int:
    """Calculates display cell width of a character considering CJK and wide glyphs."""
    w = unicodedata.east_asian_width(c)
    return 2 if w in ("W", "F") else 1


def str_width(s: str) -> int:
    """Calculates visible display width of a string stripping ANSI codes."""
    clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", s)
    return sum(char_width(c) for c in clean)


def truncate_display(s: str, max_w: int, ellipsis: str = "…") -> str:
    """Truncates string to fit within max_w display cells."""
    if str_width(s) <= max_w:
        return s

    el_w = str_width(ellipsis)
    target = max(0, max_w - el_w)
    out = []
    w = 0
    for c in s:
        cw = char_width(c)
        if w + cw > target:
            break
        out.append(c)
        w += cw
    return "".join(out) + ellipsis


def pad_cell(text: str, target_width: int, align: str = "left") -> str:
    """Pads string to exact visible width (taking wide characters and ANSI codes into account)."""
    curr_w = str_width(text)
    pad = max(0, target_width - curr_w)
    if align == "right":
        return (" " * pad) + text
    elif align == "center":
        left = pad // 2
        right = pad - left
        return (" " * left) + text + (" " * right)
    return text + (" " * pad)


def print_banner(subtitle: str = "Universal Anime, Movies & TV Shows Media Suite"):
    """
    Renders clean, modern, symmetrical rule-based banner.
    Does not use fragile closed side-boxes to guarantee 100% horizontal alignment.
    """
    term_w = shutil.get_terminal_size((80, 24)).columns
    banner_w = min(74, max(54, term_w - 4))
    line = "─" * banner_w

    print(f"\n{SURFACE}{line}{RESET}")
    title_line = f"  {BOLD}{MAUVE}OmniView{RESET}  {SURFACE}•{RESET}  {TEXT}{subtitle}{RESET}"
    print(title_line)
    print(f"{SURFACE}{line}{RESET}\n")


def print_status_box(badge: str, message: str, color: str = SAPPHIRE):
    """Renders a clean status line with colored badge."""
    print(f" {color}{BOLD}[{badge}]{RESET} {TEXT}{message}{RESET}")


def render_table(
    headers: List[Tuple[str, int, str]],  # (label, width, align)
    rows: List[List[Tuple[str, str]]],     # List of [ (cell_text, cell_color), ... ]
) -> None:
    """
    Renders a pixel-perfect symmetrical Unicode box-drawing table.
    Every row's visible display width is mathematically aligned.
    """
    col_widths = [h[1] for h in headers]

    # Top border: ┌───────┬──────────────────────────────┬────────┐
    top_parts = ["─" * (w + 2) for w in col_widths]
    print(f"{SURFACE}┌" + "┬".join(top_parts) + f"┐{RESET}")

    # Header row
    hdr_cells = []
    for (label, width, align) in headers:
        formatted = pad_cell(f"{BOLD}{TEXT}{label}{RESET}", width, align)
        hdr_cells.append(f" {formatted} ")
    print(f"{SURFACE}│{RESET}" + f"{SURFACE}│{RESET}".join(hdr_cells) + f"{SURFACE}│{RESET}")

    # Header separator: ├───────┼──────────────────────────────┼────────┤
    mid_parts = ["─" * (w + 2) for w in col_widths]
    print(f"{SURFACE}├" + "┼".join(mid_parts) + f"┤{RESET}")

    # Rows
    for row in rows:
        row_cells = []
        for idx, (cell_content, cell_color) in enumerate(row):
            w = col_widths[idx]
            align = headers[idx][2]
            trunc = truncate_display(cell_content, w)
            colored = f"{cell_color}{trunc}{RESET}"
            padded = pad_cell(colored, w, align)
            row_cells.append(f" {padded} ")
        print(f"{SURFACE}│{RESET}" + f"{SURFACE}│{RESET}".join(row_cells) + f"{SURFACE}│{RESET}")

    # Bottom border: └───────┴──────────────────────────────┴────────┘
    bot_parts = ["─" * (w + 2) for w in col_widths]
    print(f"{SURFACE}└" + "┴".join(bot_parts) + f"┘{RESET}")


def render_search_results(items: List[Dict[str, Any]]) -> None:
    """
    Renders unified search results (Anime, Movies, TV Shows).
    Columns: NUM (4), TITLE (34), TYPE (11), EXTRA/YEAR (12)
    """
    headers = [
        ("NUM", 4, "center"),
        ("TITLE", 36, "left"),
        ("TYPE", 11, "center"),
        ("INFO", 11, "center"),
    ]

    rows = []
    for idx, item in enumerate(items, 1):
        media_type = item.get("type", "anime").lower()
        if media_type == "movie":
            type_label = "🎬 Movie"
            type_color = PEACH
            info = str(item.get("year", "N/A"))
        elif media_type == "tv":
            type_label = "📺 TV Show"
            type_color = SAPPHIRE
            info = str(item.get("year", "Series"))
        else:
            type_label = "🌸 Anime"
            type_color = MAUVE
            info = item.get("id", "Episode")

        rows.append([
            (str(idx), BOLD + TEXT),
            (item.get("title", "Unknown"), TEXT),
            (type_label, type_color),
            (info, SUBTEXT),
        ])

    render_table(headers, rows)


def render_action_bar(total_items: int, default_target: str = "Local MPV"):
    """Renders symmetrical actions prompt at bottom of selection."""
    print(f"\n {OVERLAY}Actions:{RESET}")
    print(
        f"  {BOLD}{SAPPHIRE}[1-{total_items}]{RESET} {SUBTEXT}Select Media{RESET}   "
        f"{BOLD}{PEACH}[l]{RESET} {SUBTEXT}Play Locally (MPV){RESET}   "
        f"{BOLD}{GREEN}[c]{RESET} {SUBTEXT}Cast to TV{RESET}   "
        f"{BOLD}{RED}[q]{RESET} {SUBTEXT}Quit{RESET}"
    )
    print(f"  {DIM}Target:{RESET} {BOLD}{TEXT}{default_target}{RESET}\n")


if __name__ == "__main__":
    # Test rendering
    print_banner()
    sample_items = [
        {"title": "Solo Leveling", "type": "anime", "id": "18742"},
        {"title": "Interstellar", "type": "movie", "year": "2014"},
        {"title": "Breaking Bad", "type": "tv", "year": "2008"},
        {"title": "進撃の巨人 (Attack on Titan)", "type": "anime", "id": "112"},
    ]
    render_search_results(sample_items)
    render_action_bar(len(sample_items))
