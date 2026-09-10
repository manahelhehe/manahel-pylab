"""
Flame Fractal Generator (petal/flower symmetry)
------------------------------------------------
Generates a "flame fractal" -- an Iterated Function System (IFS) rendered
with the chaos-game algorithm, nonlinear "variations", log-density
tone mapping, and color blending. This is the family of fractal behind
the layered, glowing, flower-like image you shared (as produced by tools
like Apophysis / JWildfire).

Dependencies: numpy, matplotlib
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


# ----------------------------------------------------------------------
# 1. NONLINEAR VARIATIONS
#    Flame fractals don't just apply affine maps (a,b,c,d,e,f) -- they
#    warp the result with a nonlinear "variation" function. These are
#    what turn straight-line IFS attractors into organic, curved shapes.
# ----------------------------------------------------------------------
def variation(x, y, kind):
    r2 = x * x + y * y + 1e-12
    r = np.sqrt(r2)
    theta = np.arctan2(y, x)

    if kind == "linear":
        return x, y
    if kind == "sinusoidal":
        return np.sin(x), np.sin(y)
    if kind == "spherical":
        return x / r2, y / r2
    if kind == "swirl":
        return x * np.cos(r2) - y * np.sin(r2), x * np.sin(r2) + y * np.cos(r2)
    if kind == "petal":
        # Modulates radius by cos(k*theta) -> k-lobed flower/petal shape
        k = 5
        rr = r * np.cos(k * theta)
        return rr * np.cos(theta), rr * np.sin(theta)
    raise ValueError(f"Unknown variation: {kind}")


# ----------------------------------------------------------------------
# 2. BASE FUNCTION SYSTEM
#    Each transform: (x,y) -> variation(a*x + b*y + e, c*x + d*y + f)
#    "weight"    = probability of being chosen each step
#    "color"     = a scalar in [0,1] blended along the orbit for coloring
# ----------------------------------------------------------------------
base_transforms = [
    # a,     b,     c,     d,     e,     f,    weight, variation,     color
    (0.78, -0.28,  0.28,  0.78,  0.06,  0.12,  0.55,  "petal",       0.95),
    (0.55,  0.25, -0.25,  0.55, -0.10,  0.20,  0.12,  "sinusoidal",  0.55),
    (-0.55, 0.35,  0.35,  0.55,  0.15, -0.10,  0.18,  "spherical",   0.75),
    (0.45,  0.00,  0.00,  0.45,  0.00,  0.30,  0.15,  "swirl",       0.25),
]

# Impose N_SYM-fold rotational ("flower petal") symmetry: duplicate every
# base transform, rotated around the origin by multiples of 2*pi/N_SYM.
# This is the standard flame-fractal trick for producing flower patterns.
N_SYM = 5
symmetric_transforms = []
for (a, b, c, d, e, f, w, var, col) in base_transforms:
    for k in range(N_SYM):
        ang = 2 * np.pi * k / N_SYM
        ca, sa = np.cos(ang), np.sin(ang)
        # Rotation matrix R(ang) composed with the linear part [[a,b],[c,d]]
        ra = ca * a - sa * c
        rb = ca * b - sa * d
        rc = sa * a + ca * c
        rd = sa * b + ca * d
        re = ca * e - sa * f
        rf = sa * e + ca * f
        symmetric_transforms.append(
            dict(a=ra, b=rb, c=rc, d=rd, e=re, f=rf,
                 weight=w / N_SYM, variation=var, color=col)
        )

weights = np.array([t["weight"] for t in symmetric_transforms])
weights /= weights.sum()


# ----------------------------------------------------------------------
# 3. CHAOS GAME ITERATION
#    Start at a random point, repeatedly apply a randomly chosen
#    transform (weighted by probability), and record the orbit after
#    a short "skip" burn-in period (so it has converged onto the
#    attractor before we start plotting).
# ----------------------------------------------------------------------
def run_chaos_game(n_points=400_000, skip=20, seed=7):
    rng = np.random.default_rng(seed)
    n_t = len(symmetric_transforms)

    A = np.array([t["a"] for t in symmetric_transforms])
    B = np.array([t["b"] for t in symmetric_transforms])
    C = np.array([t["c"] for t in symmetric_transforms])
    D = np.array([t["d"] for t in symmetric_transforms])
    E = np.array([t["e"] for t in symmetric_transforms])
    F = np.array([t["f"] for t in symmetric_transforms])
    COL = np.array([t["color"] for t in symmetric_transforms])
    VAR = [t["variation"] for t in symmetric_transforms]

    total = n_points + skip
    choices = rng.choice(n_t, size=total, p=weights)

    xs = np.empty(n_points)
    ys = np.empty(n_points)
    cs = np.empty(n_points)

    x = y = c = 0.0
    j = 0
    for i in range(total):
        k = choices[i]
        nx = A[k] * x + B[k] * y + E[k]
        ny = C[k] * x + D[k] * y + F[k]
        nx, ny = variation(nx, ny, VAR[k])
        x, y = nx, ny
        c = 0.5 * (c + COL[k])  # exponential color blending along orbit
        if i >= skip:
            xs[j] = x
            ys[j] = y
            cs[j] = c
            j += 1
    return xs, ys, cs


# ----------------------------------------------------------------------
# 4. HISTOGRAM ACCUMULATION (density + averaged color per pixel)
# ----------------------------------------------------------------------
def render(xs, ys, cs, width=500, height=900):
    # Rare points can shoot far from the main attractor (e.g. the
    # spherical variation blows up near r -> 0). Use percentiles instead
    # of raw min/max so a handful of outliers don't collapse the whole
    # attractor into a single pixel.
    x_min, x_max = np.percentile(xs, [0.5, 99.5])
    y_min, y_max = np.percentile(ys, [0.5, 99.5])

    count_hist, _, _ = np.histogram2d(
        xs, ys, bins=[width, height], range=[[x_min, x_max], [y_min, y_max]]
    )
    color_hist, _, _ = np.histogram2d(
        xs, ys, bins=[width, height], range=[[x_min, x_max], [y_min, y_max]],
        weights=cs,
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        mean_color = np.where(count_hist > 0, color_hist / count_hist, 0)

    # Log tone mapping: flame fractals use log density (not linear) so that
    # both the faint outer structure and the bright core are visible at once.
    log_density = np.log1p(count_hist)
    log_density /= log_density.max()

    return mean_color, log_density


# ----------------------------------------------------------------------
# 5. COLOR MAPPING + COMPOSITE (pink/white palette, like the reference image)
# ----------------------------------------------------------------------
def colorize(mean_color, log_density):
    pink_cmap = LinearSegmentedColormap.from_list(
        "flower_pink",
        ["#fce8e8", "#f4bbcd", "#fe8eac", "#fe739f", "#df356e", "#6b1539"],
    )
    rgba = pink_cmap(mean_color)
    alpha = np.clip(log_density[..., None] * 1.8, 0, 1) ** 0.6

    bg = np.ones_like(rgba[..., :3])  # white background
    final_rgb = rgba[..., :3] * alpha + bg * (1 - alpha)
    return final_rgb


# ----------------------------------------------------------------------
# 6. MAIN
# ----------------------------------------------------------------------
if __name__ == "__main__":
    xs, ys, cs = run_chaos_game(n_points=600_000, skip=20, seed=7)
    mean_color, log_density = render(xs, ys, cs, width=500, height=900)
    final_rgb = colorize(mean_color, log_density)

    plt.figure(figsize=(6, 10.8), facecolor="white")
    plt.imshow(np.transpose(final_rgb, (1, 0, 2)), origin="lower")
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig("flame_fractal.png", dpi=200, facecolor="white",
                bbox_inches="tight", pad_inches=0)
    print("Saved flame_fractal.png")
