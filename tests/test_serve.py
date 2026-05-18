from madewithml.serve import make_json_safe


def test_make_json_safe_converts_probabilities_to_plain_floats():
    results = [
        {
            "prediction": "computer-vision",
            "probabilities": {"computer-vision": 0.9, "natural-language-processing": 0.1},
        }
    ]

    safe_results = make_json_safe(results)

    assert safe_results == results
    assert isinstance(safe_results[0]["probabilities"]["computer-vision"], float)
