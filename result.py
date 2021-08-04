import re

class Result:
    def __init__(self, range_data, value, value_string):
        self.range_text = range_data[0]["text"]
        self.is_abnormal_result = False
        self.is_range_type = False
        self.is_binary_type = False

        if value != None and not isinstance(value, str):
            val_range_matcher = re.search("(\d+\.\d+|\d+) *(-|–) *(\d+\.\d+|\d+)", self.range_text)

            if val_range_matcher:
                self.is_range_type = True
                self.range_lower = float(val_range_matcher.group(1))
                self.range_upper = float(val_range_matcher.group(3))
                
                if self.range_lower > self.range_upper:
                    temp = self.range_upper
                    self.range_upper = self.range_lower
                    self.range_lower = temp
                    temp = None
                
                low_out_of_range = value < self.range_lower
                high_out_of_range = value > self.range_upper
                self.range_span = self.range_upper - self.range_lower
                low_end_of_range = high_end_of_range = False
                
                if self.range_span > 0:
                    low_end_of_range = not low_out_of_range and (value - self.range_lower) / self.range_span < 0.15
                    high_end_of_range = not high_out_of_range and (self.range_upper - value) / self.range_span < 0.15
                
                if low_out_of_range or high_out_of_range or low_end_of_range or high_end_of_range:
                    self.is_abnormal_result = True
                    self.range = str(self.range_lower) + " - " + str(self.range_upper)

                    if low_out_of_range:
                        self.interpretation = "---"
                    elif low_end_of_range:
                        self.interpretation = "--"
                    elif high_end_of_range:
                        self.interpretation = "+++"
                    elif high_out_of_range:
                        self.interpretation = "++++"

            val_range_matcher = None

        elif value == None and value_string != None and isinstance(value_string, str):
            self.is_binary_type = True

            if self.range_text == "NEG" or re.match("negative", self.range_text, flags=re.IGNORECASE):
                if not value_string == "NEG" and not re.match("negative", value_string, flags=re.IGNORECASE):
                    self.is_abnormal_result = True
            elif re.match("clear", self.range_text, flags=re.IGNORECASE) and not re.match("clear", value_string, flags=re.IGNORECASE):
                self.is_abnormal_result = True
            elif re.match("positive", value_string, flags=re.IGNORECASE):
                self.is_abnormal_result = True

            if self.is_abnormal_result:
                self.interpretation = "++"

        if not self.is_abnormal_result:
            self.interpretation = ""


    def get_result_interpretation_text(self):
        if self.interpretation == "---":
            return "LOW OUT OF RANGE"
        elif self.interpretation == "--":
            return "Low in range"
        elif self.interpretation == "++":
            return "Non-negative result"
        elif self.interpretation == "+++":
            return "High in range"
        elif self.interpretation == "++++":
            return "HIGH OUT OF RANGE"
        else:
            return ""

