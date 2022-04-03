
# Apple Health Data Parser

Simple parser to extract vitals data and laboratory test results from Apple Health and combine with custom data. Generate a PDF report with visuals as well as JSON, CSV, text file output presenting and analyzing your health data.


## Output

Depending on the filters set and data found in the export directory, one or more files will be created with the extracted data.

- `HealthReport{processDate}.pdf` is a report including summaries, visuals, and all observations data

- `observations.json` contains all data collected along with statistics assembled

- `observations.csv` contains a table with all clinical records results and ranges

- `abnormal_results.csv` contains a table with only abnormal results from clinical records if any found

- `abnormal_results_by_code.txt` contains a list of abnormal results from clinical records by code if any found

- `abnormal_results_by_interpretation.csv` contains a table of all lab codes against abnormal results categories found ("LOW OUT OF RANGE", "Low in range", "Non-negative result", "High in range", "HIGH OUT OF RANGE")


## Usage

Clone this repository and ensure python3 is installed. Provide the location of the Apple Health exported data directory to the script at runtime.

```bash
$ python parse_data.py path/to/apple_health_export ${opts}
```

### Filtering Options

`--only_clinical_records` - Do not attempt to parse default XML export files (much faster)

`--start_year=[int]` - Exclude results from before a certain year

`--skip_dates` - Skip dates using a comma-separated list of format YYYY-MM-DD,YYYY-MM-DD

`--skip_long_values`

Full diagnostic report data may be mixed in as a single observation with health data integrated to Apple Health. Exclude these observations with excessively long result output using this flag.

`--json_add_all_vitals`

If using a wearable, many vital sign observations may be accumulated. By default these are not added to the JSON output - pass this option to add these to the JSON.

### Abnormal Result Handling

`--filter_abnormal_in_range`, `--in_range_abnormal_boundary=[float]`

By default abnormal results are collected when a range result is within 15% of the higher or lower ends of a range. Exclude these types of results or change the percentage used with these flags.

`--report_highlight_abnormal_results=[bool]`

By default abnormal results are highlighted in observations tables on the report. To turn this off, set this value to False.

### External Data

`--extra_observations=path/to/observations_data.csv`

Fill out the sample CSV with data to include laboratory data from providers not hooked up to your Apple Health in the output.

`--symptom_data=path/to/symptom_data.csv`

Fill out the sample CSV with data about current and past symptoms to include a timeline chart in the PDF report. See below for an example chart.

`--food_data=path/to/food_data.csv`

Fill out the sample CSV with data to include nutritional data in the PDF report. See below for an example chart.


## Example Output

Symptom Set Timeline Graph

![](https://github.com/tomhallmain/health_data_parser/blob/main/examples/symptoms_chart.png?raw=true)

Observations Table

![](https://github.com/tomhallmain/health_data_parser/blob/main/examples/observations_table.png?raw=true)

Heart Rate Charts

![](https://github.com/tomhallmain/health_data_parser/blob/main/examples/heart_rate_charts1.png?raw=true)

Heart Rate and Activity Charts

![](https://github.com/tomhallmain/health_data_parser/blob/main/examples/heart_rate_charts2.png?raw=true)

Food Data Chart

![](https://github.com/tomhallmain/health_data_parser/blob/main/examples/food_chart.png?raw=true)


## Limitations

- If there is more than one result for the same result code on a single date, only the first result will be recorded.

- Test codes that resolve to the same description will be collated regardless of their codings.

- Abnormal results can usually only be classified as such if there is a value range for comparison. If this program finds none, it does not mean no abnormal results exist in the data, just that the results cannot be interpreted.


## Disclaimers

The only form of advice expressed in this project is to ensure you are checking your lab test results thoroughly. Abnormality of results is determined by the observed value relative to the data ranges given by licensed laboratories.

Even if all results are within allowable ranges, laboratory tests are only a partial picture of a person's health state. Always consult with a physician for full health evaluations.

This script has only been tested with data from a few medical institutions in eastern US. It likely will need to be updated for other medical institutions if they have minor structural differences in their data, including language differences.
