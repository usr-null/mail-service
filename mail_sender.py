from aiodns import DNSResolver
from email.message import EmailMessage
from email.utils import make_msgid
from email.utils import formatdate
from dkim import sign
from aiofiles import open as async_open
from aiosmtplib import SMTP
from asyncio import run
from typing import Optional
from typing import List
from logging import getLogger
from sys import exc_info
from traceback import format_exception
from model import MessageSendingStepError
from model import MessageSendingStepType
from model import MessageSendingLogEntry
from model import DKIMConfiguration
from model import MessageSendingResult
from pprint import pprint


logger = getLogger(__name__)

LogBatch = List[MessageSendingLogEntry]

def _get_msg_sending_error() -> Optional[MessageSendingStepError]:
    e_type, e_message, e_trace_back = exc_info()
    if e_type is None and e_message is None and e_trace_back is None:
        return None
    return MessageSendingStepError(
        type=e_type.__name__,
        message=str(e_message),
        trace_back="".join(format_exception(e_type, e_message, e_trace_back)),
    )

def _get_log_entry(step_type: MessageSendingStepType, domain: str) -> MessageSendingLogEntry:
    return MessageSendingLogEntry(
        step_type=step_type,
        domain=domain,
        error=_get_msg_sending_error(),
    )

class MailSender:
    def __init__(self, domain: str, dkim: Optional[DKIMConfiguration] = None) -> None:
        self.domain: str = domain
        self.dkim_private_key_cached: Optional[bytes] = None
        self.dkim_config: Optional[DKIMConfiguration] = dkim
        self.resolver: DNSResolver = DNSResolver()
        self.resolver.nameservers: List[str] = ["1.1.1.1", "8.8.8.8", "77.88.8.8"]
        
        self.base_dkim_include_headers: List[str] = [
            "message-id",
            "date",
            "from",
            "to",
            "subject",
            "content-type",
            "content-transfer-encoding",
            "mime-version"
        ]

    async def _get_mx_hosts(self, host: str) -> List[str]:
        results = await self.resolver.query(host, "MX")
        return [result.host for result in sorted(results, key=lambda x: x.priority)]

    async def load_dkim_private_key(self) -> Optional[bytes]:
        if self.dkim_config is not None and self.dkim_private_key_cached is None:
            async with async_open(self.dkim_config.private_key_path, "rb") as f:
                self.dkim_private_key_cached = await f.read()
        return self.dkim_private_key_cached

    async def _send_single(
        self,
        from_user: str,
        to: str,
        title: str,
        content: str,
        html_content: str,
        sender_alias: Optional[str],
        host: str,
        port: int
    ) -> LogBatch:
        batch: LogBatch = []
        from_full = f"<{from_user}@{self.domain}>"
        to_full = f"<{to}>"
        smtp = SMTP(
            hostname=host,
            port=port,
            start_tls=False,
            use_tls=False
        )
        connected = False

        try:
            await smtp.connect()
            await smtp.ehlo(hostname=self.domain)

            tls = False
            if smtp.supports_extension("STARTTLS"):
                try:
                    await smtp.starttls()
                    await smtp.ehlo(hostname=self.domain)
                    tls = True
                    batch.append(_get_log_entry("START_TLS", host))
                except:
                    batch.append(_get_log_entry("START_TLS", host))
            if not tls:
                batch.append(_get_log_entry("START_PLAIN_TEXT", host))

            connected = True

            try:
                await smtp.mail(from_full)
                batch.append(_get_log_entry("SEND_FROM", host))
            except:
                batch.append(_get_log_entry("SEND_FROM", host))
                return batch

            try:
                await smtp.rcpt(to)
                batch.append(_get_log_entry("SEND_TO", host))
            except:
                batch.append(_get_log_entry("SEND_TO", host))
                return batch

            try:
                message = EmailMessage()
                message["Message-ID"] = make_msgid(domain=self.domain)
                message["Date"] = formatdate(localtime=False)
                if sender_alias is not None:
                    message["From"] = f"{sender_alias} {from_full}"
                else:
                    message["From"] = from_full
                message["To"] = to_full
                message["Subject"] = title
                message["MIME-Version"] = "1.0"
                message.set_content(content, charset="utf-8")
                message.add_alternative(html_content, subtype="html", charset="utf-8")

                msg_content = message.as_bytes()

                if self.dkim_config is not None:
                    msg_content = sign(
                        message=msg_content,
                        selector=self.dkim_config.selector.encode("utf-8"),
                        domain=self.domain.encode("utf-8"),
                        privkey=await self.load_dkim_private_key(),
                        include_headers=self.base_dkim_include_headers,
                    ) + msg_content

                await smtp.data(msg_content)
                batch.append(_get_log_entry("SEND_DATA", host))
            except:
                batch.append(_get_log_entry("SEND_DATA", host))
                return batch

        finally:
            if connected:
                try:
                    await smtp.quit()
                    batch.append(_get_log_entry("QUIT", host))
                except:
                    batch.append(_get_log_entry("QUIT", host))

        return batch

    async def send_mail(self, from_user: str, to: str, title: str, content: str, html_content: str, sender_alias: Optional[str] = None) -> MessageSendingResult:
        batch = list()

        try:
            domain = to.split("@")[1]
        except IndexError:
            return MessageSendingResult(success=False, logs=[])
        try:
            lookup_results = await self._get_mx_hosts(domain)
            batch.append(_get_log_entry("DNS_LOOKUP", domain))
        except:
            batch.append(_get_log_entry("DNS_LOOKUP", domain))
            return MessageSendingResult(success=False, logs=batch)

        for host in lookup_results:
            sub_batch = await self._send_single(from_user, to, title, content, html_content, sender_alias, host, 25)
            batch.extend(sub_batch)

            if not any(entry.step_type == "SEND_TO" for entry in sub_batch):
                continue
            if any(entry.step_type == "SEND_DATA" and entry.error is None for entry in sub_batch):
                return MessageSendingResult(success=True, logs=batch)
            else:
                return MessageSendingResult(success=False, logs=batch)

        return MessageSendingResult(success=False, logs=batch)
