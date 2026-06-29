from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from aiosmtpd.controller import Controller
from mail_handler import MailHandler
from mail_sender import MailSender
from contextlib import asynccontextmanager
from typing import List
from logger_cfg import setup_logging
from model import MessageSummary
from model import MessageDetails
from model import MessageSendingRequest
from model import MessageSendingResult
from environment import create_environment

service_environment = create_environment()

mail_handler = MailHandler(ttl=service_environment.ttl)
mail_sender = MailSender(domain=service_environment.sender_domain, dkim=service_environment.dkim_configuration)
mail_controller = Controller(
    mail_handler,
    hostname=service_environment.host,
    port=service_environment.port,
    tls_context=service_environment.ssl_context,
    require_starttls=False
)
setup_logging(level=service_environment.log_level)

@asynccontextmanager
async def startup_event(_):
    mail_handler.launch_cleanup()
    mail_controller.start()
    yield
    mail_controller.stop()
    mail_handler.shutdown_cleanup()

app = FastAPI(lifespan=startup_event)

@app.get("/message", response_model=List[MessageSummary])
async def list_messages(skip: int = 0, limit: int = 100) -> List[MessageSummary]:
    return mail_handler.get_messages(skip, limit)

@app.get("/message/{msg_id}", response_model=MessageDetails)
async def get_message(msg_id: str) -> MessageDetails:
    msg = mail_handler.get_message(msg_id)
    if not msg:
        raise HTTPException(status_code=404)
    return msg

@app.post("/message", response_model=MessageSendingResult)
async def send_message(data: MessageSendingRequest, from_user: str = Query("admin", alias="from"), to: str = Query()) -> MessageSendingResult:
    return await mail_sender.send_mail(from_user, to, data.title, data.content, data.html_content, data.sender_alias)
