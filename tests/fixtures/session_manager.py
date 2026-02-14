import pytest


@pytest.fixture(scope="session")
def cloudscraper_session():
    """Reuse CloudScraper session across all integration tests

    Benefits:
    - Session stays "warm" with cookies
    - Less suspicious to CloudFlare
    - Better performance
    """
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
    except ImportError:
        import requests
        scraper = requests.Session()

    yield scraper
    scraper.close()


@pytest.fixture(scope="session")
def requests_session():
    """Standard requests session for beta-api endpoints"""
    import requests
    session = requests.Session()
    yield session
    session.close()
