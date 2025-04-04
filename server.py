import asyncio
import ssl
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import ProtocolNegotiated, StreamDataReceived, DatagramFrameReceived
from aioquic.h3.connection import H3_ALPN, H3Connection  # Import H3_ALPN for HTTP/3 ALPN protocol
class MediaClient(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.streams = {}   
        print("MediaClient initialized.")

    def quic_event_received(self, event):   
        print(f"Event received: {event}")    
        super().quic_event_received(event)
        if hasattr(event, 'stream_id') and event.stream_id not in self.streams:
            print(f"New stream opened: {event.stream_id}")
            self.streams[event.stream_id] = event.stream_id
        
        elif isinstance(event, DatagramFrameReceived):
            print(f"Datagram frame received: {event.data}")
            # Handle datagram frames if needed
            return
        elif isinstance(event, ProtocolNegotiated):
            print(f"Protocol negotiated: {event}")
            if event.alpn_protocol in H3_ALPN:
                self._http = H3Connection(self._quic, enable_webtransport=True)
            # You can handle protocol negotiation here if needed
            return
    def send_stream_data(self, stream_id: int, data: bytes):
        if stream_id in self.streams:
            print(f"Sending data on stream {stream_id}: {data}")
            self._quic.send_stream_data(stream_id, data)
        else:
            print(f"Attempted to send data on untracked stream {stream_id}, ignoring.")
    async def handle_stream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                print(f"Received data: {data}")
                # Echo data back or handle accordingly
                #writer.write(data)
                #await writer.drain()
        except Exception as e:
            print(f"Error handling stream : {e}")
        finally:
            writer.close()
            await writer.wait_closed()

async def main() -> None:
    configuration = QuicConfiguration(
        
        is_client=False,
        alpn_protocols=H3_ALPN + ["shake-quic"],  # Adjust ALPN as needed (e.g., for WebTransport use "webtransport")
    )
    configuration.load_cert_chain("ssl_cert.pem", "ssl_key.pem")  # Your TLS certificate files
    configuration.verify_mode = ssl.CERT_NONE
    await serve(
        "localhost",
        4433,
        configuration=configuration,
        create_protocol=MediaClient,  # Use the MediaClient class
        stream_handler=MediaClient.handle_stream,  # Register the stream handler):
    )
    print("AioQUIC server is running...")
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user.")
        pass
