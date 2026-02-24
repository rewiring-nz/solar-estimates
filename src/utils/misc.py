def generate_duration_message(total_seconds: float) -> str:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"The pipeline took {round(days)} days, {round(hours)} hours, {round(minutes)} minutes, and {round(seconds)} seconds ({round(total_seconds)} total seconds)"
