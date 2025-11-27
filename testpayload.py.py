#!/usr/bin/env python3
# send_config.py
# Sends a binary configuration blob with 4-byte size header + payload + 4-byte CRC32.
# Usage: python send_config.py

import serial
import struct
import zlib
import time
import sys
from pathlib import Path

# === CONFIG ===
PORT = "COM17"         # <- change to your port, e.g. "/dev/ttyUSB0" on Linux
BAUD = 115200
CHUNK_SIZE = 256       # send in small chunks so device can keep up
CHUNK_DELAY = 0.002    # seconds between chunks
READ_TIMEOUT = 2       # seconds to wait for device reply after send

# === Example Config structure ===
# struct Config {
#     uint32_t version;
#     uint16_t blink_ms; // 100..5000
#     uint8_t  mode;     // 0..2
#     uint8_t  reserved;
# };
#
# Packed payload size = 8 bytes

def build_config(version=2, blink_ms=300, mode=1, reserved=0):
    # sanity bounds here
    if not (100 <= blink_ms <= 5000):
        raise ValueError("blink_ms out of bounds")
    if not (0 <= mode <= 255):
        raise ValueError("mode out of bounds")
    # '<' = little-endian, I = uint32, H = uint16, B = uint8, B = uint8
    payload = struct.pack('<IHB B'.replace(' ',''),
                          version, blink_ms, mode, reserved)
    return payload

def make_packet(payload: bytes):
    size_le = struct.pack('<I', len(payload))   # 4-byte little-endian size header
    crc = struct.pack('<I', zlib.crc32(payload) & 0xFFFFFFFF)
    packet = size_le + payload + crc
    return packet

def send_file(port, baud, packet):
    print(f"Opening {port} @ {baud}")
    with serial.Serial(port, baud, timeout=0.1) as s:
        time.sleep(0.05)  # give UART a moment
        # Drain input
        s.reset_input_buffer()
        s.reset_output_buffer()
        # Send in chunks
        total = len(packet)
        sent = 0
        print(f"Sending {total} bytes ...")
        while sent < total:
            chunk = packet[sent:sent+CHUNK_SIZE]
            s.write(chunk)
            s.flush()
            sent += len(chunk)
            # tiny delay so the target can keep pace
            time.sleep(CHUNK_DELAY)
        print("Send complete. Waiting for device response...")

        # Try to read lines / bytes from device for a short while
        deadline = time.time() + READ_TIMEOUT
        data = b''
        while time.time() < deadline:
            chunk = s.read(512)
            if chunk:
                data += chunk
            else:
                # short pause if nothing
                time.sleep(0.05)

        if data:
            try:
                print("Device replied (raw):")
                print(data)
                # Try to decode as utf-8 printable text
                print("Decoded text (utf-8):")
                print(data.decode('utf-8', errors='replace'))
            except Exception as e:
                print("Could not decode reply:", e)
        else:
            print("No response from device within timeout.")

def main():
    # build example payload
    # You can change values here to test: oversized config, bad values, etc.
    payload = build_config(version=2, blink_ms=300, mode=1, reserved=0)
    packet = make_packet(payload)

    # To test oversized-scenario: uncomment this to make payload huge
    # packet = struct.pack('<I', 65536) + (b'A' * 65536) + struct.pack('<I', zlib.crc32(b'A'*65536) & 0xFFFFFFFF)

    try:
        send_file(PORT, BAUD, packet)
    except serial.SerialException as e:
        print("Serial error:", e)
        print("Check the port, that ST-Link/VCP is not being held under reset, and target power.")
        sys.exit(2)
    except Exception as e:
        print("Error:", e)
        sys.exit(3)

if __name__ == "__main__":
    main()
