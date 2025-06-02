"""
Keyboard layout translation module for handling keyboard layout conversions.
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

def translate_text(text: str) -> str:
    """
    Translate text from English keyboard layout to Ukrainian.
    
    Args:
        text: Text to translate
        
    Returns:
        str: Translated text
    """
    return ''.join(keyboard_mapping.get(char, char) for char in text)

def is_translation_needed(text: str) -> bool:
    """
    Check if text needs translation.
    
    Args:
        text: Text to check
        
    Returns:
        bool: True if translation is needed
    """
    # Check if text contains trigger word
    if "бля!" in text.lower():
        return True
        
    # Check if text contains English characters that have Ukrainian equivalents
    english_chars = set(keyboard_mapping.keys())
    return any(char in english_chars for char in text) 