from app.identity.fingerprint import (
    build_fingerprint,
    extract_number,
    normalize_postcode,
)


def test_normalize_postcode():
    assert normalize_postcode("sw1a 1aa") == "SW1A1AA"
    assert normalize_postcode(None) == ""


def test_extract_number():
    assert extract_number("12 Church Street") == "12"
    assert extract_number("Flat 5, Grand Building") == "5"
    assert extract_number("No address") == ""


def test_fingerprint_ignores_description():
    # 描述、标题变化绝不改变身份
    fp1 = build_fingerprint(
        "SW1A 1AA", "Church Street", "12 Church Street, London", 3, "Terraced"
    )
    fp2 = build_fingerprint(
        "SW1A 1AA", "Church Street", "12 Church Street, London", 3, "Terraced"
    )
    assert fp1 == fp2


def test_fingerprint_differs_for_different_houses():
    a = build_fingerprint("SW1A 1AA", "Church Street", "12 Church Street", 3, "Terraced")
    b = build_fingerprint("SW1A 1AA", "Church Street", "14 Church Street", 3, "Terraced")
    assert a != b
    c = build_fingerprint("SW1A 1AA", "Church Street", "12 Church Street", 4, "Terraced")
    assert a != c


def test_fingerprint_stable_across_address_formatting():
    # 同一房子的地址写法不同，指纹仍应一致（只要邮编/门牌/街道/卧室/类型稳定）
    a = build_fingerprint("SW1A 1AA", "Church Street", "12 Church Street, London SW1A 1AA", 3, "Terraced")
    b = build_fingerprint("SW1A1AA", "Church Street", "12 Church St", 3, "Terraced")
    assert a == b


def test_extract_number_does_not_take_postcode_digits():
    """C2 回归：邮编内的数字（SE16 的 16）不得被当成门牌号。"""
    assert extract_number("Rotherhithe Street, London, SE16") == ""
    assert extract_number("The Pump House, SE16") == ""
    assert extract_number("12 Church Street") == "12"
    assert extract_number("Flat 5, Grand Building") == "5"
