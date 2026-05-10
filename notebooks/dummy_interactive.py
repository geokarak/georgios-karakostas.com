import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    ## Notebook demo
    Move the slider and see the chart and stats update instantly.
    """)
    return


@app.cell
def _(mo):
    points = mo.ui.slider(5, 120, value=30, step=1, label="Number of points")
    noise = mo.ui.slider(0, 100, value=20, step=5, label="Noise level")
    mo.hstack([points, noise], justify="start", gap=2)
    return noise, points


@app.cell
def _(noise, points):
    import math
    import random

    random.seed(42)
    xs = list(range(points.value))
    ys = []
    for x in xs:
        base = 40 + 35 * math.sin((x / max(points.value, 1)) * math.pi * 2)
        jitter = (random.random() - 0.5) * noise.value
        ys.append(max(0, base + jitter))
    return xs, ys


@app.cell
def _(mo, xs, ys):
    sample_points = list(zip(xs, ys))[:12]
    rows = "\n".join(f"- `{x:>2}` -> `{y:6.2f}`" for x, y in sample_points)
    mo.md(f"""### First 12 points\n{rows}""")
    return


@app.cell
def _(mo, ys):
    average = sum(ys) / len(ys)
    peak = max(ys)
    mo.md(f"""**Average:** `{average:.2f}`  \n**Peak:** `{peak:.2f}`""")
    return


if __name__ == "__main__":
    app.run()
