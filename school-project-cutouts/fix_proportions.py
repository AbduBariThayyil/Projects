import os
import subprocess

OUT_DIR = "/home/vibecoder/Projects/school-project-cutouts"
DOWNLOADS = "/home/vibecoder/Downloads"

# -------------------------------------------------------------
# SVG Common Helpers
# -------------------------------------------------------------
def svg_header(title, subtitle, width=800, height=1130):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}pt" height="{height}pt">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Fredoka+One&amp;family=Quicksand:wght@600;700&amp;display=swap');
      text {{ font-family: 'Fredoka One', 'Quicksand', 'Nunito', 'Segoe UI', Arial, sans-serif; }}
      .title {{ font-size: 26px; font-weight: bold; fill: #1E293B; text-anchor: middle; }}
      .subtitle {{ font-size: 14px; font-weight: 600; fill: #475569; text-anchor: middle; }}
      .cut-guide {{ stroke: #94A3B8; stroke-width: 1.8; stroke-dasharray: 6, 5; fill: none; }}
      .cut-text {{ font-size: 11px; fill: #64748B; font-weight: bold; }}
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
# 1. OPTION 1: 3 EMPTY BOOKSHELVES
# -------------------------------------------------------------
def generate_bookshelves_svg():
    header = svg_header(
        "Option 1: 3 Empty Bookshelves",
        "✂ Cut along dashed lines. Glue 5 books onto each bookshelf! (15 ÷ 3 = 5)"
    )
    
    body = []
    shelf_w = 720
    shelf_h = 280
    start_y = 110
    gap_y = 335
    
    for i in range(3):
        y = start_y + i * gap_y
        body.append(f"""
        <!-- Bookshelf {i+1} Container with Dotted Cut Line -->
        <rect x="30" y="{y - 10}" width="740" height="{shelf_h + 20}" rx="14" class="cut-guide" />
        {scissors_icon(45, y + 6, f"✂ Cut Bookshelf #{i+1}")}
        
        <!-- Shelf Outer Wooden Frame -->
        <rect x="45" y="{y + 18}" width="{shelf_w}" height="{shelf_h - 10}" rx="14" fill="#8D5B4C" stroke="#1E293B" stroke-width="3" />
        
        <!-- Shelf Cavity (Huge open wooden shelf: 195px high, 660px wide - PLENTY of room for books!) -->
        <rect x="65" y="{y + 45}" width="{shelf_w - 40}" height="195" rx="8" fill="#FDF6EE" stroke="#CBD5E1" stroke-width="2" />
        
        <!-- Bottom Base Board / Shelf Plank (Solid base for books to stand on) -->
        <rect x="55" y="{y + 240}" width="{shelf_w - 20}" height="28" rx="4" fill="#A76F53" stroke="#1E293B" stroke-width="2.5" />
        
        <!-- Shelf Guideline (Dashed guide showing 5 book spots) -->
        <line x1="85" y1="{y + 238}" x2="{shelf_w + 5}" y2="{y + 238}" stroke="#E2E8F0" stroke-width="2" stroke-dasharray="10,6" />
        
        <!-- Name Badge -->
        <rect x="270" y="{y + 20}" width="260" height="24" rx="12" fill="#FEF3C7" stroke="#1E293B" stroke-width="1.5" />
        <text x="400" y="{y + 37}" font-size="13" font-weight="bold" fill="#78350F" text-anchor="middle">📚 Bookshelf #{i+1} — Glue 5 Books Here</text>
        """)
        
    return header + "\n".join(body) + svg_footer()


# -------------------------------------------------------------
# 2. OPTION 1: 15 SMALL BOOKS (SIMPLE, CLEAN, NO OVER-LABELED TEXT)
# Book size: 55px wide, 140px tall. Fits easily in 195px shelf opening!
# -------------------------------------------------------------
BOOK_COLORS = [
    ("#EF476F", "#FFD166"), # Red/Yellow
    ("#3A86FF", "#E0F2FE"), # Blue/Light Blue
    ("#06D6A0", "#C7F9CC"), # Emerald/Mint
    ("#FFB703", "#FFE8D6"), # Orange/Peach
    ("#8338EC", "#E0AAFF"), # Purple/Lavender
    ("#F72585", "#FFCCD5"), # Pink/Rose
    ("#FB8500", "#FEF3C7"), # Amber/Warm
    ("#2A9D8F", "#D1FAE5"), # Teal/Sage
    ("#118AB2", "#A2D2FF"), # Ocean/Sky
    ("#D90429", "#FFCCD5"), # Crimson/Pink
    ("#48CAE4", "#CAF0F8"), # Sky/Soft
    ("#FF006E", "#FFBE0B"), # Magenta/Yellow
    ("#2B9348", "#D8F3DC"), # Forest/Pale Green
    ("#5A189A", "#E0AAFF"), # Deep Violet
    ("#E76F51", "#F4A261")  # Terracotta/Peach
]

def generate_books_svg():
    header = svg_header(
        "Option 1: 15 Small Books",
        "✂ Cut along dashed boxes. Glue 5 books on each shelf! (15 ÷ 3 = 5)"
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
    
    # Book dimensions: 55px wide, 150px tall (comfortably fits on 195px high shelf!)
    bw = 55
    bh = 150
    
    for idx, (c_cover, c_accent) in enumerate(BOOK_COLORS):
        col = idx % cols
        row = idx // cols
        bx = start_x + col * gap_x
        by = start_y + row * gap_y
        
        # Center inside cutout cell
        cx = bx + (box_w - bw) / 2
        cy = by + 65
        
        body.append(f"""
        <!-- Book #{idx+1} Cutout Box -->
        <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="10" class="cut-guide" />
        {scissors_icon(bx + 12, by + 22, f"✂ Book #{idx+1}")}
        
        <!-- Book Cover Body -->
        <rect x="{cx}" y="{cy}" width="{bw}" height="{bh}" rx="6" fill="{c_cover}" stroke="#1E293B" stroke-width="2.5" />
        
        <!-- Book Spine on left -->
        <rect x="{cx}" y="{cy}" width="12" height="{bh}" rx="4" fill="{c_accent}" stroke="#1E293B" stroke-width="2" />
        
        <!-- Decorative Spine Bands -->
        <line x1="{cx + 2}" y1="{cy + 25}" x2="{cx + 10}" y2="{cy + 25}" stroke="#1E293B" stroke-width="2" />
        <line x1="{cx + 2}" y1="{cy + bh - 25}" x2="{cx + 10}" y2="{cy + bh - 25}" stroke="#1E293B" stroke-width="2" />
        
        <!-- Simple Cute Cover Accent (Clean star, stripe, or bookmark) -->
        <rect x="{cx + 18}" y="{cy + 30}" width="{bw - 24}" height="65" rx="4" fill="rgba(255,255,255,0.3)" stroke="#1E293B" stroke-width="1.5" />
        <polygon points="{cx + 24},{cy + 60} {cx + 34},{cy + 50} {cx + 44},{cy + 60} {cx + 39},{cy + 75} {cx + 29},{cy + 75}" fill="{c_accent}" stroke="#1E293B" stroke-width="1.2" />
        
        <!-- Book Pages Edge on bottom -->
        <rect x="{cx + 12}" y="{cy + bh - 10}" width="{bw - 14}" height="8" fill="#FFFFFF" stroke="#1E293B" stroke-width="1.5" />
        
        <!-- Cutout Label at bottom -->
        <text x="{bx + box_w/2}" y="{by + box_h - 22}" font-size="12" font-weight="bold" fill="#64748B" text-anchor="middle">Book #{idx+1}</text>
        """)
        
    return header + "\n".join(body) + svg_footer()


# -------------------------------------------------------------
# 3. OPTION 2: 4 EMPTY CARS
# -------------------------------------------------------------
CAR_THEMES = [
    ("Red Cruiser", "#E63946", "#F1FAEE"),
    ("Blue Buggy", "#3A86FF", "#E0F2FE"),
    ("Sunny Van", "#FFB703", "#FEF3C7"),
    ("Green Wagon", "#2A9D8F", "#D1FAE5")
]

def generate_cars_svg():
    header = svg_header(
        "Option 2: 4 Empty Cars",
        "✂ Cut along dashed boxes. Glue 2 passengers inside each car! (8 ÷ 4 = 2)"
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
    
    for idx, (car_name, c_main, c_glass) in enumerate(CAR_THEMES):
        bx, by = positions[idx]
        cx = bx + 20
        cy = by + 90
        
        body.append(f"""
        <!-- Car #{idx+1} Cutout Card -->
        <rect x="{bx}" y="{by}" width="{card_w}" height="{card_h}" rx="14" class="cut-guide" />
        {scissors_icon(bx + 14, by + 22, f"✂ Cut Car #{idx+1}: {car_name}")}
        
        <!-- Car Badge Title -->
        <rect x="{bx + 60}" y="{by + 35}" width="{card_w - 120}" height="28" rx="14" fill="{c_main}" stroke="#1E293B" stroke-width="1.5" />
        <text x="{bx + card_w/2}" y="{by + 54}" font-size="14" font-weight="bold" fill="#FFFFFF" text-anchor="middle">Car #{idx+1}: {car_name}</text>
        
        <!-- CAR DRAWING -->
        <g transform="translate({cx}, {cy})">
          <!-- Car Cabin Roof -->
          <path d="M 40 140 Q 55 35 115 30 L 210 30 Q 265 35 275 140 Z" fill="{c_main}" stroke="#1E293B" stroke-width="3" />
          
          <!-- Large Clear Passenger Windows (Spacious 90x88px windows for people cutouts!) -->
          <rect x="58" y="42" width="92" height="92" rx="10" fill="{c_glass}" stroke="#1E293B" stroke-width="2" />
          <rect x="162" y="42" width="92" height="92" rx="10" fill="{c_glass}" stroke="#1E293B" stroke-width="2" />
          
          <!-- Seat 1 and Seat 2 targets -->
          <rect x="65" y="48" width="78" height="80" rx="8" fill="rgba(255,255,255,0.7)" stroke="#94A3B8" stroke-width="1.5" stroke-dasharray="5,4" />
          <text x="104" y="85" font-size="12" font-weight="bold" fill="#64748B" text-anchor="middle">Person 1</text>
          <text x="104" y="102" font-size="10" fill="#94A3B8" text-anchor="middle">Glue here</text>
          
          <rect x="169" y="48" width="78" height="80" rx="8" fill="rgba(255,255,255,0.7)" stroke="#94A3B8" stroke-width="1.5" stroke-dasharray="5,4" />
          <text x="208" y="85" font-size="12" font-weight="bold" fill="#64748B" text-anchor="middle">Person 2</text>
          <text x="208" y="102" font-size="10" fill="#94A3B8" text-anchor="middle">Glue here</text>

          <!-- Main Lower Car Body -->
          <rect x="10" y="130" width="285" height="75" rx="20" fill="{c_main}" stroke="#1E293B" stroke-width="3" />
          
          <!-- Headlights -->
          <circle cx="288" cy="155" r="12" fill="#FFD166" stroke="#1E293B" stroke-width="2" />
          <circle cx="17" cy="155" r="10" fill="#EF476F" stroke="#1E293B" stroke-width="2" />
          
          <!-- Door Line & Handles -->
          <line x1="156" y1="130" x2="156" y2="195" stroke="#1E293B" stroke-width="2.5" />
          <rect x="134" y="145" width="16" height="5" rx="2" fill="#1E293B" />
          <rect x="164" y="145" width="16" height="5" rx="2" fill="#1E293B" />
          
          <!-- Smiling Bumper -->
          <rect x="280" y="172" width="20" height="15" rx="4" fill="#CBD5E1" stroke="#1E293B" stroke-width="2" />
          
          <!-- Wheels -->
          <circle cx="65" cy="205" r="32" fill="#2B2D42" stroke="#1E293B" stroke-width="3" />
          <circle cx="65" cy="205" r="18" fill="#E5E7EB" stroke="#1E293B" stroke-width="2" />
          <circle cx="65" cy="205" r="6" fill="#1E293B" />
          
          <circle cx="240" cy="205" r="32" fill="#2B2D42" stroke="#1E293B" stroke-width="3" />
          <circle cx="240" cy="205" r="18" fill="#E5E7EB" stroke="#1E293B" stroke-width="2" />
          <circle cx="240" cy="205" r="6" fill="#1E293B" />
        </g>
        
        <!-- Helpful Math Note -->
        <rect x="{bx + 50}" y="{by + card_h - 40}" width="{card_w - 100}" height="24" rx="6" fill="#F8FAFC" stroke="#E2E8F0" stroke-width="1" />
        <text x="{bx + card_w/2}" y="{by + card_h - 24}" font-size="12" font-weight="bold" fill="#475569" text-anchor="middle">Seats 2 passengers (8 ÷ 4 = 2)</text>
        """)
        
    return header + "\n".join(body) + svg_footer()


# -------------------------------------------------------------
# 4. OPTION 2: 8 SMALL PASSENGERS (Sized 70x75px to fit window seats!)
# -------------------------------------------------------------
KIDS_PROFILES = [
    ("Leo", "#F97316", "#4A2810", "short"),
    ("Mia", "#EC4899", "#FBBF24", "pigtails"),
    ("Sam", "#10B981", "#1F2937", "curly"),
    ("Zoe", "#F59E0B", "#6B21A8", "headband"),
    ("Max", "#EF4444", "#78350F", "cap"),
    ("Ava", "#8B5CF6", "#1E293B", "buns"),
    ("Ben", "#06B6D4", "#92400E", "glasses"),
    ("Lily", "#F43F5E", "#C2410C", "ponytail")
]

def generate_people_svg():
    header = svg_header(
        "Option 2: 8 Small Passengers",
        "✂ Cut along dashed boxes. Glue 2 passengers inside each car! (8 ÷ 4 = 2)"
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
    
    for idx, (name, shirt, hair, hair_style) in enumerate(KIDS_PROFILES):
        col = idx % cols
        row = idx // cols
        bx = start_x + col * gap_x
        by = start_y + row * gap_y
        
        skin = "#FFDFC4"
        shoes = "#1E293B"
        blush = "#FFB4A2"
        
        # Sized to fit comfortably in the 78x80 seat box
        cx = bx + box_w / 2
        cy = by + 120
        
        hair_svg = ""
        if hair_style == "short":
            hair_svg = f"""
            <path d="M -30 45 Q -25 15 0 15 Q 25 15 30 45 C 20 28 0 26 -30 45 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <polygon points="-5,15 0,6 5,15" fill="{hair}" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "pigtails":
            hair_svg = f"""
            <path d="M -30 45 Q -25 18 0 18 Q 25 18 30 45 C 20 30 0 28 -30 45 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <circle cx="-36" cy="40" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="36" cy="40" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "curly":
            hair_svg = f"""
            <circle cx="-18" cy="24" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="0" cy="18" r="14" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="18" cy="24" r="12" fill="{hair}" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "headband":
            hair_svg = f"""
            <path d="M -30 50 Q -25 18 0 18 Q 25 18 30 50 C 20 32 0 30 -30 50 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <path d="M -28 46 Q 0 25 28 46" fill="none" stroke="#EC4899" stroke-width="5" />
            """
        elif hair_style == "cap":
            hair_svg = f"""
            <path d="M -28 42 Q 0 10 28 42 Z" fill="#EF4444" stroke="#334155" stroke-width="2.5" />
            <path d="M -5 38 L 38 34 L 34 45 L -2 46 Z" fill="#DC2626" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "buns":
            hair_svg = f"""
            <path d="M -30 46 Q 0 22 30 46 C 20 32 0 32 -30 46 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <circle cx="-20" cy="14" r="11" fill="{hair}" stroke="#334155" stroke-width="2" />
            <circle cx="20" cy="14" r="11" fill="{hair}" stroke="#334155" stroke-width="2" />
            """
        elif hair_style == "glasses":
            hair_svg = f"""
            <path d="M -30 45 Q -20 18 0 18 Q 20 18 30 45 C 15 28 0 28 -30 45 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <rect x="-20" y="40" width="16" height="14" rx="3" fill="none" stroke="#3B82F6" stroke-width="2.5" />
            <rect x="4" y="40" width="16" height="14" rx="3" fill="none" stroke="#3B82F6" stroke-width="2.5" />
            <line x1="-4" y1="47" x2="4" y2="47" stroke="#3B82F6" stroke-width="2.5" />
            """
        elif hair_style == "ponytail":
            hair_svg = f"""
            <path d="M -30 46 Q -25 18 0 18 Q 25 18 30 46 C 20 30 0 28 -30 46 Z" fill="{hair}" stroke="#334155" stroke-width="2.5" />
            <path d="M 24 35 Q 42 25 40 55 Q 32 46 24 42 Z" fill="{hair}" stroke="#334155" stroke-width="2" />
            """

        body.append(f"""
        <!-- Passenger #{idx+1}: {name} Cutout Box -->
        <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="12" class="cut-guide" />
        {scissors_icon(bx + 12, by + 18, f"✂ #{idx+1}: {name}")}
        
        <!-- Name Badge -->
        <rect x="{bx + 35}" y="{by + 35}" width="{box_w - 70}" height="26" rx="13" fill="#F1F5F9" stroke="#334155" stroke-width="1.5" />
        <text x="{cx}" y="{by + 53}" font-size="14" font-weight="bold" fill="#0F172A" text-anchor="middle">{name}</text>
        
        <!-- PASSENGER ILLUSTRATION (Waist-up passenger - sits in car seat!) -->
        <g transform="translate({cx}, {cy})">
          <!-- Waving Hand -->
          <path d="M -22 80 Q -38 55 -34 40" stroke="#334155" stroke-width="9" stroke-linecap="round" fill="none" />
          <circle cx="-34" cy="40" r="6" fill="{skin}" stroke="#334155" stroke-width="2" />
          
          <path d="M 22 80 Q 36 95 32 110" stroke="#334155" stroke-width="9" stroke-linecap="round" fill="none" />
          <circle cx="32" cy="110" r="6" fill="{skin}" stroke="#334155" stroke-width="2" />

          <!-- Shirt / Torso -->
          <path d="M -24 75 L 24 75 L 22 135 L -22 135 Z" fill="{shirt}" stroke="#334155" stroke-width="2.5" />
          <rect x="-8" y="60" width="16" height="18" rx="4" fill="{skin}" stroke="#334155" stroke-width="2" />
          
          <!-- Head -->
          <circle cx="0" cy="45" r="28" fill="{skin}" stroke="#334155" stroke-width="2.5" />
          
          <!-- Ears -->
          <circle cx="-28" cy="46" r="5" fill="{skin}" stroke="#334155" stroke-width="2" />
          <circle cx="28" cy="46" r="5" fill="{skin}" stroke="#334155" stroke-width="2" />
          
          <!-- Cheerful Eyes -->
          <circle cx="-10" cy="44" r="3.5" fill="#1E293B" />
          <circle cx="10" cy="44" r="3.5" fill="#1E293B" />
          <circle cx="-8.5" cy="42" r="1.2" fill="#FFFFFF" />
          <circle cx="11.5" cy="42" r="1.2" fill="#FFFFFF" />
          
          <!-- Blush -->
          <ellipse cx="-16" cy="50" rx="4" ry="2.5" fill="{blush}" />
          <ellipse cx="16" cy="50" rx="4" ry="2.5" fill="{blush}" />
          
          <!-- Smile -->
          <path d="M -8 54 Q 0 63 8 54" fill="none" stroke="#1E293B" stroke-width="2.2" stroke-linecap="round" />
          
          {hair_svg}
        </g>
        
        <text x="{cx}" y="{by + box_h - 22}" font-size="12" font-weight="bold" fill="#64748B" text-anchor="middle">Passenger #{idx+1}</text>
        """)
        
    return header + "\n".join(body) + svg_footer()


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
