from model import MessageSummary
from model import MessageDetails
from uuid import uuid4
from typing import Dict, List
from typing import Optional
from email.message import EmailMessage
from email.header import decode_header
from aiosmtpd.handlers import AsyncMessage
from logging import getLogger
from datetime import datetime
from datetime import timezone
from datetime import timedelta
from asyncio import sleep
from asyncio import create_task
from asyncio import Task

MessageID = str
MessageMapping = Dict[MessageID, MessageDetails]

logger = getLogger(__name__)

def decode_rfc2047_header(value: str) -> str:
    decoded_fragments = decode_header(value)
    result = ""
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            result += fragment.decode(charset or "utf-8", errors="ignore")
        else:
            result += fragment
    return result

def extract_plain_text_body_or_none(message: EmailMessage) -> Optional[str]:
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "")
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                    except UnicodeDecodeError:
                        continue
        return None
    else:
        payload = message.get_payload(decode=True)
        if payload:
            return payload.decode(message.get_content_charset() or "utf-8", errors="ignore")
        return None

class MailHandler(AsyncMessage):

    def __init__(self, ttl: int) -> None:
        super().__init__()
        self.messages: Dict[MessageID, MessageDetails] = {}
        self.cleanup_task: Optional[Task] = None
        self.ttl = ttl

    async def cleanup_process(self) -> None:
        while True:
            await sleep(self.ttl)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            expired = [msg_id for msg_id, msg in self.messages.items() if msg.received_time < cutoff]
            logger.info(f"Cleaning up {len(expired)} messages")
            for msg_id in expired:
                del self.messages[msg_id]

    def launch_cleanup(self) -> None:
        logger.info("Launching cleanup task")
        self.cleanup_task = create_task(self.cleanup_process())

    def shutdown_cleanup(self) -> None:
        logger.info("Shutting down cleanup task")
        self.cleanup_task.cancel()

    async def handle_message(self, message: EmailMessage) -> None:
        message_id = str(uuid4())
        raw_subject = message.get("Subject", "")
        raw_from = message.get("From", "")
        raw_to = message.get("To", "")
        message_subject = decode_rfc2047_header(raw_subject)
        message_from = decode_rfc2047_header(raw_from)
        message_to = decode_rfc2047_header(raw_to)
        message_content = extract_plain_text_body_or_none(message)
        received_time = datetime.now(timezone.utc)
        log_str = f"Message received (id={message_id}; from={message_from}; to={message_to}; subject={message_subject})"
        if message_content is None:
            log_str += ", but no content found."
        else:
            log_str += "."
        logger.info(log_str)
        self.messages[message_id] = MessageDetails(
            id=message_id,
            from_=message_from,
            to=message_to,
            subject=message_subject,
            received_time=received_time,
            content=message_content,
        )

    def get_messages(self, skip: int, size: int) -> List[MessageSummary]:
        return [MessageSummary(**message.model_dump(exclude={"content"})) for message in list(self.messages.values())[skip:skip + size]]

    def get_message(self, msg_id: MessageID) -> Optional[MessageDetails]:
        return self.messages.get(msg_id)
