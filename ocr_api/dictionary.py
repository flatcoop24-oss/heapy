import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
FIELD_DICTIONARY = (
    ROOT
    / "storage/source_document/nhis_screening/normalized"
    / "2026-01-07__MOHW-2026-6__result-form-field-dictionary.csv"
)


def normalize_label(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^0-9a-z가-힣γ]+", "", value)


@dataclass(frozen=True)
class ItemDefinition:
    item_code: str
    display_name: str
    value_type: str
    canonical_unit: Optional[str]


EXTRA_ALIASES = {
    "최고혈압": "SYSTOLIC_BP",
    "sbp": "SYSTOLIC_BP",
    "최저혈압": "DIASTOLIC_BP",
    "dbp": "DIASTOLIC_BP",
    "공복혈장포도당": "FASTING_GLUCOSE",
    "fpg": "FASTING_GLUCOSE",
    "hdl": "HDL_CHOLESTEROL",
    "hdl콜레스테롤": "HDL_CHOLESTEROL",
    "ldl": "LDL_CHOLESTEROL",
    "ldl콜레스테롤": "LDL_CHOLESTEROL",
    "tg": "TRIGLYCERIDES",
    "sgot": "AST",
    "sgpt": "ALT",
    "ggt": "GAMMA_GTP",
    "감마gtp": "GAMMA_GTP",
    "γgtp": "GAMMA_GTP",
    "크레아티닌": "SERUM_CREATININE",
    "creatinine": "SERUM_CREATININE",
    "egfr": "EGFR",
    "단백뇨": "URINE_PROTEIN",
}


class ScreeningDictionary:
    def __init__(self, items: Dict[str, ItemDefinition], aliases: Dict[str, str]):
        self.items = items
        self.aliases = aliases
        self._ordered_aliases = sorted(aliases, key=len, reverse=True)

    @classmethod
    def load_default(cls) -> "ScreeningDictionary":
        items: Dict[str, ItemDefinition] = {}
        aliases: Dict[str, str] = {}
        with FIELD_DICTIONARY.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                code = row["field_code"].strip()
                if row["value_type"] not in {"NUMERIC", "CODE", "TEXT"}:
                    continue
                definition = ItemDefinition(
                    item_code=code,
                    display_name=row["user_display_label"].strip(),
                    value_type=row["value_type"].strip(),
                    canonical_unit=row["canonical_unit"].strip() or None,
                )
                items[code] = definition
                for label in (row["source_label"], row["user_display_label"]):
                    if label.strip():
                        aliases[normalize_label(label)] = code
        for alias, code in EXTRA_ALIASES.items():
            if code in items:
                aliases[normalize_label(alias)] = code
        return cls(items=items, aliases=aliases)

    def match(self, text: str) -> Optional[ItemDefinition]:
        normalized = normalize_label(text)
        for alias in self._ordered_aliases:
            if alias and alias in normalized:
                return self.items[self.aliases[alias]]
        return None

    def aliases_for(self, item_code: str) -> Iterable[str]:
        return (alias for alias, code in self.aliases.items() if code == item_code)
