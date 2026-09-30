import argparse
import sys

from health_data_parser.errors import HealthDataParseError
from health_data_parser.options import (
    ParseOptions, parse_bool, parse_boundary, parse_skip_dates, parse_start_year)
from health_data_parser.pipeline import DataParser
from health_data_parser.utils.logger import setup_logger
from health_data_parser.utils.translations import _

logger = setup_logger('parse_data')


def build_parser():
    parser = argparse.ArgumentParser(
        prog="health-data-parser",
        description=_("Parse an Apple Health export (plus optional custom data) into a PDF "
                      "report and JSON/CSV/text files."))
    parser.add_argument("data_export_dir", metavar="EXPORT_DIR",
                        help=_("Apple Health export directory (containing clinical-records/)"))

    def option(name, **kwargs):
        # Each option under its original underscore name, plus a hyphenated alias
        names = [f"--{name}"]
        if "_" in name:
            names.append(f"--{name.replace('_', '-')}")
        parser.add_argument(*names, **kwargs)

    option("output_dir", metavar="DIR",
           help=_("Write outputs here instead of the export directory (created if missing)"))
    option("only_clinical_records", action="store_true",
           help=_("Do not parse export.xml (much faster)"))
    option("start_year", metavar="YEAR", help=_("Exclude results from before this year"))
    option("skip_dates", metavar="DATES",
           help=_("Exclude results from these dates (comma-separated, YYYY-MM-DD)"))
    option("skip_long_values", action="store_true",
           help=_("Exclude observations with excessively long result values (full diagnostic "
                  "report text mixed into a single observation)"))
    option("filter_abnormal_in_range", action="store_true", dest="skip_in_range_abnormal_results",
           help=_("Only collect abnormal results that are out of range, not those near the ends "
                  "of their range"))
    option("in_range_abnormal_boundary", metavar="FRACTION",
           help=_("How close to either end of a range counts as abnormal (default 0.15, i.e. 15%%; "
                  "absolute value must be under 0.5)"))
    option("extra_observations", metavar="CSV", dest="extra_observations_csv",
           help=_("Laboratory data not in Apple Health, in the format of "
                  "sample_templates/sample_observations_data.csv"))
    option("symptom_data", metavar="CSV", dest="symptom_data_csv",
           help=_("Current and past symptoms, for a timeline chart in the PDF report"))
    option("food_data", metavar="CSV", dest="food_data_csv",
           help=_("Food log, for nutrition charts in the PDF report"))
    option("report_highlight_abnormal_results", metavar="true|false",
           help=_("Highlight abnormal results in the report's observation tables (default true)"))
    option("birth_date", metavar="YYYY-MM-DD",
           help=_("Subject birth date for the report, if not found in export.xml"))
    option("json_add_all_vitals", action="store_true",
           help=_("Include every vital sign reading in observations.json (can be large with a "
                  "wearable)"))
    option("custom_only", action="store_true",
           help=_("Skip the Apple Health export data; report only on the custom files given"))
    parser.add_argument("-v", "--verbose", action="store_true", help=_("Log more detail"))
    return parser


def options_from_args(args):
    kwargs = {
        "data_export_dir": args.data_export_dir,
        "output_dir": args.output_dir,
        "verbose": args.verbose,
        "only_clinical_records": args.only_clinical_records,
        "skip_long_values": args.skip_long_values,
        "skip_in_range_abnormal_results": args.skip_in_range_abnormal_results,
        "json_add_all_vitals": args.json_add_all_vitals,
        "custom_only": args.custom_only,
        "extra_observations_csv": args.extra_observations_csv,
        "symptom_data_csv": args.symptom_data_csv,
        "food_data_csv": args.food_data_csv,
        "birth_date": args.birth_date,
    }
    if args.start_year is not None:
        kwargs["start_year"] = parse_start_year(args.start_year)
    if args.skip_dates is not None:
        kwargs["skip_dates"] = parse_skip_dates(args.skip_dates)
    if args.in_range_abnormal_boundary is not None:
        kwargs["in_range_abnormal_boundary"] = parse_boundary(args.in_range_abnormal_boundary)
    if args.report_highlight_abnormal_results is not None:
        kwargs["report_highlight_abnormal_results"] = parse_bool(
            args.report_highlight_abnormal_results, "--report_highlight_abnormal_results")
    return ParseOptions(**kwargs)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    if not argv:
        parser.print_help()
        sys.exit()

    # Exits with status 2 on unknown options, 0 after -h/--help
    args = parser.parse_args(argv)
    try:
        options = options_from_args(args)
    except HealthDataParseError as e:
        logger.error(str(e))
        parser.print_usage()
        sys.exit(1)

    data_parser = DataParser(options)
    try:
        if options.custom_only:
            data_parser.create_custom_report()
        else:
            data_parser.run()
    except HealthDataParseError as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
