import asyncio
import logging
import os
import socket
import urllib.parse
import urllib.request
import uuid

import aiosmtplib
import certifi

from app.config import settings
from app.integrations.email.base import EmailSender, build_mime_root

logger = logging.getLogger(__name__)


def _detect_proxy(target_host: str | None = None) -> dict | None:
    """Detect the best available outbound proxy for SMTP.

    Resolution order:
      1. ALL_PROXY / all_proxy env var → SOCKS5
      2. HTTP_PROXY / HTTPS_PROXY env var → HTTP CONNECT
      3. urllib system proxy map (macOS Network Preferences) → HTTP CONNECT
      4. Hardcoded SOCKS5 localhost:1080 probe (common for VPN proxy mode)

    Returns a dict with keys 'type' ('socks5' | 'http'), 'host', 'port',
    or None when no proxy is detected. Loopback/NO_PROXY targets never use a
    proxy — routing localhost through an HTTP proxy breaks local relays.
    """
    if target_host:
        host = target_host.strip().lower()
        if host in ("localhost", "127.0.0.1", "::1") or host.startswith("127."):
            return None
        try:
            if urllib.request.proxy_bypass(host):  # honors NO_PROXY / system bypass
                return None
        except Exception:
            pass
    # 1. Explicit SOCKS5
    for var in ("ALL_PROXY", "all_proxy"):
        val = os.environ.get(var, "")
        if val:
            parsed = urllib.parse.urlparse(val)
            if parsed.scheme in ("socks5", "socks5h"):
                return {"type": "socks5", "host": parsed.hostname or "127.0.0.1", "port": parsed.port or 1080}

    # 2. HTTP proxy from env
    for var in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        val = os.environ.get(var, "")
        if val:
            parsed = urllib.parse.urlparse(val)
            if parsed.scheme in ("http", "https"):
                return {"type": "http", "host": parsed.hostname or "127.0.0.1", "port": parsed.port or 1087}

    # 3. urllib system proxy map
    proxies = urllib.request.getproxies()
    for key in ("socks5", "socks"):
        raw = proxies.get(key, "")
        if raw:
            p = urllib.parse.urlparse(raw if "://" in raw else f"socks5://{raw}")
            return {"type": "socks5", "host": p.hostname or "127.0.0.1", "port": p.port or 1080}
    for key in ("http", "https"):
        raw = proxies.get(key, "")
        if raw:
            p = urllib.parse.urlparse(raw)
            if p.scheme in ("http", "https"):
                return {"type": "http", "host": p.hostname or "127.0.0.1", "port": p.port or 1087}

    return None


async def _open_proxied_socket(
    target_host: str, target_port: int, proxy: dict
) -> "asyncio.BaseTransport | socket.socket":
    """Return a connected socket through the given proxy."""
    if proxy["type"] == "socks5":
        from python_socks.async_.asyncio import Proxy

        p = Proxy.from_url(f"socks5://{proxy['host']}:{proxy['port']}")
        return await p.connect(dest_host=target_host, dest_port=target_port, timeout=30)

    # HTTP CONNECT
    loop = asyncio.get_event_loop()

    def _connect_via_http_proxy() -> socket.socket:
        s = socket.create_connection((proxy["host"], proxy["port"]), timeout=15)
        req = (
            f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            f"Host: {target_host}:{target_port}\r\n\r\n"
        )
        s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("Proxy closed connection during CONNECT handshake")
            buf += chunk
        status_line = buf.split(b"\r\n")[0].decode(errors="replace")
        if "200" not in status_line:
            raise ConnectionError(f"HTTP CONNECT rejected: {status_line}")
        return s

    return await loop.run_in_executor(None, _connect_via_http_proxy)


class SMTPSender(EmailSender):
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.host = cfg.get("host") or settings.smtp_host
        self.port = cfg.get("port") or settings.smtp_port
        self.username = cfg.get("username") or settings.smtp_username
        self.password = cfg.get("password") or settings.smtp_password
        self.use_tls = cfg.get("use_tls", settings.smtp_use_tls)

    async def send(
        self,
        from_address: str,
        to_address: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        reply_to: str | None = None,
        headers: dict | None = None,
        attachments: list[dict] | None = None,
    ) -> str:
        msg = build_mime_root(html_body, text_body, attachments)
        message_id = f"<{uuid.uuid4()}@ugc-outreach>"
        msg["Message-ID"] = message_id
        msg["Subject"] = subject
        msg["From"] = from_address
        msg["To"] = to_address

        if reply_to:
            msg["Reply-To"] = reply_to

        if headers:
            for key, value in headers.items():
                msg[key] = value

        proxy = _detect_proxy(self.host)
        # Auth is optional: internal/local relays commonly run without it, and
        # logging in with empty credentials errors out on such servers.
        has_auth = bool(self.username and self.password)
        try:
            if proxy:
                logger.debug(
                    f"SMTP: routing via {proxy['type'].upper()} proxy "
                    f"{proxy['host']}:{proxy['port']}"
                )
                sock = await _open_proxied_socket(self.host, self.port, proxy)
                # aiosmtplib: when passing sock, hostname/port must not be set
                smtp = aiosmtplib.SMTP(
                    hostname=self.host,
                    start_tls=self.use_tls,
                    cert_bundle=certifi.where(),
                    sock=sock,
                )
                await smtp.connect()
                if has_auth:
                    await smtp.login(self.username, self.password)
                await smtp.send_message(msg)
                try:
                    await smtp.quit()
                except Exception:
                    # Proxy may close the connection immediately after DATA —
                    # the message is already submitted so this is safe to ignore.
                    pass
            else:
                await aiosmtplib.send(
                    msg,
                    hostname=self.host,
                    port=self.port,
                    username=self.username if has_auth else None,
                    password=self.password if has_auth else None,
                    start_tls=self.use_tls,
                    cert_bundle=certifi.where(),
                )
            logger.info(f"SMTP email sent: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"SMTP send error: {e}")
            raise

    async def verify_connection(self) -> bool:
        try:
            proxy = _detect_proxy(self.host)
            if proxy:
                sock = await _open_proxied_socket(self.host, self.port, proxy)
                smtp = aiosmtplib.SMTP(
                    hostname=self.host,
                    start_tls=self.use_tls,
                    cert_bundle=certifi.where(),
                    sock=sock,
                )
            else:
                smtp = aiosmtplib.SMTP(
                    hostname=self.host,
                    port=self.port,
                    start_tls=self.use_tls,
                    cert_bundle=certifi.where(),
                )
            await smtp.connect()
            if self.username and self.password:
                await smtp.login(self.username, self.password)
            try:
                await smtp.quit()
            except Exception:
                pass
            return True
        except Exception:
            return False
