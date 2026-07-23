"""Governed HTTP fetch adapter."""

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.http.interface import FetchedResource
from app.kernel.security.egress import AddressResolver, GovernedEgressGuard


@dataclass(frozen=True)
class _Redirect:
    url: str


class GovernedHttpFetchPort:
    """HTTP fetch adapter wired through the application container."""

    def __init__(
        self,
        address_resolver: AddressResolver | None = None,
        client: httpx.AsyncClient | None = None,
        max_redirects: int = 5,
    ) -> None:
        self.egress_guard = GovernedEgressGuard(address_resolver=address_resolver)
        self.client = client
        self.max_redirects = max_redirects

    async def fetch(
        self,
        ctx: RequestContext,
        url: str,
        *,
        max_bytes: int,
    ) -> FetchedResource:
        """Fetch a resource after enforcing the configured egress policy."""
        if self.client is not None:
            return await self._fetch_with_redirects(
                self.client,
                ctx,
                url,
                max_bytes=max_bytes,
            )

        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            return await self._fetch_with_redirects(
                client,
                ctx,
                url,
                max_bytes=max_bytes,
            )

    async def _fetch_with_redirects(
        self,
        client: httpx.AsyncClient,
        ctx: RequestContext,
        url: str,
        *,
        max_bytes: int,
    ) -> FetchedResource:
        current_url = url
        for redirect_count in range(self.max_redirects + 1):
            await self.egress_guard.authorize(ctx, "knowledge:crawler", current_url)
            result = await self._fetch_once(client, current_url, max_bytes=max_bytes)
            if isinstance(result, FetchedResource):
                return result
            if redirect_count >= self.max_redirects:
                raise KernelError(
                    "CRAWLER_TOO_MANY_REDIRECTS",
                    f"Crawler exceeded {self.max_redirects} redirects",
                )
            current_url = result.url

        raise KernelError("CRAWLER_FETCH_FAILED", "Crawler redirect loop failed")

    async def _fetch_once(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        max_bytes: int,
    ) -> FetchedResource | _Redirect:
        try:
            async with client.stream("GET", url, follow_redirects=False) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise KernelError(
                            "CRAWLER_INVALID_REDIRECT",
                            "Crawler redirect response is missing Location",
                        )
                    return _Redirect(url=urljoin(url, location))
                if response.status_code >= 400:
                    raise KernelError(
                        "CRAWLER_FETCH_FAILED",
                        f"Fetch source URI failed with status {response.status_code}",
                    )

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise KernelError(
                        "CRAWLER_CONTENT_TOO_LARGE",
                        f"Fetched content exceeds {max_bytes} byte limit",
                    )

                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise KernelError(
                            "CRAWLER_CONTENT_TOO_LARGE",
                            f"Fetched content exceeds {max_bytes} byte limit",
                        )
                    chunks.append(chunk)

                content_type = (
                    response.headers.get("content-type", "application/octet-stream")
                    .split(";", 1)[0]
                    .strip()
                    or "application/octet-stream"
                )
                return FetchedResource(
                    content=b"".join(chunks),
                    content_type=content_type,
                    final_url=url,
                    status_code=response.status_code,
                )
        except KernelError:
            raise
        except httpx.HTTPError as exc:
            raise KernelError(
                "CRAWLER_FETCH_FAILED",
                "Crawler HTTP request failed",
            ) from exc
