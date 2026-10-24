import json
import math
import sys


# ---------------- Stage 1: read (generator) ----------------
def read_lines(path):
    """Yield one non-empty line at a time, so the whole file is never in memory."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield line


# ---------------- Stage 2: parse + validate (generator) ----------------
def to_number(value):
    """Return a finite float, or raise ValueError (booleans and 'bad' are rejected)."""
    if isinstance(value, bool) or value is None:
        raise ValueError("not numeric")
    number = float(value)                      # accepts 21.5, 30 and the string "21.5"
    if not math.isfinite(number):
        raise ValueError("not finite")
    return number


def validate(lines):
    """Yield (device_id, temperature_c, humidity). Corrupted records give temperature None.
    device_id is None when it cannot be read at all."""
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            yield None, None, None             # broken JSON
            continue
        if not isinstance(record, dict):
            yield None, None, None
            continue
        device = record.get("device_id")
        if not isinstance(device, str) or not device.strip():
            yield None, None, None             # missing or invalid device_id
            continue
        device = device.strip()
        try:
            temperature = to_number(record.get("temperature_c"))
            humidity = to_number(record.get("humidity"))
            if not 0 <= humidity <= 100:
                raise ValueError("humidity out of range")
        except (ValueError, TypeError):
            yield device, None, None           # corrupted record of a known device
            continue
        yield device, temperature, humidity


# ---------------- Stage 3: transform units (generator) ----------------
def transform(records, unit):
    """Convert Celsius to Fahrenheit when unit is 'F'; corrupted records pass through."""
    for device, temperature, humidity in records:
        if temperature is not None and unit == "F":
            temperature = temperature * 9 / 5 + 32
        yield device, temperature, humidity


# ---------------- Stage 4: group and summarise ----------------
def summarise(records):
    stats = {}              # device -> [count, min, max, total, corrupted]
    unattributed = 0        # corrupted lines where the device is unknown
    for device, temperature, _humidity in records:
        if device is None:
            unattributed += 1
            continue
        s = stats.setdefault(device, [0, math.inf, -math.inf, 0.0, 0])
        if temperature is None:
            s[4] += 1
        else:
            s[0] += 1
            s[1] = min(s[1], temperature)
            s[2] = max(s[2], temperature)
            s[3] += temperature
    return stats, unattributed


def fmt(number):
    """30.0 -> '30', 30.456 -> '30.46'"""
    return f"{number:.2f}".rstrip("0").rstrip(".")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else input("JSONL file path: ").strip()
    unit = sys.argv[2].upper() if len(sys.argv) > 2 else "C"
    if unit not in ("C", "F"):
        print("Unit must be C or F")
        return
    try:
        stats, unattributed = summarise(transform(validate(read_lines(path)), unit))
    except FileNotFoundError:
        print("File not found:", path)
        return
    except OSError as e:
        print("Cannot read file:", e)
        return
    for device in sorted(stats):
        count, low, high, total, bad = stats[device]
        if count:
            print(f"{device} count={count} min={fmt(low)} max={fmt(high)} "
                  f"avg={total / count:.2f} corrupted={bad}")
        else:
            print(f"{device} count=0 corrupted={bad}")
    if unattributed:
        print(f"UNKNOWN_DEVICE corrupted={unattributed}")


if __name__ == "__main__":
    main()