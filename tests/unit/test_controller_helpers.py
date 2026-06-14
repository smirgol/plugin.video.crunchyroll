"""Unit tests for controller_helpers.py.

TDD: written before implementation.
"""

from unittest.mock import patch


class TestIsResponseError:
    """Covers variant 1: `if not req or "error" in req`"""

    def test_none_is_error(self):
        from resources.lib.controller_helpers import is_response_error

        assert is_response_error(None) is True

    def test_empty_dict_is_error(self):
        from resources.lib.controller_helpers import is_response_error

        assert is_response_error({}) is True

    def test_dict_with_error_key_is_error(self):
        from resources.lib.controller_helpers import is_response_error

        assert is_response_error({"error": "boom"}) is True
        assert is_response_error({"error": None}) is True

    def test_valid_dict_is_not_error(self):
        from resources.lib.controller_helpers import is_response_error

        assert is_response_error({"items": []}) is False
        assert is_response_error({"data": []}) is False


class TestIsResponseErrorStrict:
    """Covers variants 2/3: `if req is None or req.get("error") is not None`"""

    def test_none_is_error(self):
        from resources.lib.controller_helpers import is_response_error_strict

        assert is_response_error_strict(None) is True

    def test_dict_with_error_none_is_not_error(self):
        from resources.lib.controller_helpers import is_response_error_strict

        # req.get("error") is None → NOT an error
        assert is_response_error_strict({"error": None}) is False

    def test_dict_with_error_string_is_error(self):
        from resources.lib.controller_helpers import is_response_error_strict

        assert is_response_error_strict({"error": "boom"}) is True

    def test_valid_dict_is_not_error(self):
        from resources.lib.controller_helpers import is_response_error_strict

        assert is_response_error_strict({"items": []}) is False


class TestRenderErrorDirectory:
    @patch("resources.lib.controller_helpers.view")
    def test_default_title_id(self, mock_view):
        from resources.lib.controller_helpers import render_error_directory

        result = render_error_directory()

        mock_view.add_item.assert_called_once_with(None, {"title": "String_30061"})
        mock_view.end_of_directory.assert_called_once_with(None)
        assert result is False

    @patch("resources.lib.controller_helpers.view")
    def test_custom_title_id(self, mock_view):
        from resources.lib.controller_helpers import render_error_directory

        result = render_error_directory(title_id=30090)

        mock_view.add_item.assert_called_once_with(None, {"title": "String_30090"})
        mock_view.end_of_directory.assert_called_once_with(None)
        assert result is False


class TestAddNextPageItem:
    @patch("resources.lib.controller_helpers.view")
    def test_basic_call(self, mock_view):
        from resources.lib.controller_helpers import add_next_page_item

        add_next_page_item(offset=50, mode="search")

        mock_view.add_item.assert_called_once_with(
            None,
            {
                "title": "String_30044",
                "offset": 50,
                "mode": "search",
            },
            is_folder=True,
        )

    @patch("resources.lib.controller_helpers.view")
    def test_with_extra_params(self, mock_view):
        from resources.lib.controller_helpers import add_next_page_item

        add_next_page_item(offset=100, mode="filter", search="naruto", category_filter="action")

        mock_view.add_item.assert_called_once_with(
            None,
            {
                "title": "String_30044",
                "offset": 100,
                "mode": "filter",
                "search": "naruto",
                "category_filter": "action",
            },
            is_folder=True,
        )
