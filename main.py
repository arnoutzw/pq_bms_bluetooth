#!/usr/bin/env python3
"""
Command Line Interface for PowerQueen LiFePO4 BMS Bluetooth Reader.

This module provides the command-line entry point for reading Battery Management
System (BMS) data from PowerQueen LiFePO4 batteries via Bluetooth. It supports
querying battery metrics, listing device services, and configuring connection
parameters.

Usage:
    python main.py <MAC_ADDRESS> --bms [options]
    python main.py <MAC_ADDRESS> --services [options]

Arguments:
    MAC_ADDRESS     Bluetooth device MAC address (format: XX:XX:XX:XX:XX:XX)

Options:
    --bms           Retrieve and display battery BMS information as JSON
    --services, -s  List all GATT services and characteristics
    --pair          Pair with device before communication
    --timeout, -t   Set Bluetooth timeout in seconds (default: 4)
    --verbose       Enable detailed logging output

Exit Codes:
    0 - Success (or when using --services)
    1 - Generic error
    2 - Bluetooth timeout error
    4 - Bleak library error
    6 - CRC checksum mismatch

Examples:
    # Read BMS information
    python main.py 12:34:56:78:AA:CC --bms

    # Read with extended timeout
    python main.py 12:34:56:78:AA:CC --bms --timeout 10

    # Read with pairing and verbose logging
    python main.py 12:34:56:78:AA:CC --bms --pair --verbose

    # List available services
    python main.py 12:34:56:78:AA:CC --services

Output Format:
    With --bms flag, outputs JSON with battery data:
    {
        "packVoltage": 13280,
        "voltage": 13275,
        "batteryPack": {"1": 3.32, "2": 3.32, "3": 3.32, "4": 3.32},
        "current": -2.5,
        "watt": -33.19,
        "remainAh": 85.5,
        "factoryAh": 100.0,
        "cellTemperature": 25,
        "mosfetTemperature": 28,
        "SOC": 85,
        "SOH": 100,
        "battery_status": "Discharging",
        ...
    }

Note:
    - Requires Bluetooth adapter and proper permissions
    - May require root/sudo on Linux for Bluetooth access
    - Battery must be within Bluetooth range (typically <10 meters)
"""

import sys
import asyncio
import logging
import argparse
from battery import BatteryInfo


def commands() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Configures an argument parser with all supported CLI options and
    parses sys.argv to extract user-provided arguments. Returns a
    Namespace object containing all parsed values.

    Returns:
        argparse.Namespace: Parsed arguments with the following attributes:
            - DEVICE_MAC (str): Bluetooth MAC address of the target device
            - bms (bool): True if --bms flag was provided
            - timeout (int): Bluetooth timeout in seconds
            - pair (bool): True if --pair flag was provided
            - services (bool): True if --services/-s flag was provided
            - verbose (bool): True if --verbose flag was provided

    Arguments Specification:
        DEVICE_MAC (positional, required):
            The Bluetooth MAC address of the PowerQueen battery.
            Must be in format XX:XX:XX:XX:XX:XX where XX are hex bytes.
            Example: "12:34:56:78:AA:CC"

        --bms (optional, flag):
            When present, retrieves full battery BMS information and
            outputs as formatted JSON. Mutually exclusive with --services
            in typical usage.

        -t/--timeout (optional, int, default=4):
            Bluetooth operation timeout in seconds. Increase this value
            if experiencing timeout errors due to weak signal or slow
            BMS response. Minimum practical value is 2 seconds.

        --pair (optional, flag):
            When present, initiates Bluetooth pairing before communication.
            Useful for first-time connections or systems requiring explicit
            pairing for BLE access.

        -s/--services (optional, flag):
            When present, lists all available GATT services and
            characteristics on the device. Useful for debugging and
            device discovery. Does not retrieve BMS data.

        --verbose (optional, flag):
            When present, enables detailed logging to stdout. Shows
            connection progress, raw data, and debugging information.

    Example:
        >>> args = commands()
        >>> print(f"MAC: {args.DEVICE_MAC}")
        >>> print(f"Get BMS: {args.bms}")
        >>> print(f"Timeout: {args.timeout}s")
    """
    parser = argparse.ArgumentParser(
        description="PowerQueen LiFePO4 BMS Bluetooth Reader - "
                    "Read battery information via Bluetooth Low Energy",
        epilog="Example: python main.py 12:34:56:78:AA:CC --bms --timeout 5"
    )
    parser.add_argument(
        "DEVICE_MAC",
        help="Bluetooth device MAC address in format 12:34:56:78:AA:CC",
        type=str,
    )

    parser.add_argument("--bms", help="Get battery BMS info", action="store_true")
    parser.add_argument(
        "-t",
        "--timeout",
        help="Bluetooth response timeout in seconds (default: 4)",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--pair", help="Pair with device before interacting", action="store_true"
    )
    parser.add_argument(
        "-s",
        "--services",
        help="List device GATT services and characteristics",
        action="store_true",
    )
    parser.add_argument("--verbose", help="Verbose logs", action="store_true")

    args = parser.parse_args()
    return args


def main() -> None:
    """
    Main entry point for the PowerQueen BMS CLI application.

    Orchestrates the complete workflow of the CLI tool:
    1. Parses command-line arguments
    2. Configures logging if verbose mode requested
    3. Creates BatteryInfo instance with provided configuration
    4. Executes the requested operation (services or BMS info)
    5. Outputs results and exits with appropriate code

    Returns:
        None: Results are printed to stdout. Exit code indicates success/failure.

    Exit Behavior:
        The function calls sys.exit() with the following codes:
        - 0: Success (always for --services, or --bms with no errors)
        - 1: Generic error (ERROR_GENERIC)
        - 2: Timeout error (ERROR_TIMEOUT)
        - 4: Bleak/Bluetooth error (ERROR_BLEAK)
        - 6: CRC checksum mismatch (ERROR_CHECKSUM)

    Logging Configuration:
        When --verbose is provided:
        - Creates StreamHandler outputting to stdout
        - Uses format: "YYYY-MM-DD HH:MM:SS [function_name] message"
        - Sets log level to DEBUG
        - Attaches handler to module logger

    Workflow:
        1. commands() parses CLI arguments
        2. If --verbose: configure logging
        3. Create BatteryInfo with MAC, pair, timeout, logger
        4. If --services: print GATT services and exit 0
        5. If --bms: read battery info, print JSON, exit with error_code

    Error Handling:
        Errors are handled internally by BatteryInfo.read_bms():
        - Exceptions are caught and stored in error_code/error_message
        - JSON output includes error fields
        - Exit code reflects error type

    Example Session:
        $ python main.py 12:34:56:78:AA:CC --bms
        {
            "packVoltage": 13280,
            "voltage": 13275,
            ...
            "error_code": 0,
            "error_message": null
        }
        $ echo $?
        0

        $ python main.py FF:FF:FF:FF:FF:FF --bms
        {
            ...
            "error_code": 4,
            "error_message": "BleakError: Device not found"
        }
        $ echo $?
        4
    """
    args = commands()

    logger = None

    if args.verbose:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s [%(funcName)s] %(message)s")
        handler.setFormatter(formatter)
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

    battery = BatteryInfo(args.DEVICE_MAC, args.pair, args.timeout, logger)

    if args.services:
        request = battery.get_request()
        asyncio.run(request.print_services())
        sys.exit(0)

    if args.bms:
        battery.read_bms()
        print(battery.get_json())
        sys.exit(battery.error_code)


if __name__ == "__main__":
    main()
