from madewithml.predict import decode, format_prob


def test_decode_labels_from_indices():
    index_to_class = {0: "computer-vision", 1: "natural-language-processing"}

    assert decode([1, 0], index_to_class) == ["natural-language-processing", "computer-vision"]


def test_format_prob_maps_probabilities_to_class_labels():
    index_to_class = {0: "computer-vision", 1: "natural-language-processing"}

    assert format_prob([0.25, 0.75], index_to_class) == {
        "computer-vision": 0.25,
        "natural-language-processing": 0.75,
    }
