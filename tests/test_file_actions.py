from pathlib import Path

from nixi.config import NixiConfig
from nixi.core.file_actions import FileActionService
from nixi.security.permissions import ActionJournal, UndoManager


def make_service(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    data = tmp_path / "nixi-data"
    data.mkdir()
    cfg = NixiConfig(data_dir=str(data))
    journal = ActionJournal(db_path=data / "audit.db", enabled=True)
    undo = UndoManager(config=cfg, journal=journal)
    return home, FileActionService(undo, home=home), undo


def test_create_move_rename_and_undo(tmp_path):
    home, actions, undo = make_service(tmp_path)
    (home / "Documents").mkdir()
    created = actions.create_file("Documents/hello.txt", "hello")
    assert "Created and verified" in created
    assert (home / "Documents/hello.txt").read_text() == "hello"

    (home / "Documents/Archive").mkdir()
    moved = actions.move_file("Documents/hello.txt", "Documents/Archive")
    assert "Moved and verified" in moved
    assert (home / "Documents/Archive/hello.txt").exists()
    assert "Undid move" in undo.undo_last()
    assert (home / "Documents/hello.txt").exists()

    renamed = actions.rename_file("Documents/hello.txt", "greeting.txt")
    assert "Renamed and verified" in renamed
    assert (home / "Documents/greeting.txt").read_text() == "hello"


def test_create_is_undoable_and_never_overwrites(tmp_path):
    home, actions, undo = make_service(tmp_path)
    (home / "Desktop").mkdir()
    target = home / "Desktop/note.txt"
    target.write_text("keep me")
    assert "already exists" in actions.create_file("Desktop/note.txt", "replace").lower()
    assert target.read_text() == "keep me"

    target.unlink()
    assert "Created and verified" in actions.create_file("Desktop/note.txt", "new")
    assert "Undid create" in undo.undo_last()
    assert not target.exists()


def test_file_actions_reject_paths_outside_home(tmp_path):
    home, actions, _ = make_service(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("protected")
    result = actions.trash_file(str(outside))
    assert "limited to your home directory" in result
    assert outside.exists()
