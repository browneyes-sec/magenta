"""Collector runner — orchestrates all enabled collectors from TOML config."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

import tomli

from magenta.config import settings
from magenta.integration.collectors.base import BaseCollector, CollectorConfig
from magenta.integration.collectors.cloud import (
    AWSCloudTrailCollector,
    AzureMonitorCollector,
    EntraIDLogCollector,
    GCPLoggingCollector,
)
from magenta.integration.collectors.customer import CustomerSFTPCollector
from magenta.integration.collectors.linux import LinuxSyslogCollector
from magenta.integration.collectors.windows import WindowsEventCollector

logger = logging.getLogger(__name__)

COLLECTOR_MAP: dict[str, type[BaseCollector]] = {
    "azure_monitor": AzureMonitorCollector,
    "entra_id": EntraIDLogCollector,
    "aws_cloudtrail": AWSCloudTrailCollector,
    "gcp_logging": GCPLoggingCollector,
    "linux_syslog": LinuxSyslogCollector,
    "windows_event": WindowsEventCollector,
    "customer_sftp": CustomerSFTPCollector,
}


async def run_collector(collector: BaseCollector, interval: int) -> None:
    """Run a single collector on its configured interval."""
    await collector.start()
    try:
        while collector.is_running:
            try:
                events = await collector.collect()
                if events:
                    logger.info("Collector %s produced %d events", collector.config.name, len(events))
                    # TODO: publish to Event Hubs via magenta.integration.eventhub
            except Exception as e:
                logger.exception("Collector %s error: %s", collector.config.name, e)
            await asyncio.sleep(interval)
    finally:
        await collector.stop()


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_path = Path(settings.collectors_config_path)
    if not config_path.exists():
        logger.error("Config not found: %s", config_path)
        return 1

    with open(config_path, "rb") as f:
        raw = tomli.load(f)

    collectors: list[BaseCollector] = []
    for name, cfg in raw.items():
        if not cfg.get("enabled", True):
            logger.info("Skipping disabled collector: %s", name)
            continue

        collector_type = cfg.get("type")
        if collector_type not in COLLECTOR_MAP:
            logger.error("Unknown collector type: %s for %s", collector_type, name)
            continue

        collector_config = CollectorConfig(
            name=name,
            source_type=collector_type,
            poll_interval_seconds=cfg.get("poll_interval_seconds", 60),
            batch_size=cfg.get("batch_size", 100),
            enabled=cfg.get("enabled", True),
            options=cfg.get("options", {}),
        )

        collector_cls = COLLECTOR_MAP[collector_type]
        collector = collector_cls(collector_config)
        collectors.append(collector)
        logger.info("Initialized collector: %s (%s)", name, collector_type)

    if not collectors:
        logger.warning("No enabled collectors configured")
        return 0

    # Run all collectors concurrently
    tasks = [
        asyncio.create_task(run_collector(c, c.config.poll_interval_seconds))
        for c in collectors
    ]

    # Graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass  # Windows

    await shutdown_event.wait()

    logger.info("Stopping all collectors...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("All collectors stopped")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
