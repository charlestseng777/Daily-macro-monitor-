from macrodash.analytics.inflation import attribute
from macrodash.narrative import fmt, llm


def test_attribution():
    assert attribute(10, 8, 2)["driver"] == "inflation"
    assert attribute(10, 1, 9)["driver"] == "real"
    assert attribute(10, 5, 5)["driver"] == "both"
    assert attribute(1, 6, -5)["driver"] == "offsetting"
    assert attribute(0.2, 0.1, 0.1)["driver"] == "none"
    assert attribute(None, 1, 1)["driver"] == "unknown"


def test_word_limit():
    text = "One two three. Four five six seven eight nine ten."
    assert fmt.word_limit(text, 5) == "One two three."
    assert fmt.bp(0) == "unch" and fmt.bp(-6.4) == "-6bp" and fmt.pct(0.42) == "+0.4%"


FACTS = {"levels": {"US2Y": {"last": 3.5, "d1": 20.19}, "DXY": {"d1": 1.02}}, "policy": [{"priced_12m_bp": -49.1}]}


def test_grounding_accepts_facts_and_names():
    text = "US 2Y yields rose 20bp to 3.50% while the dollar gained 1.0%; 2s10s and the S&P 500 fell. Fed pricing -49bp."
    assert llm.ungrounded_numbers(text, FACTS) == []


def test_grounding_rejects_invented_numbers():
    text = "Payrolls rose by 254k and yields jumped 37bp."
    bad = llm.ungrounded_numbers(text, FACTS)
    assert "254" in bad and "37" in bad


def test_validate_word_limits():
    long = " ".join(["word"] * 120)
    problems = llm.validate({"regime_paragraph": long, "regions": {"US": "ok"}}, FACTS)
    assert any("100 words" in p for p in problems)
