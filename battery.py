"""
Battery Information Module for PowerQueen LiFePO4 BMS.

This module provides the BatteryInfo class for reading and parsing Battery Management
System (BMS) data from PowerQueen LiFePO4 batteries via Bluetooth Low Energy (BLE).
The module handles communication with the battery's BMS, parses the raw data responses,
and provides structured access to battery metrics.

Protocol Overview:
    The BMS communication uses a custom binary protocol over BLE. Commands are sent
    as 8-byte hex sequences to the BMS characteristic (0000FFE1-0000-1000-8000-00805F9B34FB).
    The BMS responds with variable-length data packets containing battery metrics.
    Each packet ends with a CRC checksum byte for data integrity verification.

Command Structure:
    - Bytes 0-1: Header (00 00)
    - Byte 2: Packet length
    - Byte 3: Command type (01 for requests)
    - Byte 4: Command ID (10=SN, 13=battery info, 16=version)
    - Bytes 5-6: Magic bytes (55 AA)
    - Byte 7: Checksum

Response Data Mapping (Battery Info - Command 0x13):
    - Bytes 8-11: Pack voltage (mV, little-endian, reversed)
    - Bytes 12-15: Voltage reading (mV, little-endian, reversed)
    - Bytes 16-47: Individual cell voltages (2 bytes each, up to 16 cells)
    - Bytes 48-51: Current (mA, signed, little-endian, reversed)
    - Bytes 52-53: Cell temperature (°C, signed)
    - Bytes 54-55: MOSFET temperature (°C, signed)
    - Bytes 62-63: Remaining capacity (Ah * 100)
    - Bytes 64-65: Factory capacity (Ah * 100)
    - Bytes 68-71: Heat status flags
    - Bytes 76-79: Protection state flags
    - Bytes 80-83: Failure state flags
    - Bytes 84-87: Equilibrium/balancing state
    - Bytes 88-89: Battery state (0=Idle, 1=Charging, 2=Discharging, 4=Full)
    - Bytes 90-91: State of Charge (SOC %)
    - Bytes 92-95: State of Health (SOH)
    - Bytes 96-99: Discharge cycle count
    - Bytes 100-103: Total discharge Ah count

Example Usage:
    >>> from battery import BatteryInfo
    >>> battery = BatteryInfo("12:34:56:78:AA:CC", timeout=5)
    >>> battery.read_bms()
    >>> print(battery.get_json())
    >>> print(f"Battery at {battery.SOC}%")

Note:
    This is a read-only library. It cannot modify battery settings or parameters.
"""

import json
import asyncio
import logging
from typing import Callable, Any
from bleak import BleakError
from request import Request


class BatteryInfo:
    """
    Main class for parsing BMS information from PowerQueen LiFePO4 batteries.

    This class handles the complete workflow of reading battery data via Bluetooth:
    connecting to the device, sending BMS commands, receiving responses, parsing
    the binary data, and providing structured access to battery metrics.

    The class supports both real-time battery metrics (voltage, current, temperature,
    state of charge) and historical data (discharge counts, manufacturing info).

    Attributes:
        packVoltage (int | None): Total pack voltage in millivolts (mV).
            This represents the sum of all cell voltages.
        voltage (int | None): Battery voltage reading in millivolts (mV).
            May differ slightly from packVoltage due to measurement timing.
        batteryPack (dict): Dictionary mapping cell numbers to voltages.
            Keys are cell numbers (1-16), values are voltages in Volts.
            Example: {1: 3.28, 2: 3.29, 3: 3.28, 4: 3.29}
        current (float | None): Current flow in Amperes.
            Positive values indicate charging, negative values indicate discharging.
        watt (float | None): Calculated power in Watts (voltage * current / 1000000).
            Positive for charging power, negative for discharge power.
        remainAh (float | None): Remaining capacity in Amp-hours (Ah).
        factoryAh (float | None): Factory-rated capacity in Amp-hours (Ah).
        cellTemperature (int | None): Cell temperature in degrees Celsius.
            Measured by internal temperature sensor near the cells.
        mosfetTemperature (int | None): MOSFET temperature in degrees Celsius.
            Measured at the power switching components.
        heat (str | None): Heat status flags as hexadecimal string.
            Contains self-heating control status and discharge switch state.
        protectState (str | None): Protection status flags as hexadecimal string.
            Indicates active protection features (over-voltage, under-voltage, etc.).
        failureState (list | None): List of failure state bytes.
            Non-zero values indicate active faults.
        equilibriumState (int | None): Cell balancing/equilibrium state.
            Non-zero indicates active cell balancing.
        batteryState (int | None): Current battery operational state.
            0 = Idle, 1 = Charging, 2 = Discharging, 4 = Full Charge.
        SOC (int | None): State of Charge as percentage (0-100).
        SOH (int | None): State of Health as percentage.
        dischargeSwitchState (int | None): Bluetooth-controlled discharge switch.
            1 = enabled (discharge allowed), 0 = disabled.
        dischargesCount (int | None): Total number of discharge cycles.
        dischargesAHCount (int | None): Cumulative Amp-hours discharged.
        firmwareVersion (str | None): BMS firmware version (e.g., "1.4.0").
        manfactureDate (str | None): Manufacturing date in YYYY-M-D format.
        hardwareVersion (str | None): Hardware version string.
        battery_status (str | None): Human-readable battery status.
            One of: "Charging", "Discharging", "Standby", "Full Charge".
        balance_status (str | None): Human-readable cell balancing status.
        cell_status (str | None): Human-readable cell health status.
        bms_status (str | None): Human-readable BMS status.
        heat_status (str | None): Human-readable self-heating status.
        error_code (int): Error code from last operation. 0 = success.
        error_message (str | None): Human-readable error message if error_code != 0.

    Class Attributes:
        BMS_CHARACTERISTIC_ID (str): UUID for BMS data GATT characteristic.
        SN_CHARACTERISTIC_ID (str): UUID for serial number GATT characteristic.
        pq_commands (dict): Dictionary of command name to hex command string.
        ERROR_GENERIC (int): Error code 1 - Generic/unknown error.
        ERROR_TIMEOUT (int): Error code 2 - Bluetooth timeout.
        ERROR_BLEAK (int): Error code 4 - Bleak library error.
        ERROR_CHECKSUM (int): Error code 6 - CRC checksum mismatch.

    Example:
        >>> battery = BatteryInfo("12:34:56:78:AA:CC", pair_device=True, timeout=5)
        >>> battery.read_bms()
        >>> if battery.error_code == 0:
        ...     print(f"Battery: {battery.SOC}%, {battery.voltage/1000}V")
        ...     print(f"Current: {battery.current}A, Power: {battery.watt}W")
        ...     print(f"Cells: {battery.batteryPack}")
        ... else:
        ...     print(f"Error: {battery.error_message}")
    """

    BMS_CHARACTERISTIC_ID = (
        "0000FFE1-0000-1000-8000-00805F9B34FB"  ## Bluetooth characteristic for BMS data
    )
    SN_CHARACTERISTIC_ID = "0000FFE2-0000-1000-8000-00805F9B34FB"  ## characteristic for reading serial number (seems not implemented)

    pq_commands = {
        "GET_VERSION": "00 00 04 01 16 55 AA 1A",
        "GET_BATTERY_INFO": "00 00 04 01 13 55 AA 17",
        ## Native application does not read internal serial number.
        ## On version 1.1.4 used SN from QR code, during adding battery
        "SERIAL_NUMBER": "00 00 04 01 10 55 AA 14",
    }

    ERROR_GENERIC = 1
    ERROR_TIMEOUT = 2
    ERROR_BLEAK = 4
    ERROR_CHECKSUM = 6

    def __init__(
        self,
        bluetooth_device_mac: str,
        pair_device: bool = False,
        timeout: int = 2,
        logger=None,
    ):
        """
        Initialize a BatteryInfo instance for reading BMS data.

        Creates a new BatteryInfo object configured to communicate with a specific
        PowerQueen LiFePO4 battery via Bluetooth. The instance initializes all
        battery metric attributes to None, which will be populated after calling
        read_bms().

        Args:
            bluetooth_device_mac (str): Bluetooth MAC address of the battery.
                Must be in standard format: "XX:XX:XX:XX:XX:XX" where XX are
                hexadecimal bytes. Example: "12:34:56:78:AA:CC".
            pair_device (bool, optional): Whether to pair with the device before
                communication. Set to True if the battery requires Bluetooth pairing.
                Pairing may be required on some systems or for first-time connections.
                Defaults to False.
            timeout (int, optional): Timeout in seconds for Bluetooth communication.
                This affects connection establishment and data transfer operations.
                Increase for unreliable connections or distant batteries.
                Defaults to 2 seconds.
            logger (logging.Logger | None, optional): Python logger instance for
                debug output. If None, creates a module-level logger. Pass a custom
                logger to integrate with your application's logging infrastructure.

        Raises:
            No exceptions are raised during initialization. Connection errors
            occur when calling read_bms().

        Note:
            The timeout value should be adjusted based on:
            - Bluetooth signal strength (increase for weak signals)
            - System load (increase on busy systems)
            - Battery response time (some batteries respond slower)

        Example:
            >>> # Basic initialization
            >>> battery = BatteryInfo("12:34:56:78:AA:CC")
            >>>
            >>> # With pairing and extended timeout
            >>> battery = BatteryInfo(
            ...     "12:34:56:78:AA:CC",
            ...     pair_device=True,
            ...     timeout=10
            ... )
            >>>
            >>> # With custom logger
            >>> import logging
            >>> logger = logging.getLogger("my_app.battery")
            >>> battery = BatteryInfo("12:34:56:78:AA:CC", logger=logger)
        """
        self.packVoltage = None
        self.voltage = None
        self.batteryPack: dict = {}
        self.current = None
        self.watt = None
        self.remainAh = None
        self.factoryAh = None
        self.cellTemperature = None
        self.mosfetTemperature = None
        self.heat = None
        self.protectState = None
        self.failureState = None
        self.equilibriumState = None
        self.batteryState = None
        self.SOC = None
        self.SOH = None
        self.dischargeSwitchState = None
        self.dischargesCount = None
        self.dischargesAHCount = None

        self.firmwareVersion = None
        self.manfactureDate = None
        self.hardwareVersion = None

        ## Human readable battery status
        self.battery_status = None
        self.balance_status = None
        self.cell_status = None
        self.bms_status = None
        self.heat_status = None

        ## Error handling
        self.error_code = 0
        self.error_message = None

        self._debug = False

        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(__name__)

        self._request = Request(
            bluetooth_device_mac,
            pair_device=pair_device,
            timeout=timeout,
            logger=self._logger,
        )

    @staticmethod
    def _check_crc(func: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorator that verifies CRC checksum before executing parser methods.

        This decorator wraps parser methods (parse_battery_info, parse_version)
        to validate data integrity before parsing. The BMS protocol appends a
        checksum byte to each response packet for error detection.

        CRC Algorithm:
            The checksum is calculated as the sum of all data bytes (excluding
            the checksum byte itself), masked to 8 bits (& 0xFF). This is a
            simple additive checksum, not a true CRC polynomial.

        Args:
            func (Callable[..., Any]): The parser method to wrap. Must accept
                (self, data: bytearray) as arguments, where data includes the
                checksum byte as the last byte.

        Returns:
            Callable[..., Any]: Wrapped function that validates CRC before
                executing the original parser. The original function is always
                called, but error_code is set on checksum mismatch.

        Side Effects:
            On checksum mismatch:
            - Sets self.error_code to ERROR_CHECKSUM (6)
            - Sets self.error_message with debug information
            - Logs the mismatch via self.get_logger()

        Note:
            The decorated function is always executed even on CRC failure.
            This allows partial data recovery, though data should be treated
            as potentially corrupted when error_code == ERROR_CHECKSUM.

        Example:
            >>> @_check_crc
            ... def parse_data(self, data):
            ...     # CRC is verified before this code runs
            ...     self.value = data[0]
        """
        def wrapper(*args, **kwargs):
            self_instance = args[0]
            raw_data = args[1]
            crc_packet = int.from_bytes(raw_data[-1:], byteorder="little")
            data_crc = self_instance.crc_sum(raw_data[:-1])
            debug_message = f"of {func.__name__}: data:{data_crc}, crc-packet:{crc_packet}"
            self_instance.get_logger().info("Checksum %s", debug_message)

            if crc_packet != data_crc:
                self_instance.error = self_instance.ERROR_CHECKSUM
                self_instance.error_message = f"Error: checksum missmatch {debug_message}"

            result = func(*args, **kwargs)
            return result
        return wrapper

    def get_request(self) -> "Request":
        """
        Return the internal Bluetooth Request instance.

        Provides access to the underlying Request object for advanced operations
        such as listing available GATT services or sending custom commands.

        Returns:
            Request: The Request instance configured with this battery's
                MAC address, pairing settings, and timeout values.

        Use Cases:
            - List all Bluetooth services: request.print_services()
            - Debug connectivity issues
            - Extend functionality with custom commands

        Example:
            >>> battery = BatteryInfo("12:34:56:78:AA:CC")
            >>> request = battery.get_request()
            >>> import asyncio
            >>> asyncio.run(request.print_services())
        """
        return self._request

    def read_bms(self) -> None:
        """
        Read complete BMS information from the battery via Bluetooth.

        This is the main method for retrieving battery data. It establishes a
        Bluetooth connection, sends version and battery info commands, receives
        the responses, and parses them into the instance attributes.

        The method executes two BMS commands in sequence:
        1. GET_VERSION (0x16): Retrieves firmware version, manufacturing date,
           and hardware version.
        2. GET_BATTERY_INFO (0x13): Retrieves all real-time battery metrics
           including voltages, current, temperatures, and states.

        After successful completion, all battery metric attributes are populated
        and can be accessed directly or via get_json().

        Returns:
            None: Results are stored in instance attributes. Check error_code
                to determine if the operation succeeded.

        Raises:
            BleakError: Only raised if debug mode is enabled (set_debug(True)).
                Indicates Bluetooth communication failure.
            TimeoutError: Only raised if debug mode is enabled.
                Indicates the Bluetooth operation timed out.
            Exception: Only raised if debug mode is enabled.
                Indicates other unexpected errors.

        Error Handling:
            In normal mode (debug=False), exceptions are caught and stored:
            - error_code: Set to ERROR_BLEAK (4), ERROR_TIMEOUT (2), or
                ERROR_GENERIC (1) based on the exception type.
            - error_message: Set to a descriptive error string.

        Side Effects:
            - Establishes and closes a Bluetooth connection
            - Populates all battery metric instance attributes
            - Sets error_code and error_message on failure

        Note:
            This method blocks until completion. For async usage, access
            the Request instance directly via get_request().

        Example:
            >>> battery = BatteryInfo("12:34:56:78:AA:CC", timeout=5)
            >>> battery.read_bms()
            >>> if battery.error_code == 0:
            ...     print(f"Battery OK: {battery.SOC}%")
            ...     print(f"Voltage: {battery.voltage / 1000}V")
            ...     print(f"Current: {battery.current}A")
            ... elif battery.error_code == battery.ERROR_TIMEOUT:
            ...     print("Connection timed out - check Bluetooth range")
            ... elif battery.error_code == battery.ERROR_BLEAK:
            ...     print(f"Bluetooth error: {battery.error_message}")
            ... else:
            ...     print(f"Error: {battery.error_message}")
        """
        try:
            asyncio.run(
                self._request.bulk_send(
                    characteristic_id=self.BMS_CHARACTERISTIC_ID,
                    commands_parsers={
                        self.pq_commands["GET_VERSION"]: self.parse_version,
                        self.pq_commands["GET_BATTERY_INFO"]: self.parse_battery_info,
                        ## Internal SN not used or not implemented
                        ## self.pq_commands["SERIAL_NUMBER"]: self.parse_serial_number
                    },
                )
            )
        except BleakError as e:
            self.error_code = self.ERROR_BLEAK
            self.error_message = f"{e.__class__.__name__}: {e}"
            if self._debug:
                raise
        except TimeoutError as e:
            self.error_code = self.ERROR_TIMEOUT
            self.error_message = f"{e.__class__.__name__}: {e}"
            if self._debug:
                raise
        except Exception as e:
            self.error_code = self.ERROR_GENERIC
            self.error_message = f"{e}"
            if self._debug:
                raise

    def get_json(self) -> str:
        """
        Return complete battery data as a formatted JSON string.

        Serializes all battery metrics and status information into a JSON
        string for logging, storage, API responses, or debugging. Internal
        attributes (logger, request, debug flag) are excluded from output.

        Returns:
            str: JSON-formatted string containing all battery data.
                The JSON is pretty-printed with 4-space indentation.

        JSON Structure:
            The returned JSON includes these key sections:
            - Electrical metrics: packVoltage, voltage, current, watt
            - Cell data: batteryPack (dict of cell voltages)
            - Capacity: remainAh, factoryAh, SOC, SOH
            - Temperature: cellTemperature, mosfetTemperature
            - States: batteryState, protectState, failureState, heat
            - Counters: dischargesCount, dischargesAHCount
            - Device info: firmwareVersion, hardwareVersion, manfactureDate
            - Human-readable: battery_status, balance_status, etc.
            - Error info: error_code, error_message

        Note:
            Values are None until read_bms() is called successfully.
            The returned string can be parsed back with json.loads().

        Warning:
            This method modifies self.__dict__ by deleting internal keys.
            Multiple calls in succession will work, but internal attributes
            remain removed from the dict.

        Example:
            >>> battery = BatteryInfo("12:34:56:78:AA:CC")
            >>> battery.read_bms()
            >>> json_data = battery.get_json()
            >>> print(json_data)
            {
                "packVoltage": 13280,
                "voltage": 13275,
                "batteryPack": {
                    "1": 3.32,
                    "2": 3.32,
                    ...
                },
                "current": -2.5,
                "watt": -33.19,
                ...
            }
            >>>
            >>> # Parse back to dict
            >>> import json
            >>> data = json.loads(json_data)
            >>> print(data["SOC"])
            85
        """
        state = self.__dict__
        del state["_logger"]
        del state["_request"]
        del state["_debug"]

        return json.dumps(
            state, default=lambda o: o.__dict__, sort_keys=False, indent=4
        )

    @_check_crc
    def parse_battery_info(self, data: bytearray) -> None:
        """
        Parse complete battery information from raw BMS response data.

        This method decodes the binary response from the GET_BATTERY_INFO (0x13)
        command and populates all battery metric instance attributes. It handles
        the complex byte ordering (little-endian with byte reversal) used by the
        BMS protocol.

        Args:
            data (bytearray): Raw response data from BMS, including header bytes
                and trailing CRC checksum. Expected length is approximately 105
                bytes for a complete response.

        Returns:
            None: Results are stored directly in instance attributes.

        Data Extraction Details:
            All multi-byte values use reversed little-endian byte order.
            The [::-1] slice reverses bytes before conversion.

            Voltage Extraction (bytes 8-47):
            - Pack voltage: bytes 8-11, value in millivolts
            - Voltage: bytes 12-15, value in millivolts
            - Cell voltages: bytes 16-47, 2 bytes per cell, up to 16 cells
              Cells with 0 voltage are skipped (not present in battery)

            Current & Power (bytes 48-51):
            - Current is signed (negative = discharging, positive = charging)
            - Value in milliamps, converted to Amps
            - Watt calculated as: (voltage_mV * current_mA) / 1,000,000

            Temperature (bytes 52-55):
            - Cell and MOSFET temperatures in Celsius
            - Signed integers for sub-zero temperatures

            Capacity (bytes 62-65):
            - Remaining and factory Ah, stored as value * 100
            - Divided by 100 for actual Ah values

            State Flags (bytes 68-96):
            - Heat status (68-71): Self-heating and discharge switch state
            - Protection state (76-79): Active protections as hex
            - Failure state (80-83): Fault indicators as list
            - Equilibrium state (84-87): Cell balancing activity
            - Battery state (88-89): Operational mode
            - SOC (90-91): State of Charge percentage
            - SOH (92-95): State of Health percentage

            Counters (bytes 96-103):
            - Discharge cycle count
            - Cumulative discharge Ah

        Discharge Switch State Logic:
            The discharge switch state is extracted from the heat status:
            - If heat[6] (7th hex digit) >= 8: switch is OFF (0)
            - Otherwise: switch is ON (1)
            This represents the Bluetooth-controllable load disconnect.

        Human-Readable Status Generation:
            After parsing raw data, the method generates human-readable
            status strings:
            - battery_status: From get_battery_status()
            - balance_status: Based on equilibriumState
            - cell_status: Based on failureState
            - heat_status: Based on heat[7]

        Example:
            >>> # Called internally by read_bms(), not typically called directly
            >>> battery._check_crc(battery.parse_battery_info)(raw_data)
        """
        self.packVoltage = int.from_bytes(data[8:12][::-1], byteorder="big")
        self.voltage = int.from_bytes(data[12:16][::-1], byteorder="big")

        batPack = data[16:48]
        for key, dt in enumerate(batPack):
            if key % 2:
                continue

            cellVoltage = int.from_bytes([batPack[key + 1], dt], byteorder="big")
            if not cellVoltage:
                continue
            cell = int(key / 2 + 1)
            self.batteryPack[cell] = cellVoltage / 1000

        ## Load \ Unload current A
        current = int.from_bytes(data[48:52][::-1], byteorder="big", signed=True)
        self.current = round(current / 1000, 2)

        ## Calculated load \ unload Watt
        watt = round((self.voltage * +current) / 10000, 1) / 100
        self.watt = round(watt, 2)

        ## Remain Ah
        remainAh = int.from_bytes(data[62:64][::-1], byteorder="big")
        self.remainAh = round(remainAh / 100, 2)

        ## Factory Ah
        fccAh = int.from_bytes(data[64:66][::-1], byteorder="big")
        self.factoryAh = round(fccAh / 100, 2)

        ## Temperature
        s = pow(2, 16)
        self.cellTemperature = int.from_bytes(
            data[52:54][::-1], byteorder="big", signed=True
        )
        self.mosfetTemperature = int.from_bytes(
            data[54:56][::-1], byteorder="big", signed=True
        )

        self.heat = data[68:72][::-1].hex()

        ## Discharge switch state
        ## State of internal bluetooth controlled discharge switch
        if int(self.heat[6]) >= 8:
            self.dischargeSwitchState = 0
        else:
            self.dischargeSwitchState = 1

        self.protectState = data[76:80][::-1].hex()
        self.failureState = list(data[80:84][::-1])
        self.equilibriumState = int.from_bytes(data[84:88][::-1], byteorder="big")

        ## Idle - 0 ??
        ## Charging - 1
        ## Discharging - 2
        ## Full Charge - 4
        self.batteryState = int.from_bytes(data[88:90][::-1], byteorder="big")

        ## State of charge (Charge level)
        self.SOC = int.from_bytes(data[90:92][::-1], byteorder="big")

        ## State of Health ??
        self.SOH = int.from_bytes(data[92:96][::-1], byteorder="big")

        self.dischargesCount = int.from_bytes(data[96:100][::-1], byteorder="big")

        ## Discharge AH times
        self.dischargesAHCount = int.from_bytes(data[100:104][::-1], byteorder="big")

        ## Additional human readable statuses
        self.battery_status = self.get_battery_status()

        if self.equilibriumState > 0:
            self.balance_status = (
                "Battery cells are being balanced for better performance."
            )
        else:
            self.balance_status = "All cells are well-balanced."

        if self.failureState[0] > 0 or self.failureState[1] > 0:
            self.cell_status = "Fault alert! There may be a problem with cell."
        else:
            self.cell_status = "Battery is in optimal working condition."

        if int(self.heat[7]) == 2:
            self.heat_status = "Self-heating is on"
        else:
            self.heat_status = "Self-heating is off"

    @_check_crc
    def parse_version(self, data: bytearray) -> None:
        """
        Parse firmware and hardware version information from raw BMS response.

        This method decodes the binary response from the GET_VERSION (0x16)
        command and populates version-related instance attributes. The version
        data contains firmware revision, manufacturing date, and hardware
        identification.

        Args:
            data (bytearray): Raw response data from BMS version command,
                including 8-byte header and trailing CRC checksum.

        Returns:
            None: Results are stored in instance attributes:
                - firmwareVersion (str): e.g., "1.4.0"
                - manfactureDate (str): e.g., "2023-5-15"
                - hardwareVersion (str): ASCII hardware identifier

        Data Layout (after 8-byte header):
            Bytes 0-1: Major version number (2 bytes, reversed little-endian)
            Bytes 2-3: Minor version number (2 bytes, reversed little-endian)
            Bytes 4-5: Patch version number (2 bytes, reversed little-endian)
            Bytes 6-7: Manufacturing year (2 bytes, reversed little-endian)
            Byte 8: Manufacturing month (1 byte)
            Byte 9: Manufacturing day (1 byte)

        Firmware Version Format:
            Constructed as "MAJOR.MINOR.PATCH" (e.g., "1.4.0").
            Each component is a 16-bit integer.

        Manufacturing Date Format:
            Constructed as "YYYY-M-D" (e.g., "2023-5-15").
            Note: Month and day are not zero-padded.

        Hardware Version Extraction:
            The hardware version is extracted by reading every other byte
            (starting from byte 0) and converting printable ASCII characters
            (codes 32-126) to a string. This handles the interleaved storage
            format used by the BMS.

        Example:
            >>> # Called internally by read_bms()
            >>> battery.parse_version(version_data)
            >>> print(f"Firmware: {battery.firmwareVersion}")
            Firmware: 1.4.0
            >>> print(f"Manufactured: {battery.manfactureDate}")
            Manufactured: 2023-5-15
        """
        start = data[8:]
        self.firmwareVersion = (
            f"{int.from_bytes(start[0:2][::-1], byteorder='big')}"
            f".{int.from_bytes(start[2:4][::-1], byteorder='big')}"
            f".{int.from_bytes(start[4:6][::-1], byteorder='big')}"
        )
        self.manfactureDate = (
            f"{int.from_bytes(start[6:8][::-1], byteorder='big')}"
            f"-{int(start[8])}"
            f"-{int(start[9])}"
        )

        vers = ""
        # rawV = data[0:8]
        for ver in start[0::2]:
            if 32 <= ver <= 126:
                vers += chr(ver)

        self.hardwareVersion = vers

    def parse_serial_number(self, data: bytearray) -> None:
        """
        Parse battery serial number from raw BMS response.

        This method is intended to decode the serial number response from
        the SERIAL_NUMBER (0x10) command. However, this functionality
        appears to be unimplemented in the BMS firmware.

        Args:
            data (bytearray): Raw response data from BMS serial number command.

        Returns:
            None: Currently only prints raw data to console.

        Note:
            The PowerQueen mobile application (as of version 1.1.4) does not
            read the internal serial number from the BMS. Instead, it uses
            the serial number from the QR code scanned during battery setup.
            This suggests the BMS may not support serial number retrieval.

        Warning:
            This method is not actively used and may not produce meaningful
            results. It is preserved for potential future compatibility if
            PowerQueen implements this feature in newer BMS firmware versions.

        Example:
            >>> # Not typically used - command may not return valid data
            >>> battery.parse_serial_number(sn_data)
            Serial number: $bytearray(...)
        """
        print(f"Serial number: ${data}")

    def get_battery_status(self) -> str:
        """
        Determine and return a human-readable battery status string.

        Analyzes the current flow direction and state of charge to determine
        the battery's operational status. This provides a simple, user-friendly
        description of what the battery is currently doing.

        Returns:
            str: One of the following status strings:
                - "Standby": Battery is idle (current = 0)
                - "Charging": Battery is receiving charge (current > 0)
                - "Discharging": Battery is supplying power (current < 0)
                - "Full Charge": Battery is fully charged (SOC >= 100 or
                  batteryState == 4)

        Status Priority:
            "Full Charge" takes precedence over other statuses. A battery
            can show "Full Charge" even if current is non-zero (e.g., during
            float charging or when just reaching full capacity).

        Dependencies:
            Requires self.current and self.SOC to be populated (via read_bms()).
            Returns empty string if called before read_bms().

        Example:
            >>> battery.read_bms()
            >>> status = battery.get_battery_status()
            >>> print(f"Battery is: {status}")
            Battery is: Discharging
        """
        status = ""
        if self.current == 0:
            status = "Standby"
        elif self.current > 0:
            status = "Charging"
        elif self.current < 0:
            status = "Discharging"

        if self.SOC >= 100 or self.batteryState == 4:
            status = "Full Charge"

        return status

    def crc_sum(self, raw_data: bytearray) -> int:
        """
        Calculate the CRC checksum for data verification.

        Computes a simple 8-bit additive checksum by summing all bytes
        in the data and masking to the lowest 8 bits. This matches the
        checksum algorithm used by the PowerQueen BMS.

        Args:
            raw_data (bytearray): The data bytes to checksum. Should include
                all bytes except the trailing checksum byte.

        Returns:
            int: 8-bit checksum value (0-255). Compare this with the checksum
                byte in the BMS response to verify data integrity.

        Algorithm:
            checksum = sum(all_bytes) & 0xFF

            This is a simple additive checksum, not a polynomial CRC.
            It provides basic error detection for transmission errors
            but is not as robust as true CRC algorithms.

        Example:
            >>> data = bytearray([0x00, 0x00, 0x04, 0x01, 0x13, 0x55, 0xAA])
            >>> checksum = battery.crc_sum(data)
            >>> print(f"Checksum: 0x{checksum:02X}")
            Checksum: 0x17
        """
        return sum(raw_data) & 0xFF

    def get_logger(self) -> logging.Logger:
        """
        Return the logger instance used by this BatteryInfo object.

        Provides access to the internal logger for external logging
        configuration or for use in custom extensions.

        Returns:
            logging.Logger: The logger instance. Either the custom logger
                passed to __init__(), or a module-level logger created
                automatically.

        Example:
            >>> battery = BatteryInfo("12:34:56:78:AA:CC")
            >>> logger = battery.get_logger()
            >>> logger.setLevel(logging.DEBUG)
            >>> logger.info("Custom log message")
        """
        return self._logger

    def set_debug(self, debug: bool) -> None:
        """
        Enable or disable debug mode for exception handling.

        When debug mode is enabled, exceptions during read_bms() are raised
        instead of being caught and stored in error_code/error_message.
        This is useful for development and troubleshooting.

        Args:
            debug (bool): True to enable debug mode (exceptions are raised),
                False to disable (exceptions are caught and stored).

        Returns:
            None

        Behavior by Mode:
            debug=False (default):
                - Exceptions are caught in read_bms()
                - error_code is set to appropriate error constant
                - error_message contains exception details
                - Execution continues normally

            debug=True:
                - Exceptions propagate from read_bms()
                - Full stack traces are available
                - Useful with debuggers and testing frameworks

        Example:
            >>> battery = BatteryInfo("12:34:56:78:AA:CC")
            >>> battery.set_debug(True)
            >>> try:
            ...     battery.read_bms()
            ... except TimeoutError as e:
            ...     print(f"Timeout details: {e}")
            ...     # Full stack trace available for debugging
        """
        self._debug = debug
