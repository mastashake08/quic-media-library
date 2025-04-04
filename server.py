import asyncio
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import ProtocolNegotiated
class MediaClient(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.streams = {}   
        print("MediaClient initialized.")

    def quic_event_received(self, event):       
        super().quic_event_received(event)
        if hasattr(event, 'stream_id') and event.stream_id not in self.streams:
            print(f"New stream opened: {event.stream_id}")
            self.streams[event.stream_id] = event.stream_id
        if isinstance(event, asyncio.StreamClosed):
            stream_id = event.stream_id
            if stream_id in self.streams:
                print(f"Stream {stream_id} closed.")
                del self.streams[stream_id]
            else:
                print(f"Stream {event.stream_id} closed but was not tracked.")
        elif isinstance(event, asyncio.StreamOpened):
            print(f"Stream {event.stream_id} opened.")
            self.streams[event.stream_id] = event.stream_id
        elif isinstance(event, ProtocolNegotiated):
            print(f"Protocol negotiated: {event}")
            # You can handle protocol negotiation here if needed
            return
        elif isinstance(event, asyncio.StreamDataReceived):
            stream_id = event.stream_id
            print(f"Data received on stream {stream_id}: {event.data}")
            # Handle the received data as needed
            # For example, you could echo it back or process it
            if stream_id in self.streams:
                # Echo the data back to the client
                self.send_stream_data(stream_id, event.data)
            else:
                print(f"Received data on untracked stream {stream_id}, ignoring.")
    def send_stream_data(self, stream_id: int, data: bytes):
        if stream_id in self.streams:
            print(f"Sending data on stream {stream_id}: {data}")
            self._quic.send_stream_data(stream_id, data)
        else:
            print(f"Attempted to send data on untracked stream {stream_id}, ignoring.")
    async def handle_stream(self, stream_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        print(f"Stream {stream_id} opened by client.")
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                print(f"Received data: {data}")
                # Echo data back or handle accordingly
                writer.write(data)
                await writer.drain()
        except Exception as e:
            print(f"Error handling stream {stream_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"Stream {stream_id} closed.")

async def main() -> None:
    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=["h3", "shake-quic"],  # Adjust ALPN as needed (e.g., for WebTransport use "webtransport")
    )
    configuration.load_cert_chain("ssl_cert.pem", "ssl_key.pem")  # Your TLS certificate files

    await serve(
        "0.0.0.0",
        4433,
        configuration=configuration,
        create_protocol=MediaClient,
        stream_handler=MediaClient.handle_stream,  # Register the stream handler):
    )
    print("AioQUIC server is running...")
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
