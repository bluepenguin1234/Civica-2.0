"""
Generates og_image.png (1200×630) — the OpenGraph social preview image for Civica.
Run once: python generate_og_image.py
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

NAVY  = (26, 58, 92)     # #1a3a5c
BLUE  = (26, 127, 240)   # #1a7ff0
WHITE = (255, 255, 255)
WHITE_65 = (255, 255, 255, 165)
GRAY  = (156, 163, 175)  # --muted

W, H = 1200, 630

def find_font(bold=False):
    candidates = []
    if bold:
        candidates = [
            'C:/Windows/Fonts/arialbd.ttf',
            'C:/Windows/Fonts/calibrib.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
        ]
    else:
        candidates = [
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/calibri.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
        ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + 2*radius, y0 + 2*radius], fill=fill)
    draw.ellipse([x1 - 2*radius, y0, x1, y0 + 2*radius], fill=fill)
    draw.ellipse([x0, y1 - 2*radius, x0 + 2*radius, y1], fill=fill)
    draw.ellipse([x1 - 2*radius, y1 - 2*radius, x1, y1], fill=fill)

def draw_civica_logo(draw, x, y, size=80):
    """Draw the Civica 'A' logo icon: blue rounded rect + white inverted-V + crossbar."""
    r = size // 8
    rounded_rect(draw, [x, y, x+size, y+size], r, BLUE)
    # White A-shape: two lines meeting at top center, one crossbar
    lw = max(3, size // 13)
    cx = x + size // 2
    top_y = y + size * 0.22
    bot_y = y + size * 0.82
    left_x = x + size * 0.20
    right_x = x + size * 0.80
    bar_y = y + size * 0.60
    bar_lx = x + size * 0.30
    bar_rx = x + size * 0.70
    draw.line([(left_x, bot_y), (cx, top_y)], fill=WHITE, width=lw)
    draw.line([(cx, top_y), (right_x, bot_y)], fill=WHITE, width=lw)
    draw.line([(bar_lx, bar_y), (bar_rx, bar_y)], fill=WHITE, width=lw)

def main():
    img = Image.new('RGB', (W, H), NAVY)
    draw = ImageDraw.Draw(img)

    # Subtle gradient overlay — draw lighter bands at top
    for i in range(200):
        alpha = int(18 * (1 - i / 200))
        draw.line([(0, i), (W, i)], fill=(255, 255, 255, alpha))

    bold_path  = find_font(bold=True)
    light_path = find_font(bold=False)

    try:
        font_logo   = ImageFont.truetype(bold_path,  68) if bold_path else ImageFont.load_default()
        font_tag    = ImageFont.truetype(light_path, 28) if light_path else ImageFont.load_default()
        font_sub    = ImageFont.truetype(light_path, 22) if light_path else ImageFont.load_default()
        font_pills  = ImageFont.truetype(bold_path,  18) if bold_path else ImageFont.load_default()
    except Exception:
        font_logo = font_tag = font_sub = font_pills = ImageFont.load_default()

    # Logo icon — center horizontally, upper area
    logo_size = 92
    logo_x = (W - logo_size) // 2
    logo_y = 120
    draw_civica_logo(draw, logo_x, logo_y, logo_size)

    # Logotype: "civi" navy-on-white-ish → white, "ca" blue
    ltype_y = logo_y + logo_size + 24
    civica_text = 'civica'
    # Measure total width
    if hasattr(font_logo, 'getlength'):
        civi_w = font_logo.getlength('civi')
        ca_w   = font_logo.getlength('ca')
    else:
        civi_w = font_logo.getsize('civi')[0]
        ca_w   = font_logo.getsize('ca')[0]
    total_w = civi_w + ca_w
    ltype_x = (W - total_w) // 2
    draw.text((ltype_x, ltype_y), 'civi', font=font_logo, fill=WHITE)
    draw.text((ltype_x + civi_w, ltype_y), 'ca', font=font_logo, fill=BLUE)

    # Tagline
    tagline = 'Research-grade housing intelligence for every US county.'
    if hasattr(font_tag, 'getlength'):
        tag_w = font_tag.getlength(tagline)
    else:
        tag_w = font_tag.getsize(tagline)[0]
    tag_x = (W - tag_w) // 2
    tag_y = ltype_y + 80
    draw.text((tag_x, tag_y), tagline, font=font_tag, fill=(200, 212, 228))

    # Sub-line
    sub = '2,820 counties scored · 100% federal data · No agents · No ads'
    if hasattr(font_sub, 'getlength'):
        sub_w = font_sub.getlength(sub)
    else:
        sub_w = font_sub.getsize(sub)[0]
    sub_x = (W - sub_w) // 2
    sub_y = tag_y + 44
    draw.text((sub_x, sub_y), sub, font=font_sub, fill=(120, 140, 165))

    # Three pill badges at bottom
    pills = ['Affordability', 'Economic Vitality', 'Market Dynamics', 'Climate Risk', 'Population']
    pill_h = 36
    pill_pad_x = 22
    pill_gap = 12
    pill_y = H - 90

    # Calculate total width of all pills
    pill_widths = []
    for p in pills:
        if hasattr(font_pills, 'getlength'):
            pw = font_pills.getlength(p)
        else:
            pw = font_pills.getsize(p)[0]
        pill_widths.append(pw + pill_pad_x * 2)
    total_pills_w = sum(pill_widths) + pill_gap * (len(pills) - 1)
    px = (W - total_pills_w) // 2

    pill_bg = (255, 255, 255, 20)  # semi-transparent
    for i, (p, pw) in enumerate(zip(pills, pill_widths)):
        x0, y0 = px, pill_y
        x1, y1 = px + pw, pill_y + pill_h
        # Draw pill background
        rounded_rect(draw, [x0, y0, x1, y1], pill_h // 2, (40, 70, 110))
        # Text centered in pill
        if hasattr(font_pills, 'getlength'):
            tw = font_pills.getlength(p)
        else:
            tw = font_pills.getsize(p)[0]
        tx = x0 + (pw - tw) // 2
        ty = y0 + (pill_h - 18) // 2
        draw.text((tx, ty), p, font=font_pills, fill=(160, 190, 225))
        px += pw + pill_gap

    out_path = os.path.join(os.path.dirname(__file__), 'og_image.png')
    img.save(out_path, 'PNG', optimize=True)
    print(f'Saved: {out_path}  ({W}×{H}px)')

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
