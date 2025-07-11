"""
Keyboard layout translation module for handling keyboard layout conversions (English <-> Ukrainian).
"""

# Keyboard mapping for English to Ukrainian layout
keyboard_mapping = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г',
    'i': 'ш', 'o': 'щ', 'p': 'з', 'a': 'ф', 's': 'і', 'd': 'в', 'f': 'а',
    'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', 'z': 'я', 'x': 'ч',
    'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь'
}

# Add uppercase mappings
keyboard_mapping.update({k.upper(): v.upper() for k, v in keyboard_mapping.items()})

# Reverse mapping for Ukrainian to English layout
reverse_keyboard_mapping = {v: k for k, v in keyboard_mapping.items()}
reverse_keyboard_mapping.update({v.upper(): k.upper() for k, v in keyboard_mapping.items()})


def translate_text_en_to_ua(text: str) -> str:
    """
    Translate text from English keyboard layout to Ukrainian.
    """
    return ''.join(keyboard_mapping.get(char, char) for char in text)

def translate_text_ua_to_en(text: str) -> str:
    """
    Translate text from Ukrainian keyboard layout to English.
    """
    return ''.join(reverse_keyboard_mapping.get(char, char) for char in text)

def detect_layout(text: str) -> str:
    """
    Detect if the text is more likely English or Ukrainian layout.
    Returns 'en' or 'ua'.
    """
    en_count = sum(char in keyboard_mapping for char in text)
    ua_count = sum(char in reverse_keyboard_mapping for char in text)
    # Heuristic: if more English chars, treat as English layout, else Ukrainian
    return 'en' if en_count >= ua_count else 'ua'

def auto_translate_text(text: str) -> str:
    """
    Auto-detect layout and translate to the other layout.
    """
    layout = detect_layout(text)
    if layout == 'en':
        return translate_text_en_to_ua(text)
    else:
        return translate_text_ua_to_en(text)

def is_translation_needed(text: str) -> bool:
    """
    Check if text needs translation (legacy, not used in new logic).
    """
    english_chars = set(keyboard_mapping.keys())
    return any(char in english_chars for char in text) 