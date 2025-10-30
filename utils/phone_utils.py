import phonenumbers

def clean_phone_number(raw_number: str, default_region: str = "US") -> str:
    """
    Normalizes and validates a phone number into E.164 format.
    - Detects if number already includes +country code.
    - If it starts with '0', assumes Ghana (+233).
    - Otherwise, defaults to the provided default_region (e.g., US).

    Example:
        "0555123456"         -> "+233555123456"   (assumes Ghana)
        "+1 (628) 555-0100"  -> "+16285550100"
        "6285550100"         -> "+16285550100"   (default_region=US)
    """
    if not raw_number:
        raise ValueError("Phone number is required")

    # Trim whitespace and normalize symbols
    raw_number = raw_number.strip()

    try:
        if raw_number.startswith("+"):
            # Already has country code → parse directly
            parsed = phonenumbers.parse(raw_number, None)
        elif raw_number.startswith("0"):
            # Ghana-style local number → assume GH
            parsed = phonenumbers.parse(raw_number, "GH")
        else:
            # Fallback to default region
            parsed = phonenumbers.parse(raw_number, default_region)

        if not phonenumbers.is_valid_number(parsed):
            raise ValueError(f"Invalid phone number: {raw_number}")

        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception as e:
        raise ValueError(f"Error parsing phone number '{raw_number}': {e}")