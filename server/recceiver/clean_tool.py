"""recceiver-clean — sweep Active CF channels to Inactive for a given recceiver ID.

Run after a RecCeiver restart (with cleanOnStart=False) to mark channels Inactive
whose IOCs have not reconnected.

Usage:
    recceiver-clean -f /path/to/recceiver.conf [--recceiver-id ID] [--dry-run]
"""

import argparse
import configparser
import logging
import sys

from requests import RequestException

from recceiver.cf.adapter import PyCFClientAdapter
from recceiver.cf.config import CFConfig
from recceiver.cf.model import CFProperty, CFPropertyName, PVStatus
from recceiver.processors import ConfigAdapter

log = logging.getLogger(__name__)


def run_clean(cf_config: CFConfig, client=None, dry_run: bool = False) -> int:
    """Mark all Active channels for cf_config.recceiver_id Inactive.

    Returns the total count of channels swept. Pass a pre-built client for testing.
    """
    if client is None:
        from channelfinder import ChannelFinderClient

        client = PyCFClientAdapter(
            ChannelFinderClient(
                BaseURL=cf_config.base_url,
                username=cf_config.cf_username,
                password=cf_config.cf_password,
                verify_ssl=cf_config.verify_ssl,
            ),
            size_limit=int(cf_config.cf_query_limit),
        )

    total = 0
    # find_active_for_recceiver is paginated (bounded by size_limit). In live mode each
    # update_property call marks the current page Inactive, so the next query returns a
    # fresh batch; the loop drains all pages. In dry-run mode nothing is deactivated so
    # the same batch would come back on every iteration — break after the first page.
    while True:
        channels = client.find_active_for_recceiver(cf_config.recceiver_id)
        if not channels:
            break
        log.info(
            "Found %d active channels for recceiver_id=%r%s",
            len(channels),
            cf_config.recceiver_id,
            " (dry-run)" if dry_run else "",
        )
        if not dry_run:
            client.update_property(
                CFProperty(CFPropertyName.PV_STATUS.value, cf_config.username, PVStatus.INACTIVE.value),
                [ch.name for ch in channels],
            )
        total += len(channels)
        if dry_run:
            break
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mark active CF channels Inactive for a given recceiver ID.")
    parser.add_argument("-f", "--config", required=True, help="Path to recceiver config file")
    parser.add_argument("--recceiver-id", default=None, help="Override recceiver ID from config")
    parser.add_argument("--dry-run", action="store_true", help="Print count without modifying CF")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    conf = configparser.ConfigParser()
    conf.read(args.config)
    cf_conf = CFConfig.loads(ConfigAdapter(conf, "cf"))

    if args.recceiver_id:
        cf_conf.recceiver_id = args.recceiver_id

    if cf_conf.base_url is None:
        print("ERROR: baseUrl must be configured in [cf] section", file=sys.stderr)
        sys.exit(1)

    try:
        count = run_clean(cf_conf, dry_run=args.dry_run)
    except RequestException as err:
        print(f"ERROR: CF request failed: {err}", file=sys.stderr)
        sys.exit(2)

    action = "Would mark" if args.dry_run else "Marked"
    print(f"{action} {count} channels Inactive for recceiver_id={cf_conf.recceiver_id!r}")


if __name__ == "__main__":
    main()
