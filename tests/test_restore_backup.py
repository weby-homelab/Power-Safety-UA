from unittest.mock import patch
from app.light_service import restore_backup


class TestRestoreBackup:
    """Test backup restore path traversal prevention."""

    def test_rejects_traversal(self):
        """Should reject filenames with path traversal."""
        ok, msg = restore_backup("../config.json")
        assert ok is False
        assert "Invalid" in msg

    def test_rejects_absolute_path(self):
        """Should reject absolute paths."""
        ok, msg = restore_backup("/etc/passwd")
        assert ok is False
        assert "Invalid" in msg

    def test_rejects_double_dot(self):
        """Should reject filenames containing .."""
        ok, msg = restore_backup("../../../etc/passwd")
        assert ok is False
        assert "Invalid" in msg

    def test_rejects_empty(self):
        """Should reject empty filenames."""
        ok, msg = restore_backup("")
        assert ok is False
        assert "Invalid" in msg

    def test_rejects_relative_with_dots(self):
        """Should reject relative path with dots."""
        ok, msg = restore_backup("./config.json")
        assert ok is False
        assert "Invalid" in msg

    def test_accepts_valid_filename(self):
        """Should accept valid backup filenames."""
        with patch("os.path.exists", return_value=False):
            ok, msg = restore_backup("backup_20260101_120000.json")
            assert ok is False
            assert "Backup not found" in msg

    def test_accepts_pre_restore_filename(self):
        """Should accept 'pre_restore' as valid filename for restore."""
        with patch("os.path.exists", return_value=False):
            ok, msg = restore_backup("pre_restore")
            assert ok is False
            assert "Backup not found" in msg
