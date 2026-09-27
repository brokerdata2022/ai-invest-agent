import subprocess

import runner


def test_decode_handles_bytes_str_and_none():
    assert runner._decode(b"hello") == "hello"
    assert runner._decode("hello") == "hello"
    assert runner._decode(None) == ""


def test_timeout_expired_with_bytes_output_does_not_crash(tmp_path, monkeypatch):
    """Регресія 2026-09-27: subprocess.TimeoutExpired.stdout/.stderr лишаються
    bytes навіть при text=True (text= декодує лише успішний шлях), тому
    попередній `(exc.stdout or "") + (exc.stderr or "")` падав з TypeError —
    провал джоби (напр. quotes_universe_refresh по 30-хв timeout) ставав
    повністю невидимим: ані лог, ані Telegram-алерт."""
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path)
    monkeypatch.setattr(runner, "JOBS", {"slow_job": {"subprocess": ["sleep", "9999"]}})

    alerts: list[tuple[str, str, str]] = []
    monkeypatch.setattr(runner, "notify_failure", lambda name, reason, output: alerts.append((name, reason, output)))

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"], output=b"stdout bytes", stderr=b"stderr bytes")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    ok = runner.run_job("slow_job")

    assert ok is False
    assert len(alerts) == 1
    name, reason, output = alerts[0]
    assert name == "slow_job"
    assert "stdout bytes" in output
    assert "stderr bytes" in output

    log_files = list(tmp_path.glob("slow_job_*.log"))
    assert len(log_files) == 1
    assert "stdout bytes" in log_files[0].read_text()
