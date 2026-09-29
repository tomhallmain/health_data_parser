from datetime import datetime

import pytest

from data.food_data import FoodData
from data.symptom_set import SymptomSet

FOOD_CSV = (
    "logDateTime,logType,mealType,foodName,foodPrep,foodServingSize,categories,okDiets,warningDiets,dangerDiets\n"
    "2022-03-11 08:00:00,meal,Breakfast,Oats,Boiled,Regular,,,Low FODMAP,\n"
    "2022-03-11 12:30:00,meal,Lunch,Oats,Boiled,Small,,,,Low FODMAP\n"
    "2022-03-12 12:30:00,meal,Lunch,Rice,Steamed,Huge,,,,\n"
)

SYMPTOM_CSV = (
    "Symptom/Condition,Onset/Time of Diagnosis,Conclusion,Medications,Stimulants,Comment,Severity\n"
    'Headache,2021-02,2021-06,"Medication A, Medication B",Stimulant A,,2\n'
    "Fatigue,2020-03,,Medication A,,,1\n"
    "Old issue,2001-01,2002-01,,,,1\n"
    "Bad row,2021-01,,,,,not-a-number\n"
)


@pytest.fixture
def food_csv(tmp_path):
    path = tmp_path / "food_data.csv"
    path.write_text(FOOD_CSV, encoding="utf-8")
    return path


@pytest.fixture
def symptom_csv(tmp_path):
    path = tmp_path / "symptom_data.csv"
    path.write_text(SYMPTOM_CSV, encoding="utf-8")
    return path


class TestFoodData:
    def test_parses_records(self, food_csv):
        food_data = FoodData(str(food_csv), False)
        assert food_data.to_print
        assert food_data.record_count == 3
        # Serving sizes are weighted: Regular 6 + Small 3, Huge 12
        assert food_data.foods["Oats::Boiled"]["count"] == 9
        assert food_data.foods["Rice::Steamed"]["count"] == 12
        assert food_data.avg_meals_per_day == 1.5

    def test_diet_seen_as_danger_moves_out_of_warning(self, food_csv):
        food_data = FoodData(str(food_csv), False)
        assert not food_data.has_warning_diets()
        assert food_data.get_top_n_danger_diets(1) == ["Low FODMAP (2 records)"]

    def test_missing_file_is_not_printed(self, tmp_path):
        assert not FoodData(str(tmp_path / "missing.csv"), False).to_print

    def test_saves_chart(self, food_csv, tmp_path):
        food_data = FoodData(str(food_csv), False)
        food_data.save_most_common_foods_chart(80, str(tmp_path))
        assert (tmp_path / "most_common_foods.png").exists()


class TestSymptomSet:
    def test_parses_valid_rows_after_start_year(self, symptom_csv):
        symptom_set = SymptomSet(str(symptom_csv), start_year=2010)
        assert [s.name for s in symptom_set.symptoms] == ["Headache", "Fatigue"]
        assert symptom_set.severities == [1, 2]
        assert symptom_set.dates_recorded == [datetime(2020, 3, 1), datetime(2021, 2, 1)]

    def test_symptom_fields(self, symptom_csv):
        headache = SymptomSet(str(symptom_csv), start_year=2010).symptoms[0]
        assert headache.start_date == datetime(2021, 2, 1)
        assert headache.end_date == datetime(2021, 6, 1)
        assert headache.is_resolved
        assert headache.medications == ["MEDICATION A", "MEDICATION B"]
        assert headache.stimulants == ["STIMULANT A"]
        assert headache.severity == 2

    def test_resolved_and_unresolved(self, symptom_csv):
        symptom_set = SymptomSet(str(symptom_csv), start_year=2010)
        assert symptom_set.has_both_resolved_and_unresolved_symptoms()
        assert [s.name for s in symptom_set.get_filtered_symptoms()] == ["Fatigue"]

    def test_missing_file_has_no_symptoms(self, tmp_path):
        assert SymptomSet(str(tmp_path / "missing.csv")).symptoms == []

    def test_saves_chart(self, symptom_csv, tmp_path):
        symptom_set = SymptomSet(str(symptom_csv), start_year=2010)
        symptom_set.set_chart_start_date()
        symptom_set.generate_chart_data()
        symptom_set.save_chart(30, str(tmp_path))
        assert symptom_set.to_print
        assert (tmp_path / "symptoms.png").exists()
