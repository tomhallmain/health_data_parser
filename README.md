
# Apple Health Data Parser

Simple parser to extract laboratory test results from Apple Health. In the current iteration only CSV and text file output are supported.

## Usage

Clone this repository and ensure python is installed. Provide the location of the Apple Health exported data directory to the script at runtime.

```bash
$ python parse_data.py path/to/apple_health_export ${args}
```

Depending on the filters set and data found in the export directory, one or more files will be created with the extracted data.

- `observations.csv` contains a matrix with all laboratory test results and ranges

- `abnormal_results.csv` contains with only abnormal results of laboratory tests if any found

- `abnormal_results_by_code.txt` contains a list of abnormal results by code if any found

## Limitations

- If there is more than one result for the same result code on a single date, only the first result will be recorded.

- Test codes that resolve to the same description will be collated regardless of their codings.

- Abnormal results can usually only be classified as such if there is a value range for comparison. If this program finds none, it does not mean no abnormal results exist in the data, just that the results cannot be interpreted.

## Disclaimers

The only form of advice expressed in this project is to ensure you are checking your lab test results thoroughly. Abnormality of results is determined by the observed value relative to the data ranges given by licensed laboratories.

Even if all results are within allowable ranges, laboratory tests are only a partial picture of a person's health state. Always consult with a physician for full health evaluations.

This script has only been tested with data from a few medical institutions in eastern US. It likely will need to be updated for other medical institutions if they have minor structural differences in their data.

