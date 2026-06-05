import logging
from unittest.mock import MagicMock, patch

from recceiver.application import RecService
from recceiver.recast import CollectionSession


class TestRecServiceConfig:
    def test_commit_size_limit_defaults_to_class_default(self):
        svc = RecService({})
        assert svc.commitSizeLimit == CollectionSession.trlimit

    def test_commit_size_limit_reads_from_config(self):
        svc = RecService({"commitSizeLimit": "100"})
        assert svc.commitSizeLimit == 100

    def test_commit_size_limit_zero_disables_splitting(self):
        svc = RecService({"commitSizeLimit": "0"})
        assert svc.commitSizeLimit == 0


class TestLogStatus:
    def _make_service_with_nactive(self, nactive):
        svc = RecService({})
        svc.tcpFactory = MagicMock()
        svc.tcpFactory.NActive = nactive
        svc.tcpFactory.maxActive = 20
        svc.tcpFactory.Wait = []
        return svc

    def test_negative_nactive_logs_warning(self, caplog):
        svc = self._make_service_with_nactive(-5)
        with caplog.at_level(logging.WARNING, logger="recceiver.application"):
            svc._logStatus()
        assert any("NActive" in r.message and "-5" in r.message for r in caplog.records)

    def test_negative_nactive_clamps_to_zero_in_log(self, caplog):
        svc = self._make_service_with_nactive(-5)
        with caplog.at_level(logging.INFO, logger="recceiver.application"):
            svc._logStatus()
        status_lines = [r.message for r in caplog.records if "connections active" in r.message]
        assert len(status_lines) == 1
        assert "connections active=0/20" in status_lines[0]

    def test_negative_nactive_clamps_to_zero_in_metrics(self):
        import recceiver.metrics as m

        svc = self._make_service_with_nactive(-3)
        mock_gauge = MagicMock()
        with patch.object(m, "connections_active", mock_gauge):
            svc._logStatus()
        mock_gauge.set.assert_called_once_with(0)

    def test_normal_nactive_passes_through(self, caplog):
        svc = self._make_service_with_nactive(5)
        with caplog.at_level(logging.INFO, logger="recceiver.application"):
            svc._logStatus()
        status_lines = [r.message for r in caplog.records if "connections active" in r.message]
        assert "connections active=5/20" in status_lines[0]
