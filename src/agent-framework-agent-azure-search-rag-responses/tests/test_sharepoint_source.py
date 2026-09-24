import pytest

from sharepoint_source import parse_sharepoint_folder_url


SHARED_DOCUMENTS_URL = (
    "https://example.sharepoint.com/Shared%20Documents/Forms/AllItems.aspx"
    "?id=%2FShared%20Documents&viewid=example"
)


def test_parses_all_items_library_url() -> None:
    source = parse_sharepoint_folder_url(SHARED_DOCUMENTS_URL)

    assert source.hostname == "example.sharepoint.com"
    assert source.library_path == "/Shared Documents"
    assert source.folder_path == ""


def test_parses_nested_folder_from_id_query() -> None:
    source = parse_sharepoint_folder_url(
        "https://example.sharepoint.com/Shared%20Documents/Forms/AllItems.aspx"
        "?id=%2FShared%20Documents%2FPolicies%2FHR"
    )

    assert source.library_path == "/Shared Documents"
    assert source.folder_path == "Policies/HR"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.sharepoint.com/Shared%20Documents",
        "https://example.com/Shared%20Documents",
        "https://example.sharepoint.com/",
    ],
)
def test_rejects_invalid_source_urls(url: str) -> None:
    with pytest.raises(ValueError):
        parse_sharepoint_folder_url(url)