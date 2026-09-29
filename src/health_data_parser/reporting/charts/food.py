from dataclasses import dataclass
import os

from matplotlib.figure import Figure


@dataclass
class FoodChart:
    food: object
    path: str


def save_food_chart(food_data, output_dir, graph_cutoff=80):
    """Horizontal bars of the most common foods (serving-weighted counts over
    10, grouped by name across preparations), at most `graph_cutoff` of them,
    on a log scale."""
    path = os.path.join(output_dir, "most_common_foods.png")
    food_to_plot = {}
    for food in sorted(food_data.foods.values(), key=lambda f: f["count"]):
        if food["count"] > 10:
            food_to_plot[food["name"]] = food_to_plot.get(food["name"], 0) + food["count"]

    labels = [name[:30] for name in sorted(food_to_plot, key=lambda name: food_to_plot[name])]
    counts = sorted(food_to_plot.values())

    fig = Figure()
    ax = fig.subplots()
    ax.barh(labels[-graph_cutoff:], counts[-graph_cutoff:])
    ax.set_xscale('log')
    fig.tight_layout()
    ax.margins(x=0.02, y=0.02)
    fig.set_size_inches(7, 17)
    fig.savefig(path, pad_inches=0.02, bbox_inches='tight')
    return FoodChart(food_data, path)
