"""
Generate kobra_opcodes.ko — complete Shygazun byte table in Kobra format.
Run from any directory: python gen_opcodes.py
"""
import sys
import os

sys.path.insert(0, r'C:\DjinnOS\DjinnOS_Shyagzun')
from shygazun.kernel.constants.byte_table import _BYTE_TABLE_CSV

# Tongue → T-number assignment (ordered as they appear)
AKINEN_TONGUES = [
    "Lotus", "Rose", "Sakura", "Daisy", "AppleBlossom",
    "Aster", "Grapevine", "Cannabis",
    "Dragon", "Virus", "Bacteria", "Excavata", "Archaeplastida",
    "Myxozoa", "Archaea", "Protist", "Immune", "Neural",
    "Serpent", "Beast", "Cherub", "Chimera", "Faerie", "Djinn",
    # YeYe T25–T50
    "Fold", "Topology", "Phase", "Gradient", "Curvature",
    "Prion", "Blood", "Moon", "Koi", "Rope",
    "Hook", "Fang", "Circle", "Ledger", "Bond",
    "Venus", "Gaia", "Janus", "Thanatos", "Saturn",
    "Corpse", "Furnace", "Square", "Flesh", "Eye", "Blade",
    # YeShu T51–T78
    "Ouranos", "Pontus", "Ourea", "Oceanus", "Coeus",
    "Crius", "Hyperion", "Iapetus", "Theia", "Rhea",
    "Themis", "Mnemosyne", "Phoebe", "Tethys", "Cronus",
    "Brontes", "Steropes", "Arges", "Cottus", "Briareos",
    "Gyges", "Nereus", "Thaumas", "Phorcys", "Ceto",
    "Eurybia", "Typhon", "Antaeus",
]
TONGUE_NUM = {t: i + 1 for i, t in enumerate(AKINEN_TONGUES)}

# Non-akinen pseudo-tongues (reserved/meta — include as comments)
META_TONGUES = {"Reserved", "MetaTopology", "MetaPhysics", "Physics", "Chemistry"}

# Group boundaries
def group(tnum):
    if tnum is None:
        return "META"
    if 1 <= tnum <= 24:
        return "YeGaoh"
    if 25 <= tnum <= 50:
        return "YeYe"
    if 51 <= tnum <= 78:
        return "YeShu"
    return "META"

# Parse byte table
lines = _BYTE_TABLE_CSV.strip().split('\n')
tongue_order = []
tongue_entries = {}
seen = set()

for line in lines[1:]:
    parts = line.split(',', 4)
    if len(parts) < 4:
        continue
    dec_str, binary, tongue, symbol = parts[0], parts[1], parts[2], parts[3]
    meaning = parts[4].strip() if len(parts) > 4 else ''
    dec = int(dec_str)
    hex_addr = f'0x{dec:04X}'

    if tongue not in seen:
        tongue_order.append(tongue)
        seen.add(tongue)
        tongue_entries[tongue] = []
    tongue_entries[tongue].append((dec, hex_addr, binary, symbol, meaning))

# Generate output
out = []
out.append('# Shygazun Byte Table — Complete Akinen Opcode Map')
out.append('# Source: byte_table.py (authoritative)')
out.append('# Format per entry: [decimal hex binary symbol] — meaning')
out.append('# Groups: YeGaoh (T1–T24) · YeYe (T25–T50) · YeShu (T51–T78)')
out.append(f'# Total entries: {sum(len(v) for v in tongue_entries.values())}')
out.append('')

current_group = None

for tongue in tongue_order:
    entries = tongue_entries[tongue]
    tnum = TONGUE_NUM.get(tongue)
    grp = group(tnum)

    # Group header
    if grp != current_group and grp != "META":
        current_group = grp
        out.append('')
        out.append(f'# {"="*60}')
        if grp == "YeGaoh":
            out.append('# YeGaoh Group — Tongues T1–T24 — Core Type Kernel')
            out.append('# Primitive types through ontological ground')
        elif grp == "YeYe":
            out.append('# YeYe Group — Tongues T25–T50 — Scale/Topology/Physics')
            out.append('# Phase geometry through creative destruction')
        elif grp == "YeShu":
            out.append('# YeShu Group — Tongues T51–T78 — Hardware Abstraction Layer')
            out.append('# Virtual address through watchdog (routed via Ne not Oy)')
        out.append(f'# {"="*60}')
        out.append('')

    if tongue in META_TONGUES:
        if entries:
            out.append(f'# --- {tongue} (non-akinen annotations) ---')
            for dec, hex_addr, binary, symbol, meaning in entries:
                out.append(f'# [{dec} {hex_addr} {binary}] {symbol} — {meaning}')
            out.append('')
        continue

    # Tongue block
    byte_start = entries[0][0]
    byte_end = entries[-1][0]
    hex_start = f'0x{byte_start:04X}'
    hex_end = f'0x{byte_end:04X}'
    t_label = f'T{tnum}' if tnum else '?'

    out.append(f'Lo{tongue} : {t_label} {{  # {t_label} — {len(entries)} akinen — {hex_start}–{hex_end}')
    for dec, hex_addr, binary, symbol, meaning in entries:
        out.append(f'  [{dec} {hex_addr} {binary} {symbol}] — {meaning}')
    out.append('}')
    out.append('')

content = '\n'.join(out)

# Write output files
paths = [
    r'C:\AmbroflowEngine\ambroflow\kobra\kobra_opcodes.ko',
    r'C:\DjinnOS\DjinnOS_Shyagzun\shygazun\kernel\kobra\kobra_opcodes.ko',
]
for p in paths:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Written: {p}')

print(f'Total lines: {len(out)}')
print(f'Total akinen entries: {sum(len(tongue_entries[t]) for t in tongue_order if t not in META_TONGUES)}')
