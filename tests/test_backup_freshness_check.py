import argparse
import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, cast

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_freshness_check.py"
spec = importlib.util.spec_from_file_location("backup_freshness_check", SCRIPT)
assert spec and spec.loader
backup_freshness_check = cast(Any, importlib.util.module_from_spec(spec))
sys.modules[spec.name] = cast(ModuleType, backup_freshness_check)
spec.loader.exec_module(cast(ModuleType, backup_freshness_check))


class BackupFreshnessCheckTests(unittest.TestCase):
    def test_classifies_fresh_hermes_job_green_with_restore_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs.json"
            outdir = root / "output"
            outdir.mkdir()
            jobs.write_text(json.dumps({
                "jobs": [{
                    "id": "job1",
                    "name": "daily-hermes-backup-to-github",
                    "enabled": True,
                    "state": "scheduled",
                    "last_run_at": "2026-05-30T03:00:00+00:00",
                    "last_status": "ok",
                    "last_error": None,
                }]
            }))
            (outdir / "2026-05-30_03-00-00.md").write_text(
                "**Run Time:** 2026-05-30 03:00\n"
                "Backed up ~/.hermes to repo at 2026-05-30T03:00:00Z (restore test: ok, files=10)\n"
            )
            args = argparse.Namespace(
                hermes_jobs=jobs,
                hermes_job_id="job1",
                hermes_output_dir=outdir,
                warn_hours=26.0,
                red_hours=48.0,
            )
            now = dt.datetime(2026, 5, 30, 12, tzinfo=dt.timezone.utc)
            result = backup_freshness_check.check_hermes(args, now)
            self.assertEqual(result.status, "green")
            self.assertIn("restore test: ok", result.evidence)
            self.assertEqual(result.next_action, "No action; scheduler reports success and latest run is fresh.")

    def test_missing_hermes_job_is_red_with_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs.json"
            outdir = root / "output"
            outdir.mkdir()
            jobs.write_text(json.dumps({"jobs": []}))
            args = argparse.Namespace(
                hermes_jobs=jobs,
                hermes_job_id="missing",
                hermes_output_dir=outdir,
                warn_hours=26.0,
                red_hours=48.0,
            )
            now = dt.datetime(2026, 5, 30, 12, tzinfo=dt.timezone.utc)
            result = backup_freshness_check.check_hermes(args, now)
            self.assertEqual(result.status, "red")
            self.assertIn("recreate", result.next_action)

    def test_failed_hermes_job_does_not_claim_last_success_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs.json"
            outdir = root / "output"
            outdir.mkdir()
            jobs.write_text(json.dumps({
                "jobs": [{
                    "id": "job1",
                    "name": "daily-hermes-backup-to-github",
                    "enabled": True,
                    "state": "scheduled",
                    "last_run_at": "2026-05-30T03:00:00+00:00",
                    "last_status": "failed",
                    "last_error": "boom",
                }]
            }))
            args = argparse.Namespace(
                hermes_jobs=jobs,
                hermes_job_id="job1",
                hermes_output_dir=outdir,
                warn_hours=26.0,
                red_hours=48.0,
            )
            now = dt.datetime(2026, 5, 30, 12, tzinfo=dt.timezone.utc)
            result = backup_freshness_check.check_hermes(args, now)
            self.assertEqual(result.status, "red")
            self.assertIsNone(result.last_successful_backup_time)

    def test_prometheus_host_failure_is_red_with_concrete_action(self):
        payload = {
            "status": "success",
            "data": {"result": [{
                "metric": {"host": "jellyberry"},
                "value": [1780142400, "1780142400"],
            }]},
        }
        original = backup_freshness_check.prometheus_query
        try:
            backup_freshness_check.prometheus_query = lambda *args, **kwargs: payload
            args = argparse.Namespace(
                prometheus_url="http://prom.example/api/v1/query",
                timeout=1.0,
                borg_hosts=["jellyberry"],
                warn_hours=26.0,
                red_hours=48.0,
            )
            now = dt.datetime.fromtimestamp(1780146000, tz=dt.timezone.utc)
            result = backup_freshness_check.check_borg_from_prometheus(args, now)[0]
            self.assertEqual(result.status, "red")
            self.assertIn("Inspect /var/lib/home-network/backup-status/jellyberry.json", result.next_action)
        finally:
            backup_freshness_check.prometheus_query = original

    def test_borg_failure_does_not_claim_last_success_time(self):
        def fake_query(_url, query, _timeout):
            value = "1780142400"
            metric = {"host": "jellyberry"}
            if query == "borgmatic_last_run_success":
                value = "0"
            if query == "borgmatic_repository_reachable":
                value = "1"
            if query == "borgmatic_last_archive_info":
                metric = {"host": "jellyberry", "archive_name": "jellyberry-test"}
                value = "1"
            return {"status": "success", "data": {"result": [{"metric": metric, "value": [1780142400, value]}]}}

        original = backup_freshness_check.prometheus_query
        try:
            backup_freshness_check.prometheus_query = fake_query
            args = argparse.Namespace(
                prometheus_url="http://prom.example/api/v1/query",
                timeout=1.0,
                borg_hosts=["jellyberry"],
                warn_hours=26.0,
                red_hours=48.0,
            )
            now = dt.datetime.fromtimestamp(1780146000, tz=dt.timezone.utc)
            result = backup_freshness_check.check_borg_from_prometheus(args, now)[0]
            self.assertEqual(result.status, "red")
            self.assertIsNone(result.last_successful_backup_time)
        finally:
            backup_freshness_check.prometheus_query = original

    def test_prometheus_unavailable_keeps_overall_borg_status_red_with_local_fallback(self):
        original = backup_freshness_check.prometheus_query
        try:
            backup_freshness_check.prometheus_query = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down"))
            args = argparse.Namespace(
                prometheus_url="http://prom.example/api/v1/query",
                timeout=1.0,
                no_local_fallback=False,
                local_borg_status_dir=Path("/definitely/missing"),
            )
            now = dt.datetime.fromtimestamp(1780146000, tz=dt.timezone.utc)
            results = backup_freshness_check.check_borg(args, now)
            self.assertEqual(results[0].component, "Borgmatic backups (Prometheus)")
            self.assertEqual(results[0].status, "red")
        finally:
            backup_freshness_check.prometheus_query = original

    def test_failed_local_borg_fallback_does_not_claim_last_success_time(self):
        original_hostname = backup_freshness_check.socket.gethostname
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "testhost.json").write_text(json.dumps({
                    "updated_at": "2026-05-30T03:00:00+00:00",
                    "status": "failed",
                    "exit_code": 2,
                    "repository_reachable": False,
                    "archive_name": "testhost-failed",
                }))
                backup_freshness_check.socket.gethostname = lambda: "testhost"
                args = argparse.Namespace(
                    prometheus_url="http://prom.example/api/v1/query",
                    local_borg_status_dir=root,
                    warn_hours=26.0,
                    red_hours=48.0,
                )
                now = dt.datetime(2026, 5, 30, 12, tzinfo=dt.timezone.utc)
                result = backup_freshness_check.check_local_borg_status(args, now, "prom down")[0]
                self.assertEqual(result.status, "red")
                self.assertIsNone(result.last_successful_backup_time)
        finally:
            backup_freshness_check.socket.gethostname = original_hostname

    def test_age_thresholds_yellow_and_red(self):
        self.assertEqual(backup_freshness_check.classify_age(25 * 3600, 26, 48), "green")
        self.assertEqual(backup_freshness_check.classify_age(26 * 3600, 26, 48), "yellow")
        self.assertEqual(backup_freshness_check.classify_age(48 * 3600, 26, 48), "red")


if __name__ == "__main__":
    unittest.main()
