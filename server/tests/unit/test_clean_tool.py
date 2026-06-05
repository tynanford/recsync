from unittest.mock import MagicMock

from recceiver.cf.config import CFConfig
from recceiver.cf.model import CFChannel, CFProperty, CFPropertyName, PVStatus
from recceiver.clean_tool import run_clean


def _make_channel(name):
    return CFChannel(name, "admin", [CFProperty(CFPropertyName.PV_STATUS.value, "admin", PVStatus.ACTIVE.value)])


def _make_cfg():
    return CFConfig(base_url="http://cf", username="admin", recceiver_id="rec1")


class TestRunClean:
    def _make_client(self, *batches):
        """Return a mock client yielding `batches` in sequence, then empty."""
        client = MagicMock()
        client.find_active_for_recceiver.side_effect = list(batches) + [[]]
        return client

    def test_marks_all_active_channels_inactive(self):
        channels = [_make_channel("PV:1"), _make_channel("PV:2")]
        client = self._make_client(channels)

        count = run_clean(_make_cfg(), client=client)

        assert count == 2
        client.update_property.assert_called_once()
        prop, names = client.update_property.call_args[0]
        assert prop.value == PVStatus.INACTIVE.value
        assert set(names) == {"PV:1", "PV:2"}

    def test_returns_zero_when_no_active_channels(self):
        client = self._make_client()

        count = run_clean(_make_cfg(), client=client)

        assert count == 0
        client.update_property.assert_not_called()

    def test_dry_run_does_not_call_update(self):
        channels = [_make_channel("PV:1")]
        client = self._make_client(channels)

        count = run_clean(_make_cfg(), client=client, dry_run=True)

        assert count == 1
        client.update_property.assert_not_called()

    def test_sweeps_multiple_pages(self):
        batch1 = [_make_channel("PV:1"), _make_channel("PV:2")]
        batch2 = [_make_channel("PV:3")]
        client = self._make_client(batch1, batch2)

        count = run_clean(_make_cfg(), client=client)

        assert count == 3
        assert client.update_property.call_count == 2
