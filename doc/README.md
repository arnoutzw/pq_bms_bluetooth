# PowerQueen LiFePO4 BMS Bluetooth Library Documentation

This documentation provides comprehensive information about the PowerQueen LiFePO4 BMS Bluetooth library, an unofficial Python library for reading Battery Management System (BMS) information from PowerQueen LiFePO4 batteries via Bluetooth Low Energy (BLE).

## Documentation Index

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Quick start guide with installation and basic usage |
| [CLI Usage](cli-usage.md) | Command-line interface reference |
| [API Reference](api-reference.md) | Complete API documentation for all classes and methods |
| [BMS Protocol](protocol.md) | Technical details of the BMS communication protocol |

## Overview

This library provides read-only access to battery metrics including:

- **Electrical Metrics**: Voltage, current, power, cell voltages
- **Capacity Information**: State of Charge (SOC), remaining Ah, factory capacity
- **Temperature Data**: Cell and MOSFET temperatures
- **Health Information**: State of Health (SOH), protection states, failure states
- **Device Information**: Firmware version, hardware version, manufacturing date
- **Usage Statistics**: Discharge cycle count, cumulative Ah discharged

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                         │
│  ┌─────────────┐                                                │
│  │   main.py   │  CLI interface for command-line usage          │
│  └──────┬──────┘                                                │
│         │                                                        │
│  ┌──────▼──────┐                                                │
│  │ battery.py  │  BatteryInfo class - data parsing & storage    │
│  │             │  - BMS command definitions                     │
│  │             │  - Response parsing                            │
│  │             │  - CRC verification                            │
│  └──────┬──────┘                                                │
│         │                                                        │
│  ┌──────▼──────┐                                                │
│  │ request.py  │  Request class - BLE communication             │
│  │             │  - Connection management                       │
│  │             │  - Command transmission                        │
│  │             │  - Notification handling                       │
│  └──────┬──────┘                                                │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     Bluetooth Stack (Bleak)                      │
│  - Cross-platform BLE library                                   │
│  - GATT client implementation                                   │
│  - Async/await support                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Example

```python
from battery import BatteryInfo

# Create battery instance
battery = BatteryInfo("12:34:56:78:AA:CC", timeout=5)

# Read BMS data
battery.read_bms()

# Check for errors
if battery.error_code == 0:
    print(f"Battery: {battery.SOC}%")
    print(f"Voltage: {battery.voltage / 1000}V")
    print(f"Current: {battery.current}A")
    print(f"Status: {battery.battery_status}")
else:
    print(f"Error: {battery.error_message}")
```

## Supported Platforms

- Linux (including Raspberry Pi)
- macOS
- Windows (with compatible Bluetooth adapter)

## Requirements

- Python 3.10 or higher
- Bluetooth Low Energy (BLE) capable adapter
- PowerQueen LiFePO4 battery with Bluetooth BMS

## License

See the [LICENSE](../LICENSE) file in the project root.

## Disclaimer

This is an unofficial library and is not affiliated with PowerQueen. Use at your own risk. This library provides read-only access and cannot modify battery settings.
