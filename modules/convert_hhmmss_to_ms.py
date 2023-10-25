def convert_hhmmss_to_ms(timestamp):
    if timestamp is None:
        return None

    parts = list(map(int, timestamp.split(':')))
    parts.reverse()  # Reverse to ensure hours are optional

    multipliers = [1000, 60000, 3600000]  # multipliers for seconds, minutes, hours to milliseconds
    return sum(value * multiplier for value, multiplier in zip(parts, multipliers))
