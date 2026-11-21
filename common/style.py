"""
style.py — colours shared by every plot, so A/B/C look the same everywhere.

Validated categorical palette, slots 1-3 (colour-blind safe for 3 series).
"""

COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
NAMES = {"A": "A  threat", "B": "B  passer", "C": "C  bird"}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e4e3df"
ZONE = "#9a9893"


def style_axes(ax):
    """Quiet grid and axes so the data stands out."""
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_MUTED)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
