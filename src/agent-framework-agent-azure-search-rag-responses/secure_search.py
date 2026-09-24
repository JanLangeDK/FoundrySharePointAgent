import json
import logging
import os
from collections.abc import Sequence
from typing import Any

from agent_framework import Message
from agent_framework.azure import AzureAISearchContextProvider
from azure.ai.agentserver.core import get_request_context


logger = logging.getLogger(__name__)


class SharePointPermissionError(RuntimeError):
    pass


class SharePointSearchContextProvider(AzureAISearchContextProvider):
    """Azure AI Search retrieval restricted to the caller's SharePoint principals."""

    NO_RESULTS_CONTEXT = (
        "[SharePoint retrieval status: NO_AUTHORIZED_RESULTS] No authorized SharePoint context "
        "was found for this request. Do not answer from general knowledge and do not invent a citation. "
        "Reply that the answer could not be found in the caller's authorized SharePoint documents."
    )

    async def before_run(self, *, agent, session, context, state) -> None:
        messages = [
            message
            for message in context.input_messages
            if (
                message
                and message.text
                and message.text.strip()
                and message.role == "user"
                and message.text != self.context_prompt
                and message.text != self.NO_RESULTS_CONTEXT
                and not message.text.startswith("[Source:")
            )
        ]
        if not messages:
            return

        result_messages = await self._semantic_search(messages[-1].text)
        context.extend_messages(
            self.source_id,
            [Message(role="user", contents=[self.context_prompt]), *result_messages],
        )

    def _extract_document_text(self, document: dict[str, Any], document_id: str | None = None) -> str:
        text = super()._extract_document_text(document, doc_id=None)
        if not text:
            return ""
        source_name = document.get("sourceName") or document_id or "SharePoint document"
        source_link = document.get("sourceLink")
        citation = f"{source_name} ({source_link})" if source_link else str(source_name)
        return f"[Source: {citation}] {text}"

    def _resolve_principal_ids(self) -> list[str]:
        request_user_id = get_request_context().user_id
        if request_user_id:
            raw_mapping = os.getenv("FOUNDRY_USER_PRINCIPAL_MAP_JSON", "{}")
            mapping = json.loads(raw_mapping)
            principals = mapping.get(request_user_id, [])
            logger.info(
                "SharePoint identity mapping lookup: user_id=%r mapped=%s",
                request_user_id,
                bool(principals),
            )
        else:
            principals = []

        if not principals and os.getenv("ALLOW_LOCAL_DEVELOPMENT_IDENTITY", "").lower() == "true":
            principals = os.getenv("LOCAL_DEVELOPMENT_PRINCIPAL_IDS", "").split(",")

        normalized = [str(principal).strip() for principal in principals if str(principal).strip()]
        if not normalized:
            raise SharePointPermissionError(
                "No trusted SharePoint principal mapping is available for this caller."
            )
        if any("," in principal or "'" in principal for principal in normalized):
            raise SharePointPermissionError("SharePoint principal IDs contain invalid characters.")
        return normalized

    @staticmethod
    def _principal_filter(principal_ids: Sequence[str]) -> str:
        values = ",".join(principal_ids)
        return f"allowedPrincipals/any(principal: search.in(principal, '{values}', ','))"

    async def _semantic_search(self, query: str) -> list[Message]:
        if not self._search_client:
            raise RuntimeError("Search client is not initialized.")

        search_params: dict[str, Any] = {
            "search_text": query,
            "top": self.top_k,
            "filter": self._principal_filter(self._resolve_principal_ids()),
        }
        results = await self._search_client.search(**search_params)

        messages: list[Message] = []
        async for document in results:
            document_id = document.get("id") or document.get("@search.id")
            text = self._extract_document_text(document, document_id=document_id)
            if text:
                messages.append(Message(role="user", contents=[text]))
        return messages or [Message(role="user", contents=[self.NO_RESULTS_CONTEXT])]