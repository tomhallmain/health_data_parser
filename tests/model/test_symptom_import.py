from health_data_parser.model.symptom import ImportMode, Symptom, import_symptoms


def symptom(name="Headache", start="2021-02", end="2021-06", medications="", severity=2, comment=""):
    return Symptom([name, start, end, medications, "", comment, str(severity)])


def test_append_keeps_everything():
    existing = [symptom()]
    imported = [symptom(), symptom("Fatigue")]

    symptoms, updated = import_symptoms(existing, imported, ImportMode.APPEND)

    assert [s.name for s in symptoms] == ["Headache", "Headache", "Fatigue"]
    assert updated == 0


def test_replace_drops_existing():
    symptoms, updated = import_symptoms([symptom()], [symptom("Fatigue")], ImportMode.REPLACE)

    assert [s.name for s in symptoms] == ["Fatigue"]
    assert updated == 0


def test_merge_updates_matches_and_adds_the_rest():
    existing = [symptom(), symptom("Fatigue", start="2020-03", end="")]
    imported = [
        symptom(medications="Medication A", severity=5, comment="Worse"),
        # Same name, different dates: a separate episode
        symptom(start="2022-01", end=""),
    ]

    symptoms, updated = import_symptoms(existing, imported, ImportMode.MERGE)

    assert updated == 1
    assert [(s.name, s.start_text) for s in symptoms] == [
        ("Headache", "2021-02"), ("Fatigue", "2020-03"), ("Headache", "2022-01")]
    headache = symptoms[0]
    assert headache is existing[0]
    assert (headache.medications, headache.severity, headache.comment) == (["Medication A"], 5, "Worse")


def test_merge_matches_on_parsed_dates():
    # "2021-02" and "2021-02-01" name the same date
    existing = [symptom(start="2021-02")]

    symptoms, updated = import_symptoms(existing, [symptom(start="2021-02-01", severity=7)], ImportMode.MERGE)

    assert updated == 1
    assert len(symptoms) == 1
    assert symptoms[0].severity == 7


def test_inputs_are_not_reordered_or_extended():
    existing = [symptom()]
    imported = [symptom("Fatigue")]

    import_symptoms(existing, imported, ImportMode.APPEND)
    import_symptoms(existing, imported, ImportMode.MERGE)

    assert [s.name for s in existing] == ["Headache"]
