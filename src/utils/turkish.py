"""
Türkçe metin yardımcıları.
"""


# Türkçe karakter eşleştirme tablosu
TURKISH_CHAR_MAP = {
    'ş': 's', 'Ş': 's',
    'ı': 'i', 'İ': 'i', 'I': 'i',
    'ğ': 'g', 'Ğ': 'g',
    'ü': 'u', 'Ü': 'u',
    'ö': 'o', 'Ö': 'o',
    'ç': 'c', 'Ç': 'c',
}


def normalize_turkish(text: str) -> str:
    """
    Türkçe karakterleri ASCII karşılıklarına dönüştürür.
    Bu sayede 'Eskisehir' yazarak 'Eskişehir' bulunabilir.
    
    Args:
        text: Dönüştürülecek metin
    
    Returns:
        Normalize edilmiş metin (küçük harf)
    """
    result = text.lower()
    for turkish_char, ascii_char in TURKISH_CHAR_MAP.items():
        result = result.replace(turkish_char, ascii_char)
    return result
