import json

import pytest
from azure.ai.agentserver.core import FoundryAgentRequestContext, reset_request_context, set_request_context

from secure_search import SharePointPermissionError, SharePointSearchContextProvider


def test_principal_filter_uses_all_principals() -> None:
    result = SharePointSearchContextProvider._principal_filter(["user-id", "group-id"])

    assert result == "allowedPrincipals/any(principal: search.in(principal, 'user-id,group-id', ','))"


def test_formats_sharepoint_citation() -> None:
    provider = object.__new__(SharePointSearchContextProvider)

    result = provider._extract_document_text(
        {
            "id": "chunk-hash",
            "content": "Grounded text",
            "sourceName": "policy.pdf",
            "sourceLink": "https://example.sharepoint.com/policy.pdf",
        },
        document_id="chunk-hash",
    )

    assert result == "[Source: policy.pdf (https://example.sharepoint.com/policy.pdf)] Grounded text"


def test_no_results_context_requires_grounded_refusal() -> None:
    assert "NO_AUTHORIZED_RESULTS" in SharePointSearchContextProvider.NO_RESULTS_CONTEXT
    assert "do not invent a citation" in SharePointSearchContextProvider.NO_RESULTS_CONTEXT


def test_resolves_mapped_foundry_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FOUNDRY_USER_PRINCIPAL_MAP_JSON",
        json.dumps({"foundry-user": ["entra-user", "entra-group"]}),
    )
    request_token = set_request_context(FoundryAgentRequestContext(user_id="foundry-user"))
    try:
        provider = object.__new__(SharePointSearchContextProvider)
        assert provider._resolve_principal_ids() == ["entra-user", "entra-group"]
    finally:
        reset_request_context(request_token)


def test_fails_closed_without_trusted_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_USER_PRINCIPAL_MAP_JSON", raising=False)
    monkeypatch.delenv("ALLOW_LOCAL_DEVELOPMENT_IDENTITY", raising=False)
    provider = object.__new__(SharePointSearchContextProvider)

    with pytest.raises(SharePointPermissionError, match="No trusted SharePoint principal"):
        provider._resolve_principal_ids()


def test_local_identity_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_LOCAL_DEVELOPMENT_IDENTITY", "true")
    monkeypatch.setenv("LOCAL_DEVELOPMENT_PRINCIPAL_IDS", "user-id,group-id")
    provider = object.__new__(SharePointSearchContextProvider)

    assert provider._resolve_principal_ids() == ["user-id", "group-id"]