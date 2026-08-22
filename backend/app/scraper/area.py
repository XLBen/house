"""关键词检测：从房源文本/特征里提取建筑面积（统一换算为平方英尺 sq ft）。

来源优先级：详情页结构化 features > 搜索卡片文本 > 描述正文。
均为尽力而为：部分挂牌不写面积 → 返回 None。
"""

from __future__ import annotations

import re

# 合理的单套面积区间（sq ft）：低于/高于皆视为离群或开发整体规模
_MIN_SQFT = 100
_MAX_SQFT = 20000
_SQFT_PER_M2 = 10.7639104

_SQFT_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s*ft|sqft|ft\s*[²2]|square\s*feet|square\s*foot)",
    re.I,
)
_SQM_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s*m\b|m\s*[²2]|square\s*metres?|sq\s*metres?)",
    re.I,
)


def _parse_sqft(matches: list[re.Match], per_sqm: bool) -> list[int]:
    out: list[int] = []
    for m in matches:
        val = float(m.group(1).replace(",", ""))
        sqft = val * _SQFT_PER_M2 if per_sqm else val
        if _MIN_SQFT <= sqft <= _MAX_SQFT:
            out.append(round(sqft))
    return out


def extract_area_from_text(text: str | None) -> int | None:
    """从一段文本中提取面积。多处提及取最大合理值（通常为套内总面积）。"""
    if not text:
        return None
    candidates = _parse_sqft(_SQFT_RE.finditer(text), per_sqm=False)
    candidates += _parse_sqft(_SQM_RE.finditer(text), per_sqm=True)
    if not candidates:
        return None
    return max(candidates)


def extract_area_from_features(features: list | None) -> int | None:
    """从结构化 features（如 'Over 1,500 sq ft'）提取，逐个取首个合理值。"""
    if not features:
        return None
    for f in features:
        text = f.get("feature") if isinstance(f, dict) else str(f)
        area = extract_area_from_text(text)
        if area is not None:
            return area
    return None
