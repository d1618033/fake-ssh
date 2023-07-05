import contextlib

from loguru import logger


@contextlib.contextmanager
def suppress(exception: Exception):
    try:
        yield
    except exception as ex:
        logger.debug(f'Caught exception: {ex}')
