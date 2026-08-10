from components.event_interaction import parse_interactive_answer


def test_parse_interactive_answer_extracts_claims_and_preserves_sections() -> None:
    answer = """Finding text.

**Notable event transcript**

- **t=0.53–1.13 h** — Pressure crossed its high limit. <!--event:TR-05:0.533:1.133-->
- **t=2.00 h** — Similar event in two runs. <!--event:TR-01:2.0:2.0--><!--event:TR-03:2.1:2.1-->

**Recommendation**

Create more pressure headroom."""

    parsed = parse_interactive_answer(answer)

    assert parsed.before == "Finding text."
    assert parsed.after.startswith("**Recommendation**")
    assert len(parsed.claims) == 2
    assert parsed.claims[0]["text"] == "t=0.53–1.13 h — Pressure crossed its high limit."
    assert parsed.claims[0]["references"] == [
        {"transition_id": "TR-05", "start_hour": 0.533, "end_hour": 1.133}
    ]
    assert len(parsed.claims[1]["references"]) == 2


def test_parse_interactive_answer_leaves_unmarked_answer_unchanged() -> None:
    answer = "No interactive transcript is present."

    parsed = parse_interactive_answer(answer)

    assert parsed.before == answer
    assert parsed.claims == ()
    assert parsed.after == ""
