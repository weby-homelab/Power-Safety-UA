import datetime
from zoneinfo import ZoneInfo
from app.reports.weekly import resolve_weekly_report_period

KYIV_TZ = ZoneInfo("Europe/Kyiv")


def test_scheduled_monday_window_produces_previous_completed_week():
    # Monday 2026-04-13 at 00:20 Kyiv
    monday_now = datetime.datetime(2026, 4, 13, 0, 20, tzinfo=KYIV_TZ)
    monday, sunday, target_date, effective_no_send = resolve_weekly_report_period(
        now=monday_now,
        date_str=None,
        completed_week=False,
        force_send=False,
        no_send=False,
        has_output=False,
    )
    # Previous completed week: Monday 2026-04-06 to Sunday 2026-04-12
    assert monday == datetime.date(2026, 4, 6)
    assert sunday == datetime.date(2026, 4, 12)
    assert target_date == datetime.date(2026, 4, 12)
    assert effective_no_send is False


def test_scheduled_monday_window_01_59():
    # Monday 2026-04-13 at 01:59 Kyiv (still inside 00:00-02:00 window)
    monday_now = datetime.datetime(2026, 4, 13, 1, 59, tzinfo=KYIV_TZ)
    monday, sunday, target_date, effective_no_send = resolve_weekly_report_period(
        now=monday_now,
    )
    assert monday == datetime.date(2026, 4, 6)
    assert sunday == datetime.date(2026, 4, 12)
    assert effective_no_send is False


def test_mid_week_without_flags_defaults_to_dry_run():
    # Wednesday 2026-04-15 at 14:00 Kyiv
    wed_now = datetime.datetime(2026, 4, 15, 14, 0, tzinfo=KYIV_TZ)
    monday, sunday, target_date, effective_no_send = resolve_weekly_report_period(
        now=wed_now,
        date_str=None,
        completed_week=False,
        force_send=False,
        no_send=False,
        has_output=False,
    )
    # Boundaries are current in-progress week: Mon 2026-04-13 to Sun 2026-04-19
    assert monday == datetime.date(2026, 4, 13)
    assert sunday == datetime.date(2026, 4, 19)
    # But Telegram sending is REFUSED / defaulted to dry-run
    assert effective_no_send is True


def test_mid_week_with_completed_week_flag_generates_previous_week():
    # Wednesday 2026-04-15 at 14:00 Kyiv with --completed-week
    wed_now = datetime.datetime(2026, 4, 15, 14, 0, tzinfo=KYIV_TZ)
    monday, sunday, target_date, effective_no_send = resolve_weekly_report_period(
        now=wed_now,
        completed_week=True,
    )
    # Previous completed week: Monday 2026-04-06 to Sunday 2026-04-12
    assert monday == datetime.date(2026, 4, 6)
    assert sunday == datetime.date(2026, 4, 12)
    assert target_date == datetime.date(2026, 4, 12)
    assert effective_no_send is False


def test_explicit_date_generates_target_week():
    wed_now = datetime.datetime(2026, 4, 15, 14, 0, tzinfo=KYIV_TZ)
    monday, sunday, target_date, effective_no_send = resolve_weekly_report_period(
        now=wed_now,
        date_str="2026-03-25",
    )
    # 2026-03-25 is Wednesday -> Mon 2026-03-23 to Sun 2026-03-29
    assert monday == datetime.date(2026, 3, 23)
    assert sunday == datetime.date(2026, 3, 29)
    assert target_date == datetime.date(2026, 3, 25)
    assert effective_no_send is False


def test_mid_week_web_dashboard_output_semantics():
    # Web dashboard generation: output file provided + no_send
    wed_now = datetime.datetime(2026, 4, 15, 14, 0, tzinfo=KYIV_TZ)
    monday, sunday, target_date, effective_no_send = resolve_weekly_report_period(
        now=wed_now,
        has_output=True,
        no_send=True,
    )
    assert monday == datetime.date(2026, 4, 13)
    assert sunday == datetime.date(2026, 4, 19)
    assert effective_no_send is True


def test_mid_week_force_send_overrides_safeguard():
    wed_now = datetime.datetime(2026, 4, 15, 14, 0, tzinfo=KYIV_TZ)
    monday, sunday, target_date, effective_no_send = resolve_weekly_report_period(
        now=wed_now,
        force_send=True,
    )
    assert effective_no_send is False
