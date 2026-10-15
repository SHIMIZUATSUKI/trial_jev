from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "emails.csv"


def load_emails_csv(path: str | Path = DEFAULT_CSV) -> List[Dict[str, str]]:
    """CSV からメールデータを読み込む。"""
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "label": row["label"].strip(),
                    "subject": row["subject"].strip(),
                    "body": row["body"].strip(),
                    "difficulty": (row.get("difficulty") or "").strip(),
                }
            )
    return rows


def build_mail_text(subject: str, body: str) -> str:
    return f"件名: {subject}\n本文: {body}"
