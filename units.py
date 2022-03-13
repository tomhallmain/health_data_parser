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
        return self.value in string or self.name in string or self.name.lower() in string


class HeightUnit(Enum):
    CM = 100
    M = 1
    FT = 3.28084
    IN = 39.37008

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


def calculate_bmi(normalized_height: float, normalized_weight: float, verbose: bool):
    height_meters = convert(HeightUnit.M, normal_height_unit, normalized_height)
    weight_kilos = convert(WeightUnit.KG, normal_weight_unit, normalized_weight)
    bmi = round(weight_kilos / (height_meters ** 2), 2)
    if verbose:
        print("Calculated BMI " + str(bmi) + " (" + str(round(weight_kilos, 2)) + " kg / " + str(round(height_meters, 2)) + " m^2)")
    return bmi


def set_stats(stats: dict, time, value):
    if time == None:
        stats["list"].append(value)
    else:
        stats["list"].append({"time": time, "value": value})
    stats["count"] += 1
    if type(value) == list:
        for i in range(len(value)):
            c_value = value[i]
            stats["sum"][i] += c_value
            if stats["max"][i] == None:
                stats["max"][i] = c_value
                stats["min"][i] = c_value
            elif stats["max"][i] < c_value:
                stats["max"][i] = c_value
            elif stats["min"][i] > c_value:
                stats["min"][i] = c_value
    else:
        stats["sum"] += value
        if stats["max"] == None:
            stats["max"] = value
            stats["min"] = value
        elif stats["max"] < value:
            stats["max"] = value
        elif stats["min"] > value:
            stats["min"] = value



