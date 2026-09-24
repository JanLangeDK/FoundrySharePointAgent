from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse


@dataclass(frozen=True)
class SharePointSource:
    hostname: str
    library_path: str
    folder_path: str


def parse_sharepoint_folder_url(url: str) -> SharePointSource:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".sharepoint.com"):
        raise ValueError("SHAREPOINT_FOLDER_URL must be an HTTPS SharePoint URL.")

    query_path = parse_qs(parsed.query).get("id", [None])[0]
    selected_path = unquote(query_path) if query_path else unquote(parsed.path)
    selected_parts = [part for part in selected_path.split("/") if part]
    if not selected_parts:
        raise ValueError("SHAREPOINT_FOLDER_URL must identify a document library or folder.")

    library_path = f"/{selected_parts[0]}"
    folder_path = "/".join(selected_parts[1:])
    return SharePointSource(
        hostname=parsed.hostname,
        library_path=library_path,
        folder_path=folder_path,
    )