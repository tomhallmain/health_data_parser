from health_data_parser.model.reference_range import Interpretation


class ObservationStore:
    """The observations recorded from clinical records, with the queries the
    reports need.

    Lab results are indexed by test description ("code") and by date +
    primary code id; each date + test pair holds at most one result. Vital
    signs are kept separately, since they're reported as series rather than as
    results.
    """

    def __init__(self):
        # obs_id -> Observation, in the order recorded
        self.observations = {}
        # One LabTest per distinct test, in the order first seen
        self.tests = []
        # Test description -> the range text applied to results of that test
        # that came without one (see analysis.abnormal)
        self.ranges = {}
        self.vitals = []
        self._by_datecode = {}
        # Test description -> primary code ids, in the order first seen
        self._code_ids = {}

    def add(self, observation):
        self.observations[observation.obs_id] = observation
        if not any(test is observation.test for test in self.tests):
            self.tests.append(observation.test)
        code_ids = self._code_ids.setdefault(observation.code, [])
        if observation.primary_code_id not in code_ids:
            code_ids.append(observation.primary_code_id)
        self._by_datecode[observation.datecode] = observation

    def add_vital(self, observation):
        self.vitals.append(observation)

    def is_recorded(self, datecode):
        return datecode in self._by_datecode

    def find(self, date, code_id):
        return self._by_datecode.get(date + code_id)

    @property
    def codes(self):
        """Test descriptions, sorted."""
        return sorted(self._code_ids)

    def code_ids(self, code):
        return list(self._code_ids[code])

    @property
    def dates(self):
        """Dates with lab results, most recent first."""
        return sorted({o.date for o in self.observations.values()}, reverse=True)

    @property
    def reference_dates(self):
        """Dates with at least one result that has a reference range, oldest first."""
        return sorted({o.date for o in self.observations.values() if o.has_reference})

    @property
    def abnormal_results(self):
        """Primary code id -> abnormal results for that code, in the order recorded."""
        results = {}
        for observation in self.observations.values():
            if observation.is_abnormal:
                results.setdefault(observation.primary_code_id, []).append(observation)
        return results

    @property
    def abnormal_dates(self):
        """Dates with abnormal results, most recent first."""
        return sorted({o.date for o in self.observations.values() if o.is_abnormal}, reverse=True)

    @property
    def abnormal_count(self):
        return sum(1 for o in self.observations.values() if o.is_abnormal)

    def interpretations_by_code(self, include_in_range=True):
        """Test description -> interpretation texts found for it, in severity order.

        Every test with abnormal results is included. Without
        `include_in_range`, "in range" interpretations are left out, so a test
        whose only abnormal results are in range maps to an empty list. (They
        can occur with in-range results skipped when the abnormal boundary is
        negative.)
        """
        found = {}
        for observation in self.observations.values():
            if observation.is_abnormal:
                found.setdefault(observation.code, set()).add(observation.reference.interpretation)
        return {code: [i.text for i in Interpretation.ordered(include_in_range) if i in found[code]]
                for code in sorted(found)}

    @property
    def vitals_by_date(self):
        """Date -> vital-sign observations on it, dates oldest first."""
        by_date = {}
        for observation in sorted(self.vitals, key=lambda o: o.date):
            by_date.setdefault(observation.date, []).append(observation)
        return by_date
