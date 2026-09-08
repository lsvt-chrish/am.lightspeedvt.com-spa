"""
Fills the real VA Form 21-10210 (Lay/Witness Statement) PDF -- see
backend/app/assets/VBA-21-10210-ARE.pdf, exact field names/tooltips read via
pypdf. Fills only what we can know here: veteran name, witness name/
relationship, and the generated statement text (across the statement's two
pages if it runs long). Everything else -- SSN, VA file number, address,
phone, email, and the signature itself -- is left blank/unset for the
veteran or witness to complete by hand, same as the print-preview mock this
replaces.

This is an XFA ("LiveCycle dynamic") form: filling only the flat AcroForm
field values (as pypdf does) is invisible in Adobe Acrobat/Reader, which
renders from the embedded XFA data packets instead and ignores AcroForm
values whenever an /XFA entry is present. We drop /XFA from the AcroForm
dict below so every viewer (Acrobat included) falls back to plain AcroForm
rendering and actually shows the values we filled in.
"""
import io
from pathlib import Path
from typing import Literal

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

RelationshipT = Literal["family", "friend", "buddy", "officer", "other"]

# Empirically near the doc's stated 1400-2000 char target; the statement
# field spans most of pages 2-3, so this is a reasonable split point rather
# than an exact measurement of the field's rendered capacity.
_STATEMENT_SPLIT_AT = 1900


_PDF_PATH = Path(__file__).parent / "assets" / "VBA-21-10210-ARE.pdf"


def _split_name(full_name: str) -> tuple[str, str, str]:
    """
    Best-effort split of a full name into (first, middle_initial, last),
    clipped to the form's declared max lengths (12 / 1 / 18 chars). There's
    no reliable way to know a real middle name from a single "full name"
    string, so a 3+-word name treats the 2nd word's first letter as the
    middle initial rather than guessing at a full middle name.
    """
    parts = (full_name or "").strip().split()
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0][:12], "", ""
    if len(parts) == 2:
        return parts[0][:12], "", parts[1][:18]
    return parts[0][:12], parts[1][0][:1], parts[-1][:18]


def _split_statement(statement: str) -> tuple[str, str]:
    """Split the statement across the form's two statement fields (page 2 continued onto page 3)."""
    statement = statement or ""
    if len(statement) <= _STATEMENT_SPLIT_AT:
        return statement, ""
    # Break at the nearest preceding whitespace so a word isn't cut in half.
    cut = statement.rfind(" ", 0, _STATEMENT_SPLIT_AT)
    if cut <= 0:
        cut = _STATEMENT_SPLIT_AT
    return statement[:cut].rstrip(), statement[cut:].lstrip()


def _relationship_checkboxes(relationship: RelationshipT, relationship_detail: str) -> dict[str, str]:
    """Map our relationship type to the form's Section IV checkboxes (Section 19)."""
    on, off = "/1", "/Off"
    boxes = {
        "vba210304[0].#subform[2].SERVED_WITH_CLAIMANT[0]": off,
        "vba210304[0].#subform[2].FAMILY_OR_FRIEND_OF_CLAIMANT[0]": off,
        "vba210304[0].#subform[2].COWORKER_OR_SUPERVISOR_OF_CLAIMANT[0]": off,
        "vba210304[0].#subform[2].OTHER_Specify[0]": off,
    }
    if relationship in ("buddy", "officer"):
        boxes["vba210304[0].#subform[2].SERVED_WITH_CLAIMANT[0]"] = on
    elif relationship in ("family", "friend"):
        boxes["vba210304[0].#subform[2].FAMILY_OR_FRIEND_OF_CLAIMANT[0]"] = on
    elif relationship == "other":
        boxes["vba210304[0].#subform[2].OTHER_Specify[0]"] = on
        boxes["vba210304[0].#subform[2].OTHER_Specify[1]"] = (relationship_detail or "")[:30]
    return boxes


def fill_va_form(
    veteran_name: str,
    witness_name: str,
    relationship: RelationshipT,
    relationship_detail: str,
    statement: str,
) -> bytes:
    reader = PdfReader(str(_PDF_PATH))
    writer = PdfWriter()
    writer.append(reader)

    v_first, v_middle, v_last = _split_name(veteran_name)
    w_first, w_middle, w_last = _split_name(witness_name)
    stmt_p1, stmt_p2 = _split_statement(statement)

    fields = {
        "vba210304[0].#subform[0].Veterans_First_Name[0]": v_first,
        "vba210304[0].#subform[0].Middle_Initial1[0]": v_middle,
        "vba210304[0].#subform[0].Last_Name[0]": v_last,
        "vba210304[0].#subform[1].TextField1[0]": stmt_p1,
        "vba210304[0].#subform[2].TextField1[1]": stmt_p2,
        "vba210304[0].#subform[2].WITNESS_FIRST_NAME[0]": w_first,
        "vba210304[0].#subform[2].Middle_Initial1[2]": w_middle,
        "vba210304[0].#subform[2].Last_Name[2]": w_last,
        **_relationship_checkboxes(relationship, relationship_detail),
    }

    for page in writer.pages:
        writer.update_page_form_field_values(page, fields, auto_regenerate=False)

    # Drop the embedded XFA packets so every viewer (Acrobat included) renders
    # from the flat AcroForm values above instead of the (now stale) dynamic
    # XFA form -- see module docstring.
    acroform_ref = writer._root_object.get("/AcroForm")
    acroform = acroform_ref.get_object() if acroform_ref is not None else None
    if acroform is not None:
        if "/XFA" in acroform:
            del acroform[NameObject("/XFA")]
        acroform[NameObject("/NeedAppearances")] = BooleanObject(True)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
