"""Nächtliche SEO/GEO-Sammler.

Drei Sammler, jeder einzeln abschaltbar und ohne Zugangsdaten inaktiv:
Search Console (Service-Account), GEO-Messung (Gemini mit
Google-Search-Grounding) und die vorhandene First-Party-Zählung als
Nutzensignal. Kein Sammler wirft nach außen — ein Ausfall darf die
anderen nicht mitreißen.
"""
from __future__ import annotations
