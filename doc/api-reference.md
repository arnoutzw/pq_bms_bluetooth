# API Reference

Complete API documentation for the PowerQueen LiFePO4 BMS Bluetooth library.

## Module: battery

The main module for BMS data parsing and battery information management.

### Class: BatteryInfo

Main class for parsing BMS information from PowerQueen LiFePO4 batteries.

```python
from battery import BatteryInfo
```

#### Constructor

```python
BatteryInfo(
    bluetooth_device_mac: str,
    pair_device: bool = False,
    timeout: int = 2,
    logger: logging.Logger = None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bluetooth_device_mac` | str | required | Bluetooth MAC address (`XX:XX:XX:XX:XX:XX`) |
| `pair_device` | bool | `False` | Pair with device before communication |
| `timeout` | int | `2` | Bluetooth timeout in seconds |
| `logger` | Logger | `None` | Custom logger instance |

**Example:**

```python
# Basic initialization
battery = BatteryInfo("12:34:56:78:AA:CC")

# With all options
import logging
logger = logging.getLogger("my_app")
battery = BatteryInfo(
    "12:34:56:78:AA:CC",
    pair_device=True,
    timeout=10,
    logger=logger
)
```

---

#### Instance Attributes

##### Electrical Metrics

| Attribute | Type | Description |
|-----------|------|-------------|
| `packVoltage` | int \| None | Total pack voltage in millivolts |
| `voltage` | int \| None | Voltage reading in millivolts |
| `batteryPack` | dict | Cell voltages: `{cell_number: voltage_in_V}` |
| `current` | float \| None | Current in Amperes (+ charging, - discharging) |
| `watt` | float \| None | Calculated power in Watts |

##### Capacity

| Attribute | Type | Description |
|-----------|------|-------------|
| `remainAh` | float \| None | Remaining capacity in Ah |
| `factoryAh` | float \| None | Factory rated capacity in Ah |
| `SOC` | int \| None | State of Charge (0-100%) |
| `SOH` | int \| None | State of Health percentage |

##### Temperature

| Attribute | Type | Description |
|-----------|------|-------------|
| `cellTemperature` | int \| None | Cell temperature in °C |
| `mosfetTemperature` | int \| None | MOSFET temperature in °C |

##### State Flags

| Attribute | Type | Description |
|-----------|------|-------------|
| `batteryState` | int \| None | 0=Idle, 1=Charging, 2=Discharging, 4=Full |
| `heat` | str \| None | Heat status flags (hex string) |
| `protectState` | str \| None | Protection flags (hex string) |
| `failureState` | list \| None | Failure state bytes |
| `equilibriumState` | int \| None | Cell balancing state |
| `dischargeSwitchState` | int \| None | 1=enabled, 0=disabled |

##### Counters

| Attribute | Type | Description |
|-----------|------|-------------|
| `dischargesCount` | int \| None | Total discharge cycles |
| `dischargesAHCount` | int \| None | Cumulative Ah discharged |

##### Device Information

| Attribute | Type | Description |
|-----------|------|-------------|
| `firmwareVersion` | str \| None | BMS firmware version |
| `hardwareVersion` | str \| None | Hardware version string |
| `manfactureDate` | str \| None | Manufacturing date (YYYY-M-D) |

##### Human-Readable Status

| Attribute | Type | Description |
|-----------|------|-------------|
| `battery_status` | str \| None | "Charging", "Discharging", "Standby", "Full Charge" |
| `balance_status` | str \| None | Cell balancing status message |
| `cell_status` | str \| None | Cell health status message |
| `bms_status` | str \| None | BMS status message |
| `heat_status` | str \| None | Self-heating status message |

##### Error Information

| Attribute | Type | Description |
|-----------|------|-------------|
| `error_code` | int | Error code (0 = success) |
| `error_message` | str \| None | Error description |

---

#### Class Constants

```python
BatteryInfo.BMS_CHARACTERISTIC_ID = "0000FFE1-0000-1000-8000-00805F9B34FB"
BatteryInfo.SN_CHARACTERISTIC_ID = "0000FFE2-0000-1000-8000-00805F9B34FB"

BatteryInfo.ERROR_GENERIC = 1
BatteryInfo.ERROR_TIMEOUT = 2
BatteryInfo.ERROR_BLEAK = 4
BatteryInfo.ERROR_CHECKSUM = 6
```

---

#### Methods

##### read_bms()

Read complete BMS information from the battery via Bluetooth.

```python
def read_bms(self) -> None
```

**Returns:** None (results stored in instance attributes)

**Side Effects:**
- Establishes Bluetooth connection
- Populates all battery metric attributes
- Sets `error_code` and `error_message` on failure

**Example:**

```python
battery = BatteryInfo("12:34:56:78:AA:CC", timeout=5)
battery.read_bms()

if battery.error_code == 0:
    print(f"Battery: {battery.SOC}%")
else:
    print(f"Error: {battery.error_message}")
```

---

##### get_json()

Return complete battery data as a formatted JSON string.

```python
def get_json(self) -> str
```

**Returns:** JSON-formatted string with all battery data

**Example:**

```python
battery.read_bms()
json_data = battery.get_json()
print(json_data)

# Parse back to dict
import json
data = json.loads(json_data)
```

---

##### get_battery_status()

Return a human-readable battery status string.

```python
def get_battery_status(self) -> str
```

**Returns:** One of: "Standby", "Charging", "Discharging", "Full Charge"

**Example:**

```python
battery.read_bms()
status = battery.get_battery_status()
print(f"Battery is: {status}")
```

---

##### get_request()

Return the internal Bluetooth Request instance.

```python
def get_request(self) -> Request
```

**Returns:** The `Request` instance for advanced operations

**Example:**

```python
request = battery.get_request()
import asyncio
asyncio.run(request.print_services())
```

---

##### get_logger()

Return the logger instance.

```python
def get_logger(self) -> logging.Logger
```

**Returns:** The logger instance used by BatteryInfo

---

##### set_debug()

Enable or disable debug mode.

```python
def set_debug(self, debug: bool) -> None
```

**Parameters:**
- `debug`: True to raise exceptions, False to catch them

**Example:**

```python
battery.set_debug(True)
try:
    battery.read_bms()
except TimeoutError:
    print("Connection timed out")
```

---

##### crc_sum()

Calculate CRC checksum for data verification.

```python
def crc_sum(self, raw_data: bytearray) -> int
```

**Parameters:**
- `raw_data`: Bytes to checksum

**Returns:** 8-bit checksum value (0-255)

---

## Module: request

Bluetooth Low Energy request handler for BMS communication.

### Class: Request

```python
from request import Request
```

#### Constructor

```python
Request(
    bluetooth_device_mac: str,
    pair_device: bool = False,
    timeout: int = 2,
    logger: logging.Logger = None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bluetooth_device_mac` | str | required | Bluetooth MAC address |
| `pair_device` | bool | `False` | Pair before communication |
| `timeout` | int | `2` | Bluetooth timeout in seconds |
| `logger` | Logger | `None` | Custom logger instance |

---

#### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `bluetooth_device_mac` | str | Target device MAC address |
| `pair` | bool | Pairing enabled flag |
| `callback_func` | Callable | Current data callback |
| `bluetooth_timeout` | int | Operation timeout |
| `logger` | Logger | Logger instance |

---

#### Methods

##### send()

Send a single command to the BLE device.

```python
async def send(
    self,
    characteristic_id: str,
    command: str,
    callback_func: Callable
) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `characteristic_id` | str | GATT characteristic UUID |
| `command` | str | Hex command string (space-separated) |
| `callback_func` | Callable | Response handler function |

**Example:**

```python
async def handle_response(data):
    print(f"Received: {data.hex()}")

await request.send(
    "0000FFE1-0000-1000-8000-00805F9B34FB",
    "00 00 04 01 13 55 AA 17",
    handle_response
)
```

---

##### bulk_send()

Send multiple commands in sequence.

```python
async def bulk_send(
    self,
    characteristic_id: str,
    commands_parsers: dict
) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `characteristic_id` | str | GATT characteristic UUID |
| `commands_parsers` | dict | `{command_string: callback_function}` |

**Example:**

```python
commands = {
    "00 00 04 01 16 55 AA 1A": parse_version,
    "00 00 04 01 13 55 AA 17": parse_battery
}
await request.bulk_send(
    "0000FFE1-0000-1000-8000-00805F9B34FB",
    commands
)
```

---

##### print_services()

Discover and print all GATT services.

```python
async def print_services(self) -> None
```

**Example:**

```python
import asyncio
request = Request("12:34:56:78:AA:CC")
asyncio.run(request.print_services())
```

---

## Module: main

Command-line interface entry point.

### Function: commands()

Parse command-line arguments.

```python
def commands() -> argparse.Namespace
```

**Returns:** Namespace with parsed arguments

---

### Function: main()

Main CLI entry point.

```python
def main() -> None
```

**Exit Codes:**
- 0: Success
- 1: Generic error
- 2: Timeout error
- 4: Bleak error
- 6: Checksum error

---

## Complete Example

```python
import logging
from battery import BatteryInfo

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("battery_monitor")

# Create battery instance
battery = BatteryInfo(
    bluetooth_device_mac="12:34:56:78:AA:CC",
    pair_device=False,
    timeout=5,
    logger=logger
)

# Read data
battery.read_bms()

# Check result
if battery.error_code == 0:
    # Electrical data
    print(f"Pack Voltage: {battery.packVoltage / 1000:.2f}V")
    print(f"Current: {battery.current:.2f}A")
    print(f"Power: {battery.watt:.2f}W")

    # Capacity
    print(f"SOC: {battery.SOC}%")
    print(f"Remaining: {battery.remainAh:.1f}Ah / {battery.factoryAh:.1f}Ah")

    # Cell voltages
    print("Cell Voltages:")
    for cell, voltage in battery.batteryPack.items():
        print(f"  Cell {cell}: {voltage:.3f}V")

    # Temperature
    print(f"Cell Temp: {battery.cellTemperature}°C")
    print(f"MOSFET Temp: {battery.mosfetTemperature}°C")

    # Status
    print(f"Status: {battery.battery_status}")
    print(f"Balance: {battery.balance_status}")

    # Device info
    print(f"Firmware: {battery.firmwareVersion}")
    print(f"Manufactured: {battery.manfactureDate}")

    # JSON export
    with open("battery_data.json", "w") as f:
        f.write(battery.get_json())

elif battery.error_code == battery.ERROR_TIMEOUT:
    print("Timeout - check Bluetooth range")
elif battery.error_code == battery.ERROR_BLEAK:
    print(f"Bluetooth error: {battery.error_message}")
elif battery.error_code == battery.ERROR_CHECKSUM:
    print("Data corruption - retry")
else:
    print(f"Error {battery.error_code}: {battery.error_message}")
```
