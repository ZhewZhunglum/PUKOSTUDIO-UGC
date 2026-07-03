from decimal import Decimal

from app.models.woto import WotoBillingOperation
from app.services.woto_pricing_service import discount_for_call_count, get_price_rule, money


def test_woto_pricing_rules_match_quote_sheet():
    assert get_price_rule(WotoBillingOperation.influencer_search, "youtube").unit_price_cny == Decimal("0.50")
    assert get_price_rule(WotoBillingOperation.influencer_detail, "youtube").unit_price_cny == Decimal("0.75")
    assert get_price_rule(WotoBillingOperation.influencer_detail, "instagram").unit_price_cny == Decimal("1.50")
    assert get_price_rule(WotoBillingOperation.influencer_detail, "tiktok").unit_price_cny == Decimal("1.50")
    assert get_price_rule(WotoBillingOperation.video_data, "tiktok").unit_price_cny == Decimal("0.38")
    assert get_price_rule(WotoBillingOperation.contact_email, "instagram").unit_price_cny == Decimal("1.50")
    assert get_price_rule(WotoBillingOperation.brand_monitoring).unit_price_cny == Decimal("1500.00")


def test_woto_discount_tiers_match_quote_sheet():
    assert discount_for_call_count(9_999) == Decimal("1.00")
    assert discount_for_call_count(10_000) == Decimal("0.90")
    assert discount_for_call_count(50_000) == Decimal("0.80")
    assert discount_for_call_count(100_000) == Decimal("0.70")


def test_money_rounds_to_two_decimals():
    assert money(Decimal("1.005")) == Decimal("1.01")
