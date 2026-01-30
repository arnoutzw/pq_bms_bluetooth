# BMS Communication Protocol

This document describes the technical details of the communication protocol used by PowerQueen LiFePO4 battery BMS devices.

## Overview

The BMS uses Bluetooth Low Energy (BLE) GATT protocol for communication. Commands are sent as binary packets, and responses are received via BLE notifications.

## BLE Characteristics

### Primary Service

**Service UUID:** `0000FFE0-0000-1000-8000-00805F9B34FB`

### Characteristics

| UUID | Name | Properties | Description |
|------|------|------------|-------------|
| `0000FFE1-0000-1000-8000-00805F9B34FB` | BMS Data | Read, Write, Notify | Primary BMS communication |
| `0000FFE2-0000-1000-8000-00805F9B34FB` | Serial Number | Read | Device serial number (may not be implemented) |

## Command Structure

### Request Format

All commands follow an 8-byte structure:

```
Byte:   0    1    2    3    4    5    6    7
      ┌────┬────┬────┬────┬────┬────┬────┬────┐
      │ 00 │ 00 │ LEN│ 01 │ CMD│ 55 │ AA │ CRC│
      └────┴────┴────┴────┴────┴────┴────┴────┘
```

| Byte | Value | Description |
|------|-------|-------------|
| 0-1 | `00 00` | Header (fixed) |
| 2 | Variable | Packet length (typically `04`) |
| 3 | `01` | Request type indicator |
| 4 | Variable | Command ID |
| 5-6 | `55 AA` | Magic bytes |
| 7 | Variable | Checksum |

### Available Commands

| Command ID | Hex | Name | Description |
|------------|-----|------|-------------|
| 0x10 | `10` | `SERIAL_NUMBER` | Request serial number (may not work) |
| 0x13 | `13` | `GET_BATTERY_INFO` | Request battery metrics |
| 0x16 | `16` | `GET_VERSION` | Request firmware/hardware version |

### Command Examples

**GET_VERSION:**
```
00 00 04 01 16 55 AA 1A
```
Calculation: `00 + 00 + 04 + 01 + 16 + 55 + AA = 11A` → `1A` (lowest 8 bits)

**GET_BATTERY_INFO:**
```
00 00 04 01 13 55 AA 17
```
Calculation: `00 + 00 + 04 + 01 + 13 + 55 + AA = 117` → `17` (lowest 8 bits)

## Response Format

### General Structure

Responses use variable-length packets:

```
Bytes:  0    1    2    3    4    5    6    7    8 ... N-1   N
      ┌────┬────┬────┬────┬────┬────┬────┬────┬─────────┬────┐
      │ 00 │ 00 │ LEN│ 02 │ CMD│ 55 │ AA │ ?? │  DATA   │ CRC│
      └────┴────┴────┴────┴────┴────┴────┴────┴─────────┴────┘
                      │
                      └─ 02 indicates response
```

### Checksum Verification

The checksum is calculated as the sum of all bytes (excluding the checksum byte) masked to 8 bits:

```python
def calculate_checksum(data: bytearray) -> int:
    return sum(data[:-1]) & 0xFF
```

To verify:
```python
received_crc = data[-1]
calculated_crc = sum(data[:-1]) & 0xFF
is_valid = received_crc == calculated_crc
```

## GET_VERSION Response (0x16)

### Packet Structure

Total length: ~32 bytes

```
Offset  Size  Description
------  ----  -----------
0-7     8     Header
8-9     2     Major version (little-endian, reversed)
10-11   2     Minor version (little-endian, reversed)
12-13   2     Patch version (little-endian, reversed)
14-15   2     Manufacturing year (little-endian, reversed)
16      1     Manufacturing month
17      1     Manufacturing day
18+     var   Hardware version (interleaved ASCII)
N       1     Checksum
```

### Version Parsing

Firmware version is constructed from three 16-bit values:

```python
major = int.from_bytes(data[8:10][::-1], byteorder="big")
minor = int.from_bytes(data[10:12][::-1], byteorder="big")
patch = int.from_bytes(data[12:14][::-1], byteorder="big")
firmware_version = f"{major}.{minor}.{patch}"
# Example: "1.4.0"
```

### Manufacturing Date

```python
year = int.from_bytes(data[14:16][::-1], byteorder="big")
month = data[16]
day = data[17]
manufacture_date = f"{year}-{month}-{day}"
# Example: "2023-5-15"
```

### Hardware Version

Hardware version is stored with interleaved null bytes. Extract printable ASCII:

```python
hardware = ""
for i in range(0, len(data) - 1, 2):
    if 32 <= data[i] <= 126:  # Printable ASCII
        hardware += chr(data[i])
# Example: "HW1.0"
```

## GET_BATTERY_INFO Response (0x13)

### Packet Structure

Total length: ~105 bytes

```
Offset  Size  Description
------  ----  -----------
0-7     8     Header
8-11    4     Pack voltage (mV, little-endian reversed)
12-15   4     Voltage reading (mV, little-endian reversed)
16-47   32    Cell voltages (16 cells × 2 bytes each)
48-51   4     Current (mA, signed, little-endian reversed)
52-53   2     Cell temperature (°C, signed)
54-55   2     MOSFET temperature (°C, signed)
56-61   6     Reserved
62-63   2     Remaining capacity (Ah × 100)
64-65   2     Factory capacity (Ah × 100)
66-67   2     Reserved
68-71   4     Heat status flags
72-75   4     Reserved
76-79   4     Protection state flags
80-83   4     Failure state flags
84-87   4     Equilibrium/balance state
88-89   2     Battery state
90-91   2     State of Charge (SOC %)
92-95   4     State of Health (SOH)
96-99   4     Discharge count
100-103 4     Discharge Ah count
104     1     Checksum
```

### Byte Ordering

All multi-byte values use **reversed little-endian** byte order:

```python
# Standard little-endian would be:
# [low_byte, high_byte] → value

# This protocol uses reversed:
# [byte0, byte1, byte2, byte3] → reverse → [byte3, byte2, byte1, byte0] → parse as big-endian

value = int.from_bytes(data[offset:offset+4][::-1], byteorder="big")
```

### Voltage Parsing

**Pack Voltage (mV):**
```python
pack_voltage = int.from_bytes(data[8:12][::-1], byteorder="big")
# Example: 13280 mV = 13.28V
```

**Cell Voltages:**
```python
cell_voltages = {}
cells = data[16:48]  # 32 bytes for 16 cells
for i in range(16):
    voltage = int.from_bytes(cells[i*2:(i+1)*2][::-1], byteorder="big")
    if voltage > 0:  # Skip empty cell slots
        cell_voltages[i + 1] = voltage / 1000  # Convert to Volts
# Example: {1: 3.32, 2: 3.32, 3: 3.32, 4: 3.32}
```

### Current Parsing

Current is a **signed** value (negative = discharging, positive = charging):

```python
current_raw = int.from_bytes(data[48:52][::-1], byteorder="big", signed=True)
current = current_raw / 1000  # Convert mA to A
# Example: -2500 mA = -2.5A (discharging)
```

### Power Calculation

```python
watt = (voltage * current) / 1000000
# Example: 13280mV × -2500mA / 1000000 = -33.2W
```

### Temperature Parsing

Temperatures are **signed** values (can be negative):

```python
cell_temp = int.from_bytes(data[52:54][::-1], byteorder="big", signed=True)
mosfet_temp = int.from_bytes(data[54:56][::-1], byteorder="big", signed=True)
# Example: 25°C, 28°C
```

### Capacity Parsing

Capacity values are stored as Ah × 100:

```python
remain_ah = int.from_bytes(data[62:64][::-1], byteorder="big") / 100
factory_ah = int.from_bytes(data[64:66][::-1], byteorder="big") / 100
# Example: 85.5 Ah, 100.0 Ah
```

### State Flags

**Heat Status (bytes 68-71):**
```python
heat = data[68:72].hex()
# Example: "00000000"

# Discharge switch state from heat[6]:
discharge_switch = 0 if int(heat[6], 16) >= 8 else 1
```

**Protection State (bytes 76-79):**
```python
protect_state = data[76:80].hex()
# Example: "00000000" (no protections active)
```

**Failure State (bytes 80-83):**
```python
failure_state = list(data[80:84])
# Example: [0, 0, 0, 0] (no failures)
```

**Equilibrium/Balance State (bytes 84-87):**
```python
equilibrium = int.from_bytes(data[84:88][::-1], byteorder="big")
# 0 = no balancing, non-zero = balancing active
```

### Battery State

```python
battery_state = int.from_bytes(data[88:90][::-1], byteorder="big")
```

| Value | State |
|-------|-------|
| 0 | Idle |
| 1 | Charging |
| 2 | Discharging |
| 4 | Full Charge |

### SOC and SOH

```python
soc = int.from_bytes(data[90:92][::-1], byteorder="big")  # 0-100%
soh = int.from_bytes(data[92:96][::-1], byteorder="big")  # State of Health
```

### Discharge Counters

```python
discharge_count = int.from_bytes(data[96:100][::-1], byteorder="big")
discharge_ah = int.from_bytes(data[100:104][::-1], byteorder="big")
```

## Communication Timing

### Command Sequence

1. Connect to device
2. Enable notifications on characteristic
3. Write command bytes
4. Wait for notification (~1 second)
5. Process response
6. Repeat for additional commands
7. Disconnect

### Recommended Delays

| Operation | Delay |
|-----------|-------|
| Between commands | 1 second |
| Connection timeout | 4-10 seconds |
| Response wait | 1 second |

## Error Handling

### Checksum Mismatch

If the calculated checksum doesn't match the received checksum:

```python
if calculated_crc != received_crc:
    # Data may be corrupted
    # Retry the command
    error_code = 6  # ERROR_CHECKSUM
```

### Incomplete Response

If fewer bytes received than expected:
- Increase timeout
- Retry command
- Check Bluetooth signal strength

### No Response

If no notification received:
- Check device is powered on
- Check Bluetooth range
- Try pairing (`--pair` option)
- Restart Bluetooth stack

## Example: Complete Transaction

```
→ Connect to 12:34:56:78:AA:CC
→ Start notifications on FFE1

→ Write: 00 00 04 01 16 55 AA 1A  (GET_VERSION)
← Receive: 00 00 18 02 16 55 AA 00 01 00 04 00 00 00 E7 07 05 0F ... [CRC]
  → Parse: Firmware 1.4.0, Manufactured 2023-5-15

→ Write: 00 00 04 01 13 55 AA 17  (GET_BATTERY_INFO)
← Receive: 00 00 64 02 13 55 AA 00 E0 33 00 00 DB 33 00 00 ... [CRC]
  → Parse: Voltage 13280mV, Current -2500mA, SOC 85%, etc.

→ Stop notifications
→ Disconnect
```

## Notes

1. **Read-only protocol**: This library only reads data. Writing settings is not supported.

2. **Serial number**: The SERIAL_NUMBER command (0x10) appears to be unimplemented in current BMS firmware.

3. **Byte order**: The reversed little-endian format is unusual. Always use `data[::-1]` before parsing.

4. **Cell count**: The protocol supports up to 16 cells, but actual cell count depends on battery configuration. Empty cell slots report 0V.

5. **Signed values**: Current and temperature are signed. Other values are unsigned.
