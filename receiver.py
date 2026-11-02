
import struct
import zlib
import json
from pathlib import Path

# ==========================================
# UNO Q IMAGE PACKET RECEIVER
# ==========================================

FOLDER = Path(__file__).parent

PACKET_FILE = FOLDER / "packets.bin"
METADATA_FILE = FOLDER / "metadata.json"
REFERENCE_FILE = FOLDER / "reference_compressed.jpg"
OUTPUT_FILE = FOLDER / "reconstructed.jpg"

MAGIC = b"\xA5\x5A"

HEADER_FORMAT = "<2sIHHHI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
CRC_SIZE = 4

received_packets = {}

# ==========================================
# LOAD METADATA
# ==========================================

with open(METADATA_FILE, "r") as f:
    metadata = json.load(f)

image_id = metadata["image_id"]
total_packets = metadata["total_packets"]
expected_size = metadata["compressed_size"]

print("\n========== UNO Q IMAGE RECEIVER ==========")
print("Image ID:", image_id)
print("Expected packets:", total_packets)
print("Expected JPEG size:", expected_size, "bytes")

# ==========================================
# READ PACKETS
# ==========================================

with open(PACKET_FILE, "rb") as f:

    packet_number = 0

    while True:

        length_data = f.read(2)

        if not length_data:
            break

        if len(length_data) != 2:
            raise ValueError("Incomplete packet length prefix")

        packet_length = struct.unpack("<H", length_data)[0]

        packet = f.read(packet_length)

        if len(packet) != packet_length:
            raise ValueError("Incomplete packet data")

        if packet_length < HEADER_SIZE + CRC_SIZE:
            raise ValueError("Packet is too short")

        # Extract header
        header = packet[:HEADER_SIZE]

        magic, packet_image_id, index, total, payload_length, jpeg_size = (
            struct.unpack(HEADER_FORMAT, header)
        )

        # Validate magic
        if magic != MAGIC:
            raise ValueError(f"Invalid packet magic at packet {packet_number}")

        # Validate image ID
        if packet_image_id != image_id:
            raise ValueError("Image ID mismatch")

        # Validate packet count
        if total != total_packets:
            raise ValueError("Total packet count mismatch")

        # Validate JPEG size
        if jpeg_size != expected_size:
            raise ValueError("JPEG size mismatch")

        if index >= total:
            raise ValueError("Invalid packet index")

        # Extract CRC and payload
        received_crc = struct.unpack(
            "<I", packet[HEADER_SIZE:HEADER_SIZE + CRC_SIZE]
        )[0]

        payload = packet[HEADER_SIZE + CRC_SIZE:]

        if len(payload) != payload_length:
            raise ValueError("Payload length mismatch")

        # Calculate CRC32
        calculated_crc = zlib.crc32(header + payload) & 0xFFFFFFFF

        if received_crc != calculated_crc:
            raise ValueError(f"CRC ERROR in packet {index}")

        # Store payload
        if index in received_packets:
            if received_packets[index] != payload:
                raise ValueError(f"Conflicting duplicate packet {index}")
        else:
            received_packets[index] = payload

        print(f"Packet {index + 1}/{total}: CRC OK")

        packet_number += 1

# ==========================================
# CHECK MISSING PACKETS
# ==========================================

missing = [
    i for i in range(total_packets)
    if i not in received_packets
]

if missing:
    raise ValueError(f"Missing packets: {missing}")

print("\nAll packets received successfully!")

# ==========================================
# REASSEMBLE JPEG
# ==========================================

reconstructed = b"".join(
    received_packets[i] for i in range(total_packets)
)

if len(reconstructed) != expected_size:
    raise ValueError("Reconstructed image size mismatch")

# Validate JPEG markers
if not reconstructed.startswith(b"\xFF\xD8"):
    raise ValueError("Invalid JPEG start marker")

if not reconstructed.endswith(b"\xFF\xD9"):
    raise ValueError("Invalid JPEG end marker")

# Save reconstructed JPEG
with open(OUTPUT_FILE, "wb") as f:
    f.write(reconstructed)

print("\nJPEG reconstructed successfully!")
print("Saved at:", OUTPUT_FILE)
print("Reconstructed size:", len(reconstructed), "bytes")

# ==========================================
# BYTE-BY-BYTE COMPARISON
# ==========================================

with open(REFERENCE_FILE, "rb") as f:
    reference = f.read()

if reconstructed == reference:

    print("\n====================================")
    print("SUCCESS: EXACT IMAGE MATCH!")
    print("All bytes are identical.")
    print("====================================")

else:

    print("\nERROR: Images are not identical!")

    if len(reconstructed) != len(reference):
        print("Different file sizes.")

    else:
        for i, (a, b) in enumerate(zip(reconstructed, reference)):
            if a != b:
                print("First mismatch at byte:", i)
                break
