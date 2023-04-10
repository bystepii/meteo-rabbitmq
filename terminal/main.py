import logging
import os

import click

from common.log import setup_logger, LOGGER_LEVEL_CHOICES
from terminal import Terminal

logger = logging.getLogger(__name__)


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('rabbitmq-address', type=str, required=False, default=os.environ.get('RABBITMQ_ADDRESS'))
@click.option('--debug', is_flag=True, help="Enable debug logging")
@click.option('--log-level', type=click.Choice(LOGGER_LEVEL_CHOICES),
              default=os.environ.get('LOG_LEVEL', 'info'), help="Set the log level")
def main(
        rabbitmq_address: str,
        log_level: str,
        debug: bool = False,
):
    setup_logger(log_level=logging.DEBUG if debug else log_level.upper())

    if rabbitmq_address is None:
        raise ValueError("RabbitMQ address is required")

    logger.info("Starting load balancer")

    # Create Terminal
    terminal = Terminal(
        rabbitmq_address
    )

    try:
        terminal.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        exit(0)


if __name__ == '__main__':
    main()
