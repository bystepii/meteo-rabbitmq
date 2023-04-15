# Distributed meteorological data processing system
## Implementation 2: indirect communication

This is the second implementation of the distributed meteorological data processing system.
It is based on indirect communication between the client and the server using th RabbitMQ message broker.

## Installation and execution

### Server side and sensors

To run the system, you need to have Docker and Docker Compose installed on your machine.
Refer to the [official documentation](https://docs.docker.com/engine/install/) for installation instructions.

Before running the system, ensure that the ports 5672, 15672 and 6379 are not in use.

To run the system in the background, execute the following command in the root directory of the project:

    docker compose up -d

By default, only one processing server instance is started and the two types of sensors.
If you want to start more processing server instances, you can do so by executing the following command:

    docker compose up -d --scale server=NUMBER_OF_INSTANCES

You can also start more sensors by executing the following commands

    docker compose up -d --scale air-quality-sensor=NUMBER_OF_INSTANCES
    docker compose up -d --scale pollution-sensor=NUMBER_OF_INSTANCES

To check the current status of the system, execute the following command:

    docker compose ps

To view the logs of the system, execute the following command (by default, the logs are in debug mode
so the output will be very verbose):

    docker compose logs

To stop the system, execute the following command:

    docker compose down

See the [docker official documentation](https://docs.docker.com/compose/reference/up/) for more information
and the [docker-compose.yml](docker-compose.yml) file for the configuration of the system. Most
of the configuration is specified by environment variables, which are self-explanatory.

### Terminal client

To run the terminal client you must have Python 3.8 or higher installed on your machine. Install
the required dependencies by executing the following command in the root directory of the project:

    pip install -r terminal/requirements.txt

Finally, you can then run the terminal:

    PYTHONPATH=. python3 terminal/main.py amqp://localhost:5672 --debug

The `amqp://localhost:5672` argument specifies the address of the RabbitMQ server. The `--debug` flag
enables debug logging.
