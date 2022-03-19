import csv
from datetime import datetime
import os
import matplotlib.pyplot as plt


def _get_size_count(size_str: str):
    size_str = size_str.lower()
    if size_str == "tiny":
        return 1
    elif size_str == "small":
        return 3
    elif size_str == "regular" or size_str == "medium":
        return 6
    elif size_str == "large":
        return 10
    elif size_str == "huge":
        return 12
    else:
        return 0


class FoodData:
    def __init__(self, food_data_loc, verbose):
        self.food_data_loc = food_data_loc

        if os.path.exists(self.food_data_loc) and self.food_data_loc[-4:] == ".csv":
            if verbose:
                print("Using food data file: " + food_data_loc)
        else:
            print("WARNING: Food data CSV file " + self.food_data_loc
                  + " is invalid, skipping food analysis.")
            self.to_print = False
            return

        self.verbose = verbose
        self.record_count = 0
        self.foods = {}
        self.meal_times = []
        self.dates_recorded = []
        self.danger_diets = {}
        self.warning_diets = {}
        datetime_format = "%Y-%m-%d %X"

        try:
            with open(food_data_loc, "r") as f:
                reader = csv.reader(f, delimiter=',', quotechar='"')
                has_seen_header = False
                for row in reader:
                    if not has_seen_header:
                        has_seen_header = True
                        continue
                    name = row[3]
                    prep = row[4]
                    key = name + "::" + prep
                    size = _get_size_count(row[5])
                    ok = list(row[7].split(";"))
                    warning = list(row[8].split(";"))
                    danger = list(row[9].split(";"))
                    for diet in danger:
                        if diet == "":
                            continue
                        if diet not in self.danger_diets:
                            if diet in self.warning_diets:
                                self.danger_diets[diet] = self.warning_diets[diet]
                                del self.warning_diets[diet]
                            else:
                                self.danger_diets[diet] = 0
                        self.danger_diets[diet] += 1
                    for diet in warning:
                        if diet == "":
                            continue
                        if diet not in self.danger_diets:
                            if diet not in self.warning_diets:
                                self.warning_diets[diet] = 0
                            self.warning_diets[diet] += 1
                    if key in self.foods:
                        self.foods[key]["count"] += size
                    else:
                        self.foods[key] = {"name": name,
                                           "prep": prep,
                                           "category": None,
                                           "ok": ok,
                                           "warning": warning,
                                           "danger": danger,
                                           "count": size,
                                           "unknown": True}
                    date_str = row[0]
                    try:
                        date = datetime.fromisoformat(date_str[:10])
                        time = datetime.strptime(date_str, datetime_format)
                    except Exception:
                        time = date
                    if date is None:
                        if verbose:
                            print(
                                "Error collecting date from food data record for " + name)
                    elif date not in self.dates_recorded:
                        self.dates_recorded.append(date)
                    if time is None:
                        if verbose:
                            print(
                                "Error collecting date and time from food data record for " + name)
                    elif time not in self.meal_times:
                        self.meal_times.append(time)
                    self.record_count += 1
        except Exception as e:
            if verbose:
                print(e)
            print("WARNING: Failed to parse food data CSV file " + self.food_data_loc
                  + ", ensure the file is consistent with sample - skipping food analysis.")
            self.to_print = False
            return

        self.meal_times.sort()
        self.avg_meals_per_day = round(
            len(self.meal_times) / len(self.dates_recorded), 1)
        self.to_print = True

    def save_most_common_foods_chart(self, graph_cutoff: int, base_dir: str):
        self.save_loc = os.path.join(base_dir, "most_common_foods.png")
        food_to_plot = {}
        for food in sorted(self.foods.values(), key=lambda f: f["count"]):
            if food["count"] > 10:
                if food["name"] in food_to_plot:
                    food_to_plot[food["name"]] += food["count"]
                else:
                    food_to_plot[food["name"]] = food["count"]

        self.food_labels = [food[:30] for food in sorted(
            food_to_plot.keys(), key=lambda f: food_to_plot[f])]
        self.food_counts = [count for count in sorted(food_to_plot.values())]

        fig, ax = plt.subplots(1)
        ax.barh(self.food_labels[-graph_cutoff:],
                self.food_counts[-graph_cutoff:])
        ax.set_xscale('log')
        plt.tight_layout()
        plt.margins(x=0.02, y=0.02)
        fig.set_size_inches(7, 17)
        fig.savefig(self.save_loc, pad_inches=0.02, bbox_inches='tight')
        fig.clear(True)

    def has_warning_diets(self):
        return len(self.warning_diets) > 0

    def has_danger_diets(self):
        return len(self.danger_diets) > 0

    def get_top_n_danger_diets(self, n: int):
        top_n = []
        for diet in sorted(self.danger_diets,
                           key=lambda d: self.danger_diets[d], reverse=True):
            if len(top_n) == n:
                break
            top_n.append(
                diet + " (" + str(self.danger_diets[diet]) + " records)")
        return top_n

    def get_top_n_warning_diets(self, n):
        top_n = []
        for diet in sorted(self.warning_diets,
                           key=lambda d: self.warning_diets[d], reverse=True):
            if len(top_n) == n:
                break
            top_n.append(
                diet + " (" + str(self.warning_diets[diet]) + " records)")
        return top_n
