from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_text_pdf(text: str, password: str | None = None) -> bytes:
    """Create a small text PDF for statement parser tests."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )

    commands = ["BT /F1 12 Tf 50 720 Td"]
    for line in text.splitlines():
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({escaped}) Tj 0 -20 Td")
    commands.append("ET")

    content = DecodedStreamObject()
    content.set_data(" ".join(commands).encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    if password:
        writer.encrypt(password)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_positioned_text_pdf(
    text_items: list[tuple[float, float, str]], password: str | None = None
) -> bytes:
    """Create a PDF whose text is emitted out of visual reading order."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )

    commands = ["BT /F1 12 Tf"]
    for x, y, text in text_items:
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"1 0 0 1 {x} {y} Tm ({escaped}) Tj")
    commands.append("ET")

    content = DecodedStreamObject()
    content.set_data(" ".join(commands).encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    if password:
        writer.encrypt(password)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
