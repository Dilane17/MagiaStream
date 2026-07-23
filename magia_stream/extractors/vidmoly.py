"""Extracteur spécifique pour Vidmoly."""

from __future__ import annotations

import re
from typing import Optional, Any
from magia_stream.extractors.base import BaseExtractor


class VidmolyExtractor(BaseExtractor):
    """Extracteur pour leslecteurs vidéo hébergés sur Vidmoly."""

    name: str = "vidmoly"

    def can_handle(self, url_or_html: str) -> bool:
        return "vidmoly" in url_or_html.lower()

    def extract_stream_url(self, page_or_content: Any, **kwargs: Any) -> Optional[str]:
        content = page_or_content if isinstance(page_or_content, str) else str(page_or_content)
        match = re.search(r'file\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', content)
        if match:
            return match.group(1)
        
        # Pattern alternatif avec https://.../master.m3u8
        match_alt = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', content)
        if match_alt:
            return match_alt.group(1)

        return None
