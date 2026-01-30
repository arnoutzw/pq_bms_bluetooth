# Command Line Interface Usage

The PowerQueen BMS library includes a command-line interface (CLI) for quick battery data retrieval without writing Python code.

## Synopsis

```
python main.py <MAC_ADDRESS> [OPTIONS]
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `MAC_ADDRESS` | string | Yes | Bluetooth device MAC address in format `XX:XX:XX:XX:XX:XX` |

## Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--bms` | | flag | | Retrieve battery BMS information (outputs JSON) |
| `--services` | `-s` | flag | | List all GATT services and characteristics |
| `--timeout` | `-t` | int | 4 | Bluetooth response timeout in seconds |
| `--pair` | | flag | | Pair with device before communication |
| `--verbose` | | flag | | Enable detailed logging output |

## Exit Codes

| Code | Constant | Description |
|------|----------|-------------|
| 0 | - | Success |
| 1 | `ERROR_GENERIC` | Generic/unknown error |
| 2 | `ERROR_TIMEOUT` | Bluetooth timeout error |
| 4 | `ERROR_BLEAK` | Bleak library/Bluetooth error |
| 6 | `ERROR_CHECKSUM` | CRC checksum mismatch |

## Usage Examples

### Read Battery Information

Basic battery data retrieval:

```bash
python main.py 12:34:56:78:AA:CC --bms
```

Output:
```json
{
    "packVoltage": 13280,
    "voltage": 13275,
    "batteryPack": {
        "1": 3.32,
        "2": 3.32,
        "3": 3.32,
        "4": 3.32
    },
    "current": -2.5,
    "watt": -33.19,
    "remainAh": 85.5,
    "factoryAh": 100.0,
    "cellTemperature": 25,
    "mosfetTemperature": 28,
    "heat": "00000000",
    "protectState": "00000000",
    "failureState": [0, 0, 0, 0],
    "equilibriumState": 0,
    "batteryState": 2,
    "SOC": 85,
    "SOH": 100,
    "dischargeSwitchState": 1,
    "dischargesCount": 42,
    "dischargesAHCount": 3580,
    "firmwareVersion": "1.4.0",
    "manfactureDate": "2023-5-15",
    "hardwareVersion": "HW1.0",
    "battery_status": "Discharging",
    "balance_status": "Cell balancing is not active",
    "cell_status": "All cells are healthy",
    "bms_status": "Normal",
    "heat_status": "Self-heating is disabled",
    "error_code": 0,
    "error_message": null
}
```

### Extended Timeout

For unreliable connections or distant batteries:

```bash
python main.py 12:34:56:78:AA:CC --bms --timeout 10
```

### With Bluetooth Pairing

For systems requiring device pairing:

```bash
python main.py 12:34:56:78:AA:CC --bms --pair
```

### Verbose Logging

For debugging connection issues:

```bash
python main.py 12:34:56:78:AA:CC --bms --verbose
```

Example verbose output:
```
2024-01-15 10:30:45 [bulk_send] Connecting to 12:34:56:78:AA:CC...
2024-01-15 10:30:46 [bulk_send] Connected to 12:34:56:78:AA:CC
2024-01-15 10:30:46 [bulk_send] Sending command: 00 00 04 01 16 55 AA 1A
2024-01-15 10:30:46 [_data_callback] Function: parse_version
                    characteristic_id: 0000ffe1-0000-1000-8000-00805f9b34fb
                    Raw data: bytearray(b'...')
...
```

### List Device Services

Discover available GATT services and characteristics:

```bash
python main.py 12:34:56:78:AA:CC --services
```

Output:
```
0000ffe0-0000-1000-8000-00805f9b34fb (Handle: 1): Unknown
    characteristic: $0000ffe1-0000-1000-8000-00805f9b34fb
    bytearray(b'\x00\x00...')
    characteristic: $0000ffe2-0000-1000-8000-00805f9b34fb
    Error: Characteristic not readable
```

### Combined Options

```bash
python main.py 12:34:56:78:AA:CC --bms --pair --timeout 15 --verbose
```

## Processing Output

### Parse JSON with jq

Extract specific fields:

```bash
# Get SOC percentage
python main.py 12:34:56:78:AA:CC --bms | jq '.SOC'

# Get voltage in volts
python main.py 12:34:56:78:AA:CC --bms | jq '.voltage / 1000'

# Get cell voltages
python main.py 12:34:56:78:AA:CC --bms | jq '.batteryPack'

# Get only if no error
python main.py 12:34:56:78:AA:CC --bms | jq 'select(.error_code == 0)'
```

### Save to File

```bash
# Save single reading
python main.py 12:34:56:78:AA:CC --bms > battery_status.json

# Append with timestamp
echo "{\"timestamp\": \"$(date -Iseconds)\", \"data\": $(python main.py 12:34:56:78:AA:CC --bms)}" >> battery_log.json
```

### Check Exit Code

```bash
python main.py 12:34:56:78:AA:CC --bms
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Success"
elif [ $EXIT_CODE -eq 2 ]; then
    echo "Timeout - check Bluetooth range"
elif [ $EXIT_CODE -eq 4 ]; then
    echo "Bluetooth error - check adapter"
elif [ $EXIT_CODE -eq 6 ]; then
    echo "Data corruption - retry"
else
    echo "Unknown error: $EXIT_CODE"
fi
```

### Cron Job Example

Monitor battery every 5 minutes:

```cron
*/5 * * * * /usr/bin/python3 /path/to/main.py 12:34:56:78:AA:CC --bms >> /var/log/battery.log 2>&1
```

## JSON Output Fields

### Electrical Metrics

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `packVoltage` | int | mV | Total pack voltage |
| `voltage` | int | mV | Voltage reading |
| `batteryPack` | object | V | Individual cell voltages (cell number: voltage) |
| `current` | float | A | Current flow (+ charging, - discharging) |
| `watt` | float | W | Calculated power |

### Capacity

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `remainAh` | float | Ah | Remaining capacity |
| `factoryAh` | float | Ah | Factory rated capacity |
| `SOC` | int | % | State of Charge (0-100) |
| `SOH` | int | % | State of Health |

### Temperature

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `cellTemperature` | int | °C | Cell temperature |
| `mosfetTemperature` | int | °C | MOSFET temperature |

### Status Flags

| Field | Type | Description |
|-------|------|-------------|
| `batteryState` | int | 0=Idle, 1=Charging, 2=Discharging, 4=Full |
| `heat` | string | Heat status flags (hex) |
| `protectState` | string | Protection flags (hex) |
| `failureState` | array | Failure state bytes |
| `equilibriumState` | int | Cell balancing state |
| `dischargeSwitchState` | int | 1=enabled, 0=disabled |

### Counters

| Field | Type | Description |
|-------|------|-------------|
| `dischargesCount` | int | Total discharge cycles |
| `dischargesAHCount` | int | Cumulative Ah discharged |

### Device Info

| Field | Type | Description |
|-------|------|-------------|
| `firmwareVersion` | string | BMS firmware version |
| `hardwareVersion` | string | Hardware version |
| `manfactureDate` | string | Manufacturing date |

### Human-Readable Status

| Field | Type | Description |
|-------|------|-------------|
| `battery_status` | string | "Charging", "Discharging", "Standby", "Full Charge" |
| `balance_status` | string | Cell balancing status |
| `cell_status` | string | Cell health status |
| `bms_status` | string | BMS status |
| `heat_status` | string | Self-heating status |

### Error Information

| Field | Type | Description |
|-------|------|-------------|
| `error_code` | int | 0 = success, non-zero = error |
| `error_message` | string/null | Error description if error_code != 0 |
