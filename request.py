"""
Bluetooth Low Energy (BLE) Request Handler for PowerQueen BMS Communication.

This module provides the Request class for handling Bluetooth Low Energy
communication with PowerQueen LiFePO4 battery BMS devices. It abstracts the
Bleak library's async API and provides a clean interface for sending commands
and receiving responses.

Architecture Overview:
    The Request class manages the complete BLE communication lifecycle:
    1. Connection establishment with optional pairing
    2. Command transmission via GATT characteristic writes
    3. Response reception via GATT notifications
    4. Connection cleanup and disconnection

BLE Communication Flow:
    1. Client connects to device using MAC address
    2. Optional pairing is performed for secure communication
    3. Notification listener is registered for response characteristic
    4. Command bytes are written to the characteristic
    5. BMS processes command and sends response via notification
    6. Callback function is invoked with response data
    7. Connection is closed and optionally unpaired

GATT Characteristics Used:
    - 0000FFE1-0000-1000-8000-00805F9B34FB: Primary BMS data read/write
    - 0000FFE2-0000-1000-8000-00805F9B34FB: Serial number (unimplemented)

Dependencies:
    - asyncio: Async/await support for BLE operations
    - bleak: Cross-platform Bluetooth Low Energy library
    - logging: Debug and info logging

Example Usage:
    >>> import asyncio
    >>> from request import Request
    >>>
    >>> async def handle_response(data):
    ...     print(f"Received: {data.hex()}")
    ...
    >>> request = Request("12:34:56:78:AA:CC", timeout=5)
    >>> asyncio.run(request.send(
    ...     "0000FFE1-0000-1000-8000-00805F9B34FB",
    ...     "00 00 04 01 13 55 AA 17",
    ...     handle_response
    ... ))

Note:
    All public methods in this class are async coroutines and must be
    awaited or run via asyncio.run().
"""

import asyncio
import logging
from typing import Callable
from bleak import BleakClient, BleakGATTCharacteristic


class Request:
    """
    Bluetooth Low Energy request handler for BMS communication.

    This class encapsulates all Bluetooth communication logic, providing
    methods to send commands to the battery BMS and receive responses.
    It handles connection management, pairing, notifications, and error
    handling for robust BLE communication.

    The class is designed for use with PowerQueen LiFePO4 batteries but
    may work with other BLE devices that use similar GATT-based protocols.

    Attributes:
        bluetooth_device_mac (str): The MAC address of the target BLE device.
            Format: "XX:XX:XX:XX:XX:XX".
        pair (bool): Whether to pair with the device before communication.
            Pairing may be required for certain security configurations.
        callback_func (Callable | None): The currently registered callback
            function for handling received data. Set before each command.
        bluetooth_timeout (int): Timeout in seconds for BLE operations.
            Applies to connection establishment and data transfer.
        logger (logging.Logger): Logger instance for debug output.

    Thread Safety:
        This class is not thread-safe. All methods should be called from
        the same async context. For multi-threaded usage, create separate
        Request instances per thread.

    Example:
        >>> request = Request("12:34:56:78:AA:CC", pair_device=True, timeout=5)
        >>> async def callback(data):
        ...     print(f"Got {len(data)} bytes")
        >>> await request.send(char_id, command, callback)
    """

    def __init__(
        self,
        bluetooth_device_mac: str,
        pair_device: bool = False,
        timeout: int = 2,
        logger=None,
    ):
        """
        Initialize a Request instance for Bluetooth communication.

        Creates a configured Request object ready to communicate with a
        specific BLE device. The instance stores configuration but does
        not establish a connection until send() or bulk_send() is called.

        Args:
            bluetooth_device_mac (str): MAC address of the target Bluetooth
                device. Must be in standard format: "XX:XX:XX:XX:XX:XX"
                where XX are hexadecimal bytes.
                Example: "12:34:56:78:AA:CC"
            pair_device (bool, optional): Whether to perform Bluetooth pairing
                before communication. Pairing creates a trusted relationship
                and may be required for:
                - First-time connections
                - Systems with strict security policies
                - Some Linux Bluetooth configurations
                Defaults to False.
            timeout (int, optional): Timeout in seconds for Bluetooth operations.
                This affects:
                - Connection establishment time
                - Command response wait time
                Increase this value if experiencing timeout errors due to:
                - Weak Bluetooth signals
                - Busy BMS processing
                - System performance issues
                Defaults to 2 seconds.
            logger (logging.Logger | None, optional): Logger instance for
                debug and info messages. If None, a module-level logger
                is created automatically using __name__.

        Raises:
            No exceptions during initialization. Connection errors occur
            when calling communication methods.

        Example:
            >>> # Basic initialization
            >>> request = Request("12:34:56:78:AA:CC")
            >>>
            >>> # With all options
            >>> import logging
            >>> logger = logging.getLogger("my_app")
            >>> request = Request(
            ...     "12:34:56:78:AA:CC",
            ...     pair_device=True,
            ...     timeout=10,
            ...     logger=logger
            ... )
        """
        self.bluetooth_device_mac = bluetooth_device_mac
        self.pair = pair_device
        self.callback_func = None
        self.bluetooth_timeout = timeout

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)

    async def send(
        self, characteristic_id: str, command: str, callback_func: Callable
    ) -> None:
        """
        Send a single command to the BLE device and receive response.

        This is a convenience wrapper around bulk_send() for sending a single
        command. The method establishes a connection, sends the command,
        waits for the response, and closes the connection.

        Args:
            characteristic_id (str): The UUID of the GATT characteristic to
                write to. For PowerQueen BMS, use:
                - "0000FFE1-0000-1000-8000-00805F9B34FB" for BMS data
                - "0000FFE2-0000-1000-8000-00805F9B34FB" for serial number
            command (str): The command to send as a space-separated hex string.
                Each byte is represented as two hex digits.
                Example: "00 00 04 01 13 55 AA 17"
            callback_func (Callable): Function to call with the response data.
                Signature: callback_func(data: bytearray) -> None
                The callback is invoked when the BMS sends a notification
                with the command response.

        Returns:
            None: Response is delivered via the callback function.

        Raises:
            BleakError: If Bluetooth connection or communication fails.
            TimeoutError: If the connection or response times out.

        Example:
            >>> async def handle_battery_info(data):
            ...     print(f"Battery data: {data.hex()}")
            ...
            >>> await request.send(
            ...     "0000FFE1-0000-1000-8000-00805F9B34FB",
            ...     "00 00 04 01 13 55 AA 17",
            ...     handle_battery_info
            ... )
        """
        await self.bulk_send(
            characteristic_id, commands_parsers={command: callback_func}
        )

    async def bulk_send(self, characteristic_id: str, commands_parsers: dict) -> None:
        """
        Send multiple commands to the BLE device in sequence.

        Establishes a single Bluetooth connection and sends multiple commands
        in sequence, each with its own callback function. This is more efficient
        than calling send() multiple times as it reuses the connection.

        Args:
            characteristic_id (str): The UUID of the GATT characteristic for
                all commands. All commands are sent to the same characteristic.
            commands_parsers (dict): Dictionary mapping command strings to
                callback functions. Commands are sent in dictionary iteration
                order (insertion order in Python 3.7+).
                Keys: Command strings (space-separated hex bytes)
                Values: Callback functions (Callable[[bytearray], None])

        Returns:
            None: Responses are delivered via respective callback functions.

        Raises:
            BleakError: If Bluetooth connection or communication fails.
            TimeoutError: If any operation times out.

        Communication Flow:
            1. Connect to device with configured timeout
            2. Optionally pair if pair=True
            3. For each command:
               a. Register notification handler with callback
               b. Write command bytes to characteristic
               c. Wait 1 second for response
               d. Stop notification listening
            4. Disconnect from device
            5. Optionally unpair if paired

        Timing:
            Each command has a 1-second wait period for the response. Total
            execution time is approximately: connection_time + (n_commands * 1s)
            + disconnection_time.

        Note:
            Commands are sent sequentially, not concurrently. Each command
            completes before the next begins. This matches the BMS's
            single-threaded command processing.

        Example:
            >>> def parse_version(data):
            ...     print(f"Version: {data[8:14]}")
            ...
            >>> def parse_battery(data):
            ...     voltage = int.from_bytes(data[8:12][::-1], 'big')
            ...     print(f"Voltage: {voltage}mV")
            ...
            >>> commands = {
            ...     "00 00 04 01 16 55 AA 1A": parse_version,
            ...     "00 00 04 01 13 55 AA 17": parse_battery
            ... }
            >>> await request.bulk_send(
            ...     "0000FFE1-0000-1000-8000-00805F9B34FB",
            ...     commands
            ... )
        """
        self.logger.info(
            "Connecting to %s... (timeout: %s)",
            self.bluetooth_device_mac,
            self.bluetooth_timeout,
        )
        async with BleakClient(
            self.bluetooth_device_mac, timeout=self.bluetooth_timeout
        ) as client:
            if self.pair:
                self.logger.info("Pairing %s...", self.bluetooth_device_mac)
                await client.pair()

            for commandStr, parser in commands_parsers.items():
                command = self._create_command(commandStr)
                self.callback_func = parser

                await client.start_notify(characteristic_id, self._data_callback)
                self.logger.info("Sending command: %s", command)
                result = await client.write_gatt_char(
                    characteristic_id, data=command, response=True
                )
                await asyncio.sleep(1.0)

                self.logger.info("Raw result: %s", result)
                await client.stop_notify(characteristic_id)

        self.logger.info("Disconnecting %s...", self.bluetooth_device_mac)
        if self.pair:
            client.unpair()
        await client.disconnect()
        self.logger.info("Disconnected %s", self.bluetooth_device_mac)

    async def print_services(self) -> None:
        """
        Discover and print all GATT services and characteristics.

        Connects to the BLE device and enumerates all available GATT services
        and their characteristics. For each characteristic, attempts to read
        its current value. This is useful for debugging and discovering
        device capabilities.

        Returns:
            None: Service information is printed to stdout.

        Raises:
            BleakError: If Bluetooth connection fails.
            TimeoutError: If connection times out.

        Output Format:
            For each service, prints:
            - Service UUID and description
            - List of characteristics with their UUIDs
            - Current value of each readable characteristic
            - Error message for unreadable characteristics

        Use Cases:
            - Discover available characteristics on new devices
            - Debug connectivity issues
            - Verify device compatibility
            - Explore BMS capabilities

        Example:
            >>> request = Request("12:34:56:78:AA:CC")
            >>> await request.print_services()
            0000ffe0-0000-1000-8000-00805f9b34fb (Handle: 1): Unknown
                characteristic: $0000ffe1-0000-1000-8000-00805f9b34fb
                bytearray(b'...')
                characteristic: $0000ffe2-0000-1000-8000-00805f9b34fb
                Error: Characteristic not readable
        """
        async with BleakClient(
            self.bluetooth_device_mac, timeout=self.bluetooth_timeout
        ) as client:
            if self.pair:
                self.logger.info("Pairing %s...", self.bluetooth_device_mac)
                await client.pair()
            await self.parse_services(client, client.services)

        self.logger.info("Disconnecting %s...", self.bluetooth_device_mac)
        if self.pair:
            await client.unpair()
        await client.disconnect()
        self.logger.info("Disconnected %s", self.bluetooth_device_mac)

    async def parse_services(
        self, client: BleakClient, services
    ) -> None:
        """
        Parse and print GATT services and their characteristics.

        Iterates through all BLE services and characteristics, printing
        their information and attempting to read values. This is a helper
        method called by print_services().

        Args:
            client (BleakClient): Active Bleak client connection to the device.
                Must be connected before calling this method.
            services: Iterable of BLE services from client.services.
                Each service contains characteristics accessible via iteration.

        Returns:
            None: Information is printed to stdout.

        Output Details:
            - Service line: Shows service UUID and handle
            - Characteristic line: Shows characteristic UUID with $ prefix
            - Value line: Shows raw bytearray data if readable
            - Error line: Shows exception message if read fails

        Note:
            Some characteristics are write-only or require pairing to read.
            Errors reading individual characteristics do not stop enumeration;
            the method continues with remaining characteristics.

        Example:
            >>> async with BleakClient(mac) as client:
            ...     await request.parse_services(client, client.services)
        """
        for service in services:
            print(service)
            for charc in service.characteristics:
                print(f"\tcharacteristic: ${charc}")
                try:
                    result = await client.read_gatt_char(charc)
                    print(f"\t{result}")
                    ## print("Model Number: {0}".format("".join(map(chr, model_number))))
                except Exception as e:
                    print(f"\tError: {e}")

    def _set_callback(self, callback_func: Callable) -> None:
        """
        Set the callback function for the next data reception.

        Internal method to register a callback that will be invoked when
        data is received via BLE notification. Called automatically by
        send() and bulk_send() before sending each command.

        Args:
            callback_func (Callable): Function to call with received data.
                Signature: callback_func(data: bytearray) -> None

        Returns:
            None

        Note:
            This is an internal method. Prefer using send() or bulk_send()
            which handle callback registration automatically.
        """
        self.callback_func = callback_func

    def _create_command(self, command: str) -> bytearray:
        """
        Convert a hex string command to a bytearray for BLE transmission.

        Parses a space-separated string of hexadecimal bytes and converts
        it to a bytearray suitable for writing to a BLE characteristic.

        Args:
            command (str): Space-separated hex string. Each byte is
                represented as two hex digits (uppercase or lowercase).
                Example: "00 00 04 01 13 55 AA 17"

        Returns:
            bytearray: Binary command data ready for BLE transmission.
                The returned bytearray has one byte per hex pair in
                the input string.

        Conversion:
            "00 00 04 01 13 55 AA 17" -> bytearray([0, 0, 4, 1, 19, 85, 170, 23])

        Raises:
            ValueError: If the string contains invalid hex digits.

        Example:
            >>> cmd = request._create_command("00 00 04 01 13 55 AA 17")
            >>> print(cmd.hex())
            0000040113550aa17
            >>> print(list(cmd))
            [0, 0, 4, 1, 19, 85, 170, 23]
        """
        command_bytes = [int(el, 16) for el in command.split(" ")]
        message_bytes = bytearray(command_bytes)

        return message_bytes

    async def _data_callback(
        self, sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """
        Internal callback handler for BLE characteristic notifications.

        This method is registered with Bleak as the notification handler.
        When the BMS sends a response, this method receives it and forwards
        the data to the currently registered callback function.

        Args:
            sender (BleakGATTCharacteristic): The characteristic that sent
                the notification. Contains UUID and handle information.
            data (bytearray): Raw data received from the BMS. This is the
                complete response packet including headers and checksum.

        Returns:
            None: Data is forwarded to self.callback_func.

        Logging:
            When logger is at INFO level or below, logs:
            - The name of the callback function being invoked
            - The characteristic ID that sent the data
            - The raw data bytes in hex format

        Flow:
            1. Receives notification from BLE stack
            2. Logs the callback details
            3. Invokes self.callback_func with the raw data
            4. Callback function parses and stores the data

        Note:
            The callback_func must be set before starting notifications.
            This is handled automatically by send() and bulk_send().
        """
        self.logger.info(
            "Function: %s\n characteristic_id: %s\n Raw data: %s",
            self.callback_func.__name__,
            sender,
            data,
        )
        self.callback_func(data)
