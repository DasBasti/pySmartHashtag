#!/usr/bin/python3
"""Simple executable to demonstrate and test the usage of the library."""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import httpx

from pysmarthashtag.account import SmartAccount


def main_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description="Smart API demo")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    status_parser = subparsers.add_parser("status", help="Get status of vehicle.")
    _add_default_args(status_parser)

    parser.set_defaults(func=get_status)

    return parser

async def get_status(args) -> None:
    """Get status of vehicle."""
    account = SmartAccount(args.username, args.password)
    await account.get_vehicles()

    print(f"Found {len(account.vehicles)} vehicles:{','.join([v.name for v in account.vehicles])}")

    for vehicle in account.vehicles:
        print(f"VIN: {vehicle.vin}")
        print(f"Mileage: {vehicle.mileage.value} {vehicle.mileage.unit}")
        print("Vehicle data:")

def _add_default_args(parser: argparse.ArgumentParser):
    """Add the default arguments username, password to the parser."""
    parser.add_argument("username", help="Smart username")
    parser.add_argument("password", help="Smart password")


def main():
    """Get arguments from parser and run function in event loop."""
    parser = main_parser()
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(args.func(args))


if __name__ == "__main__":
    main()
