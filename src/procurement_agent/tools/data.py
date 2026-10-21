"""Load operational records and refuse anything the register does not match.

Integrity before use: each data-backed tool verifies the file it reads
against the SHA-256 in ``knowledge/source-register.csv`` and records that
hash (first 16 hex characters) as ``data_fingerprint``. Line endings are
normalised to ``\\n`` before hashing, the same way the corpus loader does,
so Windows checkouts do not fail the checksum.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import CATEGORIES, LOCATIONS

DEFAULT_REGISTER = Path("knowledge") / "source-register.csv"
DEFAULT_INVENTORY = Path("knowledge") / "data" / "inventory.csv"
DEFAULT_SUPPLIERS = Path("knowledge") / "data" / "suppliers.json"
DEFAULT_QUOTATIONS = Path("knowledge") / "data" / "quotations.json"

REGISTER_ID_INVENTORY = "DAT-001"
REGISTER_ID_SUPPLIERS = "DAT-002"
REGISTER_ID_QUOTATIONS = "DAT-003"

FINGERPRINT_LENGTH = 16

# A stock system is somebody else's process: bound the wait and the payload.
SERVICE_TIMEOUT_S = 5.0
MAX_SERVICE_BYTES = 4 * 1024 * 1024

INVENTORY_FIELDS = (
    "sku",
    "item_name",
    "category",
    "unit_of_measure",
    "current_stock",
    "reorder_point",
    "target_stock_level",
    "unit_cost_ugx",
    "location",
    "last_counted",
)


class DataUnavailable(RuntimeError):
    """A data file could not be read. Fail closed; never substitute figures."""


class DataIntegrityError(ValueError):
    """The file was read but failed its registered checksum or an invariant."""


@dataclass(frozen=True)
class LoadedFile:
    path: Path
    text: str
    fingerprint: str
    register_id: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint_of(checksum: str) -> str:
    return checksum[:FINGERPRINT_LENGTH]


def read_registered_file(
    path: str | os.PathLike[str],
    register_id: str,
    register_path: str | os.PathLike[str] | None = None,
) -> LoadedFile:
    file_path = Path(path)
    try:
        raw = file_path.read_bytes()
    except FileNotFoundError as exc:
        raise DataUnavailable(f"{file_path} could not be read") from exc
    except OSError as exc:
        raise DataUnavailable(f"{file_path} could not be read") from exc

    text = raw.decode("utf-8").replace("\r\n", "\n")
    actual = sha256_text(text)
    expected = _registered_checksum(register_id, register_path)
    if actual != expected:
        raise DataIntegrityError(
            f"{file_path}: content does not match the registered checksum for "
            f"{register_id}. The file was edited after it was registered; "
            "refuse rather than use an unreviewed figure."
        )
    return LoadedFile(
        path=file_path,
        text=text,
        fingerprint=fingerprint_of(actual),
        register_id=register_id,
    )


def _registered_checksum(
    register_id: str,
    register_path: str | os.PathLike[str] | None,
) -> str:
    path = Path(register_path) if register_path is not None else DEFAULT_REGISTER
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except FileNotFoundError as exc:
        raise DataUnavailable(f"source register {path} could not be read") from exc
    except OSError as exc:
        raise DataUnavailable(f"source register {path} could not be read") from exc

    for row in rows:
        if row.get("source_id") == register_id:
            checksum = (row.get("checksum_sha256") or "").strip()
            if not checksum:
                raise DataIntegrityError(
                    f"{register_id} has no checksum in {path}"
                )
            return checksum
    raise DataIntegrityError(f"{register_id} is not in the source register {path}")


def load_inventory(
    path: str | os.PathLike[str] | None = None,
    register_path: str | os.PathLike[str] | None = None,
    as_of: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """The stock position, from the registered snapshot or from a stock system.

    When `path` is an http or https URL it is treated as a stock system to ask
    rather than a file to read, and `as_of` is the date to ask about. Both
    routes return the same rows and the same kind of fingerprint, so nothing
    downstream knows or cares which was used.

    The two are not equally trustworthy and the difference is worth stating. A
    registered file is checked against a checksum held in the source register,
    which the file's author does not control, so an edited file is caught. A
    service's checksum travels with its own payload, so it catches a mangled
    response and nothing else. Asking a system instead of reading a file buys
    realism and a stock position that moves, and it costs that guarantee.
    """
    if _is_url(path):
        return _load_inventory_from_service(str(path), as_of)
    loaded = read_registered_file(
        path or DEFAULT_INVENTORY,
        REGISTER_ID_INVENTORY,
        register_path,
    )
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(loaded.text.splitlines())
    if reader.fieldnames is None:
        raise DataIntegrityError(f"{loaded.path}: inventory file has no header")
    missing_header = [name for name in INVENTORY_FIELDS if name not in reader.fieldnames]
    if missing_header:
        raise DataIntegrityError(
            f"{loaded.path}: header is missing {', '.join(missing_header)}"
        )

    for index, raw in enumerate(reader, start=2):
        try:
            row = _parse_inventory_row(raw)
        except DataIntegrityError as exc:
            raise DataIntegrityError(f"{loaded.path} row {index}: {exc}") from exc
        rows.append(row)

    if not rows:
        raise DataIntegrityError(f"{loaded.path}: snapshot contains no SKUs")
    skus = [row["sku"] for row in rows]
    if len(skus) != len(set(skus)):
        raise DataIntegrityError(f"{loaded.path}: duplicate SKU in the snapshot")
    return rows, loaded.fingerprint


def _is_url(path: Any) -> bool:
    return isinstance(path, str) and path.lower().startswith(("http://", "https://"))


def _load_inventory_from_service(
    url: str,
    as_of: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Ask a stock system for its position, and check what comes back."""
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    target = url
    if as_of:
        joiner = "&" if urllib.parse.urlparse(url).query else "?"
        target = f"{url}{joiner}as_of={urllib.parse.quote(as_of)}"

    request = urllib.request.Request(target, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=SERVICE_TIMEOUT_S) as response:
            raw = response.read(MAX_SERVICE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise DataUnavailable(f"{url} answered {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise DataUnavailable(f"{url} could not be reached: {exc}") from exc

    if len(raw) > MAX_SERVICE_BYTES:
        raise DataIntegrityError(f"{url} returned more than {MAX_SERVICE_BYTES} bytes")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataIntegrityError(f"{url} did not return JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise DataIntegrityError(f"{url} did not return a stock position")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload["items"], start=1):
        if not isinstance(item, dict):
            raise DataIntegrityError(f"{url} item {index} is not a record")
        try:
            rows.append(_parse_inventory_row({
                name: str(item.get(name, "")) for name in INVENTORY_FIELDS
            }))
        except DataIntegrityError as exc:
            raise DataIntegrityError(f"{url} item {index}: {exc}") from exc

    if not rows:
        raise DataIntegrityError(f"{url}: the stock position is empty")
    skus = [row["sku"] for row in rows]
    if len(skus) != len(set(skus)):
        raise DataIntegrityError(f"{url}: the same SKU twice in one position")

    # The service states a checksum of its own payload. Recomputing it catches
    # a truncated or rewritten response in transit. It cannot catch a service
    # that is wrong about its own stock, and nothing here pretends otherwise.
    from ..inventory.ledger import checksum as snapshot_checksum

    computed = snapshot_checksum(rows)
    stated = str(payload.get("checksum") or "")
    if stated and stated != computed:
        raise DataIntegrityError(
            f"{url}: the position does not match the checksum it came with. "
            "Refuse rather than use a figure that arrived damaged."
        )
    return rows, computed[:FINGERPRINT_LENGTH]


def _parse_inventory_row(raw: dict[str, str]) -> dict[str, Any]:
    sku = (raw.get("sku") or "").strip()
    if not sku:
        raise DataIntegrityError("sku is missing")
    item_name = (raw.get("item_name") or "").strip()
    category = (raw.get("category") or "").strip()
    unit = (raw.get("unit_of_measure") or "").strip()
    location = (raw.get("location") or "").strip()
    last_counted = (raw.get("last_counted") or "").strip()

    current_stock = _require_non_negative_int(raw.get("current_stock"), "current_stock")
    reorder_point = _require_non_negative_int(raw.get("reorder_point"), "reorder_point")
    target = _require_non_negative_int(raw.get("target_stock_level"), "target_stock_level")
    unit_cost = _require_non_negative_number(raw.get("unit_cost_ugx"), "unit_cost_ugx")

    if category not in CATEGORIES:
        raise DataIntegrityError(f"category {category!r} is not a known category")
    if location not in LOCATIONS:
        raise DataIntegrityError(f"location {location!r} is not a known store")
    if target <= reorder_point:
        raise DataIntegrityError(
            f"sku {sku}: target_stock_level must be strictly greater than "
            "reorder_point (Requirement 1.3)"
        )
    if current_stock < 0:
        raise DataIntegrityError(f"sku {sku}: negative quantity (Requirement 1.3)")

    return {
        "sku": sku,
        "item_name": item_name,
        "category": category,
        "unit_of_measure": unit,
        "current_stock": current_stock,
        "reorder_point": reorder_point,
        "target_stock_level": target,
        "unit_cost_ugx": unit_cost,
        "location": location,
        "last_counted": last_counted,
    }


def load_suppliers(
    path: str | os.PathLike[str] | None = None,
    register_path: str | os.PathLike[str] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    loaded = read_registered_file(
        path or DEFAULT_SUPPLIERS,
        REGISTER_ID_SUPPLIERS,
        register_path,
    )
    try:
        payload = json.loads(loaded.text)
    except json.JSONDecodeError as exc:
        raise DataIntegrityError(f"{loaded.path}: not valid JSON") from exc
    suppliers = payload.get("suppliers") if isinstance(payload, dict) else None
    if not isinstance(suppliers, list) or not suppliers:
        raise DataIntegrityError(f"{loaded.path}: suppliers list is missing")
    parsed: list[dict[str, Any]] = []
    for entry in suppliers:
        if not isinstance(entry, dict):
            raise DataIntegrityError(f"{loaded.path}: supplier entry is not an object")
        parsed.append(entry)
    return parsed, loaded.fingerprint


def load_quotations(
    path: str | os.PathLike[str] | None = None,
    register_path: str | os.PathLike[str] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    loaded = read_registered_file(
        path or DEFAULT_QUOTATIONS,
        REGISTER_ID_QUOTATIONS,
        register_path,
    )
    try:
        payload = json.loads(loaded.text)
    except json.JSONDecodeError as exc:
        raise DataIntegrityError(f"{loaded.path}: not valid JSON") from exc
    quotations = payload.get("quotations") if isinstance(payload, dict) else None
    if not isinstance(quotations, list) or not quotations:
        raise DataIntegrityError(f"{loaded.path}: quotations list is missing")
    parsed: list[dict[str, Any]] = []
    for entry in quotations:
        if not isinstance(entry, dict):
            raise DataIntegrityError(f"{loaded.path}: quotation entry is not an object")
        parsed.append(entry)
    return parsed, loaded.fingerprint


def _require_non_negative_int(value: str | None, field: str) -> int:
    try:
        number = int((value or "").strip())
    except ValueError as exc:
        raise DataIntegrityError(f"{field} is not an integer") from exc
    if number < 0:
        raise DataIntegrityError(f"{field} is negative")
    return number


def _require_non_negative_number(value: str | None, field: str) -> float:
    try:
        number = float((value or "").strip())
    except ValueError as exc:
        raise DataIntegrityError(f"{field} is not a number") from exc
    if number < 0:
        raise DataIntegrityError(f"{field} is negative")
    return number
