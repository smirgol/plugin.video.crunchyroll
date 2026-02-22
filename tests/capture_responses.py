#!/usr/bin/env python3
"""Simple script to capture API responses using integration test fixtures"""

import json
import time
from pathlib import Path

# Use pytest to get the fixtures
import pytest

# Run a custom test that captures responses
test_code = """
import pytest
import json
import time
from pathlib import Path

@pytest.mark.integration
def test_capture_all_responses(api_client):
    '''Capture all API responses'''
    fixtures = {}

    # 1. Profile
    print("\\n1. Capturing profile...")
    try:
        data = api_client.make_request("GET", api_client.PROFILE_ENDPOINT)
        fixtures["profile_response"] = data
        print("   ✓ Profile captured")
    except Exception as e:
        print(f"   ✗ Profile failed: {e}")

    time.sleep(2)

    # 2. Index
    print("2. Capturing index...")
    try:
        data = api_client.make_request("GET", api_client.INDEX_ENDPOINT)
        fixtures["index_response"] = data
        print("   ✓ Index captured")
    except Exception as e:
        print(f"   ✗ Index failed: {e}")

    time.sleep(2)

    # 3. Browse
    print("3. Capturing browse...")
    try:
        data = api_client.make_request(
            "GET", api_client.BROWSE_ENDPOINT,
            params={"start": 0, "n": 5, "locale": "en-US"}
        )
        fixtures["browse_response"] = data
        print("   ✓ Browse captured")
    except Exception as e:
        print(f"   ✗ Browse failed: {e}")

    time.sleep(2)

    # 4. Search
    print("4. Capturing search...")
    try:
        data = api_client.make_request(
            "GET", api_client.SEARCH_ENDPOINT,
            params={"q": "one piece", "n": 3, "locale": "en-US"}
        )
        fixtures["search_response"] = data
        print("   ✓ Search captured")
    except Exception as e:
        print(f"   ✗ Search failed: {e}")

    time.sleep(2)

    # 5. Seasons
    print("5. Capturing seasons...")
    try:
        bucket = api_client.account_data.cms.bucket
        data = api_client.make_request(
            "GET", api_client.SEASONS_ENDPOINT.format(bucket),
            params={"series_id": "GQWH0M1J3", "locale": "de-DE"}
        )
        fixtures["seasons_response"] = data
        print("   ✓ Seasons captured")
    except Exception as e:
        print(f"   ✗ Seasons failed: {e}")

    time.sleep(2)

    # 6. Episodes
    print("6. Capturing episodes...")
    try:
        bucket = api_client.account_data.cms.bucket
        data = api_client.make_request(
            "GET", api_client.EPISODES_ENDPOINT.format(bucket),
            params={"season_id": "GYE5CQNJ2", "locale": "de-DE"}
        )
        fixtures["episodes_response"] = data
        print("   ✓ Episodes captured")
    except Exception as e:
        print(f"   ✗ Episodes failed: {e}")

    time.sleep(2)

    # 7. Watchlist
    print("7. Capturing watchlist...")
    try:
        account_id = api_client.account_data.account_id
        if account_id:
            data = api_client.make_request(
                "GET", api_client.WATCHLIST_LIST_ENDPOINT.format(account_id),
                params={"locale": "de-DE"}
            )
            fixtures["watchlist_response"] = data
            print("   ✓ Watchlist captured")
        else:
            print("   ⚠ Account ID not found, skipping")
    except Exception as e:
        print(f"   ✗ Watchlist failed: {e}")

    time.sleep(2)

    # 8. History
    print("8. Capturing history...")
    try:
        account_id = api_client.account_data.account_id
        if account_id:
            data = api_client.make_request(
                "GET", api_client.HISTORY_ENDPOINT.format(account_id),
                params={"locale": "de-DE"}
            )
            fixtures["history_response"] = data
            print("   ✓ History captured")
        else:
            print("   ⚠ Account ID not found, skipping")
    except Exception as e:
        print(f"   ✗ History failed: {e}")

    time.sleep(2)

    # 9. Playheads
    print("9. Capturing playheads...")
    try:
        account_id = api_client.account_data.account_id
        if account_id:
            data = api_client.make_request(
                "GET", api_client.PLAYHEADS_ENDPOINT.format(account_id),
                params={"content_ids": "GRVN8VK8R,GYDQNM3ZY"}
            )
            fixtures["playheads_response"] = data
            print("   ✓ Playheads captured")
        else:
            print("   ⚠ Account ID not found, skipping")
    except Exception as e:
        print(f"   ✗ Playheads failed: {e}")

    # Save
    output_file = Path("tests/fixtures/captured_responses.json")
    with open(output_file, "w") as f:
        json.dump(fixtures, f, indent=2)

    print(f"\\n✓ Captured {len(fixtures)} responses to {output_file}")
    print("\\nResponse keys:")
    for key in fixtures.keys():
        print(f"   - {key}")

    assert len(fixtures) > 0, "No responses captured!"
"""

# Write temporary test file
test_file = Path("tests/integration/test_capture.py")
test_file.write_text(test_code)

try:
    # Run with pytest
    import subprocess
    result = subprocess.run(
        ["uv", "run", "pytest", str(test_file), "-m", "integration", "-v", "-s"],
        capture_output=False
    )
finally:
    # Cleanup
    test_file.unlink(missing_ok=True)
