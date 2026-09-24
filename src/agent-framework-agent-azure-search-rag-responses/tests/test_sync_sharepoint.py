from sync_sharepoint import chunk_text, extract_allowed_principals, extract_text


def test_extracts_entra_and_site_group_principals() -> None:
    permissions = [
        {
            "roles": ["read"],
            "grantedToV2": {
                "user": {"id": "user-id"},
                "siteUser": {"id": "5"},
            },
            "inheritedFrom": {"id": "parent-id"},
        },
        {
            "roles": ["write"],
            "grantedToIdentitiesV2": [
                {"group": {"id": "group-id"}},
                {"siteGroup": {"id": "7"}},
            ],
        },
        {"roles": ["read"], "link": {"scope": "organization"}},
    ]

    assert extract_allowed_principals(permissions, "tenant-id") == {
        "user-id",
        "group-id",
        "siteGroup:7",
        "tenant:tenant-id",
    }


def test_ignores_non_access_roles_and_anonymous_links() -> None:
    permissions = [
        {"roles": ["ownerless"], "grantedToV2": {"user": {"id": "user-id"}}},
        {"roles": ["read"], "link": {"scope": "anonymous"}},
    ]

    assert extract_allowed_principals(permissions, "tenant-id") == set()


def test_extracts_utf8_text() -> None:
    assert extract_text("notes.txt", b"first\nsecond") == "first\nsecond"


def test_chunks_long_text_with_overlap() -> None:
    chunks = chunk_text(" ".join(f"word-{index}" for index in range(100)), max_characters=120, overlap_characters=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)