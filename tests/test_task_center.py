import time

from nixi.core.task_center import TaskCenter


def test_task_progress_and_complete():
    center = TaskCenter()
    task_id = center.start("open browser")
    assert center.update(task_id, "Launching", progress=35)
    active = center.snapshot()[0]
    assert active["state"] == "active"
    assert active["progress"] == 35
    assert center.finish(task_id, "Opened")
    done = center.snapshot()[0]
    assert done["state"] == "completed"
    assert done["result"] == "Opened"


def test_cancel_is_cooperative_and_visible():
    center = TaskCenter()
    task_id = center.start("long action")
    assert center.cancel(task_id)
    event = center.cancel_event(task_id)
    assert event is not None and event.is_set()
    assert center.finish(task_id, "Stopped at checkpoint")
    assert center.snapshot()[0]["state"] == "cancelled"


def test_cancel_latest_selects_most_recent_active():
    center = TaskCenter()
    older = center.start("older")
    newer = center.start("newer")
    assert center.cancel_latest() == newer
    assert center.cancel_event(newer).is_set()
    assert not center.cancel_event(older).is_set()
