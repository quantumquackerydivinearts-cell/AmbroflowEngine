"""
Shared void palette for all runner screens.
All colours are (R, G, B) tuples.
"""

# ── Backgrounds ───────────────────────────────────────────────────────────────
VOID          = (  8,   5,  14)   # deepest background
CARD          = ( 16,  10,  26)   # tile / panel background
CARD_HOVER    = ( 26,  18,  40)   # tile hovered
CARD_ACTIVE   = ( 36,  24,  56)   # tile selected / active

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER        = ( 48,  36,  68)   # default tile border
BORDER_HOVER  = ( 90,  70, 115)   # hovered
BORDER_SELECT = (160, 124,  68)   # selected (warm gold)
BORDER_BUILT  = ( 68, 110,  68)   # game is playable

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY  = (185, 168, 145)   # main body text
TEXT_DIM      = ( 95,  85,  75)   # secondary / disabled
TEXT_GOLD     = (200, 162,  72)   # numbers, highlights
TEXT_WHITE    = (230, 220, 210)   # headers

# ── Status dots ───────────────────────────────────────────────────────────────
STATUS_IDLE   = ( 55,  45,  70)   # not started
STATUS_ACTIVE = ( 48, 120, 180)   # in progress
STATUS_DONE   = (180, 142,  58)   # complete

# ── Accent / Ko ───────────────────────────────────────────────────────────────
KO_GOLD       = (210, 170,  80)   # Ko gold accent
KO_SPIRAL_DIM = ( 38,  28,  52)   # faint spiral marks

# ── Star field (used in title + game select bg) ───────────────────────────────
STAR_BRIGHT   = (200, 195, 210)
STAR_MID      = (110, 105, 125)
STAR_DIM      = ( 50,  45,  62)