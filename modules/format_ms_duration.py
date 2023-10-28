def format_ms_duration(ms, use_separator=False):
    """
    Convert duration from milliseconds to a formatted string: "hh:mm:ss".
    
    :param ms: Duration in milliseconds.
    :type ms: int
    :return: Formatted duration.
    :rtype: str
    """
    if ms < 0:
        raise ValueError("Duration must be non-negative.")

    # Convert milliseconds to seconds, then compute hours, minutes, and seconds
    seconds = ms // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    separator = use_separator and ':' or ''  # Use ':' as separator if requested, otherwise use empty string.

    # Format the result as "hh:mm:ss"
    formatted_duration = f"{hours:02}{separator}{minutes:02}{separator}{seconds:02}"

    return formatted_duration
