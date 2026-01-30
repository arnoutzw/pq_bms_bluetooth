# Getting Started

This guide will help you get up and running with the PowerQueen LiFePO4 BMS Bluetooth library.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10+**: Check with `python --version` or `python3 --version`
- **Bluetooth adapter**: A BLE-capable Bluetooth adapter
- **PowerQueen battery**: A PowerQueen LiFePO4 battery with Bluetooth BMS
- **Battery MAC address**: Find this in the PowerQueen mobile app or via Bluetooth scanning

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/pq_bms_bluetooth.git
cd pq_bms_bluetooth
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The requirements include:
- `bleak`: Bluetooth Low Energy library
- `dbus-fast`: D-Bus library for Linux Bluetooth
- `typing_extensions`: Extended typing support

## Finding Your Battery's MAC Address

### Method 1: PowerQueen Mobile App

1. Open the PowerQueen app
2. Connect to your battery
3. Look for device information or Bluetooth settings
4. The MAC address is displayed as `XX:XX:XX:XX:XX:XX`

### Method 2: Bluetooth Scan (Linux)

```bash
# Using bluetoothctl
bluetoothctl scan on
# Look for devices starting with "PQ_" or similar

# Using hcitool
sudo hcitool lescan
```

### Method 3: Bluetooth Scan (macOS)

Use a BLE scanner app like "LightBlue" from the App Store.

## Basic Usage

### Command Line

The simplest way to read battery data:

```bash
python main.py 12:34:56:78:AA:CC --bms
```

Output (JSON format):
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
    "SOC": 85,
    "SOH": 100,
    "battery_status": "Discharging",
    "error_code": 0,
    "error_message": null
}
```

### Python API

```python
from battery import BatteryInfo

# Initialize with MAC address
battery = BatteryInfo(
    bluetooth_device_mac="12:34:56:78:AA:CC",
    pair_device=False,  # Set True if pairing required
    timeout=5           # Seconds to wait for response
)

# Read BMS data
battery.read_bms()

# Check for errors
if battery.error_code == 0:
    # Access battery metrics
    print(f"Pack Voltage: {battery.packVoltage / 1000}V")
    print(f"Current: {battery.current}A")
    print(f"Power: {battery.watt}W")
    print(f"SOC: {battery.SOC}%")
    print(f"Temperature: {battery.cellTemperature}°C")
    print(f"Status: {battery.battery_status}")

    # Individual cell voltages
    for cell, voltage in battery.batteryPack.items():
        print(f"  Cell {cell}: {voltage}V")
else:
    print(f"Error ({battery.error_code}): {battery.error_message}")
```

## Common Issues and Solutions

### Permission Denied (Linux)

If you get permission errors, you may need to:

```bash
# Option 1: Run with sudo
sudo python main.py 12:34:56:78:AA:CC --bms

# Option 2: Add user to bluetooth group
sudo usermod -a -G bluetooth $USER
# Log out and back in for changes to take effect

# Option 3: Set capabilities on Python binary
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python)
```

### Timeout Errors

If connections time out frequently:

1. **Move closer** to the battery (within 10 meters)
2. **Increase timeout**:
   ```bash
   python main.py 12:34:56:78:AA:CC --bms --timeout 10
   ```
3. **Try pairing**:
   ```bash
   python main.py 12:34:56:78:AA:CC --bms --pair
   ```

### Device Not Found

If the device isn't found:

1. **Verify MAC address** is correct
2. **Check battery is powered on** and Bluetooth enabled
3. **Ensure no other device** is connected (e.g., PowerQueen app)
4. **Restart Bluetooth**:
   ```bash
   sudo systemctl restart bluetooth
   ```

### Connection Drops

For unstable connections:

1. Increase timeout value
2. Enable pairing with `--pair`
3. Check for Bluetooth interference
4. Update Bluetooth drivers/firmware

## Verbose Logging

For debugging, enable verbose output:

```bash
python main.py 12:34:56:78:AA:CC --bms --verbose
```

This shows:
- Connection progress
- Commands sent
- Raw data received
- Parsing steps

## Next Steps

- [CLI Usage](cli-usage.md) - Full command-line reference
- [API Reference](api-reference.md) - Complete API documentation
- [BMS Protocol](protocol.md) - Technical protocol details

## Example Scripts

### Continuous Monitoring

```python
import time
from battery import BatteryInfo

battery = BatteryInfo("12:34:56:78:AA:CC", timeout=5)

while True:
    battery.read_bms()

    if battery.error_code == 0:
        print(f"[{time.strftime('%H:%M:%S')}] "
              f"SOC: {battery.SOC}% | "
              f"Voltage: {battery.voltage/1000:.2f}V | "
              f"Current: {battery.current:.2f}A | "
              f"Status: {battery.battery_status}")
    else:
        print(f"Error: {battery.error_message}")

    time.sleep(10)  # Poll every 10 seconds
```

### JSON Logging

```python
import json
from datetime import datetime
from battery import BatteryInfo

battery = BatteryInfo("12:34:56:78:AA:CC", timeout=5)
battery.read_bms()

if battery.error_code == 0:
    data = json.loads(battery.get_json())
    data['timestamp'] = datetime.now().isoformat()

    with open('battery_log.jsonl', 'a') as f:
        f.write(json.dumps(data) + '\n')
```
