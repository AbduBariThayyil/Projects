import os
import math
import subprocess

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

def make_star(cx, cy, r_out=19, r_in=9):
    pts = []
    for k in range(10):
        ang = k * math.pi / 5 - math.pi / 2
        r = r_out if k % 2 == 0 else r_in
        pts.append(f"{cx + r * math.cos(ang):.1f},{cy + r * math.sin(ang):.1f}")
    return " ".join(pts)

def generate_15_books():
    cols = 5
    rows = 3
    # Optimized dimensions: 85px wide, 175px tall
    # In a 235px high shelf, this leaves 60px (~1.5cm) of natural vertical room!
    # 5 books side-by-side = 425px width in a 670px shelf = fits with beautiful spacing!
    bw = 85
    bh = 175
    
    start_x = 45
    start_y = 75
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
            star_pts = make_star(cx_mid, cy_mid, 19, 8.5)
            motif_svg = f'<polygon points="{star_pts}" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />'
        elif motif == "heart":
            motif_svg = f"""<path d="M {cx_mid} {cy_mid + 16} 
                            C {cx_mid - 20} {cy_mid - 4}, {cx_mid - 20} {cy_mid - 22}, {cx_mid} {cy_mid - 10} 
                            C {cx_mid + 20} {cy_mid - 22}, {cx_mid + 20} {cy_mid - 4}, {cx_mid} {cy_mid + 16} Z" 
                            fill="{c_sec}" stroke="#1E293B" stroke-width="2" />"""
        elif motif == "circle":
            motif_svg = f"""<circle cx="{cx_mid}" cy="{cy_mid - 22}" r="12" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />
                            <circle cx="{cx_mid}" cy="{cy_mid + 22}" r="12" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />"""
        elif motif == "stripe":
            motif_svg = f"""<rect x="{x + 20}" y="{cy_mid - 38}" width="{bw - 26}" height="12" rx="2" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />
                            <rect x="{x + 20}" y="{cy_mid - 10}" width="{bw - 26}" height="12" rx="2" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />
                            <rect x="{x + 20}" y="{cy_mid + 18}" width="{bw - 26}" height="12" rx="2" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />"""
        elif motif == "diamond":
            motif_svg = f'<polygon points="{cx_mid},{cy_mid - 22} {cx_mid + 16},{cy_mid} {cx_mid},{cy_mid + 22} {cx_mid - 16},{cy_mid}" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />'

        body.append(f"""
        <!-- Snug Cut Guide: 5px margin around the book -->
        <rect x="{x - 5}" y="{y - 5}" width="{bw + 10}" height="{bh + 10}" rx="10" class="cut-guide" />
        
        <!-- Book Base -->
        <rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="7" fill="{c_main}" stroke="#1E293B" stroke-width="3" />
        
        <!-- Spine on Left -->
        <rect x="{x}" y="{y}" width="16" height="{bh}" rx="5" fill="{c_sec}" stroke="#1E293B" stroke-width="2" />
        <line x1="{x + 3}" y1="{y + 28}" x2="{x + 13}" y2="{y + 28}" stroke="#1E293B" stroke-width="2" />
        <line x1="{x + 3}" y1="{y + bh - 28}" x2="{x + 13}" y2="{y + bh - 28}" stroke="#1E293B" stroke-width="2" />
        
        <!-- Motif Art Centered -->
        {motif_svg}
        
        <!-- Bookmark Ribbon -->
        <polygon points="{x + bw - 20},{y} {x + bw - 6},{y} {x + bw - 6},{y + 32} {x + bw - 13},{y + 24} {x + bw - 20},{y + 32}" fill="{c_sec}" stroke="#1E293B" stroke-width="1.8" />
        
        <!-- Bottom Pages Trim -->
        <rect x="{x + 16}" y="{y + bh - 10}" width="{bw - 18}" height="8" rx="1" fill="#FFFFFF" stroke="#1E293B" stroke-width="1.8" />
        """)
    return svg_wrap("\n".join(body))

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
        <!-- Snug Cut Line: 6px around bookshelf -->
        <rect x="{x - 6}" y="{y - 6}" width="{shelf_w + 12}" height="{shelf_h + 12}" rx="14" class="cut-guide" />
        
        <!-- Bookshelf Frame -->
        <rect x="{x}" y="{y}" width="{shelf_w}" height="{shelf_h}" rx="12" fill="{c_outer}" stroke="#1E293B" stroke-width="3.5" />
        
        <!-- Large Open Shelf Cavity: 235px high x 670px wide! -->
        <rect x="{x + 25}" y="{y + 25}" width="{shelf_w - 50}" height="235" rx="8" fill="{c_inner}" stroke="#CBD5E1" stroke-width="2" />
        
        <!-- Solid Wooden Shelf Plank (Bottom Base) -->
        <rect x="{x + 12}" y="{y + 260}" width="{shelf_w - 24}" height="26" rx="4" fill="{c_trim}" stroke="#1E293B" stroke-width="3" />
        
        <!-- Top Crown Molding -->
        <rect x="{x - 4}" y="{y}" width="{shelf_w + 8}" height="18" rx="6" fill="{c_trim}" stroke="#1E293B" stroke-width="2.5" />
        """)
    return svg_wrap("\n".join(body))

def main():
    pages = [
        ("15_Books.svg", generate_15_books()),
        ("3_Bookshelves.svg", generate_3_bookshelves())
    ]
    
    for fname, svg_str in pages:
        svg_file = os.path.join(OUT_DIR, fname)
        with open(svg_file, "w", encoding="utf-8") as f:
            f.write(svg_str)
        pdf_file = svg_file.replace(".svg", ".pdf")
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf_file, svg_file], check=True)
        dest_pdf = os.path.join(DOWNLOADS, os.path.basename(pdf_file))
        subprocess.run(["cp", "-f", pdf_file, dest_pdf], check=True)
        print(f"Generated {dest_pdf}")

    # Combine Option 1
    opt1_combined = os.path.join(DOWNLOADS, "Option1_Bookshelves_and_Books_Color.pdf")
    subprocess.run([
        "pdfunite",
        os.path.join(DOWNLOADS, "3_Bookshelves.pdf"),
        os.path.join(DOWNLOADS, "15_Books.pdf"),
        opt1_combined
    ], check=True)
    print(f"Combined {opt1_combined}")

if __name__ == "__main__":
    main()
