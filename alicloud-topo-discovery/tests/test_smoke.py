def test_pytest_works():
    """Smoke test: verify pytest discovers and runs tests."""
    assert 1 + 1 == 2


def test_fixtures_dir_exists(fixtures_dir):
    """Verify fixtures directory is accessible."""
    assert fixtures_dir.exists()
    assert fixtures_dir.is_dir()


def test_temp_output_dir(temp_output_dir):
    """Verify temp output dir fixture works."""
    assert temp_output_dir.exists()
    assert temp_output_dir.is_dir()
