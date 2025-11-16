from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from config import settings


def _now_ts() -> float:
    return time.time()


@dataclass
class CachedValue:
    value: Any
    expires_at: float


class CentralBankClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        cache_ttl_seconds: int = 900,
    ) -> None:
        self._base_url = base_url or settings.CBR_API_BASE_URL
        self._timeout = timeout_seconds
        self._cache_ttl = max(0, cache_ttl_seconds)
        self._cache: dict[str, CachedValue] = {}

    async def fetch(self, mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        cache_key = f"{mode}:{json.dumps(payload, sort_keys=True, ensure_ascii=False)}"
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > _now_ts():
            return {"status": "ok", "data": cached.value, "cached": True}

        if not self._base_url:
            data = self._stub_response(mode, payload)
        else:
            try:
                data = await self._call_api(mode, payload)
            except Exception as exc:
                data = self._stub_response(mode, payload, error=str(exc))

        if self._cache_ttl:
            self._cache[cache_key] = CachedValue(
                value=data, expires_at=_now_ts() + self._cache_ttl
            )
        return {"status": "ok", "data": data, "cached": False}

    async def _call_api(self, mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        if mode == "key_rate":
            return await self._fetch_key_rate(payload)
        if mode == "currency":
            return await self._fetch_currency(payload)
        raise ValueError(f"Unsupported CBR mode: {mode}")

    async def _fetch_key_rate(self, payload: dict[str, Any]) -> dict[str, Any]:
        import datetime as dt
        import xml.etree.ElementTree as ET

        to_date = payload.get("date") or dt.date.today().isoformat()
        from_date = (
            payload.get("from_date")
            or (dt.date.fromisoformat(to_date) - dt.timedelta(days=60)).isoformat()
        )
        envelope = self._build_envelope(
            body=f"""
            <KeyRate xmlns="http://web.cbr.ru/">
                <fromDate>{from_date}</fromDate>
                <ToDate>{to_date}</ToDate>
            </KeyRate>
            """
        )
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://web.cbr.ru/KeyRate",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._base_url, content=envelope, headers=headers
            )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "web": "http://web.cbr.ru/",
        }
        rates = []
        for item in root.findall(".//web:KeyRate", ns):
            dt_text = item.findtext("web:DT", default="", namespaces=ns)
            value_text = item.findtext("web:Value", default="", namespaces=ns)
            if not value_text:
                continue
            rates.append(
                {
                    "date": dt_text.split("T")[0] if dt_text else None,
                    "value": self._to_float(value_text),
                }
            )
        return {"rates": rates}

    async def _fetch_currency(self, payload: dict[str, Any]) -> dict[str, Any]:
        import datetime as dt
        import xml.etree.ElementTree as ET

        code = (payload.get("code") or "USD").upper()
        date = payload.get("date") or dt.date.today().isoformat()
        envelope = self._build_envelope(
            body=f"""
            <GetCursOnDateXML xmlns="http://web.cbr.ru/">
                <On_date>{date}T00:00:00</On_date>
            </GetCursOnDateXML>
            """
        )
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://web.cbr.ru/GetCursOnDateXML",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._base_url, content=envelope, headers=headers
            )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "web": "http://web.cbr.ru/",
        }
        for item in root.findall(".//web:ValuteCursOnDate", ns):
            vch_code = item.findtext("web:VchCode", default="", namespaces=ns)
            if vch_code != code:
                continue
            value = self._to_float(
                item.findtext("web:Vcurs", default="", namespaces=ns)
            )
            nominal = self._to_float(
                item.findtext("web:Vnom", default="1", namespaces=ns)
            )
            return {
                "currency": code,
                "value": value / nominal if nominal else value,
                "nominal": nominal,
                "date": date,
            }
        raise ValueError(f"Currency {code} not found for {date}")

    def _build_envelope(self, *, body: str) -> str:
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            f"<soap:Body>{body}</soap:Body>"
            "</soap:Envelope>"
        )

    @staticmethod
    def _to_float(value: str | None) -> float:
        if not value:
            return 0.0
        return float(value.replace(",", "."))

    def _stub_response(
        self, mode: str, payload: dict[str, Any], error: str | None = None
    ) -> dict[str, Any]:
        if mode == "key_rate":
            return {
                "value": 0.16,
                "date": payload.get("date") or "2024-09-15",
                "source": "cbr_stub",
                "error": error,
            }
        if mode == "currency":
            currency = payload.get("code") or "USD"
            return {
                "currency": currency,
                "value": 92.5,
                "date": payload.get("date") or "2024-09-15",
                "source": "cbr_stub",
                "error": error,
            }
        return {
            "mode": mode,
            "payload": payload,
            "message": "stub response",
            "error": error,
        }


class TavilyClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 8.0,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._api_key = api_key or settings.TAVILY_API_KEY
        self._base_url = base_url or settings.TAVILY_BASE_URL
        self._timeout = timeout_seconds
        self._cache_ttl = max(0, cache_ttl_seconds)
        self._cache: dict[str, CachedValue] = {}

    async def search(
        self, *, query: str, max_results: int = 5, search_depth: str = "advanced"
    ) -> dict[str, Any]:
        cache_key = f"{query}:{max_results}:{search_depth}"
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > _now_ts():
            return {"status": "ok", "results": cached.value, "cached": True}

        if not (self._api_key and self._base_url):
            results = self._stub_results(query, max_results)
        else:
            try:
                results = await self._call_api(query, max_results, search_depth)
            except Exception as exc:
                results = self._stub_results(query, max_results)
                return {"status": "stub", "results": results, "error": str(exc)}

        if self._cache_ttl:
            self._cache[cache_key] = CachedValue(
                value=results, expires_at=_now_ts() + self._cache_ttl
            )
        return {"status": "ok", "results": results, "cached": False}

    async def _call_api(
        self, query: str, max_results: int, search_depth: str
    ) -> list[dict[str, Any]]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._base_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def _stub_results(self, query: str, max_results: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for idx in range(1, max_results + 1):
            results.append(
                {
                    "title": f"Stub news #{idx} для '{query}'",
                    "url": f"https://news.example.com/{idx}",
                    "snippet": "Здесь будет краткое описание новости.",
                    "published_at": "2024-09-15",
                }
            )
        return results


__all__ = ["CentralBankClient", "TavilyClient"]
