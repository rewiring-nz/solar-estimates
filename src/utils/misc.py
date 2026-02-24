def generate_duration_message(total_seconds: float) -> str:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = round(divmod(remainder, 60))
    return f"The pipeline took {days} days, {hours} hours, {minutes} minutes, and {seconds} seconds ({round(total_seconds)} total seconds)"
