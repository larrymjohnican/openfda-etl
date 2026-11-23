from pipeline.validate import extract_drugs, extract_reactions

REPORT = {
    "safetyreportid": "10001",
    "receivedate": "20260311",
    "patient": {
        "drug": [
            {
                "medicinalproduct": "LIPITOR",
                "activesubstance": {"activesubstancename": "ATORVASTATIN CALCIUM"},
                "drugcharacterization": "1",
                "drugindication": "HYPERCHOLESTEROLAEMIA",
            },
            {
                "medicinalproduct": "ASPIRIN",
                "drugcharacterization": "2",
            },
        ],
        "reaction": [
            {"reactionmeddrapt": "Myalgia", "reactionoutcome": "1"},
            {"reactionmeddrapt": "Fatigue"},
        ],
    },
}


def test_extract_drugs_one_row_per_drug():
    assert extract_drugs(REPORT) == [
        {
            "safetyreportid": "10001",
            "medicinalproduct": "LIPITOR",
            "activesubstancename": "ATORVASTATIN CALCIUM",
            "drugcharacterization": "1",
            "drugindication": "HYPERCHOLESTEROLAEMIA",
        },
        {
            # No nested activesubstance object: name comes back as None.
            "safetyreportid": "10001",
            "medicinalproduct": "ASPIRIN",
            "activesubstancename": None,
            "drugcharacterization": "2",
            "drugindication": None,
        },
    ]


def test_extract_reactions_one_row_per_reaction():
    assert extract_reactions(REPORT) == [
        {"safetyreportid": "10001", "reactionmeddrapt": "Myalgia", "reactionoutcome": "1"},
        {"safetyreportid": "10001", "reactionmeddrapt": "Fatigue", "reactionoutcome": None},
    ]


def test_every_row_carries_the_parent_id():
    rows = extract_drugs(REPORT) + extract_reactions(REPORT)
    assert {r["safetyreportid"] for r in rows} == {"10001"}


def test_empty_arrays_give_no_rows():
    r = {"safetyreportid": "10001", "patient": {"drug": [], "reaction": []}}
    assert extract_drugs(r) == []
    assert extract_reactions(r) == []


def test_missing_arrays_give_no_rows():
    r = {"safetyreportid": "10001", "patient": {}}
    assert extract_drugs(r) == []
    assert extract_reactions(r) == []


def test_missing_patient_gives_no_rows():
    r = {"safetyreportid": "10001"}
    assert extract_drugs(r) == []
    assert extract_reactions(r) == []
