from logging import basicConfig
from logging import INFO
from logging import StreamHandler

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

def setup_logging(level: int = INFO):
    basicConfig(
        level=INFO,
        format=LOG_FORMAT,
        handlers=[StreamHandler()]
    )
