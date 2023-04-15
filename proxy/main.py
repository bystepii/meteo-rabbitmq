import logging
import os
from typing import Optional

import click
import redis as redis
from pika import BlockingConnection, URLParameters

from common.log import setup_logger, LOGGER_LEVEL_CHOICES
from proxy.tumbling_window import TumblingWindow

logger = logging.getLogger(__name__)


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('rabbitmq-address', type=str, required=False, default=os.environ.get('RABBITMQ_ADDRESS'))
@click.argument('redis-address', type=str, required=False,
                default=os.environ.get("REDIS_ADDRESS"))
@click.option('--debug', is_flag=True, help="Enable debug logging")
@click.option('--log-level', type=click.Choice(LOGGER_LEVEL_CHOICES),
              default=os.environ.get('LOG_LEVEL', 'info'), help="Set the log level")
@click.option('--interval', type=int, default=os.environ.get("INTERVAL"),
              help="Set the default tumbling window interval in ms")
def main(
        rabbitmq_address: str,
        redis_address: str,
        log_level: str,
        debug: bool = False,
        interval: Optional[int] = None,
):
    setup_logger(log_level=logging.DEBUG if debug else log_level.upper())

    if not rabbitmq_address:
        raise ValueError("RabbitMQ address must be provided")

    if not redis_address:
        raise ValueError("Redis address must be provided")

    logger.info("Starting proxy server")

    # Create the tumbling window
    tumbling_window = TumblingWindow(
        redis.from_url(redis_address, db=0),
        BlockingConnection(URLParameters(rabbitmq_address)),
        interval
    )

    try:
        tumbling_window.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        exit(0)


if __name__ == '__main__':
    main()
