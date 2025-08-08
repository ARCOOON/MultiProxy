"""
server
======

Asynchronous HTTP proxy server with plugin support.  The server listens
on a specified host and port, accepts client connections, parses
HTTP/1.1 requests and forwards them to the target host.  Before a
request is proxied, it is passed through a chain of plugins which
may allow or deny it or even modify the request.  Responses from
upstream servers similarly flow through the plugin chain.

This implementation is intentionally simplified for clarity and is
**not** suitable for production use.  It does not support HTTPS
tunnelling via the CONNECT method, persistent connections or chunked
transfer encoding.  The intent is to demonstrate a clean
architecture rather than to cover every edge case in the HTTP
specification.

Usage:

```bash
python -m proxy.server --listen 127.0.0.1:8080 --plugins ./external_plugins
```

After launching the server you can direct your HTTP clients to
``http://localhost:8080``.  To manage firewall rules and other plugin
state use the separate shell entry point defined in ``shell.py``.
"""

from __future__ import annotations

import asyncio
import argparse
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit

from .plugin_manager import PluginManager


@dataclass
class HTTPRequest:
    """Represents a parsed HTTP/1.1 request."""

    raw: bytes
    method: str
    path: str
    version: str
    headers: Dict[str, str]
    body: bytes
    client: Tuple[str, int]

    def header(self, name: str) -> Optional[str]:
        return self.headers.get(name.lower())


class ProxyServer:
    def __init__(
        self, listen_host: str, listen_port: int, plugins_dir: Optional[str] = None
    ) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.manager = PluginManager()

        # Load built‑in plugins
        self.manager.load_builtin_plugins()

        # Load external plugins if provided
        if plugins_dir:
            self.manager.load_external_plugins(plugins_dir)

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        addr = writer.get_extra_info("peername")

        try:
            request = await self.read_http_request(reader, addr)
        except asyncio.IncompleteReadError:
            writer.close()
            await writer.wait_closed()
            return

        if request is None:
            # Invalid request
            writer.close()
            await writer.wait_closed()
            return

        # Pass request through plugins
        allowed = self.manager.process_request(request)
        if not allowed:
            # Denied by a plugin
            resp = b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n"
            writer.write(resp)
            await writer.drain()

            writer.close()
            await writer.wait_closed()
            return

        # HTTPS & generic‐TCP tunnelling via CONNECT
        if request.method.upper() == "CONNECT":
            await self.handle_connect_tunnel(request, reader, writer)
            return

        # Determine upstream host and port
        host_header = request.header("host")
        if not host_header:
            resp = b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n"
            writer.write(resp)
            await writer.drain()

            writer.close()
            await writer.wait_closed()
            return

        upstream_host, upstream_port = self.parse_host(host_header)

        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream_host, upstream_port
            )
        except Exception:
            resp = b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n"
            writer.write(resp)
            await writer.drain()

            writer.close()
            await writer.wait_closed()
            return

        # Prepare request line for upstream (remove scheme and host from absolute URI)
        path = self.extract_path(request.path)

        # Reconstruct request header lines
        lines = [f"{request.method} {path} {request.version}"]
        for key, value in request.headers.items():
            # Use original case if available (not preserved here).  Lowercase keys suffice.
            lines.append(f"{key}: {value}")

        header_bytes = "\r\n".join(lines).encode("latin-1") + b"\r\n\r\n"
        body = request.body

        upstream_writer.write(header_bytes + body)
        await upstream_writer.drain()

        # 1) Read just the response headers (up to \r\n\r\n)
        header_data = await upstream_reader.readuntil(b"\r\n\r\n")
        writer.write(header_data)
        await writer.drain()

        # 2) If this is a WebSocket handshake (101 + Upgrade: websocket), tunnel raw bytes
        first_line = header_data.split(b"\r\n", 1)[0]
        if b"101" in first_line and b"upgrade: websocket" in header_data.lower():
            await self.pipe_bidirectional(
                reader, writer, upstream_reader, upstream_writer
            )
            return

        # 3) Otherwise read the rest of the HTTP body and run it through plugins
        body_data = await upstream_reader.read(-1)
        full_response = header_data + body_data
        processed = self.manager.process_response(full_response, request)
        writer.write(processed)
        await writer.drain()

        # 4) Teardown
        upstream_writer.close()
        writer.close()
        await upstream_writer.wait_closed()
        await writer.wait_closed()

    async def read_http_request(
        self, reader: asyncio.StreamReader, addr: Tuple[str, int]
    ) -> Optional[HTTPRequest]:
        # Read header until blank line
        try:
            header_data = await reader.readuntil(b"\r\n\r\n")
        except asyncio.LimitOverrunError:
            return None
        except asyncio.IncompleteReadError:
            return None

        # Decode header lines
        try:
            header_text = header_data.decode("latin-1")
        except UnicodeDecodeError:
            return None

        lines = header_text.split("\r\n")
        if not lines:
            return None

        # Parse request line
        request_line = lines[0]
        parts = request_line.split()

        if len(parts) != 3:
            return None

        method, path, version = parts

        # Parse headers
        headers: Dict[str, str] = {}

        for line in lines[1:]:
            if not line:
                continue
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()

        # Determine body length
        body = b""
        cl = headers.get("content-length")

        if cl and cl.isdigit():
            length = int(cl)
            if length > 0:
                body = await reader.readexactly(length)

        return HTTPRequest(
            raw=header_data + body,
            method=method,
            path=path,
            version=version,
            headers=headers,
            body=body,
            client=addr,
        )

    @staticmethod
    def parse_host(host_header: str) -> Tuple[str, int]:
        """Parse a Host header into host and port.

        The previous implementation naïvely split on the first colon which
        broke for IPv6 addresses like ``[2001:db8::1]:8080`` because the
        embedded colons were treated as port separators.  Using ``urlsplit``
        handles IPv6 literals and optional ports correctly.
        """
        result = urlsplit(f"//{host_header}")
        host = result.hostname or host_header
        port = result.port or 80
        return host, port

    @staticmethod
    def extract_path(url: str) -> str:
        # Remove scheme and host from absolute URL to send to upstream
        m = re.match(r"https?://[^/]+(.*)", url)
        if m:
            path = m.group(1)
            return path or "/"
        return url

    async def handle_connect_tunnel(
        self, request, client_reader, client_writer
    ) -> None:
        """Implements HTTP CONNECT for HTTPS & generic TCP/IP tunneling."""
        host, port_str = request.path.split(":", 1)
        port = int(port_str)

        try:
            remote_reader, remote_writer = await asyncio.open_connection(host, port)
        except:  # noqa
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await client_writer.drain()
            client_writer.close()
            return

        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()

        # tunnel raw bytes both ways
        await self.pipe_bidirectional(
            client_reader, client_writer, remote_reader, remote_writer
        )

    async def pipe_bidirectional(self, r1, w1, r2, w2) -> None:
        """Pump bytes r1→w2 and r2→w1 until one side closes."""

        async def pump(src, dst):
            try:
                while True:
                    chunk = await src.read(4096)
                    if not chunk:
                        break
                    dst.write(chunk)
                    await dst.drain()
            except asyncio.CancelledError:
                pass

        t1 = asyncio.create_task(pump(r1, w2))
        t2 = asyncio.create_task(pump(r2, w1))

        done, pending = await asyncio.wait(
            [t1, t2], return_when=asyncio.FIRST_COMPLETED
        )

        for p in pending:
            p.cancel()

        w1.close()
        w2.close()

        await w1.wait_closed()
        await w2.wait_closed()

    async def run(self) -> None:
        server = await asyncio.start_server(
            self.handle_client, self.listen_host, self.listen_port
        )
        addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)

        print(f"Proxy listening on {addrs}")

        async with server:
            try:
                await server.serve_forever()
            except asyncio.CancelledError:
                pass
            finally:
                # Finalize plugins on shutdown
                self.manager.finalize_plugins()


def parse_listen(arg: str) -> Tuple[str, int]:
    if ":" not in arg:
        raise argparse.ArgumentTypeError("Expected HOST:PORT")

    host, port_str = arg.split(":", 1)

    try:
        port = int(port_str)
    except ValueError:
        raise argparse.ArgumentTypeError("Invalid port")

    return host, port


def main() -> None:
    parser = argparse.ArgumentParser(description="Asynchronous HTTP proxy server")
    parser.add_argument(
        "--listen",
        type=parse_listen,
        default=("127.0.0.1", 8080),
        help="Address and port to listen on (HOST:PORT)",
    )
    parser.add_argument(
        "--plugins",
        type=str,
        help="Optional path to directory containing external plugins",
    )
    args = parser.parse_args()
    host, port = args.listen

    proxy = ProxyServer(host, port, plugins_dir=args.plugins)

    try:
        asyncio.run(proxy.run())
    except KeyboardInterrupt:
        print("Shutting down proxy")


if __name__ == "__main__":
    main()
