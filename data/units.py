from datetime import datetime
from enum import Enum


class VitalSignCategory(Enum):
    BLOOD_PRESSURE = "Blood Pressure"
    HEIGHT = "Height"
    PULSE = "Pulse"
    RESPIRATION = "Respiration"
    SPO2 = "SpO2"
    TEMPERATURE = "Temperature"
    WEIGHT = "Weight"

    def matches(self, string: str):
        return (self.value in string
                or self.name in string
                or self.name.lower() in string)


class HeightUnit(Enum):
    CM = 100
    M = 1
    FT = 3.28084
    IN = 39.37008

    @staticmethod
    def from_value(value: str):
        value = value.upper()

        for name, unit in HeightUnit.__members__.items():
            if name == value:
                return unit

        try:
            if value in "INCHES" and "INCHES".index(value) == 0:
                return HeightUnit.IN
            elif value in "FEET" and "FEET".index(value) == 0:
                return HeightUnit.FT
            elif value in "METERS" and "METERS".index(value) == 0:
                return HeightUnit.M
            elif value in "CENTIMETERS" and "CENTIMETERS".index(value) == 0:
                return HeightUnit.CM
        except Exception as e:
            print(e)
            return None


class WeightUnit(Enum):
    G = 1000
    KG = 1
    LB = 2.204623

    @staticmethod
    def from_value(value: str):
        value = value.upper()

        for name, unit in WeightUnit.__members__.items():
            if name == value:
                return unit

        try:
            if value in "POUNDS" and "POUNDS".index(value) == 0:
                return WeightUnit.LB
            elif value == "KILOS":
                return WeightUnit.KG
            elif value in "KILOGRAMS" and "KILOGRAMS".index(value) == 0:
                return WeightUnit.KG
            elif value in "GRAMS" and "GRAMS".index(value) == 0:
                return WeightUnit.G
        except Exception as e:
            print(e)
            return None


class TemperatureUnit(Enum):
    C = 0
    F = 32

    @staticmethod
    def from_value(value: str):
        value = value.upper()
        value.replace("DEGREES", "").replace("°", "").replace(" ", "")

        # XML export units
        if value == "DEGF":
            return TemperatureUnit.F
        elif value == "DEGC":
            return TemperatureUnit.C

        for name, unit in WeightUnit.__members__.items():
            if name == value:
                return unit

        try:
            if value in "FAHRENHEIT" and "FAHRENHEIT".index(value) == 0:
                return TemperatureUnit.F
            elif value in "CELCIUS" and "CELCIUS".index(value) == 0:
                return TemperatureUnit.C
        except Exception as e:
            print(e)
            return None

    def convertTo(self, temperatureUnit, value):
        if self is temperatureUnit:
            return value
        elif self is TemperatureUnit.F:
            return (value - 32) * 5/9
        else:
            return value * 9/5 + 32


def convert(to_unit, from_unit, value: float):
    return value / from_unit.value * to_unit.value


def calculate_bmi(normalized_height: float, normalized_weight: float,
                  normal_height_unit, normal_weight_unit, verbose: bool):
    height_meters = convert(HeightUnit.M, normal_height_unit, normalized_height)
    weight_kilos = convert(WeightUnit.KG, normal_weight_unit, normalized_weight)
    divisor = height_meters ** 2
    if divisor == 0.0:
        raise Exception("Invalid height in meters provided to calculate_bmi - would create division by zero error")
    bmi = round(weight_kilos / divisor, 2)
    if verbose:
        print(f"Calculated BMI {bmi} ({round(weight_kilos, 2)}" + \
              f" kg / {round(height_meters, 2)} m^2)")
    return bmi


base_stats = {
    "count": 0,
    "sum": 0,
    "avg": None,
    "max": None,
    "min": None,
    "mostRecent": None,
    "unit": None,
    "list": []}


def set_stats(stats: dict, time, value):
    if time is None:
        stats["list"].append(value)
    else:
        stats["list"].append({"time": time, "value": value})
    stats["count"] += 1
    if type(value) == list:
        for i in range(len(value)):
            c_value = value[i]
            stats["sum"][i] += c_value
            if stats["max"][i] is None:
                stats["max"][i] = c_value
                stats["min"][i] = c_value
            elif stats["max"][i] < c_value:
                stats["max"][i] = c_value
            elif stats["min"][i] > c_value:
                stats["min"][i] = c_value
    else:
        stats["sum"] += value
        if stats["max"] is None:
            stats["max"] = value
            stats["min"] = value
        elif stats["max"] < value:
            stats["max"] = value
        elif stats["min"] > value:
            stats["min"] = value


def get_age(birth_date):
    today = datetime.today()
    age = today.year - birth_date.year
    test_date = datetime(today.year, birth_date.month, birth_date.day, 0, 0, 0)
    age += round((today - test_date).days / 365, 1)
    return age