#!/usr/bin/python3
"""Simple executable to demonstrate and test the usage of the library."""

import argparse
import asyncio
import logging.config
import os
import time

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.control.climate import HeatingLocation


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
            "httpx": {
                "handlers": ["default"],
                "level": "ERROR",
            },
        },
    }

    logging.config.dictConfig(LOGGING_CONFIG)

    parser = argparse.ArgumentParser(description="Smart API demo")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    _ = subparsers.add_parser("status", help="Get status of vehicle.")

    _ = subparsers.add_parser("info", help="Get info of vehicle.")

    watch_parser = subparsers.add_parser("watch", help="Watch vehicle.")
    watch_parser.add_argument("-i", help="scan intervall", default=60, type=int)

    climate_parser = subparsers.add_parser("climate", help="Set climate of vehicle.")
    climate_parser.add_argument("--vin", help="VIN of vehicle", default=None)
    climate_parser.add_argument("--temp", help="Temperature", default=22)
    climate_parser.add_argument("--active", help="Active", action="store_true")

    seatheating_parser = subparsers.add_parser("seatheating", help="Set heating of seats in vehicle.")
    seatheating_parser.add_argument("--vin", help="VIN of vehicle", default=None)
    seatheating_parser.add_argument("--level", type=int, choices=[1, 2, 3], help="Heating level (1-3)", default=3)
    seatheating_parser.add_argument("--temp", help="Temperature", default=22)
    seatheating_parser.add_argument("--active", help="Active", action="store_true")

    _add_default_args(parser)
    parser.set_defaults(func=parse_command)

    return parser


async def parse_command(args) -> None:
    """Parse command."""
    if args.command == "status":
        await get_status(args)
    elif args.command == "info":
        await get_vehicle_information(args)
    elif args.command == "watch":
        await watch_car(args)
    elif args.command == "climate":
        await set_climate(args)
    elif args.command == "seatheating":
        await set_seatheating(args)
    else:
        raise NotImplementedError(f"Command {args.command} not implemented.")


async def get_status(args) -> None:
    """Get status of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()

    for vin, vehicle in account.vehicles.items():
        print(f"VIN: {vin} -> {vehicle.engine_state}")


async def get_vehicle_information(args) -> None:
    """Get status of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()

    for vin, vehicle in account.vehicles.items():
        car = await account.get_vehicle_information(vin)
        print(f"VIN: {vin}")
        print(f"{car}")


async def watch_car(args) -> None:
    """Get status of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()

    while True:
        for vin, vehicle in account.vehicles.items():
            car = await account.get_vehicle_information(vin)
            print(car)
        time.sleep(args.i)


async def set_climate(args) -> None:
    """Set climate of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()
    if not args.vin:
        args.vin = list(account.vehicles.keys())[0]
    await account.get_vehicle_information(args.vin)

    climate_ctrl = account.vehicles[args.vin].climate_control
    await climate_ctrl.set_climate_conditioning(args.temp, args.active)


async def set_seatheating(args) -> None:
    """Set heating of driver's seat in vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()
    if not args.vin:
        args.vin = list(account.vehicles.keys())[0]
    await account.get_vehicle_information(args.vin)

    climate_ctrl = account.vehicles[args.vin].climate_control
    climate_ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, args.level)
    await climate_ctrl.set_climate_conditioning(args.temp, args.active)


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
