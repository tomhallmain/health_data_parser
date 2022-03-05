
# Apple Health Data Parser

Simple parser to extract laboratory test results from Apple Health. In the current iteration only JSON, CSV and text file output are supported.

## Usage

Clone this repository and ensure python is installed. Provide the location of the Apple Health exported data directory to the script at runtime.

Various filtering options are available:

```bash
$ python parse_data.py path/to/apple_health_export -h

--start_year=[int] 
    Exclude results from before a certain year

--skip_long_values
    Full diagnostic report data may be mixed in as a single observation with 
    health data integrated to Apple Health. Exclude these observations with
    excessively long result output using this flag.

--skip_dates
    Skip dates using a comma-separated list of format YYYY-MM-DD,YYYY-MM-DD

--filter_abnormal_in_range
    By default abnormal results are collected when a range result is within 15% 
    of the higher or lower ends of a range. Exclude these types of results with
    this flag.

--in_range_abnormal_boundary=[float]
    By default abnormal results are collected when a range result is within 15%
    of the higher or lower ends of a range. Change that percentage with this flag.

--report_highlight_abnormal_results=[bool]
    By default abnormal results are highlighted in observations tables on the 
    report. To turn this off, set this value to False.
```

Depending on the filters set and data found in the export directory, one or more files will be created with the extracted data.

- `LaboratoryResultsReport{processDate}.pdf` is a report including summaries and all results

- `observations.json` contains all data collected along with a few statistics

- `observations.csv` contains a matrix with all laboratory test results and ranges

- `abnormal_results.csv` contains a matrix with only abnormal results of laboratory tests if any found

- `abnormal_results_by_code.txt` contains a list of abnormal results by code if any found

- `abnormal_results_by_interpretation.csv` contains a table of all lab codes against abnormal results categories found ("LOW OUT OF RANGE", "Low in range", "Non-negative result", "High in range", "HIGH OUT OF RANGE")

## Limitations

- If there is more than one result for the same result code on a single date, only the first result will be recorded.

- Test codes that resolve to the same description will be collated regardless of their codings.

- Abnormal results can usually only be classified as such if there is a value range for comparison. If this program finds none, it does not mean no abnormal results exist in the data, just that the results cannot be interpreted.

## Disclaimers

The only form of advice expressed in this project is to ensure you are checking your lab test results thoroughly. Abnormality of results is determined by the observed value relative to the data ranges given by licensed laboratories.

Even if all results are within allowable ranges, laboratory tests are only a partial picture of a person's health state. Always consult with a physician for full health evaluations.

This script has only been tested with data from a few medical institutions in eastern US. It likely will need to be updated for other medical institutions if they have minor structural differences in their data, including language differences.

