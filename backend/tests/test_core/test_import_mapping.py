from app.core.import_mapping import normalize_import_row


def test_canonical_headers_pass_through():
    row = {
        "name": "Jane Creator", "email": "jane@example.com", "niche": "beauty",
        "country": "US", "platform": "tiktok", "username": "janeugc",
        "followers": "12000", "engagement_rate": "3.5", "avg_views": "800",
        "profile_url": "https://www.tiktok.com/@janeugc",
    }

    out = normalize_import_row(row)

    assert out == row


def test_creator_finder_export_headers():
    """The creator-finder extension exports platform,username,displayName,
    profileUrl,emails,followerCount,... — historically every row was skipped
    with 'Missing name'."""
    row = {
        "platform": "tiktok",
        "username": "cook.sam",
        "displayname": "Sam Cooks",  # parse_tabular lower-cases headers
        "profileurl": "https://www.tiktok.com/@cook.sam",
        "emails": "sam@gmail.com; biz@cook.sam.com",
        "inferredregion": "US",
        "followercount": "125,300",
        "averageviews": "40.5k",
        "engagementrate": "4.2",
        "externallinks": "https://linktr.ee/cooksam",
    }

    out = normalize_import_row(row)

    assert out["name"] == "Sam Cooks"
    assert out["email"] == "sam@gmail.com"
    assert out["platform"] == "tiktok"
    assert out["username"] == "cook.sam"
    assert out["followers"] == "125300"
    assert out["avg_views"] == "40500"
    assert out["engagement_rate"] == "4.2"
    assert out["country"] == "US"
    assert out["profile_url"] == "https://www.tiktok.com/@cook.sam"


def test_chinese_headers():
    row = {
        "达人名称": "小美", "邮箱": "Mei@Example.com", "平台": "IG",
        "账号": "@mei.beauty", "粉丝数": "1.2m", "领域": "美妆", "国家": "us",
    }

    out = normalize_import_row(row)

    assert out["name"] == "小美"
    assert out["email"] == "mei@example.com"
    assert out["platform"] == "instagram"
    assert out["username"] == "mei.beauty"
    assert out["followers"] == "1200000"
    assert out["niche"] == "美妆"
    assert out["country"] == "US"


def test_influencer_library_export_headers():
    """The 达人库 export (2026-07-10 user file): 红人名|频道ID|红人主页链接|平台|
    国家|分类|粉丝数|近30天gmv|近60天平均观看量|... — no email column at all;
    913 rows used to be skipped with '表头无法识别'."""
    row = {
        "红人名": "Fit Coach Anna",
        "频道id": "UCabcdefghijklmnopqrstuv",  # parse_tabular lower-cases headers
        "红人主页链接": "https://www.youtube.com/@fitcoachanna",
        "平台": "YouTube",
        "国家": "美国",
        "分类": "健身",
        "粉丝数": "1.2万",
        "近30天gmv": "$5,400",
        "近60天平均观看量": "3.5万",
        "自定义标签": "重点",
        "是否有平台邮箱": "是",
    }

    out = normalize_import_row(row)

    assert out["name"] == "Fit Coach Anna"
    assert out["platform"] == "youtube"
    # The @handle from the profile URL beats the raw channel id.
    assert out["username"] == "fitcoachanna"
    assert out["country"] == "US"
    assert out["niche"] == "健身"
    assert out["followers"] == "12000"
    assert out["avg_views"] == "35000"
    assert out["email"] == ""  # "是否有平台邮箱" is yes/no, not an address


def test_channel_id_is_last_resort_username():
    out = normalize_import_row({"红人名": "某达人", "频道id": "UCabcdefghijklmnopqrstuv", "平台": "油管"})

    assert out["platform"] == "youtube"
    assert out["username"] == "UCabcdefghijklmnopqrstuv"


def test_name_falls_back_to_username():
    out = normalize_import_row({"username": "@baker.bob", "platform": "tiktok"})

    assert out["name"] == "baker.bob"
    assert out["username"] == "baker.bob"


def test_platform_and_username_derived_from_profile_url():
    tiktok = normalize_import_row({"链接": "https://www.tiktok.com/@daily.creator"})
    youtube = normalize_import_row({"url": "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv"})
    instagram = normalize_import_row({"profile url": "https://instagram.com/some_user/"})

    assert (tiktok["platform"], tiktok["username"], tiktok["name"]) == (
        "tiktok", "daily.creator", "daily.creator"
    )
    assert (youtube["platform"], youtube["username"]) == (
        "youtube", "UCabcdefghijklmnopqrstuv"
    )
    assert (instagram["platform"], instagram["username"]) == ("instagram", "some_user")


def test_unusable_values_are_dropped_not_crashed():
    row = {
        "name": "X", "email": "not-an-email", "followers": "many",
        "engagement_rate": "high", "country": "United States",
        "profile_url": "https://twitter.com/someone",
    }

    out = normalize_import_row(row)

    assert out["name"] == "X"
    assert out["email"] == ""
    assert out["followers"] == ""
    assert out["engagement_rate"] == ""
    assert out["country"] == ""
    assert out["platform"] == ""


def test_empty_row():
    assert normalize_import_row({})["name"] == ""
