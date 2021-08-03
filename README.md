
# Apple Health Data Parser

Simple parser to extract laboratory test results from Apple Health. In the current iteration only CSV and text file output are supported.

## Usage

Clone this repository and ensure python is installed. Provide the location of the Apple Health exported data directory to the script at runtime.

```bash
$ python apple_health_data_parser.py path/to/apple_health_export ${args}
```

Depending on the filters set and data found in the export directory, one or more files will be created with the extracted data.

## Limitations

If there is more than one result for the same result code on a single date, only the first result will be recorded.

Test codes that resolve to the same description will be collated regardless of their codings

This script has only been tested with data from a few medical institutions in eastern US. It likely will need to be updated for other medical institutions if they have minor structural differences in their data.

