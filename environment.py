from pydantic import BaseModel
from typing import Optional
from ssl import create_default_context
from ssl import SSLContext
from ssl import Purpose
from os import getenv
from model import DKIMConfiguration

import logging

class Environment(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    log_level: int

    sender_domain: str

    host: str
    port: int

    ttl: int

    ssl_context: Optional[SSLContext] = None
    dkim_configuration: Optional[DKIMConfiguration] = None


def create_environment() -> Environment:
    smtp_ssl_cert = getenv("SMTP_CERT")
    smtp_ssl_key = getenv("SMTP_KEY")
    smtp_dkim_selector = getenv("SMTP_DKIM_SELECTOR")
    smtp_dkim_private_key = getenv("SMTP_DKIM_PRIVATE_KEY")
    sender_domain = getenv("SMTP_SENDER_DOMAIN")
    smtp_host = getenv("SMTP_HOST") or "127.0.0.1"
    try:
        smtp_port_str = getenv("SMTP_PORT") or 25
        smtp_port = int(smtp_port_str)
    except ValueError:
        print(f"[Environment] Cannot parse SMTP_PORT")
        smtp_port = 1025
    try:
        smtp_ttl_str = getenv("SMTP_TTL") or 3600
        smtp_ttl = int(smtp_ttl_str)
    except ValueError:
        print(f"[Environment] Cannot parse SMTP_TTL")
        smtp_ttl = 3600
    smtp_log_level = getenv("SMTP_LOG_LEVEL") or "info"

    if sender_domain is None:
        raise ValueError("[Environment] SMTP_SENDER_DOMAIN cannot be None")

    environment = Environment(
        log_level=logging.__dict__[smtp_log_level.upper()],
        sender_domain=sender_domain,
        host=smtp_host,
        port=smtp_port,
        ttl=smtp_ttl,
        dkim_configuration=DKIMConfiguration(private_key_path=smtp_dkim_private_key, selector=smtp_dkim_selector)
                           if smtp_dkim_private_key and smtp_dkim_selector else None
    )

    if smtp_ssl_cert is not None and smtp_ssl_key is not None:
        ssl_context = create_default_context(Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=smtp_ssl_cert, keyfile=smtp_ssl_key)
        environment.ssl_context = ssl_context

    return environment
