"""Smoke test to verify package import works."""


def test_import():
    from alicloud_shared import chat_context, subprocess_utils
    from alicloud_shared.adapters import __init__ as adapters_pkg
    assert chat_context is not None
    assert subprocess_utils is not None
    assert adapters_pkg is not None