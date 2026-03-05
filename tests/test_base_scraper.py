"""Tests for BaseScraper failure signaling and browser detection."""

import os
import shutil

from config import Config
from scrapers.base_scraper import BaseScraper


class _SuccessScraper(BaseScraper):
    def __init__(self):
        super().__init__(company_name='TestSuccess', source_url='https://example.com')

    def init_driver(self):
        return True

    def scrape_jobs(self):
        return [{'title': 'Example'}]


class _FailScraper(BaseScraper):
    def __init__(self):
        super().__init__(company_name='TestFail', source_url='https://example.com')

    def init_driver(self):
        return False

    def scrape_jobs(self):
        return []


def test_scrape_with_retry_marks_failure_when_all_attempts_fail():
    scraper = _FailScraper()

    jobs = scraper.scrape_with_retry(max_retries=1)

    assert jobs == []
    assert scraper.last_run_failed is True
    assert scraper.last_error == 'Failed to initialize WebDriver'


def test_scrape_with_retry_clears_failure_state_on_success():
    scraper = _SuccessScraper()

    jobs = scraper.scrape_with_retry(max_retries=1)

    assert jobs == [{'title': 'Example'}]
    assert scraper.last_run_failed is False
    assert scraper.last_error is None


def test_detect_chrome_binary_finds_macos_app_bundle(monkeypatch):
    monkeypatch.setattr(Config, 'CHROME_BINARY_PATH', '')
    monkeypatch.delenv('GOOGLE_CHROME_BIN', raising=False)
    monkeypatch.delenv('GOOGLE_CHROME_SHIM', raising=False)
    monkeypatch.delenv('CHROMIUM_PATH', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda _binary: None)

    def fake_exists(path):
        return path == '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

    monkeypatch.setattr(os.path, 'exists', fake_exists)

    path, browser_type = BaseScraper._detect_chrome_binary()

    assert path == '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    assert browser_type == 'chrome'


def test_detect_chrome_binary_finds_direct_linux_path(monkeypatch):
    monkeypatch.setattr(Config, 'CHROME_BINARY_PATH', '')
    monkeypatch.delenv('GOOGLE_CHROME_BIN', raising=False)
    monkeypatch.delenv('GOOGLE_CHROME_SHIM', raising=False)
    monkeypatch.delenv('CHROMIUM_PATH', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda _binary: None)

    def fake_exists(path):
        return path == '/usr/bin/chromium'

    monkeypatch.setattr(os.path, 'exists', fake_exists)

    path, browser_type = BaseScraper._detect_chrome_binary()

    assert path == '/usr/bin/chromium'
    assert browser_type == 'chromium'


def test_detect_chromedriver_uses_config_path(monkeypatch):
    monkeypatch.setattr(Config, 'CHROMEDRIVER_PATH', '/custom/chromedriver')
    monkeypatch.setattr(shutil, 'which', lambda _binary: None)
    monkeypatch.setattr(
        os.path,
        'exists',
        lambda p: p == '/custom/chromedriver'
    )

    path = BaseScraper._detect_chromedriver()

    assert path == '/custom/chromedriver'


def test_build_service_with_webdriver_manager_falls_back_when_install_returns_none(monkeypatch):
    scraper = _SuccessScraper()

    class _FakeChromeDriverManager:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        def install(self):
            return None

    class _FakeService:
        def __init__(self, path):
            self.path = path

    monkeypatch.setattr('scrapers.base_scraper.ChromeDriverManager', _FakeChromeDriverManager)
    monkeypatch.setattr('scrapers.base_scraper.Service', _FakeService)
    monkeypatch.setattr(scraper, '_detect_chromedriver', lambda: '/tmp/fallback-chromedriver')
    monkeypatch.setattr(os.path, 'exists', lambda p: p == '/tmp/fallback-chromedriver')
    monkeypatch.delenv('CHROMEDRIVER_PATH', raising=False)

    service = scraper._build_service_with_webdriver_manager('chrome')

    assert service.path == '/tmp/fallback-chromedriver'
    assert os.environ.get('CHROMEDRIVER_PATH') == '/tmp/fallback-chromedriver'


def test_kill_zombie_chrome_kills_chromedriver_and_crashpad(monkeypatch):
    calls = []
    sleep_calls = []

    def _fake_run(args, capture_output=True, timeout=5):
        calls.append((tuple(args), capture_output, timeout))
        return None

    monkeypatch.setattr('scrapers.base_scraper.subprocess.run', _fake_run)
    monkeypatch.setattr('scrapers.base_scraper.time.sleep', lambda value: sleep_calls.append(value))

    BaseScraper._kill_zombie_chrome()

    patterns = [call[0] for call in calls]
    assert ('pkill', '-f', 'chromedriver') in patterns
    assert ('pkill', '-f', 'chrome_crashpad_handler') in patterns
    assert sleep_calls == [2]
