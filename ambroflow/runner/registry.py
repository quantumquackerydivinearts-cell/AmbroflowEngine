"""
KLGS Game Registry
==================
Canonical list of all 31 games in Ko's Labyrinth.
The engine uses this for game selection, save state keying, and phase routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GameEntry:
    number:    int
    slug:      str           # e.g. "7_KLGS"
    title:     str
    subtitle:  Optional[str] = None   # short descriptor shown on tile
    built:     bool = False           # True = playable in this build


GAMES: tuple[GameEntry, ...] = (
    GameEntry(1,  "1_KLGS",  "Princess of Eclipses",
              "Luminyx · timeline split · 5237/1728", built=False),
    GameEntry(2,  "2_KLGS",  "Knights of the Veil",
              "Thool origins · Illuminati · nuclear family", built=False),
    GameEntry(3,  "3_KLGS",  "Fullmetal Forest",
              "Forest internet · chimeras · Arks · nuclear", built=False),
    GameEntry(4,  "4_KLGS",  "Secrets of Neverland",
              "Post-nuclear · Sulphera leakage · Threshold Events", built=False),
    GameEntry(5,  "5_KLGS",  "Truth Be Told",
              "Minerva Moon · alchemy as survival · early space empire", built=False),
    GameEntry(6,  "6_KLGS",  "As Within So Without",
              "33rd century · Great Obscenity trigger · Zukoru", built=False),
    GameEntry(7,  "7_KLGS",  "An Alchemist's Labor of Love",
              "Hypatia's apprentice · Saelith born · Ko's Labyrinth", built=True),
    GameEntry(8,  "8_KLGS",  "Reign of Nobody",          built=False),
    GameEntry(9,  "9_KLGS",  "Rise of Alzedros",
              "New entity: Alzedros", built=False),
    GameEntry(10, "10_KLGS", "The Voice of Ko",
              "Ko-centered arc", built=False),
    GameEntry(11, "11_KLGS", "Icons of Time",             built=False),
    GameEntry(12, "12_KLGS", "Students of Sha",
              "Sha · Intellect and Embodied Knowledge", built=False),
    GameEntry(13, "13_KLGS", "Ghosts of Azoth",
              "Azoth · BreathOfKo formula embodied", built=False),
    GameEntry(14, "14_KLGS", "Chimeras of The Archons",
              "Gnostic mythology · cellular liberation", built=False),
    GameEntry(15, "15_KLGS", "Lost Yokai",                built=False),
    GameEntry(16, "16_KLGS", "Battered Stars",            built=False),
    GameEntry(17, "17_KLGS", "Saelith's Mercy",
              "FaeDjinn hybrid · Elemental Resistance · The Test", built=False),
    GameEntry(18, "18_KLGS", "Mystic Blood",
              "KLGS × Mystic Pines · YuYu · sanctioned kill", built=False),
    GameEntry(19, "19_KLGS", "Tides of The Cause",        built=False),
    GameEntry(20, "20_KLGS", "Daath Most Have Seen",
              "Daath · hidden knowledge", built=False),
    GameEntry(21, "21_KLGS", "Callsigns of Thool",
              "Network identification · fascist signal structure", built=False),
    GameEntry(22, "22_KLGS", "Horrors of The Void",       built=False),
    GameEntry(23, "23_KLGS", "Requiem of Po'Elfan",
              "Po'Elfan · demon of anxiety · nonlocal death-song", built=False),
    GameEntry(24, "24_KLGS", "Polar Shift",               built=False),
    GameEntry(25, "25_KLGS", "Galactic Hallows",          built=False),
    GameEntry(26, "26_KLGS", "Fires of Sha",
              "Sha's end · purifying fire · Ko cycle", built=False),
    GameEntry(27, "27_KLGS", "Gourds of Ash",             built=False),
    GameEntry(28, "28_KLGS", "Legacy of Luminyx",
              "Luminyx honored · spirit after 1782", built=False),
    GameEntry(29, "29_KLGS", "Barkeep of Broken Dreams",  built=False),
    GameEntry(30, "30_KLGS", "Death of an Empress",       built=False),
    GameEntry(31, "31_KLGS", "The Great Work",
              "Series conclusion · alchemical Magnum Opus", built=False),
)

GAME_BY_SLUG:   dict[str, GameEntry] = {g.slug:   g for g in GAMES}
GAME_BY_NUMBER: dict[int, GameEntry] = {g.number: g for g in GAMES}