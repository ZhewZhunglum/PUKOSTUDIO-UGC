from app.services.attachment_service import (
    _EXT_BY_CONTENT_TYPE,
    _sanitize_filename,
)


def test_sanitize_filename_strips_path_separators_and_newlines():
    # Path separators become underscores and leading dots are stripped, so the
    # result can never be a traversal sequence or a dotfile.
    sanitized = _sanitize_filename("../../etc/passwd")
    assert "/" not in sanitized and "\\" not in sanitized
    assert not sanitized.startswith(".")
    assert _sanitize_filename("evil\r\nname.pdf") == "evilname.pdf"
    assert _sanitize_filename(None) == "file"
    assert _sanitize_filename("   ") == "file"


def test_sanitize_filename_truncates_to_255():
    assert len(_sanitize_filename("a" * 500)) == 255


def test_extension_map_only_covers_whitelisted_types():
    assert _EXT_BY_CONTENT_TYPE["application/pdf"] == ".pdf"
    assert _EXT_BY_CONTENT_TYPE["image/jpeg"] == ".jpg"
    # An unknown/unsafe type is absent — the service maps it to "" (no ext)
    assert "application/x-msdownload" not in _EXT_BY_CONTENT_TYPE
