#!/usr/bin/python3
"""Simple executable to demonstrate and test the usage of the library."""

import argparse
import asyncio
import logging.config
import os
import time

from pysmarthashtag.account import SmartAccount


def environ_or_required(key):
    """Return default or required argument based on the existence of an environment variable."""
    return {"default": os.environ.get(key)} if os.environ.get(key) else {"required": True}


def main_parser() -> argparse.ArgumentParser:
    """Create argument parser."""

    LOGGING_CONFIG = {
        "version": 1,
        "handlers": {
            "default": {"class": "logging.StreamHandler", "formatter": "http", "stream": "ext://sys.stderr"},
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "http",
                "filename": "pysmarthashtag.log",
                "maxBytes": 1024 * 1024 * 10,
                "backupCount": 10,
            },
        },
        "formatters": {
            "http": {
                "format": "%(levelname)s [%(asctime)s] %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "loggers": {
            "pysmarthashtag": {
                "handlers": ["default", "file"],
                "level": "INFO",
            },
        },
    }

    logging.config.dictConfig(LOGGING_CONFIG)

    parser = argparse.ArgumentParser(description="Smart API demo")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    status_parser = subparsers.add_parser("status", help="Get status of vehicle.")
    _add_default_args(status_parser)

    parser.set_defaults(func=watch_car)

    return parser


async def get_status(args) -> None:
    """Get status of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()

    print(f"Found {len(account.vehicles)} vehicles:{','.join([v.data.get('vin') for v in account.vehicles])}")

    for vehicle in account.vehicles:
        print(f"VIN: {vehicle.vin}")


async def get_vehicle_information(args) -> None:
    """Get status of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicle_information()

    print(f"Found {len(account.vehicles)} vehicles:{','.join([v.name for v in account.vehicles])}")


async def watch_car(args) -> None:
    """Get status of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()

    def dict_to_point(d, p):
        for key, value in d.items():
            if isinstance(value, dict):
                dict_to_point(value, p)
            else:
                if hasattr(value, "isnumeric") and value.isnumeric():
                    if value.isdigit():
                        value = int(value)
                    else:
                        value = float(value)
                p.field(key, value)

    while True:
        for vehicle in account.vehicles:
            car = await account.get_vehicle_information(vehicle.vin)
            print(car)
        time.sleep(60)


def _add_default_args(parser: argparse.ArgumentParser):
    """Add the default arguments username, password to the parser."""
    parser.add_argument("--username", help="Smart username", **environ_or_required("SMART_USERNAME"))
    parser.add_argument("--password", help="Smart password", **environ_or_required("SMART_PASSWORD"))


def main():
    """Get arguments from parser and run function in event loop."""
    parser = main_parser()
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(args.func(args))


if __name__ == "__main__":
    main()
