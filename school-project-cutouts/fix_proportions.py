import os
import subprocess

OUT_DIR = "/home/vibecoder/Projects/school-project-cutouts"
DOWNLOADS = "/home/vibecoder/Downloads"

# -------------------------------------------------------------
# SVG Common Helpers (ZERO TEXT)
# -------------------------------------------------------------
def svg_wrapper(content, width=800, height=1130):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}pt" height="{height}pt">
  <defs>
    <style>
      .cut-guide {{ stroke: #A0AEC0; stroke-width: 2; stroke-dasharray: 8, 6; fill: none; }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" fill="#FFFFFF" />
  {content}
</svg>"""

# -------------------------------------------------------------
# 1. OPTION 1: 3 EMPTY BOOKSHELVES (NO TEXT, VIBRANT WOOD)
# -------------------------------------------------------------
def generate_bookshelves_svg():
    body = []
    shelf_w = 730
    shelf_h = 320
    start_y = 40
    gap_y = 360
    
    wood_colors = [
        ("#8D5B4C", "#A76F53", "#FFF8EE"), # Classic Warm Cedar
        ("#795548", "#9C786C", "#FFF3E0"), # Honey Oak
        ("#6D4C41", "#8D6E63", "#EFEBE9")  # Rich Mahogany
    ]
    
    for i in range(3):
        y = start_y + i * gap_y
        c_outer, c_trim, c_inner = wood_colors[i]
        
        body.append(f"""
        <!-- Bookshelf {i+1} Dotted Cut Box -->
        <rect x="25" y="{y}" width="750" height="{shelf_h}" rx="16" class="cut-guide" />
        
        <!-- Bookshelf Outer Frame -->
        <rect x="40" y="{y + 15}" width="{shelf_w}" height="{shelf_h - 30}" rx="14" fill="{c_outer}" stroke="#2D3748" stroke-width="3.5" />
        
        <!-- Big Open Shelf Interior (220px high - plenty of room for books) -->
        <rect x="60" y="{y + 35}" width="{shelf_w - 40}" height="220" rx="8" fill="{c_inner}" stroke="#CBD5E1" stroke-width="2" />
        
        <!-- Solid Base Shelf Board -->
        <rect x="50" y="{y + 255}" width="{shelf_w - 20}" height="25" rx="4" fill="{c_trim}" stroke="#2D3748" stroke-width="3" />
        
        <!-- Top Crown Molding -->
        <rect x="35" y="{y + 12}" width="{shelf_w + 10}" height="18" rx="6" fill="{c_trim}" stroke="#2D3748" stroke-width="2.5" />
        """)
        
    return svg_wrapper("\n".join(body))


# -------------------------------------------------------------
# 2. OPTION 1: 15 SMALL BOOKS (SUPER COLORFUL, ZERO TEXT)
# Sized 55px wide x 160px tall. Fits in 220px tall shelves!
# -------------------------------------------------------------
VIBRANT_BOOK_STYLES = [
    ("#FF1654", "#FFE600", "star"),      # Hot Pink & Yellow Star
    ("#3A86FF", "#FFBE0B", "stripe"),    # Electric Blue & Gold
    ("#06D6A0", "#118AB2", "circle"),    # Mint Emerald & Teal
    ("#FF5400", "#FFD166", "heart"),     # Vivid Orange & Sunshine
    ("#9B5DE5", "#F15BB5", "star"),      # Bright Purple & Magenta
    ("#00F5D4", "#7B2CBF", "stripe"),    # Bright Turquoise & Violet
    ("#F72585", "#7209B7", "heart"),     # Neon Pink & Purple
    ("#38B000", "#CCFF33", "circle"),    # Lime & Neon Green
    ("#FFB703", "#FB8500", "stripe"),    # Amber & Orange
    ("#E63946", "#A8DADC", "star"),      # Ruby & Sky Blue
    ("#4361EE", "#4CC9F0", "heart"),     # Royal Blue & Cyan
    ("#D81159", "#FFBC42", "stripe"),    # Crimson & Goldenrod
    ("#8F2D56", "#218380", "circle"),    # Berry & Sea Green
    ("#7209B7", "#F72585", "star"),      # Deep Purple & Hot Pink
    ("#2EC4B6", "#FF9F1C", "stripe")     # Aqua & Tangerine
]

def generate_books_svg():
    cols = 5
    rows = 3
    box_w = 140
    box_h = 330
    start_x = 40
    start_y = 50
    gap_x = 148
    gap_y = 350
    
    body = []
    bw = 62
    bh = 175
    
    for idx, (c_main, c_sec, pattern) in enumerate(VIBRANT_BOOK_STYLES):
        col = idx % cols
        row = idx // cols
        bx = start_x + col * gap_x
        by = start_y + row * gap_y
        
        cx = bx + (box_w - bw) / 2
        cy = by + (box_h - bh) / 2
        
        pattern_svg = ""
        if pattern == "star":
            pattern_svg = f"""
            <polygon points="{cx + bw/2},{cy + 55} {cx + bw/2 + 12},{cy + 85} {cx + bw/2 + 40},{cy + 87} {cx + bw/2 + 16},{cy + 104} {cx + bw/2 + 25},{cy + 132} {cx + bw/2},{cy + 114} {cx + bw/2 - 25},{cy + 132} {cx + bw/2 - 16},{cy + 104} {cx + bw/2 - 40},{cy + 87} {cx + bw/2 - 12},{cy + 85}" fill="{c_sec}" stroke="#2D3748" stroke-width="2" transform="scale(0.55) translate({cx + 12}, {cy - 10})" />
            """
        elif pattern == "heart":
            pattern_svg = f"""
            <path d="M {cx + bw/2} {cy + 92} C {cx + bw/2 - 25} {cy + 60}, {cx + bw/2 - 25} {cy + 40}, {cx + bw/2} {cy + 58} C {cx + bw/2 + 25} {cy + 40}, {cx + bw/2 + 25} {cy + 60}, {cx + bw/2} {cy + 92} Z" fill="{c_sec}" stroke="#2D3748" stroke-width="2" />
            """
        elif pattern == "stripe":
            pattern_svg = f"""
            <rect x="{cx + 16}" y="{cy + 45}" width="{bw - 18}" height="14" fill="{c_sec}" stroke="#2D3748" stroke-width="1.5" />
            <rect x="{cx + 16}" y="{cy + 75}" width="{bw - 18}" height="14" fill="{c_sec}" stroke="#2D3748" stroke-width="1.5" />
            <rect x="{cx + 16}" y="{cy + 105}" width="{bw - 18}" height="14" fill="{c_sec}" stroke="#2D3748" stroke-width="1.5" />
            """
        elif pattern == "circle":
            pattern_svg = f"""
            <circle cx="{cx + bw/2 + 4}" cy="{cy + 60}" r="14" fill="{c_sec}" stroke="#2D3748" stroke-width="2" />
            <circle cx="{cx + bw/2 + 4}" cy="{cy + 105}" r="14" fill="{c_sec}" stroke="#2D3748" stroke-width="2" />
            """
            
        body.append(f"""
        <!-- Book Cutout Dotted Box -->
        <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="12" class="cut-guide" />
        
        <!-- Book Base -->
        <rect x="{cx}" y="{cy}" width="{bw}" height="{bh}" rx="8" fill="{c_main}" stroke="#2D3748" stroke-width="3" />
        
        <!-- Spine Stripe -->
        <rect x="{cx}" y="{cy}" width="15" height="{bh}" rx="4" fill="{c_sec}" stroke="#2D3748" stroke-width="2" />
        <line x1="{cx + 3}" y1="{cy + 25}" x2="{cx + 12}" y2="{cy + 25}" stroke="#2D3748" stroke-width="2" />
        <line x1="{cx + 3}" y1="{cy + bh - 25}" x2="{cx + 12}" y2="{cy + bh - 25}" stroke="#2D3748" stroke-width="2" />
        
        <!-- Cover Art Pattern -->
        {pattern_svg}
        
        <!-- Bookmark Ribbon -->
        <polygon points="{cx + bw - 20},{cy} {cx + bw - 6},{cy} {cx + bw - 6},{cy + 30} {cx + bw - 13},{cy + 22} {cx + bw - 20},{cy + 30}" fill="{c_sec}" stroke="#2D3748" stroke-width="1.5" />
        
        <!-- Clean Book Page Edge on Bottom -->
        <rect x="{cx + 15}" y="{cy + bh - 10}" width="{bw - 17}" height="8" rx="1" fill="#FFFFFF" stroke="#2D3748" stroke-width="1.8" />
        """)
        
    return svg_wrapper("\n".join(body))


# -------------------------------------------------------------
# 3. OPTION 2: 4 EMPTY CARS (NO TEXT, VIBRANT COLORS)
# -------------------------------------------------------------
CAR_PALETTES = [
    ("#FF1654", "#E0F2FE", "#FFE600"), # Hot Red + Light Blue Glass + Gold Lights
    ("#3A86FF", "#E0F7FA", "#FFBE0B"), # Electric Blue + Ice Blue Glass + Amber Lights
    ("#FFB703", "#FFF9C4", "#FF006E"), # Sunny Yellow + Light Yellow Glass + Pink Lights
    ("#06D6A0", "#E8F8F5", "#FFD166")  # Vibrant Green + Mint Glass + Yellow Lights
]

def generate_cars_svg():
    body = []
    card_w = 345
    card_h = 490
    positions = [
        (40, 50),
        (415, 50),
        (40, 580),
        (415, 580)
    ]
    
    for idx, (c_body, c_glass, c_lamp) in enumerate(CAR_PALETTES):
        bx, by = positions[idx]
        cx = bx + 22
        cy = by + 120
        
        body.append(f"""
        <!-- Car Dotted Cut Card -->
        <rect x="{bx}" y="{by}" width="{card_w}" height="{card_h}" rx="16" class="cut-guide" />
        
        <!-- CAR DRAWING -->
        <g transform="translate({cx}, {cy})">
          <!-- Car Cabin Roof -->
          <path d="M 40 140 Q 55 30 115 25 L 210 25 Q 265 30 275 140 Z" fill="{c_body}" stroke="#1E293B" stroke-width="3.5" />
          
          <!-- Large Spacious Passenger Windows (Fit people cutouts easily!) -->
          <rect x="56" y="38" width="94" height="96" rx="12" fill="{c_glass}" stroke="#1E293B" stroke-width="2.5" />
          <rect x="162" y="38" width="94" height="96" rx="12" fill="{c_glass}" stroke="#1E293B" stroke-width="2.5" />
          
          <!-- Lower Car Body -->
          <rect x="10" y="130" width="285" height="85" rx="22" fill="{c_body}" stroke="#1E293B" stroke-width="3.5" />
          
          <!-- Racing / Color Trim Stripe -->
          <rect x="12" y="152" width="281" height="15" fill="#FFFFFF" opacity="0.4" />
          
          <!-- Bright Headlights & Tail Lights -->
          <circle cx="288" cy="160" r="14" fill="{c_lamp}" stroke="#1E293B" stroke-width="2.5" />
          <circle cx="16" cy="160" r="10" fill="#FF0055" stroke="#1E293B" stroke-width="2" />
          
          <!-- Door Line & Handles -->
          <line x1="156" y1="130" x2="156" y2="205" stroke="#1E293B" stroke-width="2.5" />
          <rect x="132" y="148" width="18" height="6" rx="3" fill="#1E293B" />
          <rect x="164" y="148" width="18" height="6" rx="3" fill="#1E293B" />
          
          <!-- Front Grille -->
          <rect x="280" y="180" width="20" height="16" rx="4" fill="#CBD5E1" stroke="#1E293B" stroke-width="2" />
          
          <!-- Wheels & Colorful Rims -->
          <circle cx="65" cy="215" r="34" fill="#1E293B" stroke="#0F172A" stroke-width="3" />
          <circle cx="65" cy="215" r="20" fill="#F1F5F9" stroke="#1E293B" stroke-width="2.5" />
          <circle cx="65" cy="215" r="9" fill="{c_body}" />
          
          <circle cx="240" cy="215" r="34" fill="#1E293B" stroke="#0F172A" stroke-width="3" />
          <circle cx="240" cy="215" r="20" fill="#F1F5F9" stroke="#1E293B" stroke-width="2.5" />
          <circle cx="240" cy="215" r="9" fill="{c_body}" />
        </g>
        """)
        
    return svg_wrapper("\n".join(body))


# -------------------------------------------------------------
# 4. OPTION 2: 8 SMALL PASSENGERS (NO TEXT, SUPER COLORFUL)
# Sized ~70x85px to fit inside the car windows!
# -------------------------------------------------------------
PASSENGER_STYLES = [
    ("#FF5400", "#4A2810", "short"),    # Orange shirt, spiky hair
    ("#EC4899", "#FBBF24", "pigtails"), # Hot Pink shirt, blonde pigtails
    ("#10B981", "#1F2937", "curly"),    # Emerald shirt, dark curls
    ("#F59E0B", "#6B21A8", "headband"), # Sun Yellow shirt, purple headband
    ("#EF4444", "#78350F", "cap"),      # Bright Red shirt & red cap
    ("#8B5CF6", "#1E293B", "buns"),     # Purple shirt, twin buns
    ("#06B6D4", "#92400E", "glasses"),  # Cyan shirt, blue glasses
    ("#F43F5E", "#C2410C", "ponytail")  # Coral shirt, orange ponytail
]

def generate_people_svg():
    cols = 4
    rows = 2
    box_w = 170
    box_h = 490
    start_x = 35
    start_y = 50
    gap_x = 185
    gap_y = 520
    
    body = []
    
    for idx, (shirt, hair, hair_style) in enumerate(PASSENGER_STYLES):
        col = idx % cols
        row = idx // cols
        bx = start_x + col * gap_x
        by = start_y + row * gap_y
        
        skin = "#FFDFC4"
        blush = "#FF8FA3"
        cx = bx + box_w / 2
        cy = by + 140
        
        hair_svg = ""
        if hair_style == "short":
            hair_svg = f"""
            <path d="M -32 45 Q -25 12 0 12 Q 25 12 32 45 C 20 26 0 24 -32 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <polygon points="-6,12 0,2 6,12" fill="{hair}" stroke="#1E293B" stroke-width="2" />
            """
        elif hair_style == "pigtails":
            hair_svg = f"""
            <path d="M -32 45 Q -25 16 0 16 Q 25 16 32 45 C 20 28 0 26 -32 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-38" cy="40" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="38" cy="40" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-30" cy="40" r="5" fill="#FF006E" />
            <circle cx="30" cy="40" r="5" fill="#FF006E" />
            """
        elif hair_style == "curly":
            hair_svg = f"""
            <circle cx="-20" cy="22" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="0" cy="15" r="16" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="20" cy="22" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            """
        elif hair_style == "headband":
            hair_svg = f"""
            <path d="M -32 50 Q -25 16 0 16 Q 25 16 32 50 C 20 30 0 28 -32 50 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <path d="M -30 46 Q 0 22 30 46" fill="none" stroke="#FF007F" stroke-width="6" />
            <circle cx="-22" cy="36" r="6" fill="#FFE600" />
            """
        elif hair_style == "cap":
            hair_svg = f"""
            <path d="M -30 42 Q 0 8 30 42 Z" fill="#EF4444" stroke="#1E293B" stroke-width="2.5" />
            <path d="M -5 38 L 42 34 L 38 46 L -2 47 Z" fill="#DC2626" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="0" cy="20" r="4" fill="#FFFFFF" />
            """
        elif hair_style == "buns":
            hair_svg = f"""
            <path d="M -32 46 Q 0 20 32 46 C 20 30 0 30 -32 46 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-22" cy="12" r="13" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="22" cy="12" r="13" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-22" cy="22" r="4" fill="#00F5D4" />
            <circle cx="22" cy="22" r="4" fill="#00F5D4" />
            """
        elif hair_style == "glasses":
            hair_svg = f"""
            <path d="M -32 45 Q -20 16 0 16 Q 20 16 32 45 C 15 26 0 26 -32 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <rect x="-22" y="38" width="18" height="16" rx="4" fill="none" stroke="#3B82F6" stroke-width="3" />
            <rect x="4" y="38" width="18" height="16" rx="4" fill="none" stroke="#3B82F6" stroke-width="3" />
            <line x1="-4" y1="46" x2="4" y2="46" stroke="#3B82F6" stroke-width="3" />
            """
        elif hair_style == "ponytail":
            hair_svg = f"""
            <path d="M -32 46 Q -25 16 0 16 Q 25 16 32 46 C 20 28 0 26 -32 46 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <path d="M 26 35 Q 46 22 44 58 Q 35 48 26 44 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="28" cy="38" r="5" fill="#3B82F6" />
            """

        body.append(f"""
        <!-- Passenger Dotted Cut Box -->
        <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="14" class="cut-guide" />
        
        <!-- PASSENGER ILLUSTRATION -->
        <g transform="translate({cx}, {cy})">
          <!-- Waving Left Hand -->
          <path d="M -24 82 Q -42 55 -38 38" stroke="#1E293B" stroke-width="11" stroke-linecap="round" fill="none" />
          <circle cx="-38" cy="38" r="7" fill="{skin}" stroke="#1E293B" stroke-width="2.5" />
          
          <!-- Right Hand -->
          <path d="M 24 82 Q 40 98 36 115" stroke="#1E293B" stroke-width="11" stroke-linecap="round" fill="none" />
          <circle cx="36" cy="115" r="7" fill="{skin}" stroke="#1E293B" stroke-width="2.5" />

          <!-- Bright Colorful Shirt -->
          <path d="M -26 78 L 26 78 L 24 150 L -24 150 Z" fill="{shirt}" stroke="#1E293B" stroke-width="3" />
          <rect x="-8" y="62" width="16" height="20" rx="4" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          
          <!-- Cheerful Shirt Star / Emblem -->
          <circle cx="0" cy="105" r="6" fill="#FFFFFF" opacity="0.9" />
          <circle cx="0" cy="125" r="6" fill="#FFFFFF" opacity="0.9" />

          <!-- Head -->
          <circle cx="0" cy="46" r="30" fill="{skin}" stroke="#1E293B" stroke-width="3" />
          <circle cx="-30" cy="48" r="6" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          <circle cx="30" cy="48" r="6" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          
          <!-- Eyes -->
          <circle cx="-11" cy="44" r="4" fill="#1E293B" />
          <circle cx="11" cy="44" r="4" fill="#1E293B" />
          <circle cx="-9" cy="42" r="1.5" fill="#FFFFFF" />
          <circle cx="13" cy="42" r="1.5" fill="#FFFFFF" />
          
          <!-- Rosy Cheeks -->
          <ellipse cx="-18" cy="52" rx="5" ry="3" fill="{blush}" />
          <ellipse cx="18" cy="52" rx="5" ry="3" fill="{blush}" />
          
          <!-- Big Friendly Smile -->
          <path d="M -9 56 Q 0 68 9 56" fill="none" stroke="#1E293B" stroke-width="2.8" stroke-linecap="round" />
          
          {hair_svg}
        </g>
        """)
        
    return svg_wrapper("\n".join(body))


def main():
    pages = [
        ("option1_bookshelves_color.svg", generate_bookshelves_svg()),
        ("option1_books_color.svg", generate_books_svg()),
        ("option2_cars_color.svg", generate_cars_svg()),
        ("option2_people_color.svg", generate_people_svg())
    ]
    
    for filename, content in pages:
        svg_path = os.path.join(OUT_DIR, filename)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        pdf_path = svg_path.replace(".svg", ".pdf")
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf_path, svg_path], check=True)
        print(f"Rendered {pdf_path}")

    # Combine Option 1
    opt1_combined = os.path.join(DOWNLOADS, "Option1_Bookshelves_and_Books_Color.pdf")
    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option1_bookshelves_color.pdf"),
        os.path.join(OUT_DIR, "option1_books_color.pdf"),
        opt1_combined
    ], check=True)
    print(f"Updated {opt1_combined}")

    # Combine Option 2
    opt2_combined = os.path.join(DOWNLOADS, "Option2_Cars_and_People_Color.pdf")
    subprocess.run([
        "pdfunite",
        os.path.join(OUT_DIR, "option2_cars_color.pdf"),
        os.path.join(OUT_DIR, "option2_people_color.pdf"),
        opt2_combined
    ], check=True)
    print(f"Updated {opt2_combined}")

if __name__ == "__main__":
    main()
