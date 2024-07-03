"""Management of connection with an Onkyo Receiver."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
from typing import Any, TypedDict

import pyeiscp
from pyeiscp import Connection as Receiver  # noqa: F401

from .const import ZONES

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReceiverInfo:
    """Onkyo Receiver information."""

    host: str
    port: int
    model_name: str
    identifier: str


async def async_interview(host: str) -> ReceiverInfo | None:
    """Interview Onkyo Receiver."""
    _LOGGER.debug("Interviewing receiver: %s", host)

    receiver_info: ReceiverInfo | None = None

    async def _callback(conn: pyeiscp.Connection):
        """Receiver interviewed, connection not yet active."""
        nonlocal receiver_info
        info = ReceiverInfo(host, conn.port, conn.name, conn.identifier)
        _LOGGER.debug("Receiver interviewed: %s (%s)", info.model_name, info.host)
        receiver_info = info

    await pyeiscp.Connection.discover(
        host=host,
        discovery_callback=_callback,
    )

    return receiver_info


async def async_discover() -> Iterable[ReceiverInfo]:
    """Discover Onkyo Receivers."""
    _LOGGER.debug("Discovering receivers")

    receiver_infos: list[ReceiverInfo] = []

    async def _callback(conn: pyeiscp.Connection):
        """Receiver discovered, connection not yet active."""
        info = ReceiverInfo(conn.host, conn.port, conn.name, conn.identifier)
        _LOGGER.debug("Receiver discovered: %s (%s)", info.model_name, info.host)
        receiver_infos.append(info)

    await pyeiscp.Connection.discover(discovery_callback=_callback)

    return receiver_infos


class Callbacks(TypedDict):
    """Onkyo Receiver Callbacks."""

    connect: list[Callable[[Receiver], None]]
    update: list[Callable[[Receiver, tuple[str, str, Any]], None]]


async def async_setup(info: ReceiverInfo) -> Receiver:
    """Set up Onkyo Receiver."""

    receiver: Receiver | None = None

    callbacks: Callbacks = {
        "connect": [],
        "update": [],
    }

    def _connect_callback(_origin: str) -> None:
        """Receiver (re)connected."""
        assert receiver is not None
        _LOGGER.debug(
            "Receiver (re)connected: %s (%s)", receiver.identifier, receiver.host
        )

        # Discover what zones are available for the receiver by querying the power.
        # If we get a response for the specific zone, it means it is available.
        for zone in ZONES:
            receiver.query_property(zone, "power")

        for callback in callbacks["connect"]:
            callback(receiver)

        receiver.first_connect = False

    def _update_callback(message: tuple[str, str, Any], _origin: str) -> None:
        """Process new message from the receiver."""
        assert receiver is not None
        _LOGGER.debug(
            "Received update callback from %s: %s", receiver.identifier, message
        )
        for callback in callbacks["update"]:
            callback(receiver, message)

    _LOGGER.debug("Creating receiver: %s (%s)", info.model_name, info.host)
    receiver = await pyeiscp.Connection.create(
        host=info.host,
        port=info.port,
        connect_callback=_connect_callback,
        update_callback=_update_callback,
        auto_connect=False,
    )

    receiver.callbacks = callbacks
    receiver.first_connect = True

    receiver.model_name = info.model_name
    receiver.identifier = info.identifier

    return receiver
