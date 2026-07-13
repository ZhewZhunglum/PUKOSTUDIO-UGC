from app.services.woto_service import build_search_payload, normalize_candidate


def test_build_search_payload_maps_keyword_filters():
    payload = build_search_payload(
        {
            "search_type": "KEYWORD",
            "keyword": "collagen",
            "exclude_keywords": ["giveaway"],
            "region_ids": ["1"],
            "category_ids": ["9"],
            "min_followers": 10000,
            "max_followers": 500000,
            "min_engagement_rate": 3,
            "has_email": True,
            "min_avg_views": 5000,
            "sort": "INTERACTIVE_RATE",
            "sort_order": "desc",
        },
        page_num=2,
        page_size=50,
    )

    assert payload["searchType"] == "KEYWORD"
    assert payload["advancedKeywordList"] == [
        {"value": "collagen", "exclude": False},
        {"value": "giveaway", "exclude": True},
    ]
    assert payload["regionList"] == [{"id": "1"}]
    assert payload["blogCateIds"] == ["9"]
    assert payload["minFansNum"] == 10000
    assert payload["maxFansNum"] == 500000
    assert payload["minInteractiveRate"] == 3
    assert payload["hasEmail"] is True
    assert payload["viewVolumeCombination"]["min"] == 5000
    assert payload["searchSort"] == "INTERACTIVE_RATE"
    assert payload["pageNum"] == 2


def test_build_search_payload_splits_compound_keywords():
    payload = build_search_payload(
        {
            "search_type": "KEYWORD",
            "keyword": "supplement/energy, collagen",
            "exclude_keywords": [],
        },
        page_num=1,
        page_size=20,
    )

    assert payload["advancedKeywordList"] == [
        {"value": "supplement", "exclude": False},
        {"value": "energy", "exclude": False},
        {"value": "collagen", "exclude": False},
    ]


def test_normalize_candidate_prefers_contact_email_and_woto_ids():
    candidate = normalize_candidate(
        "youtube",
        {
            "channelUid": "abc-123",
            "nickname": "Creator Co",
            "username": "creatorco",
            "link": "https://youtube.com/@creatorco",
            "avatar": "https://cdn.example/avatar.png",
            "region": "US",
            "fansNum": "12345",
            "interactiveRate": "5.2",
            "tagList": ["fitness"],
            "hasEmail": True,
        },
        contact=[{"email": "hello@example.com"}],
    )

    assert candidate is not None
    assert candidate.external_id == "abc-123"
    assert candidate.username == "creatorco"
    assert candidate.name == "Creator Co"
    assert candidate.email == "hello@example.com"
    assert candidate.country == "US"
    assert candidate.followers == 12345
    assert candidate.engagement_rate == 5.2
    assert candidate.raw_data["provider"] == "woto"
