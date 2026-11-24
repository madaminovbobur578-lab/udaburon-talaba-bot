from pathlib import Path

path = Path("bot.py")

source = path.read_text(encoding="utf-8")

try:

    fixed = source.encode("latin-1").decode("utf-8")

    path.write_text(fixed, encoding="utf-8")

    print("Emoji va matnlar tuzatildi!")

except (UnicodeEncodeError, UnicodeDecodeError):

    print("Fayl allaqachon UTF-8 yoki aralash 
