import pytest

from nixi.config import NixiConfig
from nixi.core.file_actions import FileActionService
from nixi.integrations.office import OfficeIntegration
from nixi.security.permissions import ActionJournal, UndoManager


def make_office(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    config = NixiConfig(data_dir=str(data))
    journal = ActionJournal(db_path=data / "audit.db", enabled=True)
    files = FileActionService(UndoManager(config=config, journal=journal), home=home)
    return home, OfficeIntegration(files)


def test_word_create_read_and_no_overwrite(tmp_path):
    pytest.importorskip("docx")
    home, office = make_office(tmp_path)
    (home / "Documents").mkdir()
    result = office.create_word_document("Documents/brief.docx", "Weekly brief", "First line\nSecond line")
    assert "Created and verified" in result
    assert "Weekly brief" in office.read_word_document("Documents/brief.docx")
    assert "First line" in office.read_word_document("Documents/brief.docx")
    assert "nothing overwritten" in office.create_word_document("Documents/brief.docx", "Replace").lower()


def test_excel_create_read_and_formula_escape(tmp_path):
    pytest.importorskip("openpyxl")
    home, office = make_office(tmp_path)
    (home / "Documents").mkdir()
    result = office.create_workbook("Documents/data.xlsx", rows=[["Name", "Value"], ["Alice", "=1+1"]])
    assert "Created and verified" in result
    rows = office.read_workbook("Documents/data.xlsx")
    assert rows[0][:2] == ["Name", "Value"]
    assert rows[1][1] == "'=1+1"
