"""Attribute key mapping and allowed-attributes list for APL."""

# Attributes that may be requested and passed through (LSVT user fields)
DEFAULT_ATTRIBUTES = [
    "userId",
    "username",
    "firstName",
    "lastName",
    "email",
    "locationId",
    "locationName",
    "locationVendorId",
    "systemId",
    "systemName",
    "phone1",
    "phone2",
    "address1",
    "address2",
    "city",
    "state",
    "zip",
    "country",
    "companyName",
    "title",
    "accessLevel",
    "misc1",
    "misc2",
]


def apply_key_map(
    attributes: dict[str, str],
    key_map: dict[str, str] | None,
) -> dict[str, str]:
    """
    Map attribute names to query parameter names.

    Args:
        attributes: Dict of attribute name -> value (e.g. from LSVT API).
        key_map: Optional mapping of attribute name -> query param name.
                 If an attribute has no mapping, the original name is used.

    Returns:
        Dict of query param name -> value (string), ready for URL encoding.
    """
    if not key_map:
        return dict(attributes)

    result: dict[str, str] = {}
    for name, value in attributes.items():
        param_name = key_map.get(name, name)
        if value is not None:
            result[param_name] = str(value)
    return result
