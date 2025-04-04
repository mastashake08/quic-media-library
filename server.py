import asyncio
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.asyncio.protocol import QuicConnectionProtocol

class MediaClient(QuicConnectionProtocol):
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
        alpn_protocols=["h3"],  # Adjust ALPN as needed (e.g., for WebTransport use "webtransport")
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
