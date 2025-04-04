import argparse
import asyncio
import logging
import ssl
from typing import Optional, cast

from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import DatagramFrameReceived, QuicEvent, PingAcknowledged, HandshakeCompleted, ConnectionTerminated, ProtocolNegotiated
from aioquic.h3.connection import H3Connection, H3_ALPN
from aioquic.quic.logger import QuicFileLogger
try:
    import uvloop
except ImportError:
    uvloop = None

logger = logging.getLogger("client")


class MediaClient(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ack_waiter: Optional[asyncio.Future[None]] = None

    async def sendMedia(self) -> None:
        assert self._ack_waiter is None, "Only one sendMedia at a time."
        self._quic.send_datagram_frame(b"sendMedia")

        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()

        return await asyncio.shield(waiter)

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            if event.alpn_protocol in H3_ALPN:
                logger.info(f"Protocol negotiated: {event.alpn_protocol}")
                self._http = H3Connection(self._quic, enable_webtransport=True)
        if isinstance(event, ConnectionTerminated):
            logger.error(
                f"Connection terminated: {event.reason_phrase} (error code: {event.error_code})"
            )
            if self._ack_waiter is not None:
                self._ack_waiter.set_exception(
                    asyncio.CancelledError("Connection terminated")
                )
            return
        if isinstance(event, HandshakeCompleted):
            logger.info("Handshake completed successfully.")
            # Optionally, you can send media immediately after handshake completion
            #asyncio.create_task(self.sendMedia())
            return
        if self._ack_waiter is not None:
            if isinstance(event, DatagramFrameReceived) and event.data == b"sendMedia-ack":
                waiter = self._ack_waiter
                self._ack_waiter = None
                waiter.set_result(None)
            if isinstance(event, PingAcknowledged):
                # If we receive a PingAcknowledged event, it means the connection is still alive.
                logger.debug("Ping acknowledged, connection is alive.")
                #self.sendMedia()

class StreamClient(MediaClient):
    """A specialized client that handles media streams, if needed.
    This class can be extended to handle specific media stream logic.
    Currently, it inherits from MediaClient without additional functionality.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Additional initialization for stream handling can go here.

    async def sendMedia(self) -> None:
        assert self._ack_waiter is None, "Only one sendMedia at a time."
        self._quic.send_datagram_frame(b"sendMedia")
        stream_id = self._quic.get_next_stream_id()
        if stream_id is None:
            logger.error("No available stream ID for sending media.")
          
        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()

        return await asyncio.shield(waiter)

    def quic_event_received(self, event: QuicEvent) -> None:
        if self._ack_waiter is not None:
            if isinstance(event, DatagramFrameReceived) and event.data == b"sendMedia-ack":
                waiter = self._ack_waiter
                self._ack_waiter = None
                waiter.set_result(None)
            if isinstance(event, PingAcknowledged):
                # If we receive a PingAcknowledged event, it means the connection is still alive.
                logger.debug("Ping acknowledged, connection is alive.")
                #await self.sendMedia()
async def main(configuration: QuicConfiguration, host: str, port: int) -> None:
    async with connect(
        host, port, configuration=configuration, create_protocol=MediaClient
    ) as client:
        logger.info("Connected to server at %s:%d", host, port)
        client = cast(MediaClient, client)
        logger.info("sending sendMedia")
        #await client.sendMedia()
        logger.info("received sendMedia-ack")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SiDUCK client")
    parser.add_argument(
        "host", type=str, help="The remote peer's host name or IP address"
    )
    parser.add_argument("port", type=int, help="The remote peer's port number")
    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="do not validate server certificate",
    )
    parser.add_argument(
        "-q",
        "--quic-log",
        type=str,
        help="log QUIC events to QLOG files in the specified directory",
    )
    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

    args = parser.parse_args()
    logging.info("Starting SiDUCK client with arguments:")
    logging.info(args)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    configuration = QuicConfiguration(
        alpn_protocols=["h3"], is_client=True, max_datagram_frame_size=65536
    )
    if args.insecure:
        configuration.verify_mode = ssl.CERT_NONE
    if args.quic_log:
        configuration.quic_logger = QuicFileLogger(args.quic_log)
    if args.secrets_log:
        configuration.secrets_log_file = open(args.secrets_log, "a")
    if uvloop is not None:
            uvloop.install()
    asyncio.run(
        main(
            configuration=configuration,
            host=args.host,
            port=args.port,
        )
    )