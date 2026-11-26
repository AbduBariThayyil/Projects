import os
import math
import subprocess
from PIL import Image

OUT_DIR = "/home/vibecoder/Projects/school-project-cutouts"
DOWNLOADS = "/home/vibecoder/Downloads"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(DOWNLOADS, exist_ok=True)

def svg_wrap(content, w=800, h=1130):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}pt" height="{h}pt">
  <defs>
    <style>
      .cut-guide {{ stroke: #718096; stroke-width: 2.2; stroke-dasharray: 6, 5; fill: none; }}
    </style>
  </defs>
  <rect width="{w}" height="{h}" fill="#FFFFFF" />
  {content}
</svg>"""

# -------------------------------------------------------------
# 1. 15 BOOKS (PERFECTLY ALIGNED SHAPES & SNUG CUT LINES)
# -------------------------------------------------------------
VIBRANT_PALETTES = [
    ("#FF1654", "#FFE600", "star"),      # 1
    ("#3A86FF", "#FFD166", "heart"),     # 2
    ("#06D6A0", "#FFFFFF", "stripe"),    # 3
    ("#FF5400", "#FFE600", "circle"),    # 4
    ("#9B5DE5", "#F15BB5", "diamond"),   # 5
    ("#00BBF9", "#FFFFFF", "stripe"),    # 6
    ("#F72585", "#FFE600", "star"),      # 7
    ("#38B000", "#FFFFFF", "heart"),     # 8
    ("#FFB703", "#7209B7", "circle"),    # 9
    ("#E63946", "#FFFFFF", "stripe"),    # 10
    ("#4361EE", "#4CC9F0", "diamond"),   # 11
    ("#D81159", "#FFE600", "star"),      # 12
    ("#2EC4B6", "#FF9F1C", "heart"),     # 13
    ("#7209B7", "#FFFFFF", "stripe"),    # 14
    ("#FB5607", "#FFE600", "circle")     # 15
]

def make_star(cx, cy, r_out=18, r_in=8):
    pts = []
    for k in range(10):
        ang = k * math.pi / 5 - math.pi / 2
        r = r_out if k % 2 == 0 else r_in
        pts.append(f"{cx + r * math.cos(ang):.1f},{cy + r * math.sin(ang):.1f}")
    return " ".join(pts)

def generate_15_books():
    cols = 5
    rows = 3
    bw = 95
    bh = 220
    
    start_x = 42
    start_y = 65
    gap_x = 146
    gap_y = 350
    
    body = []
    for idx, (c_main, c_sec, motif) in enumerate(VIBRANT_PALETTES):
        col = idx % cols
        row = idx // cols
        x = start_x + col * gap_x
        y = start_y + row * gap_y
        
        # Center of book cover
        cx_mid = x + 16 + (bw - 16) / 2
        cy_mid = y + bh / 2
        
        motif_svg = ""
        if motif == "star":
            star_pts = make_star(cx_mid, cy_mid, 22, 10)
            motif_svg = f'<polygon points="{star_pts}" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />'
        elif motif == "heart":
            motif_svg = f"""<path d="M {cx_mid} {cy_mid + 20} 
                            C {cx_mid - 24} {cy_mid - 6}, {cx_mid - 24} {cy_mid - 26}, {cx_mid} {cy_mid - 12} 
                            C {cx_mid + 24} {cy_mid - 26}, {cx_mid + 24} {cy_mid - 6}, {cx_mid} {cy_mid + 20} Z" 
                            fill="{c_sec}" stroke="#1E293B" stroke-width="2" />"""
        elif motif == "circle":
            motif_svg = f"""<circle cx="{cx_mid}" cy="{cy_mid - 26}" r="15" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />
                            <circle cx="{cx_mid}" cy="{cy_mid + 26}" r="15" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />"""
        elif motif == "stripe":
            motif_svg = f"""<rect x="{x + 22}" y="{cy_mid - 45}" width="{bw - 30}" height="14" rx="2" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />
                            <rect x="{x + 22}" y="{cy_mid - 12}" width="{bw - 30}" height="14" rx="2" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />
                            <rect x="{x + 22}" y="{cy_mid + 20}" width="{bw - 30}" height="14" rx="2" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />"""
        elif motif == "diamond":
            motif_svg = f'<polygon points="{cx_mid},{cy_mid - 26} {cx_mid + 20},{cy_mid} {cx_mid},{cy_mid + 26} {cx_mid - 20},{cy_mid}" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />'

        body.append(f"""
        <!-- SNUG CUT LINE (Directly wrapping the book with 6px margin) -->
        <rect x="{x - 6}" y="{y - 6}" width="{bw + 12}" height="{bh + 12}" rx="12" class="cut-guide" />
        
        <!-- Book Cover -->
        <rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="8" fill="{c_main}" stroke="#1E293B" stroke-width="3" />
        
        <!-- Spine on Left -->
        <rect x="{x}" y="{y}" width="18" height="{bh}" rx="6" fill="{c_sec}" stroke="#1E293B" stroke-width="2.2" />
        <line x1="{x + 4}" y1="{y + 35}" x2="{x + 14}" y2="{y + 35}" stroke="#1E293B" stroke-width="2" />
        <line x1="{x + 4}" y1="{y + bh - 35}" x2="{x + 14}" y2="{y + bh - 35}" stroke="#1E293B" stroke-width="2" />
        
        <!-- Motif Art Centered -->
        {motif_svg}
        
        <!-- Bookmark Ribbon -->
        <polygon points="{x + bw - 24},{y} {x + bw - 8},{y} {x + bw - 8},{y + 38} {x + bw - 16},{y + 28} {x + bw - 24},{y + 38}" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />
        
        <!-- Bottom Pages Trim -->
        <rect x="{x + 18}" y="{y + bh - 12}" width="{bw - 20}" height="10" rx="1" fill="#FFFFFF" stroke="#1E293B" stroke-width="2" />
        """)
    return svg_wrap("\n".join(body))

# -------------------------------------------------------------
# 2. 3 EMPTY BOOKSHELVES (SNUG CUT LINES & OPEN SHELVES)
# -------------------------------------------------------------
def generate_3_bookshelves():
    body = []
    shelf_w = 720
    shelf_h = 300
    start_y = 60
    gap_y = 355
    
    wood_colors = [
        ("#8D5B4C", "#A76F53", "#FFFDF9"),
        ("#795548", "#9C786C", "#FFFDF9"),
        ("#6D4C41", "#8D6E63", "#FFFDF9")
    ]
    
    for i in range(3):
        y = start_y + i * gap_y
        c_outer, c_trim, c_inner = wood_colors[i]
        x = 40
        
        body.append(f"""
        <!-- SNUG CUT LINE: 6px around bookshelf -->
        <rect x="{x - 6}" y="{y - 6}" width="{shelf_w + 12}" height="{shelf_h + 12}" rx="14" class="cut-guide" />
        
        <!-- Bookshelf Frame -->
        <rect x="{x}" y="{y}" width="{shelf_w}" height="{shelf_h}" rx="12" fill="{c_outer}" stroke="#1E293B" stroke-width="3.5" />
        
        <!-- Large Open Shelf Cavity: 235px high! Sized to hold 5 books easily -->
        <rect x="{x + 25}" y="{y + 25}" width="{shelf_w - 50}" height="235" rx="8" fill="{c_inner}" stroke="#CBD5E1" stroke-width="2" />
        
        <!-- Solid Wooden Shelf Plank (Bottom Base) -->
        <rect x="{x + 12}" y="{y + 260}" width="{shelf_w - 24}" height="26" rx="4" fill="{c_trim}" stroke="#1E293B" stroke-width="3" />
        
        <!-- Top Crown Molding -->
        <rect x="{x - 4}" y="{y}" width="{shelf_w + 8}" height="18" rx="6" fill="{c_trim}" stroke="#1E293B" stroke-width="2.5" />
        """)
    return svg_wrap("\n".join(body))

# -------------------------------------------------------------
# 3. 4 CARS (SNUG CUT LINES AROUND CAR)
# -------------------------------------------------------------
CAR_COLORS = [
    ("#FF1654", "#E0F2FE", "#FFE600"),
    ("#3A86FF", "#E0F7FA", "#FFBE0B"),
    ("#FFB703", "#FFF9C4", "#FF006E"),
    ("#06D6A0", "#E8F8F5", "#FFD166")
]

def generate_4_cars():
    body = []
    cw = 320
    ch = 260
    positions = [
        (55, 120),
        (425, 120),
        (55, 620),
        (425, 620)
    ]
    
    for idx, (c_body, c_glass, c_lamp) in enumerate(CAR_COLORS):
        x, y = positions[idx]
        
        body.append(f"""
        <!-- SNUG CUT LINE (8px around the car silhouette) -->
        <rect x="{x - 8}" y="{y - 8}" width="{cw + 16}" height="{ch + 16}" rx="16" class="cut-guide" />
        
        <g transform="translate({x}, {y})">
          <!-- Car Cabin Roof -->
          <path d="M 35 145 Q 50 32 115 28 L 210 28 Q 275 32 285 145 Z" fill="{c_body}" stroke="#1E293B" stroke-width="3.5" />
          
          <!-- Big Clear Passenger Windows -->
          <rect x="52" y="38" width="96" height="98" rx="12" fill="{c_glass}" stroke="#1E293B" stroke-width="2.5" />
          <rect x="168" y="38" width="96" height="98" rx="12" fill="{c_glass}" stroke="#1E293B" stroke-width="2.5" />
          
          <!-- Lower Car Body -->
          <rect x="8" y="135" width="304" height="88" rx="22" fill="{c_body}" stroke="#1E293B" stroke-width="3.5" />
          <rect x="10" y="158" width="300" height="15" fill="#FFFFFF" opacity="0.35" />
          
          <!-- Headlights -->
          <circle cx="302" cy="165" r="14" fill="{c_lamp}" stroke="#1E293B" stroke-width="2.5" />
          <circle cx="18" cy="165" r="10" fill="#FF0055" stroke="#1E293B" stroke-width="2" />
          
          <!-- Door Line & Handles -->
          <line x1="160" y1="135" x2="160" y2="215" stroke="#1E293B" stroke-width="2.5" />
          <rect x="135" y="152" width="18" height="6" rx="3" fill="#1E293B" />
          <rect x="168" y="152" width="18" height="6" rx="3" fill="#1E293B" />
          
          <!-- Wheels -->
          <circle cx="68" cy="225" r="34" fill="#1E293B" stroke="#0F172A" stroke-width="3" />
          <circle cx="68" cy="225" r="20" fill="#F1F5F9" stroke="#1E293B" stroke-width="2.5" />
          <circle cx="68" cy="225" r="9" fill="{c_body}" />
          
          <circle cx="252" cy="225" r="34" fill="#1E293B" stroke="#0F172A" stroke-width="3" />
          <circle cx="252" cy="225" r="20" fill="#F1F5F9" stroke="#1E293B" stroke-width="2.5" />
          <circle cx="252" cy="225" r="9" fill="{c_body}" />
        </g>
        """)
    return svg_wrap("\n".join(body))

# -------------------------------------------------------------
# 4. 8 PEOPLE (SNUG CUT LINES AROUND EACH PERSON!)
# -------------------------------------------------------------
PEOPLE_COLORS = [
    ("#FF5400", "#4A2810", "short"),
    ("#EC4899", "#FBBF24", "pigtails"),
    ("#10B981", "#1F2937", "curly"),
    ("#F59E0B", "#6B21A8", "headband"),
    ("#EF4444", "#78350F", "cap"),
    ("#8B5CF6", "#1E293B", "buns"),
    ("#06B6D4", "#92400E", "glasses"),
    ("#F43F5E", "#C2410C", "ponytail")
]

def generate_8_people():
    cols = 4
    rows = 2
    pw = 125
    ph = 230
    start_x = 55
    start_y = 130
    gap_x = 180
    gap_y = 480
    
    body = []
    for idx, (shirt, hair, hair_style) in enumerate(PEOPLE_COLORS):
        col = idx % cols
        row = idx // cols
        x = start_x + col * gap_x
        y = start_y + row * gap_y
        
        skin = "#FFDFC4"
        blush = "#FF8FA3"
        cx = x + pw / 2
        cy = y + 70
        
        hair_svg = ""
        if hair_style == "short":
            hair_svg = f"""
            <path d="M -30 45 Q -25 12 0 12 Q 25 12 30 45 C 20 26 0 24 -30 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <polygon points="-6,12 0,2 6,12" fill="{hair}" stroke="#1E293B" stroke-width="2" />
            """
        elif hair_style == "pigtails":
            hair_svg = f"""
            <path d="M -30 45 Q -25 16 0 16 Q 25 16 30 45 C 20 28 0 26 -30 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-36" cy="40" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="36" cy="40" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-28" cy="40" r="5" fill="#FF006E" />
            <circle cx="28" cy="40" r="5" fill="#FF006E" />
            """
        elif hair_style == "curly":
            hair_svg = f"""
            <circle cx="-18" cy="22" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="0" cy="15" r="16" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="18" cy="22" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            """
        elif hair_style == "headband":
            hair_svg = f"""
            <path d="M -30 50 Q -25 16 0 16 Q 25 16 30 50 C 20 30 0 28 -30 50 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <path d="M -28 46 Q 0 22 28 46" fill="none" stroke="#FF007F" stroke-width="6" />
            <circle cx="-22" cy="36" r="6" fill="#FFE600" />
            """
        elif hair_style == "cap":
            hair_svg = f"""
            <path d="M -28 42 Q 0 8 28 42 Z" fill="#EF4444" stroke="#1E293B" stroke-width="2.5" />
            <path d="M -5 38 L 40 34 L 36 46 L -2 47 Z" fill="#DC2626" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="0" cy="20" r="4" fill="#FFFFFF" />
            """
        elif hair_style == "buns":
            hair_svg = f"""
            <path d="M -30 46 Q 0 20 30 46 C 20 30 0 30 -30 46 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-22" cy="12" r="13" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="22" cy="12" r="13" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="-22" cy="22" r="4" fill="#00F5D4" />
            <circle cx="22" cy="22" r="4" fill="#00F5D4" />
            """
        elif hair_style == "glasses":
            hair_svg = f"""
            <path d="M -30 45 Q -20 16 0 16 Q 20 16 30 45 C 15 26 0 26 -30 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <rect x="-20" y="38" width="17" height="15" rx="4" fill="none" stroke="#3B82F6" stroke-width="3" />
            <rect x="3" y="38" width="17" height="15" rx="4" fill="none" stroke="#3B82F6" stroke-width="3" />
            <line x1="-3" y1="46" x2="3" y2="46" stroke="#3B82F6" stroke-width="3" />
            """
        elif hair_style == "ponytail":
            hair_svg = f"""
            <path d="M -30 46 Q -25 16 0 16 Q 25 16 30 46 C 20 28 0 26 -30 46 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <path d="M 24 35 Q 44 22 42 56 Q 33 46 24 42 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
            <circle cx="26" cy="38" r="5" fill="#3B82F6" />
            """

        body.append(f"""
        <!-- SNUG CUT LINE (6px around the person) -->
        <rect x="{x - 6}" y="{y - 6}" width="{pw + 12}" height="{ph + 12}" rx="14" class="cut-guide" />
        
        <!-- PERSON ILLUSTRATION -->
        <g transform="translate({cx}, {cy})">
          <!-- Waving Left Hand -->
          <path d="M -22 82 Q -38 55 -34 38" stroke="#1E293B" stroke-width="10" stroke-linecap="round" fill="none" />
          <circle cx="-34" cy="38" r="7" fill="{skin}" stroke="#1E293B" stroke-width="2.5" />
          
          <!-- Right Hand -->
          <path d="M 22 82 Q 38 98 34 115" stroke="#1E293B" stroke-width="10" stroke-linecap="round" fill="none" />
          <circle cx="34" cy="115" r="7" fill="{skin}" stroke="#1E293B" stroke-width="2.5" />

          <!-- Bright Colorful Shirt -->
          <path d="M -26 78 L 26 78 L 24 145 L -24 145 Z" fill="{shirt}" stroke="#1E293B" stroke-width="3" />
          <rect x="-8" y="62" width="16" height="20" rx="4" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          
          <!-- Shirt Emblems -->
          <circle cx="0" cy="105" r="5" fill="#FFFFFF" opacity="0.9" />
          <circle cx="0" cy="122" r="5" fill="#FFFFFF" opacity="0.9" />

          <!-- Head -->
          <circle cx="0" cy="46" r="28" fill="{skin}" stroke="#1E293B" stroke-width="3" />
          <circle cx="-28" cy="48" r="5.5" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          <circle cx="28" cy="48" r="5.5" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          
          <!-- Eyes -->
          <circle cx="-10" cy="44" r="4" fill="#1E293B" />
          <circle cx="10" cy="44" r="4" fill="#1E293B" />
          <circle cx="-8" cy="42" r="1.5" fill="#FFFFFF" />
          <circle cx="12" cy="42" r="1.5" fill="#FFFFFF" />
          
          <!-- Rosy Cheeks -->
          <ellipse cx="-16" cy="52" rx="4.5" ry="3" fill="{blush}" />
          <ellipse cx="16" cy="52" rx="4.5" ry="3" fill="{blush}" />
          
          <!-- Big Smile -->
          <path d="M -8 56 Q 0 66 8 56" fill="none" stroke="#1E293B" stroke-width="2.8" stroke-linecap="round" />
          
          {hair_svg}
        </g>
        """)
    return svg_wrap("\n".join(body))

# -------------------------------------------------------------
# 5. BONUS: ALL-IN-ONE SINGLE SHEET OPTION 2 (4 CARS + 8 PEOPLE ON 1 PAGE)
# -------------------------------------------------------------
def generate_cars_and_people_single_page():
    # Top half: 4 cars (2x2 grid)
    # Bottom half: 8 people (4x2 grid)
    body = []
    
    # 4 Cars at top: y = 40 to 600
    cw = 320
    ch = 220
    car_pos = [
        (55, 40),
        (425, 40),
        (55, 300),
        (425, 300)
    ]
    for idx, (c_body, c_glass, c_lamp) in enumerate(CAR_COLORS):
        x, y = car_pos[idx]
        body.append(f"""
        <rect x="{x - 6}" y="{y - 6}" width="{cw + 12}" height="{ch + 12}" rx="14" class="cut-guide" />
        <g transform="translate({x}, {y})">
          <path d="M 35 125 Q 50 28 115 24 L 210 24 Q 275 28 285 125 Z" fill="{c_body}" stroke="#1E293B" stroke-width="3" />
          <rect x="52" y="32" width="96" height="85" rx="10" fill="{c_glass}" stroke="#1E293B" stroke-width="2.5" />
          <rect x="168" y="32" width="96" height="85" rx="10" fill="{c_glass}" stroke="#1E293B" stroke-width="2.5" />
          <rect x="8" y="118" width="304" height="75" rx="20" fill="{c_body}" stroke="#1E293B" stroke-width="3" />
          <rect x="10" y="138" width="300" height="12" fill="#FFFFFF" opacity="0.35" />
          <circle cx="302" cy="145" r="12" fill="{c_lamp}" stroke="#1E293B" stroke-width="2" />
          <circle cx="18" cy="145" r="9" fill="#FF0055" stroke="#1E293B" stroke-width="2" />
          <line x1="160" y1="118" x2="160" y2="190" stroke="#1E293B" stroke-width="2.5" />
          <circle cx="68" cy="195" r="28" fill="#1E293B" stroke="#0F172A" stroke-width="2.5" />
          <circle cx="68" cy="195" r="16" fill="#F1F5F9" stroke="#1E293B" stroke-width="2" />
          <circle cx="68" cy="195" r="7" fill="{c_body}" />
          <circle cx="252" cy="195" r="28" fill="#1E293B" stroke="#0F172A" stroke-width="2.5" />
          <circle cx="252" cy="195" r="16" fill="#F1F5F9" stroke="#1E293B" stroke-width="2" />
          <circle cx="252" cy="195" r="7" fill="{c_body}" />
        </g>
        """)
        
    # 8 People at bottom: y = 570 to 1100 (4x2 grid)
    pw = 125
    ph = 230
    p_start_x = 55
    p_start_y = 570
    p_gap_x = 180
    p_gap_y = 260
    
    for idx, (shirt, hair, hair_style) in enumerate(PEOPLE_COLORS):
        col = idx % 4
        row = idx // 4
        x = p_start_x + col * p_gap_x
        y = p_start_y + row * p_gap_y
        
        skin = "#FFDFC4"
        blush = "#FF8FA3"
        cx = x + pw / 2
        cy = y + 70
        
        hair_svg = ""
        if hair_style == "short":
            hair_svg = f"""<path d="M -30 45 Q -25 12 0 12 Q 25 12 30 45 C 20 26 0 24 -30 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <polygon points="-6,12 0,2 6,12" fill="{hair}" stroke="#1E293B" stroke-width="2" />"""
        elif hair_style == "pigtails":
            hair_svg = f"""<path d="M -30 45 Q -25 16 0 16 Q 25 16 30 45 C 20 28 0 26 -30 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <circle cx="-36" cy="40" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <circle cx="36" cy="40" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />"""
        elif hair_style == "curly":
            hair_svg = f"""<circle cx="-18" cy="22" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <circle cx="0" cy="15" r="16" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <circle cx="18" cy="22" r="14" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />"""
        elif hair_style == "headband":
            hair_svg = f"""<path d="M -30 50 Q -25 16 0 16 Q 25 16 30 50 C 20 30 0 28 -30 50 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <path d="M -28 46 Q 0 22 28 46" fill="none" stroke="#FF007F" stroke-width="6" />"""
        elif hair_style == "cap":
            hair_svg = f"""<path d="M -28 42 Q 0 8 28 42 Z" fill="#EF4444" stroke="#1E293B" stroke-width="2.5" />
                           <path d="M -5 38 L 40 34 L 36 46 L -2 47 Z" fill="#DC2626" stroke="#1E293B" stroke-width="2.5" />"""
        elif hair_style == "buns":
            hair_svg = f"""<path d="M -30 46 Q 0 20 30 46 C 20 30 0 30 -30 46 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <circle cx="-22" cy="12" r="13" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <circle cx="22" cy="12" r="13" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />"""
        elif hair_style == "glasses":
            hair_svg = f"""<path d="M -30 45 Q -20 16 0 16 Q 20 16 30 45 C 15 26 0 26 -30 45 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <rect x="-20" y="38" width="17" height="15" rx="4" fill="none" stroke="#3B82F6" stroke-width="3" />
                           <rect x="3" y="38" width="17" height="15" rx="4" fill="none" stroke="#3B82F6" stroke-width="3" />"""
        elif hair_style == "ponytail":
            hair_svg = f"""<path d="M -30 46 Q -25 16 0 16 Q 25 16 30 46 C 20 28 0 26 -30 46 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />
                           <path d="M 24 35 Q 44 22 42 56 Q 33 46 24 42 Z" fill="{hair}" stroke="#1E293B" stroke-width="2.5" />"""

        body.append(f"""
        <rect x="{x - 6}" y="{y - 6}" width="{pw + 12}" height="{ph + 12}" rx="14" class="cut-guide" />
        <g transform="translate({cx}, {cy})">
          <path d="M -22 82 Q -38 55 -34 38" stroke="#1E293B" stroke-width="10" stroke-linecap="round" fill="none" />
          <circle cx="-34" cy="38" r="7" fill="{skin}" stroke="#1E293B" stroke-width="2.5" />
          <path d="M 22 82 Q 38 98 34 115" stroke="#1E293B" stroke-width="10" stroke-linecap="round" fill="none" />
          <circle cx="34" cy="115" r="7" fill="{skin}" stroke="#1E293B" stroke-width="2.5" />
          <path d="M -26 78 L 26 78 L 24 145 L -24 145 Z" fill="{shirt}" stroke="#1E293B" stroke-width="3" />
          <rect x="-8" y="62" width="16" height="20" rx="4" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          <circle cx="0" cy="105" r="5" fill="#FFFFFF" opacity="0.9" />
          <circle cx="0" cy="122" r="5" fill="#FFFFFF" opacity="0.9" />
          <circle cx="0" cy="46" r="28" fill="{skin}" stroke="#1E293B" stroke-width="3" />
          <circle cx="-28" cy="48" r="5.5" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          <circle cx="28" cy="48" r="5.5" fill="{skin}" stroke="#1E293B" stroke-width="2" />
          <circle cx="-10" cy="44" r="4" fill="#1E293B" />
          <circle cx="10" cy="44" r="4" fill="#1E293B" />
          <circle cx="-8" cy="42" r="1.5" fill="#FFFFFF" />
          <circle cx="12" cy="42" r="1.5" fill="#FFFFFF" />
          <ellipse cx="-16" cy="52" rx="4.5" ry="3" fill="{blush}" />
          <ellipse cx="16" cy="52" rx="4.5" ry="3" fill="{blush}" />
          <path d="M -8 56 Q 0 66 8 56" fill="none" stroke="#1E293B" stroke-width="2.8" stroke-linecap="round" />
          {hair_svg}
        </g>
        """)
        
    return svg_wrap("\n".join(body))

def main():
    targets = [
        ("15_Books.svg", generate_15_books()),
        ("3_Bookshelves.svg", generate_3_bookshelves()),
        ("4_Cars.svg", generate_4_cars()),
        ("8_People.svg", generate_8_people()),
        ("Option2_Cars_and_People_Single_Page.svg", generate_cars_and_people_single_page())
    ]
    
    for fname, svg_str in targets:
        svg_file = os.path.join(OUT_DIR, fname)
        with open(svg_file, "w", encoding="utf-8") as f:
            f.write(svg_str)
        pdf_file = svg_file.replace(".svg", ".pdf")
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf_file, svg_file], check=True)
        # Also copy directly to Downloads
        dest_pdf = os.path.join(DOWNLOADS, os.path.basename(pdf_file))
        subprocess.run(["cp", "-f", pdf_file, dest_pdf], check=True)
        print(f"Generated {dest_pdf}")

    # Combine Option 1 (Bookshelves + Books)
    opt1_combined = os.path.join(DOWNLOADS, "Option1_Bookshelves_and_Books_Color.pdf")
    subprocess.run([
        "pdfunite",
        os.path.join(DOWNLOADS, "3_Bookshelves.pdf"),
        os.path.join(DOWNLOADS, "15_Books.pdf"),
        opt1_combined
    ], check=True)
    print(f"Combined {opt1_combined}")

    # Combine Option 2 (Cars + People 2-page)
    opt2_combined = os.path.join(DOWNLOADS, "Option2_Cars_and_People_Color.pdf")
    subprocess.run([
        "pdfunite",
        os.path.join(DOWNLOADS, "4_Cars.pdf"),
        os.path.join(DOWNLOADS, "8_People.pdf"),
        opt2_combined
    ], check=True)
    print(f"Combined {opt2_combined}")

if __name__ == "__main__":
    main()
