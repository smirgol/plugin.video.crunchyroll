"""Unit tests for PluginContext in resources.lib.context."""

from unittest.mock import MagicMock


class TestPluginContext:
    def test_fixture_provides_isolated_context(self, ctx):
        assert ctx.api is not None
        assert ctx.args is not None
        assert ctx.monitor is not None

    def test_can_be_created_with_mocked_dependencies(self):
        from resources.lib.context import PluginContext

        mock_api = MagicMock()
        mock_args = MagicMock()
        mock_monitor = MagicMock()

        ctx = PluginContext(api=mock_api, args=mock_args, monitor=mock_monitor)

        assert ctx.api is mock_api
        assert ctx.args is mock_args
        assert ctx.monitor is mock_monitor

    def test_fields_are_accessible(self):
        from resources.lib.context import PluginContext

        ctx = PluginContext(api=1, args=2, monitor=3)
        assert ctx.api == 1
        assert ctx.args == 2
        assert ctx.monitor == 3
