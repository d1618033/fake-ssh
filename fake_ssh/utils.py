import contextlib

import logbook

logger = logbook.Logger(__name__)


@contextlib.contextmanager
def suppress(exception: BaseException):
    try:
        yield
    except exception as ex:
        logger.debug(f"Caught exception: {ex}")
