import multiprocessing

from app.reports import weekly


def _hold_weekly_lock(lock_path, acquired, release):
    handle = weekly.acquire_weekly_report_lock(lock_path)
    acquired.set()
    release.wait(10)
    handle.close()


def test_weekly_report_lock_serializes_processes(tmp_path):
    context = multiprocessing.get_context("spawn")
    lock_path = str(tmp_path / "weekly_report.lock")
    first_acquired = context.Event()
    first_release = context.Event()
    second_acquired = context.Event()
    second_release = context.Event()
    first = context.Process(
        target=_hold_weekly_lock,
        args=(lock_path, first_acquired, first_release),
    )
    second = context.Process(
        target=_hold_weekly_lock,
        args=(lock_path, second_acquired, second_release),
    )

    first.start()
    second.start()
    try:
        assert first_acquired.wait(20)
        assert not second_acquired.wait(1)
        first_release.set()
        assert second_acquired.wait(20)
    finally:
        first_release.set()
        second_release.set()
        first.join(5)
        second.join(5)

    assert first.exitcode == 0
    assert second.exitcode == 0
