from datetime import datetime
from types import SimpleNamespace

import pytest

from health_data_parser.model.food import FoodData
from health_data_parser.model.symptom import SymptomSet
from health_data_parser.reporting.charts.food import save_food_chart
from health_data_parser.reporting.charts.symptoms import _shift_date, chart_start_date, save_symptom_charts

FOOD_CSV = (
    "logDateTime,logType,mealType,foodName,foodPrep,foodServingSize,categories,okDiets,warningDiets,dangerDiets\n"
    "2022-03-11 08:00:00,meal,Breakfast,Oats,Boiled,Huge,,,,\n"
    "2022-03-12 12:30:00,meal,Lunch,Rice,Steamed,Huge,,,,\n"
)
HEADER = "Name,Start Date,End Date,Medications,Stimulants,Comment,Severity\n"


def symptom_file(tmp_path, rows):
    path = tmp_path / "symptoms.csv"
    path.write_text(HEADER + rows, encoding="utf-8")
    return str(path)


def test_food_chart(tmp_path):
    csv_path = tmp_path / "food.csv"
    csv_path.write_text(FOOD_CSV, encoding="utf-8")
    food = FoodData(str(csv_path), False)

    chart = save_food_chart(food, str(tmp_path))

    assert chart.food is food
    assert chart.path == str(tmp_path / "most_common_foods.png")
    assert (tmp_path / "most_common_foods.png").exists()


class TestSymptomCharts:
    def test_resolved_and_unresolved_charts(self, tmp_path):
        symptoms = SymptomSet(symptom_file(tmp_path, (
            "Headache,2021-02,2021-06,Medication A,Coffee,,2\n"
            # Same stimulant in another case: one legend entry
            "Fatigue,2020-03,,medication a,coffee,,1\n")))

        charts = save_symptom_charts(symptoms, str(tmp_path))

        assert charts.all_symptoms_path == str(tmp_path / "symptoms.png")
        assert charts.unresolved_path == str(tmp_path / "symptoms_unresolved.png")
        assert (tmp_path / "symptoms.png").exists()
        assert (tmp_path / "symptoms_unresolved.png").exists()

    def test_only_unresolved(self, tmp_path):
        symptoms = SymptomSet(symptom_file(tmp_path, "Fatigue,2020-03,,,,,1\n"))
        charts = save_symptom_charts(symptoms, str(tmp_path))
        assert charts.unresolved_path is None
        assert not (tmp_path / "symptoms_unresolved.png").exists()

    def test_no_symptoms(self, tmp_path):
        assert save_symptom_charts(SymptomSet(symptom_file(tmp_path, "")), str(tmp_path)) is None


class TestChartStartDate:
    @staticmethod
    def symptom_set(dates, chronic=False, start_year=None):
        return SimpleNamespace(dates_recorded=dates, has_chronic_conditions_from_start=chronic,
                               start_year=start_year)

    def test_earliest_start(self):
        assert chart_start_date(self.symptom_set([datetime(2021, 5, 1)])) == datetime(2021, 5, 1)

    def test_three_months_earlier_with_chronic_symptoms(self):
        assert chart_start_date(self.symptom_set([datetime(2021, 5, 1)], chronic=True)) == datetime(2021, 2, 1)
        assert chart_start_date(self.symptom_set([datetime(2021, 2, 1)], chronic=True)) == datetime(2020, 11, 1)

    def test_day_is_clamped_to_the_month(self):
        # Three months before May 31 has no 31st
        assert chart_start_date(self.symptom_set([datetime(2021, 5, 31)], chronic=True)) == datetime(2021, 2, 28)

    def test_start_year_is_the_floor(self):
        assert chart_start_date(self.symptom_set([datetime(2015, 5, 1)], start_year=2020)) == datetime(2020, 1, 1)

    def test_without_dates_three_years_back(self):
        start = chart_start_date(self.symptom_set([]))
        assert start.year == datetime.today().year - 3

    @pytest.mark.parametrize("date, years, months, expected", [
        (datetime(2024, 2, 29), -3, 0, datetime(2021, 2, 28)),
        (datetime(2021, 1, 15), 0, -3, datetime(2020, 10, 15)),
        (datetime(2021, 3, 31), 0, -1, datetime(2021, 2, 28)),
    ])
    def test_shift_date(self, date, years, months, expected):
        assert _shift_date(date, years=years, months=months) == expected
