from macrodash.analytics.regime import classify_regime


def test_hawkish():
    z = {"US2Y": 3, "UK2Y": 1.5, "DE2Y": 1, "US10Y": 1.5, "US_2s10s": -2, "DXY": 2, "SPX": -1, "GOLD": -1.5}
    assert classify_regime(z)["name"] == "Hawkish repricing"


def test_risk_off():
    z = {"SPX": -2.5, "SX5E": -2, "US_HY_OAS": 2, "VIX": 2.5, "US10Y": -1.5, "DE10Y": -1, "GOLD": 1}
    assert classify_regime(z)["name"] == "Risk-off / flight to quality"


def test_quiet():
    z = {"SPX": 0.1, "US10Y": -0.2, "DXY": 0.1, "GOLD": 0.05}
    assert classify_regime(z)["name"] == "Quiet / range-bound"


def test_empty():
    assert classify_regime({})["name"] == "Insufficient data"
