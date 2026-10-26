"""Stream URLs for Blue Iris cameras (HTTP with a session, or RTSP)."""
from typing import Optional
from urllib.parse import quote

from .const import STREAM_PROTOCOL_RTSP, STREAM_VIDEO


def is_rtsp(stream_type: str) -> bool:
    return STREAM_VIDEO.get(stream_type, {}).get("protocol") == STREAM_PROTOCOL_RTSP


def build_stream_url(
    config_data, base_url: str, session_id: Optional[str], camera_id: str
) -> str:
    """URL HA's stream component opens for a camera.

    HTTP types: Blue Iris' /h264 or /mjpg path with the session.
    RTSP types: rtsp://user:password@host:port/<camera> on Blue Iris' web
    server port (manual, 'RTSP from your HTTP port'), no session; the
    sub stream adds ?decode=-1.
    """
    video = STREAM_VIDEO.get(config_data.stream_type, {})

    if video.get("protocol") != STREAM_PROTOCOL_RTSP:
        stream_name = video.get("stream_name")
        file_name = video.get("file_name", "")
        return f"{base_url}/{stream_name}/{camera_id}/{file_name}?session={session_id}"

    host_port = base_url.split("://", 1)[-1]
    username = config_data.username
    password = config_data.password_clear_text

    login = ""
    if username and password:
        login = f"{quote(username, safe='')}:{quote(password, safe='')}@"

    url = f"rtsp://{login}{host_port}/{quote(camera_id, safe='')}"

    query = video.get("query")
    if query:
        url = f"{url}?{query}"

    return url


def redact_url(url: Optional[str]) -> Optional[str]:
    """Hide a password in user:password@ (for state attributes)."""
    if not url or "://" not in url:
        return url

    scheme, rest = url.split("://", 1)
    netloc, sep, path = rest.partition("/")

    if "@" not in netloc:
        return url

    login, host = netloc.rsplit("@", 1)
    user = login.split(":", 1)[0]

    return f"{scheme}://{user}:****@{host}{sep}{path}"
