"""
Ambroflow Engine
================
Python game runtime for the KLGS series.

Separate from the Atelier (atelier-api / atelier-desktop), which is the
authoring and production factory.  This engine handles:

  - Dungeon generation and runtime (BSP, tile, encounter)
  - Encounter resolution (combat, negotiation, observation, trap, lore)
  - Skill / perk runtime
  - Pathfinding (A* over collision map)
  - Game state machines
  - Live sanity tracking
  - Quest completion tracking
  - Inventory management
  - Alchemy system
  - Journal system
  - Ko dream sequence / VITRIOL assignment
  - Void Wraith live observation
  - Orrery client (writes outcomes to atelier-api)
"""
