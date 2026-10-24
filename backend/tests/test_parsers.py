"""Parsers tested against representative payloads of each provider's
documented format (live endpoints are exercised by `python -m macrodash sources`)."""

import json

import pytest

from macrodash.clients import fred, mof, sdmx, stooq, treasury, yahoo
from macrodash.clients.base import SourceError
from macrodash.clients.boe import parse_iadb_csv
from macrodash.clients.feeds import parse_feed
from macrodash.clients.refinitiv import YIELD_FIELDS, parse_interday


def test_fred_graph_csv():
    s = fred.parse_graph_csv("observation_date,DGS10\n2026-10-21,4.02\n2026-10-22,.\n2026-10-23,4.10\n", "DGS10")
    assert list(s.values) == [4.02, 4.10]


def test_fred_graph_csv_old_header():
    s = fred.parse_graph_csv("DATE,DGS2\n2026-10-22,3.50\n", "DGS2")
    assert s.iloc[0] == 3.50


def test_fred_api_json():
    body = json.dumps({"observations": [{"date": "2026-10-22", "value": "3.1"}, {"date": "2026-10-23", "value": "."}]})
    assert len(fred.parse_api_json(body, "X")) == 1


def test_treasury_csv():
    text = 'Date,"1 Mo","2 Yr","10 Yr"\n10/23/2026,3.9,3.50,4.10\n10/22/2026,3.9,3.45,4.05\n'
    s = treasury.parse_year_csv(text, "10 Yr")
    assert s.index[0].day == 22 and s.iloc[-1] == 4.10


def test_sdmx_csv():
    text = "KEY,FREQ,TIME_PERIOD,OBS_VALUE\nEXR.D.USD.EUR.SP00.A,D,2026-10-22,1.1601\nEXR.D.USD.EUR.SP00.A,D,2026-10-23,1.1580\n"
    assert sdmx.parse_sdmx_csv(text, "EXR/D").iloc[-1] == 1.1580
    with pytest.raises(SourceError):
        sdmx.parse_sdmx_csv("a,b\n1,2\n", "X")


def test_boe_iadb_csv():
    s = parse_iadb_csv("DATE,IUDBEDR\n22 Oct 2026,3.75\n23 Oct 2026,3.75\n", "IUDBEDR")
    assert len(s) == 2 and s.index[-1].day == 23


def test_mof_csv():
    text = ("Interest Rate,,,,\nDate,1Y,2Y,10Y,30Y\n2026/10/22,0.85,1.00,1.70,3.30\n2026/10/23,0.86,-,1.72,3.31\n")
    frame = mof.parse_csv(text)
    assert frame.loc["2026-10-23", "10Y"] == 1.72
    assert frame["2Y"].isna().sum() == 1


def test_yahoo_chart():
    body = json.dumps({"chart": {"result": [{"meta": {"gmtoffset": 32400},
                                             "timestamp": [1792540800, 1792627200],
                                             "indicators": {"quote": [{"close": [45000.5, None]}]}}], "error": None}})
    s = yahoo.parse_chart(body, "^N225")
    assert len(s) == 1 and s.iloc[0] == 45000.5
    assert yahoo.fed_funds_contract(2026, 12) == "ZQZ26.CBT"


def test_stooq():
    s = stooq.parse_csv("Date,Open,High,Low,Close\n2026-10-23,4.1,4.2,4.0,4.12\n", "10usy.b")
    assert s.iloc[0] == 4.12
    with pytest.raises(SourceError):
        stooq.parse_csv("Exceeded the daily hits limit", "x")


def test_refinitiv_interday():
    body = json.dumps([{"headers": [{"name": "DATE"}, {"name": "B_YLD_1"}, {"name": "BID"}, {"name": "ASK"}],
                        "data": [["2026-10-23", 4.1, None, None], ["2026-10-22", None, 4.0, 4.02]]}])
    s = parse_interday(body, "US10YT=RR", YIELD_FIELDS)
    assert s.loc["2026-10-23"] == 4.1 and s.loc["2026-10-22"] == pytest.approx(4.01)


def test_rss_and_atom():
    rss = ("<rss><channel><item><title>Speech A</title><link>http://a</link>"
           "<pubDate>Thu, 22 Oct 2026 14:00:00 GMT</pubDate></item></channel></rss>")
    atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Speech B</title>'
            '<link href="http://b"/><updated>2026-10-23T09:00:00Z</updated></entry></feed>')
    assert parse_feed(rss, "Fed")[0]["date"] == "2026-10-22"
    assert parse_feed(atom, "ECB")[0]["url"] == "http://b"


def test_cnbc_chart():
    from macrodash.clients.cnbc import parse_chart
    body = json.dumps({"barData": {"priceBars": [
        {"tradeTime": "20261022000000", "close": "3.551"}, {"tradeTime": "20261023000000", "close": "3.602"}]}})
    s = parse_chart(body, "IT10Y-IT")
    assert s.iloc[-1] == 3.602 and s.index[0].day == 22
    with pytest.raises(SourceError):
        parse_chart("<html>", "X")


def test_sdmx_xml_both_flavours():
    specific = ('<message:StructureSpecificData xmlns:message="m"><DataSet><Series>'
                '<Obs TIME_PERIOD="2026-10-22" OBS_VALUE="2.65"/><Obs TIME_PERIOD="2026-10-23" OBS_VALUE="2.70"/>'
                '</Series></DataSet></message:StructureSpecificData>')
    generic = ('<m:GenericData xmlns:m="m" xmlns:generic="g"><generic:Series><generic:Obs>'
               '<generic:ObsDimension value="2026-10-23"/><generic:ObsValue value="2.71"/>'
               '</generic:Obs></generic:Series></m:GenericData>')
    assert sdmx.parse_any(specific, "X").iloc[-1] == 2.70
    assert sdmx.parse_any(generic, "X").iloc[-1] == 2.71
    assert sdmx.parse_any("Title;x\n2026-10-23;2,72;\n", "X").iloc[-1] == 2.72


def test_bundesbank_semicolon_sdmx_csv():
    text = "﻿DATAFLOW;BBK_STD_FREQ;TIME_PERIOD;OBS_VALUE\nBBK:BBSIS;D;2026-10-22;3,31\nBBK:BBSIS;D;2026-10-23;3,35\n"
    assert sdmx.parse_any(text, "X").iloc[-1] == 3.35


def test_weekend_rows_dropped():
    from macrodash.clients.base import clean_series
    s = clean_series({"2026-10-23": 1.0, "2026-10-24": 1.0})   # Fri, Sat
    assert len(s) == 1


def test_refinitiv_circuit_breaker(tmp_path):
    from macrodash.clients.base import HttpClient
    from macrodash.clients.refinitiv import RefinitivSession
    session = RefinitivSession(HttpClient(timeout=1, retries=0, cache_dir=tmp_path, cache_ttl_seconds=0))
    session._token, session._expires = "t", 1e12
    for _ in range(3):
        session.record(False, "timeout")
    with pytest.raises(SourceError):
        session.token()
