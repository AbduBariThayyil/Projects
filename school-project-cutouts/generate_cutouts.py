#!/usr/bin/env python3
import os
import subprocess

OUT_DIR = "/home/vibecoder/Projects/school-project-cutouts"
os.makedirs(OUT_DIR, exist_ok=True)

def svg_header(title, subtitle, width=800, height=1130):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}pt" height="{height}pt">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Fredoka+One&amp;family=Quicksand:wght@600;700&amp;display=swap');
      text {{ font-family: 'Fredoka One', 'Quicksand', 'Nunito', 'Segoe UI', Arial, sans-serif; }}
      .title {{ font-size: 24px; font-weight: bold; fill: #1E293B; text-anchor: middle; }}
      .subtitle {{ font-size: 14px; font-weight: 600; fill: #475569; text-anchor: middle; }}
      .cut-guide {{ stroke: #94A3B8; stroke-width: 1.8; stroke-dasharray: 6, 5; fill: none; }}
      .cut-text {{ font-size: 11px; fill: #64748B; font-weight: bold; }}
      .seat-guide {{ stroke: #94A3B8; stroke-width: 1.5; stroke-dasharray: 5, 4; fill: rgba(255,255,255,0.85); }}
      .seat-text {{ font-size: 11px; fill: #64748B; font-weight: bold; text-anchor: middle; }}
    </style>
  </defs>
  <!-- Background -->
  <rect width="{width}" height="{height}" fill="#FCFDFD" />
  
  <!-- Header Bar -->
  <rect x="25" y="15" width="{width - 50}" height="75" rx="14" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5" />
  <text x="{width / 2}" y="45" class="title">{title}</text>
  <text x="{width / 2}" y="72" class="subtitle">{subtitle}</text>
"""

def svg_footer():
    return "</svg>"

def scissors_icon(x, y, text="✂ cut"):
    return f"""<g transform="translate({x}, {y})">
      <text x="0" y="0" class="cut-text">{text}</text>
    </g>"""

# -------------------------------------------------------------
# 1. BOOKSHELVES (3 Empty Bookshelves)
# -------------------------------------------------------------
def generate_bookshelves_svg(color=True):
    header = svg_header(
        "Option 1: 3 Empty Bookshelves" + ("" if color else " (Coloring Version)"),
        "✂ Cut along dashed lines. Glue all 3 onto chart paper! (5 books will fit in each!)"
    )
    
    wood_outer = "#8D5B4C" if color else "#FFFFFF"
    wood_inner = "#FAF5EF" if color else "#FFFFFF"
    wood_shelf = "#A76F53" if color else "#FFFFFF"
    label_bg = "#FEF3C7" if color else "#FFFFFF"
    label_text = "#78350F" if color else "#0F172A"
    
    body = []
    shelf_w = 710
    shelf_h = 285
    start_y = 110
    gap_y = 335
    
    for i in range(3):
        y = start_y + i * gap_y
        body.append(f"""
        <!-- Bookshelf {i+1} Container with Dotted Cut Line -->
        <rect x="35" y="{y - 10}" width="730" height="{shelf_h + 20}" rx="14" class="cut-guide" />
        {scissors_icon(50, y + 6, f"✂ Cut Bookshelf #{i+1}")}
        
        <!-- Shelf Outer Frame -->
        <rect x="50" y="{y + 18}" width="{shelf_w}" height="{shelf_h - 10}" rx="12" fill="{wood_outer}" stroke="#1E293B" stroke-width="3" />
        
        <!-- Top Shelf Cavity -->
        <rect x="70" y="{y + 50}" width="{shelf_w - 40}" height="100" rx="6" fill="{wood_inner}" stroke="#CBD5E1" stroke-width="2" />
        
        <!-- Middle Shelf Board -->
        <rect x="60" y="{y + 150}" width="{shelf_w - 20}" height="20" rx="4" fill="{wood_shelf}" stroke="#1E293B" stroke-width="2.5" />
        
        <!-- Bottom Shelf Cavity -->
        <rect x="70" y="{y + 170}" width="{shelf_w - 40}" height="100" rx="6" fill="{wood_inner}" stroke="#CBD5E1" stroke-width="2" />
        
        <!-- Bottom Base Board -->
        <rect x="60" y="{y + 270}" width="{shelf_w - 20}" height="20" rx="4" fill="{wood_shelf}" stroke="#1E293B" stroke-width="2.5" />
        
        <!-- Name Badge -->
        <rect x="290" y="{y + 22}" width="220" height="24" rx="12" fill="{label_bg}" stroke="#1E293B" stroke-width="1.5" />
        <text x="400" y="{y + 39}" font-size="13" font-weight="bold" fill="{label_text}" text-anchor="middle">📚 Bookshelf #{i+1} (Glue 5 books here)</text>
        """)
        
    return header + "\n".join(body) + svg_footer()


# -------------------------------------------------------------
# 2. 15 SMALL BOOKS
# -------------------------------------------------------------
BOOK_THEMES = [
    ("Star", "#EF476F", "#FFD166", "★"),
    ("Heart", "#F72585", "#FFCCD5", "♥"),
    ("Sun", "#FFB703", "#FFE8D6", "☀"),
    ("Music", "#06D6A0", "#C7F9CC", "♫"),
    ("Rocket", "#118AB2", "#A2D2FF", "🚀"),
    ("Flower", "#FB8500", "#FFE5D9", "✿"),
    ("Apple", "#D90429", "#FFCCD5", "🍎"),
    ("Cat", "#8338EC", "#E0AAFF", "🐱"),
    ("Smile", "#3A86FF", "#BEE9E8", "☺"),
    ("Tree", "#2B9348", "#D8F3DC", "🌲"),
    ("Moon", "#5A189A", "#E0AAFF", "☾"),
    ("Pencil", "#E76F51", "#F4A261", "✎"),
    ("Fish", "#0077B6", "#90E0EF", "🐟"),
    ("Cloud", "#48CAE4", "#CAF0F8", "☁"),
    ("Rainbow", "#FF006E", "#FFBE0B", "🌈")
]

def generate_books_svg(color=True):
    header = svg_header(
        "Option 1: 15 Small Books" + ("" if color else " (Coloring Version)"),
        "✂ Cut along dashed rectangles. Divide equally: 15 ÷ 3 = 5 books on each shelf!"
    )
    
    cols = 5
    rows = 3
    box_w = 138
    box_h = 320
    start_x = 45
    start_y = 110
    gap_x = 146
    gap_y = 330
    
    body = []
    
    for idx, (title, c_main, c_sec, symbol) in enumerate(BOOK_THEMES):
        col = idx % cols
        row = idx // cols
        bx = start_x + col * gap_x
        by = start_y + row * gap_y
        
        c_fill = c_main if color else "#FFFFFF"
        c_spine = c_sec if color else "#F1F5F9"
        symbol_fill = "#FFFFFF" if color else "#1E293B"
        text_color = "#FFFFFF" if color else "#0F172A"
        
        bw = 96
        bh = 240
        cx = bx + (box_w - bw) / 2
        cy = by + 32
        
        body.append(f"""
        <!-- Book #{idx+1} Cutout Cell -->
        <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="8" class="cut-guide" />
        {scissors_icon(bx + 8, by + 18, f"✂ Book #{idx+1}")}
        
        <!-- Book Body -->
        <rect x="{cx}" y="{cy}" width="{bw}" height="{bh}" rx="8" fill="{c_fill}" stroke="#1E293B" stroke-width="2.5" />
        
        <!-- Spine Stripe -->
        <rect x="{cx}" y="{cy}" width="18" height="{bh}" rx="4" fill="{c_spine}" stroke="#1E293B" stroke-width="2" />
        
        <!-- Spine Stitch Marks -->
        <line x1="{cx + 5}" y1="{cy + 25}" x2="{cx + 13}" y2="{cy + 25}" stroke="#1E293B" stroke-width="2" />
        <line x1="{cx + 5}" y1="{cy + bh - 25}" x2="{cx + 13}" y2="{cy + bh - 25}" stroke="#1E293B" stroke-width="2" />
        
        <!-- Book Cover Emblem Box -->
        <rect x="{cx + 25}" y="{cy + 25}" width="{bw - 32}" height="75" rx="8" fill="rgba(255,255,255,0.25)" stroke="#1E293B" stroke-width="1.8" />
        <text x="{cx + 25 + (bw - 32)/2}" y="{cy + 75}" font-size="34" text-anchor="middle" fill="{symbol_fill}">{symbol}</text>
        
        <!-- Book Title Label -->
        <rect x="{cx + 24}" y="{cy + 120}" width="{bw - 30}" height="55" rx="6" fill="rgba(255,255,255,0.95)" stroke="#1E293B" stroke-width="1.5" />
        <text x="{cx + 24 + (bw - 30)/2}" y="{cy + 143}" font-size="13" font-weight="bold" fill="#0F172A" text-anchor="middle">{title}</text>
        <text x="{cx + 24 + (bw - 30)/2}" y="{cy + 162}" font-size="11" font-weight="bold" fill="#64748B" text-anchor="middle">Book #{idx+1}</text>
        
        <!-- Bookmark Ribbon -->
        <polygon points="{cx + bw - 24},{cy} {cx + bw - 8},{cy} {cx + bw - 8},{cy + 35} {cx + bw - 16},{cy + 26} {cx + bw - 24},{cy + 35}" fill="#FFD166" stroke="#1E293B" stroke-width="1.5" />
        """)
        
    return header + "\n".join(body) + svg_footer()


# -------------------------------------------------------------
# 3. 4 EMPTY CARS
# -------------------------------------------------------------
CAR_COLORS = [
    ("Red Cruiser", "#E63946", "#F1FAEE", "#1D3557"),
    ("Blue Buggy", "#3A86FF", "#E0F2FE", "#03045E"),
    ("Sunny Van", "#FFB703", "#FEF3C7", "#78350F"),
    ("Green Wagon", "#2A9D8F", "#D1FAE5", "#264653")
]

def generate_cars_svg(color=True):
    header = svg_header(
        "Option 2: 4 Empty Cars" + ("" if color else " (Coloring Version)"),
        "✂ Cut along dashed cards. Glue 2 passengers in each car! (8 ÷ 4 = 2)"
    )
    
    body = []
    card_w = 345
    card_h = 470
    positions = [
        (40, 110),
        (415, 110),
        (40, 610),
        (415, 610)
    ]
    
    for idx, (car_name, c_main, c_glass, c_dark) in enumerate(CAR_COLORS):
        bx, by = positions[idx]
        
        car_body = c_main if color else "#FFFFFF"
        window_bg = c_glass if color else "#FFFFFF"
        tire_color = "#2B2D42" if color else "#FFFFFF"
        rim_color = "#E5E7EB" if color else "#FFFFFF"
        
        cx = bx + 20
        cy = by + 90
        
        body.append(f"""
        <!-- Car #{idx+1} Cutout Card -->
        <rect x="{bx}" y="{by}" width="{card_w}" height="{card_h}" rx="14" class="cut-guide" />
        {scissors_icon(bx + 14, by + 22, f"✂ Cut Car #{idx+1}: {car_name}")}
        
        <!-- Car Badge Title -->
        <rect x="{bx + 60}" y="{by + 35}" width="{card_w - 120}" height="28" rx="14" fill="{c_main if color else '#F1F5F9'}" stroke="#1E293B" stroke-width="1.5" />
        <text x="{bx + card_w/2}" y="{by + 54}" font-size="14" font-weight="bold" fill="{'#FFFFFF' if color else '#0F172A'}" text-anchor="middle">Car #{idx+1}: {car_name}</text>
        
        <!-- CAR DRAWING -->
        <g transform="translate({cx}, {cy})">
          <!-- Car Cabin / Roof Top -->
          <path d="M 45 140 Q 60 40 120 35 L 205 35 Q 260 40 270 140 Z" fill="{car_body}" stroke="#1E293B" stroke-width="3" />
          
          <!-- Large Windows / Passenger Area with Designated Cut/Paste Targets -->
          <rect x="68" y="48" width="80" height="82" rx="10" fill="{window_bg}" stroke="#1E293B" stroke-width="2" />
          <rect x="162" y="48" width="80" height="82" rx="10" fill="{window_bg}" stroke="#1E293B" stroke-width="2" />
          
          <!-- Seat 1 and Seat 2 dotted targets -->
          <rect x="74" y="54" width="68" height="70" rx="6" class="seat-guide" />
          <text x="108" y="88" class="seat-text">Person 1</text>
          <text x="108" y="104" font-size="10" fill="#64748B" font-weight="bold" text-anchor="middle">Glue here</text>
          
          <rect x="168" y="54" width="68" height="70" rx="6" class="seat-guide" />
          <text x="202" y="88" class="seat-text">Person 2</text>
          <text x="202" y="104" font-size="10" fill="#64748B" font-weight="bold" text-anchor="middle">Glue here</text>

          <!-- Main Lower Car Body -->
          <rect x="10" y="130" width="285" height="75" rx="20" fill="{car_body}" stroke="#1E293B" stroke-width="3" />
          
          <!-- Headlights -->
          <circle cx="288" cy="155" r="12" fill="{'#FFD166' if color else '#FFFFFF'}" stroke="#1E293B" stroke-width="2" />
          <circle cx="17" cy="155" r="10" fill="{'#EF476F' if color else '#FFFFFF'}" stroke="#1E293B" stroke-width="2" />
          
          <!-- Door line and handles -->
          <line x1="152" y1="130" x2="152" y2="195" stroke="#1E293B" stroke-width="2.5" />
          <rect x="130" y="145" width="16" height="5" rx="2" fill="#1E293B" />
          <rect x="160" y="145" width="16" height="5" rx="2" fill="#1E293B" />
          
          <!-- Wheels & Hubcaps -->
          <circle cx="65" cy="205" r="32" fill="{tire_color}" stroke="#1E293B" stroke-width="3" />
          <circle cx="65" cy="205" r="18" fill="{rim_color}" stroke="#1E293B" stroke-width="2" />
          <circle cx="65" cy="205" r="6" fill="#1E293B" />
          
          <circle cx="240" cy="205" r="32" fill="{tire_color}" stroke="#1E293B" stroke-width="3" />
          <circle cx="240" cy="205" r="18" fill="{rim_color}" stroke="#1E293B" stroke-width="2" />
          <circle cx="240" cy="205" r="6" fill="#1E293B" />
        </g>
        
        <!-- Helpful Math Note -->
        <rect x="{bx + 50}" y="{by + card_h - 40}" width="{card_w - 100}" height="24" rx="6" fill="#F8FAFC" stroke="#E2E8F0" stroke-width="1" />
        <text x="{bx + card_w/2}" y="{by + card_h - 24}" font-size="12" font-weight="bold" fill="#475569" text-anchor="middle">Seats 2 passengers (8 ÷ 4 = 2)</text>
        """)
        
    return header + "\n".join(body) + svg_footer()


# -------------------------------------------------------------
# 4. 8 SMALL PEOPLE
# -------------------------------------------------------------
KIDS_PROFILES = [
    ("Leo", "#F97316", "#3B82F6", "#4A2810", "short"),
    ("Mia", "#EC4899", "#8B5CF6", "#FBBF24", "pigtails"),
    ("Sam", "#10B981", "#1E293B", "#1F2937", "curly"),
    ("Zoe", "#F59E0B", "#06B6D4", "#6B21A8", "headband"),
    ("Max", "#EF4444", "#3B82F6", "#78350F", "cap"),
    ("Ava", "#8B5CF6", "#10B981", "#1E293B", "buns"),
    ("Ben", "#06B6D4", "#F97316", "#92400E", "glasses"),
    ("Lily", "#F43F5E", "#EAB308", "#C2410C", "ponytail")
]

def generate_people_svg(color=True):
    header = svg_header(
        "Option 2: 8 Small People" + ("" if color else " (Coloring Version)"),
        "✂ Cut along dashed boxes. Glue 2 people into each of the 4 cars! (8 ÷ 4 = 2)"
    )
    
    cols = 4
    rows = 2
    box_w = 170
    box_h = 475
    start_x = 35
    start_y = 110
    gap_x = 185
    gap_y = 505
    
    body = []
    
    for idx, (name, shirt_c, pants_c, hair_c, hair_style) in enumerate(KIDS_PROFILES):
        col = idx % cols
        row = idx // cols
        bx = start_x + col * gap_x
        by = start_y + row * gap_y
        
        skin = "#FFDFC4" if color else "#FFFFFF"
        hair = hair_c if color else "#FFFFFF"
        shirt = shirt_c if color else "#FFFFFF"
        pants = pants_c if color else "#FFFFFF"
        shoes = "#1E293B" if color else "#FFFFFF"
        blush = "#FFB4A2" if color else "#FFFFFF"
        
        cx = bx + box_w / 2
        cy = by + 90
        
        hair_svg = ""
        if hair_style == "short":
            hair_svg = f"""
            <path d="M -32 45 Q -25 15 0 15 Q 25 15 32 45 C 20 28 0 26 -32 45 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <polygon points="-5,15 0,6 5,15" fill="{hair}" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "pigtails":
            hair_svg = f"""
            <path d="M -32 45 Q -25 18 0 18 Q 25 18 32 45 C 20 30 0 28 -32 45 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <circle cx="-38" cy="40" r="14" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="38" cy="40" r="14" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="-30" cy="40" r="4" fill="#EC4899" />
            <circle cx="30" cy="40" r="4" fill="#EC4899" />
            """
        elif hair_style == "curly":
            hair_svg = f"""
            <circle cx="-20" cy="24" r="14" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="0" cy="18" r="15" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="20" cy="24" r="14" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="-30" cy="38" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="30" cy="38" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "headband":
            hair_svg = f"""
            <path d="M -33 50 Q -25 18 0 18 Q 25 18 33 50 C 20 32 0 30 -33 50 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <path d="M -31 46 Q 0 25 31 46" fill="none" stroke="#EC4899" stroke-width="5" />
            <circle cx="-24" cy="38" r="6" fill="#FBBF24" />
            """
        elif hair_style == "cap":
            hair_svg = f"""
            <path d="M -30 42 Q 0 10 30 42 Z" fill="#EF4444" stroke="#334155" stroke-width="2.5" />
            <path d="M -5 38 L 42 34 L 38 45 L -2 46 Z" fill="#DC2626" stroke="#334155" stroke-width="2" />
            <circle cx="0" cy="22" r="3" fill="#FFFFFF" />
            """
        elif hair_style == "buns":
            hair_svg = f"""
            <path d="M -32 46 Q 0 22 32 46 C 20 32 0 32 -32 46 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <circle cx="-22" cy="14" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="22" cy="14" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "glasses":
            hair_svg = f"""
            <path d="M -32 45 Q -20 18 0 18 Q 20 18 32 45 C 15 28 0 28 -32 45 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <rect x="-21" y="40" width="18" height="15" rx="3" fill="none" stroke="#3B82F6" stroke-width="2.5" />
            <rect x="3" y="40" width="18" height="15" rx="3" fill="none" stroke="#3B82F6" stroke-width="2.5" />
            <line x1="-3" y1="47" x2="3" y2="47" stroke="#3B82F6" stroke-width="2.5" />
            """
        elif hair_style == "ponytail":
            hair_svg = f"""
            <path d="M -32 46 Q -25 18 0 18 Q 25 18 32 46 C 20 30 0 28 -32 46 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <path d="M 25 35 Q 46 25 45 60 Q 35 50 25 45 Z" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="26" cy="38" r="4" fill="#3B82F6" />
            """

        body.append(f"""
        <!-- Kid #{idx+1}: {name} Cutout Cell -->
        <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="12" class="cut-guide" />
        {scissors_icon(bx + 12, by + 18, f"✂ #{idx+1}: {name}")}
        
        <!-- Name Badge -->
        <rect x="{bx + 35}" y="{by + 32}" width="{box_w - 70}" height="24" rx="12" fill="{'#F1F5F9' if color else '#FFFFFF'}" stroke="#334155" stroke-width="1.5" />
        <text x="{cx}" y="{by + 48}" font-size="13" font-weight="bold" fill="#0F172A" text-anchor="middle">{name}</text>
        
        <!-- KID ILLUSTRATION -->
        <g transform="translate({cx}, {cy})">
          <!-- Waving Left Arm -->
          <path d="M -24 95 Q -45 65 -40 45" stroke="#334155" stroke-width="10" stroke-linecap="round" fill="none" />
          <circle cx="-40" cy="45" r="7" fill="{skin}" stroke="#334155" stroke-width="2" />
          
          <!-- Right Arm By Side -->
          <path d="M 24 95 Q 40 120 35 135" stroke="#334155" stroke-width="10" stroke-linecap="round" fill="none" />
          <circle cx="35" cy="135" r="7" fill="{skin}" stroke="#334155" stroke-width="2" />

          <!-- Legs & Shoes -->
          <rect x="-18" y="150" width="14" height="75" rx="5" fill="{pants}" stroke="#334155" stroke-width="2.5" />
          <ellipse cx="-11" cy="225" rx="12" ry="7" fill="{shoes}" stroke="#334155" stroke-width="2" />
          <rect x="4" y="150" width="14" height="75" rx="5" fill="{pants}" stroke="#334155" stroke-width="2.5" />
          <ellipse cx="11" cy="225" rx="12" ry="7" fill="{shoes}" stroke="#334155" stroke-width="2" />
          
          <!-- Torso / Shirt -->
          <path d="M -26 90 L 26 90 L 22 155 L -22 155 Z" fill="{shirt}" stroke="#334155" stroke-width="2.5" />
          <rect x="-8" y="70" width="16" height="22" rx="4" fill="{skin}" stroke="#334155" stroke-width="2" />
          
          <circle cx="0" cy="115" r="4" fill="{'#FFFFFF' if color else '#334155'}" />
          <circle cx="0" cy="132" r="4" fill="{'#FFFFFF' if color else '#334155'}" />

          <!-- Head -->
          <circle cx="0" cy="50" r="32" fill="{skin}" stroke="#334155" stroke-width="2.5" />
          
          <!-- Ears -->
          <circle cx="-32" cy="52" r="6" fill="{skin}" stroke="#334155" stroke-width="2" />
          <circle cx="32" cy="52" r="6" fill="{skin}" stroke="#334155" stroke-width="2" />
          
          <!-- Cheerful Eyes -->
          <circle cx="-11" cy="48" r="4" fill="#1E293B" />
          <circle cx="11" cy="48" r="4" fill="#1E293B" />
          <circle cx="-9.5" cy="46" r="1.5" fill="#FFFFFF" />
          <circle cx="12.5" cy="46" r="1.5" fill="#FFFFFF" />
          
          <!-- Blush -->
          <ellipse cx="-18" cy="56" rx="5" ry="3" fill="{blush}" />
          <ellipse cx="18" cy="56" rx="5" ry="3" fill="{blush}" />
          
          <!-- Smile -->
          <path d="M -9 60 Q 0 70 9 60" fill="none" stroke="#1E293B" stroke-width="2.5" stroke-linecap="round" />
          
          {hair_svg}
        </g>
        
        <text x="{cx}" y="{by + box_h - 18}" font-size="11" font-weight="bold" fill="#64748B" text-anchor="middle">Passenger #{idx+1}</text>
        """)
        
    return header + "\n".join(body) + svg_footer()


# -------------------------------------------------------------
# MAIN BUILD & RENDER
# -------------------------------------------------------------
def main():
    pages = [
        ("option1_bookshelves_color.svg", generate_bookshelves_svg(color=True)),
        ("option1_bookshelves_bw.svg", generate_bookshelves_svg(color=False)),
        ("option1_books_color.svg", generate_books_svg(color=True)),
        ("option1_books_bw.svg", generate_books_svg(color=False)),
        ("option2_cars_color.svg", generate_cars_svg(color=True)),
        ("option2_cars_bw.svg", generate_cars_svg(color=False)),
        ("option2_people_color.svg", generate_people_svg(color=True)),
        ("option2_people_bw.svg", generate_people_svg(color=False))
    ]
    
    for filename, content in pages:
        svg_path = os.path.join(OUT_DIR, filename)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated {svg_path}")
        
        pdf_path = svg_path.replace(".svg", ".pdf")
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf_path, svg_path], check=True)
        
        png_path = svg_path.replace(".svg", ".png")
        subprocess.run(["rsvg-convert", "-f", "png", "-d", "200", "-p", "200", "-o", png_path, svg_path], check=True)
        print(f"Rendered {pdf_path} and {png_path}")

    # Combine PDFs using pdfunite
    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option1_bookshelves_color.pdf"),
        os.path.join(OUT_DIR, "option1_books_color.pdf"),
        os.path.join(OUT_DIR, "Option1_Bookshelves_and_Books_Color.pdf")
    ], check=True)

    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option1_bookshelves_bw.pdf"),
        os.path.join(OUT_DIR, "option1_books_bw.pdf"),
        os.path.join(OUT_DIR, "Option1_Bookshelves_and_Books_BW.pdf")
    ], check=True)

    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option2_cars_color.pdf"),
        os.path.join(OUT_DIR, "option2_people_color.pdf"),
        os.path.join(OUT_DIR, "Option2_Cars_and_People_Color.pdf")
    ], check=True)

    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option2_cars_bw.pdf"),
        os.path.join(OUT_DIR, "option2_people_bw.pdf"),
        os.path.join(OUT_DIR, "Option2_Cars_and_People_BW.pdf")
    ], check=True)

    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option1_bookshelves_color.pdf"),
        os.path.join(OUT_DIR, "option1_books_color.pdf"),
        os.path.join(OUT_DIR, "option2_cars_color.pdf"),
        os.path.join(OUT_DIR, "option2_people_color.pdf"),
        os.path.join(OUT_DIR, "Complete_School_Project_All_Options_Color.pdf")
    ], check=True)

    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option1_bookshelves_bw.pdf"),
        os.path.join(OUT_DIR, "option1_books_bw.pdf"),
        os.path.join(OUT_DIR, "option2_cars_bw.pdf"),
        os.path.join(OUT_DIR, "option2_people_bw.pdf"),
        os.path.join(OUT_DIR, "Complete_School_Project_All_Options_BW.pdf")
    ], check=True)

    print("All combined PDFs generated successfully!")

if __name__ == "__main__":
    main()
