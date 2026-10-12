"""Conservative identity keys for application matching without a requisition ID."""

import re
import unicodedata
from html import unescape


def formatted_identity(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", unescape(value or "")).casefold()
    text = text.translate(
        str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u200b": None,
                "\ufeff": None,
            }
        )
    )
    return " ".join(text.split())


def company_key(value: str | None) -> str:
    # Legal suffix spelling/punctuation can vary; brand and subsidiary words stay.
    text = formatted_identity(value).replace("&", " and ")
    words = re.findall(r"[^\W_]+", text)
    suffixes = {"inc", "incorporated", "corp", "corporation", "ltd", "limited", "llc", "llp", "plc"}
    while len(words) > 1 and words[-1] in suffixes:
        words.pop()
    return " ".join(words)


def role_key(value: str | None) -> str:
    text = formatted_identity(value).replace("&", " and ")
    text = re.sub(r"\bco[ -]?op\b", "coop", text)
    text = re.sub(r"\bfull[ -]?stack\b", "fullstack", text)
    text = re.sub(r"\bsr\.?\b", "senior", text)
    text = re.sub(r"\bjr\.?\b", "junior", text)
    # Preserve order, seniority, geography, numbers, and language marks such as C++/C#/.NET.
    return " ".join(re.findall(r"[\w]+(?:\+\+|#)?|\.net\b", text))
