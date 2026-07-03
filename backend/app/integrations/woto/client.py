import asyncio
from typing import Any

import httpx

from app.config import settings


class WotoConfigurationError(RuntimeError):
    pass


class WotoAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class WotoClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.woto_api_key
        self.base_url = (base_url or settings.woto_api_base_url).rstrip("/")
        self.timeout = timeout or settings.woto_request_timeout_seconds
        self._client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> "WotoClient":
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise WotoConfigurationError(
                "Woto API Key 未配置。请前往「系统设置 → Woto API」填写 API Key，"
                "或在后端 .env 中设置 WOTO_API_KEY。"
            )

    def _headers(self) -> dict[str, str]:
        self._ensure_configured()
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_configured()
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            self._owns_client = True

        url = f"{self.base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                )
                if response.status_code == 429:
                    raise WotoAPIError("Woto API quota 或频率限制已触发", response.status_code)
                if response.status_code >= 500:
                    raise WotoAPIError(
                        f"Woto API 暂时不可用（HTTP {response.status_code}）",
                        response.status_code,
                    )
                if response.status_code >= 400:
                    raise WotoAPIError(
                        f"Woto API 请求失败（HTTP {response.status_code}）：{response.text[:300]}",
                        response.status_code,
                    )

                payload = response.json()
                code = payload.get("code")
                if code not in (None, 0, 200, "0", "200"):
                    message = payload.get("message") or payload.get("msg") or "Woto API 返回业务错误"
                    raise WotoAPIError(str(message), response.status_code)
                return payload
            except (httpx.TimeoutException, httpx.TransportError, WotoAPIError) as exc:
                last_error = exc
                if isinstance(exc, WotoAPIError) and exc.status_code not in (429, 500, 502, 503, 504):
                    raise
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))

        if isinstance(last_error, WotoAPIError):
            raise last_error
        raise WotoAPIError(f"Woto API 请求失败：{last_error}")

    async def query_quota(self) -> dict[str, Any]:
        return await self._request("GET", "v1/baseInfo/queryQuota")

    async def list_dict_by_code(self, dict_type_code: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "v1/baseInfo/listDictByCode",
            json_body={"dictTypeCode": dict_type_code},
        )

    async def search_bloggers(self, platform: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"v1/{platform}/bloggerSearch", json_body=body)

    async def blogger_detail(self, platform: str, channel_uid: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"v1/{platform}/bloggerDetail",
            json_body={"channelUid": channel_uid},
        )

    async def blogger_contact(self, platform: str, channel_uid: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"v1/{platform}/bloggerContactByChannelUid",
            json_body={"channelUid": channel_uid},
        )
