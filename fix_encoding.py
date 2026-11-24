
from pathlib import Path

path = Path("bot.py")
source = path.read_text(encoding="utf-8")

parts = []
run = ""

def fix_run(value):
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value

for char in source:
    if ord(char) <= 255:
        run += char
    else:
        parts.append(fix_run(run))
        parts.append(char)
        run = ""

parts.append(fix_run(run))

fixed = "".join(parts)
path.write_text(fixed, encoding="utf-8")

print("Bot matnlari va emojilari tekshirildi!")
