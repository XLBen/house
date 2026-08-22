"""房子物理身份指纹。

核心原则：身份判定永不依赖描述文字（description）。
指纹由「规范化地址（邮编+门牌号+街道）+ 卧室数 + 物业类型」构成，
因此描述、标题、照片如何变化都不会让系统把同一套房子识别成两个。
"""

from __future__ import annotations

import hashlib
import re

_RE_WHITESPACE = re.compile(r"\s+")
_RE_NUMBER = re.compile(r"(\d{1,5}[A-Za-z]?)")


def normalize_postcode(postcode: str | None) -> str:
    if not postcode:
        return ""
    return _RE_WHITESPACE.sub("", postcode).upper()


def extract_number(address: str | None) -> str:
    """从地址中提取门牌号，如 "12 Church St" -> "12"，"Flat 5" -> "5"。

    仅匹配独立的数字 token（行首/逗号/空格之后），避免把邮编里的数字
    （如 "SE16" 的 16、"LS1" 的 1）误当门牌号。
    """
    if not address:
        return ""
    # 数字 token：位于行首、逗号或空格之后；可选带字母后缀 / "1-3" 区间
    m = re.search(
        r"(?:^|,|\s)(?:(?:Flat|Apartment|Unit|Suite)\s+)?([0-9]+[A-Za-z]?(?:\s*-\s*[0-9]+)?)",
        address,
    )
    if m:
        return m.group(1).replace(" ", "")
    return ""


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return _RE_WHITESPACE.sub(" ", text).strip().lower()


def build_fingerprint(
    postcode: str | None,
    street: str | None,
    address: str | None,
    bedrooms: int | None,
    property_type: str | None,
) -> str:
    pc = normalize_postcode(postcode)
    number = extract_number(address or street or "")
    st = normalize_text(street)
    if not st and address:
        # 从 display address 里剥掉邮编和门牌号，取剩余街道部分
        remainder = address
        if pc:
            remainder = remainder.replace(pc, " ")
        remainder = re.sub(r"[0-9]+[A-Za-z]?(\s*-\s*[0-9]+)?", " ", remainder)
        st = normalize_text(remainder)
    key = "|".join([pc, number, st, str(bedrooms or ""), normalize_text(property_type)])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
