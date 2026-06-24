"""Outbox publisher accessor."""

from magenta.data.sql.outbox import get_outbox_publisher as _get_outbox_publisher


async def get_outbox_publisher():
    return await _get_outbox_publisher()
