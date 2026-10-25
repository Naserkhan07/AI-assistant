import tempfile
from nixi.integrations.info import Calculator, Translator, WeatherClient, NewsClient
from nixi.integrations.calendar import CalendarReader
from nixi.config import NixiConfig

def test_calculator():
    c = Calculator()
    assert c.evaluate("2 + 2")["result"] == 4
    assert c.evaluate("sqrt(16)")["result"] == 4.0
    assert not c.evaluate("__import__('os').system('echo pwned')")["ok"]
    assert not c.evaluate("")["ok"]

def test_translator_offline():
    t = Translator()
    r = t.translate("hello", source="en", target="hi")
    assert r["ok"] and r["text"]

def test_weather_local_only():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_LOCAL_ONLY": "true"})
        w = WeatherClient(cfg)
        assert not w.get()["ok"]

def test_news_local_only():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_LOCAL_ONLY": "true"})
        n = NewsClient(cfg)
        assert n.fetch() == []

def test_calendar_empty():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp})
        cal = CalendarReader(cfg)
        assert "No upcoming" in cal.format_briefing()

def test_calendar_with_ics():
    import tempfile, pathlib, datetime
    with tempfile.TemporaryDirectory() as tmp:
        ics = pathlib.Path(tmp) / "test.ics"
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%dT%H%M%S")
        ics.write_text(f"BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Test Meeting\nDTSTART:{tomorrow}\nDTEND:{tomorrow}\nEND:VEVENT\nEND:VCALENDAR\n")
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_CALENDAR_ICS": str(ics)})
        cal = CalendarReader(cfg)
        events = cal.upcoming(days=7)
        assert len(events) == 1 and events[0]["summary"] == "Test Meeting"
