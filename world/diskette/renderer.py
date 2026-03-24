"""
Diskette — ASCII board renderer.

Board layout (columns A-F, rows 1-6):

      A   B   C   D   E   F
   1 [ ] [1] [ ] [ ] [ ] [ ]
   2 [ ] [ ] [ ] [ ] [ ] [ ]
   3 [ ] [ ] [ ] [ ] [ ] [ ]
   4 [ ] [ ] [ ] [ ] [ ] [ ]
   5 [ ] [ ] [ ] [ ] [ ] [ ]
   6 [ ] [ ] [ ] [ ] [2] [ ]

Symbols:
  1 / 2   — player slot
  *       — disc (in flight)
  @       — player on own disc tile (holding or same-tile pre-catch)
  !       — player on enemy disc tile (about to be hit)
  (space) — empty
"""
from world.diskette.physics import COLS, ROWS, DisketteBoard


def render_board(board: DisketteBoard) -> str:
    p1, p2 = board.players

    # Build lookup: (col, row) → symbol
    # Layering priority: hit > player+disc > disc > player
    grid = {}

    # Discs first (background layer)
    for owner in (p1, p2):
        disc = board.discs[owner.id]
        if disc.in_flight:
            pos = disc.pos
            grid[pos] = grid.get(pos, "") + "disc"

    # Players on top
    for slot, player in enumerate((p1, p2), start=1):
        pos = board.positions[player.id]
        existing = grid.get(pos, "")

        # Determine what disc is at this tile, if any
        own_disc = board.discs[player.id]
        other = p2 if slot == 1 else p1
        enemy_disc = board.discs[other.id]

        own_here = own_disc.in_flight and own_disc.pos == pos
        enemy_here = enemy_disc.in_flight and enemy_disc.pos == pos

        if enemy_here:
            grid[pos] = "!"   # player + enemy disc = hit indicator
        elif own_here:
            grid[pos] = "@"   # player + own disc
        else:
            grid[pos] = str(slot)

    # Discs with no player on them
    for owner in (p1, p2):
        disc = board.discs[owner.id]
        if disc.in_flight:
            pos = disc.pos
            if pos not in grid or grid[pos] == "disc":
                grid[pos] = "*"

    # Render
    col_header = "      " + "   ".join(COLS)
    rows_rendered = []
    for ry, row_label in enumerate(ROWS):
        cells = []
        for cx in range(6):
            sym = grid.get((cx, ry), " ")
            cells.append(f"[{sym}]")
        rows_rendered.append(f"   {row_label} " + " ".join(cells))

    return col_header + "\n" + "\n".join(rows_rendered)


def render_scores(game) -> str:
    p1, p2 = game.players
    s1 = game.scores.get(p1.id, 0)
    s2 = game.scores.get(p2.id, 0)
    return f"|w{p1.key}|n {s1} — {s2} |w{p2.key}|n  (Round {game.round_num})"
