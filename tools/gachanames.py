"""Generate gacha name-plate textures (960x240 PNG) per card, to replace the cut's fixed English
placeholder (Ais Wallenstein). Reads web/data/gacha.json, writes web/data/gachaname/<id>.png.
Usage: python tools/gachanames.py [cardId ...]   (no args = all gacha cards)"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

WEB = config.load()["web"]  # follow config.json (build_web may be pointed at another output dir)
OUT = os.path.join(WEB, "data", "gachaname")
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
W, H = 960, 240


def fit_font(text, size, max_w):
    f = ImageFont.truetype(FONT, size)
    while size > 10:
        if f.getlength(text) <= max_w:
            return f
        size -= 2
        f = ImageFont.truetype(FONT, size)
    return f


# Colours sampled from the game's own plates (the global client ships one per card,
# files/lottery/name/<id>.png): the name is a 3-stop vertical gradient with a dark outline and a
# soft halo, all by rarity; the title above is near-white with a dark navy outline.
STYLE = {
    1: {"fill": [(226, 241, 249), (212, 245, 250), (216, 232, 248)], "stroke": (6, 44, 60), "glow": (128, 180, 251), "tbot": (220, 233, 250)},
    3: {"fill": [(249, 243, 199), (250, 247, 165), (248, 238, 181)], "stroke": (60, 44, 5), "glow": (251, 205, 17), "tbot": (249, 239, 197)},
    4: {"fill": [(241, 227, 226), (198, 230, 249), (240, 222, 246)], "stroke": (45, 7, 61), "glow": (212, 144, 239), "tbot": (241, 225, 246)},
}
STYLE[2] = STYLE[1]
TITLE_TOP, TITLE_STROKE = (242, 243, 245), (11, 45, 85)


def gradient(stops, height):
    """A W x height RGBA strip running through `stops` top to bottom."""
    col = Image.new("RGBA", (1, len(stops)))
    for i, c in enumerate(stops):
        col.putpixel((0, i), (*c, 255))
    return col.resize((W, max(2, int(height))), Image.BILINEAR)


def draw_line(base, text, cy, size, stops, stroke, glow, glow_alpha=230, glow_blur=9):
    if not text:
        return
    f = fit_font(text, size, W - 90)
    w = f.getlength(text)
    x = (W - w) / 2
    asc, desc = f.getmetrics()
    y = cy - (asc + desc) / 2
    sw = max(3, size // 9)
    # halo in the rarity colour: a wide soft layer plus a tight bright one, like the game's plates
    halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).text((x, y), text, font=f, fill=(*glow, glow_alpha), stroke_width=sw + 5, stroke_fill=(*glow, glow_alpha))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(glow_blur * 1.6)))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(glow_blur * 0.6)))
    # dark outline
    ImageDraw.Draw(base).text((x, y), text, font=f, fill=(*stroke, 255), stroke_width=sw, stroke_fill=(*stroke, 255))
    # gradient fill, masked by the glyphs (gradient spans the glyph box)
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).text((x, y), text, font=f, fill=255)
    box = mask.getbbox()
    if not box:
        return
    fill = Image.new("RGBA", base.size, (0, 0, 0, 0))
    fill.paste(gradient(stops, box[3] - box[1]), (0, box[1]))
    base.paste(fill, (0, 0), mask)


def make(title, name, rarity=4):
    st = STYLE.get(rarity, STYLE[4])
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if title:
        draw_line(img, title, 52, 46, [TITLE_TOP, TITLE_TOP, st["tbot"]], TITLE_STROKE, st["glow"], 150, 6)
        draw_line(img, name, 150, 100, st["fill"], st["stroke"], st["glow"])
    else:
        draw_line(img, name, 120, 112, st["fill"], st["stroke"], st["glow"])
    return img


def main_from_cards(card_list, only=None):
    """Generate a name plate per card (title + name). `card_list` is the gacha.json card list."""
    os.makedirs(OUT, exist_ok=True)
    cards = {str(c["id"]): c for c in card_list}
    ids = only or list(cards)
    n = 0
    for cid in ids:
        c = cards.get(cid)
        if not c:
            print("skip (not a card):", cid)
            continue
        make(c.get("title", ""), c.get("name", ""), c.get("rarity", 4)).save(os.path.join(OUT, f"{cid}.png"))
        n += 1
    print(f"wrote {n} name plates to {OUT}")


def main():
    data = json.load(open(os.path.join(WEB, "data", "gacha.json"), encoding="utf-8"))
    main_from_cards(data["cards"], only=sys.argv[1:] or None)


if __name__ == "__main__":
    main()
