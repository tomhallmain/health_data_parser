from health_data_parser.utils.logger import setup_logger

logger = setup_logger('abnormal')


def apply_shared_reference_ranges(store, rules, verbose=False):
    """Classify results that came without a reference range, using the range
    recorded for the same test on another date.

    Each test's range comes from its most recent result that has one, and is
    recorded in store.ranges. It's applied to a result only when the result's
    unit appears in the range text, so a range isn't applied across units.
    """
    for code in store.codes:
        range_text = _most_recent_range(store, code)
        if range_text is not None:
            store.ranges[code] = range_text

    for code in sorted(store.ranges):
        for date in store.dates:
            for code_id in store.code_ids(code):
                observation = store.find(date, code_id)
                if observation is None or observation.has_reference:
                    continue
                if verbose:
                    logger.info(f"Found missing reference range for code {code} on {date} "
                                "- attempting to apply range from other results")
                observation.reference = rules.reference_range(
                    store.ranges[code], observation.value, observation.value_string,
                    observation.unit, check_units_match=True)


def _most_recent_range(store, code):
    for date in store.dates:
        for code_id in store.code_ids(code):
            observation = store.find(date, code_id)
            if observation is not None and observation.has_reference:
                return observation.reference.range_text
    return None
