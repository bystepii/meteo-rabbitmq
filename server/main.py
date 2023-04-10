import logging
import os

import click
import redis.asyncio as redis

from common.log import setup_logger, LOGGER_LEVEL_CHOICES
from common.meteo_utils import MeteoDataProcessor
from server import Server

logger = logging.getLogger(__name__)


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('rabbitmq-address', type=str, required=False, default=os.environ.get('RABBITMQ_ADDRESS'))
@click.argument('redis-address', type=str, required=False,
                default=os.environ.get("REDIS_ADDRESS"))
@click.option('--debug', is_flag=True, help="Enable debug logging")
@click.option('--log-level', type=click.Choice(LOGGER_LEVEL_CHOICES),
              default=os.environ.get('LOG_LEVEL', 'info'), help="Set the log level")
def main(
        rabbitmq_address: str,
        redis_address: str,
        log_level: str,
        debug: bool = False,
):
    setup_logger(log_level=logging.DEBUG if debug else log_level.upper())

    if not rabbitmq_address:
        raise ValueError("RabbitMQ address must be provided")

    if not redis_address:
        raise ValueError("Redis address must be provided")

    logger.info("Starting processing server")

    # Create server
    server = Server(
        MeteoDataProcessor(),
        redis.from_url(redis_address, db=0),
        rabbitmq_address
    )

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        server.stop()
        exit(0)


if __name__ == '__main__':
    main()
