"""
Java 临床路径后端 HTTP 客户端。

封装对 Java 端（Ch8 案例）REST API 的调用，提供：
- get_anomaly_rule: 查询预警规则
- create_anomaly_event: 记录异常事件

使用 httpx.AsyncClient 实现异步 HTTP 调用，支持重试与超时。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.models.schemas import (
    AnomalyEventCreateRequest,
    AnomalyEventResponse,
    AnomalyRuleResponse,
)

logger = logging.getLogger(__name__)

# 默认 Java 服务地址（可通过环境变量覆盖）
DEFAULT_JAVA_BASE_URL = "http://localhost:8080"
JAVA_BASE_URL = getattr(settings, "JAVA_SERVICE_URL", DEFAULT_JAVA_BASE_URL)
SERVICE_TOKEN = getattr(settings, "SERVICE_TOKEN", "default-service-token")


class JavaApiClientError(Exception):
    """Java API 调用异常基类。"""


class JavaApiClientNotFoundError(JavaApiClientError):
    """资源不存在（404）。"""


class JavaApiClientAuthError(JavaApiClientError):
    """认证失败（401）。"""


class JavaApiClient:
    """Java 临床路径后端 REST API 客户端。

    用法:
        client = JavaApiClient()
        rule = await client.get_anomaly_rule("GLU-001")
        event = await client.create_anomaly_event(request)
    """

    def __init__(
        self,
        base_url: str = JAVA_BASE_URL,
        service_token: str = SERVICE_TOKEN,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
        max_retries: int = 3,
        retry_interval: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._max_retries = max_retries
        self._retry_interval = retry_interval
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建异步 HTTP 客户端。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._read_timeout, connect=self._connect_timeout),
            )
        return self._client

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头，包含服务认证与链路追踪。"""
        return {
            "X-Service-Token": self._service_token,
            "X-Trace-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """发送 HTTP 请求，带重试逻辑。"""
        client = await self._get_client()
        headers = self._build_headers()
        url = f"{self._base_url}{path}"

        last_exception: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                )

                if response.status_code == 404:
                    raise JavaApiClientNotFoundError(
                        f"Resource not found: {method} {path}"
                    )
                if response.status_code == 401:
                    raise JavaApiClientAuthError(
                        f"Authentication failed: {method} {path}"
                    )

                response.raise_for_status()
                return response.json()

            except (JavaApiClientNotFoundError, JavaApiClientAuthError):
                raise
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Java API HTTP error (attempt %d/%d): %s %s - %s",
                    attempt, self._max_retries, method, path, e,
                )
                last_exception = e
                if attempt < self._max_retries:
                    import asyncio
                    await asyncio.sleep(self._retry_interval)
            except httpx.RequestError as e:
                logger.error(
                    "Java API request failed (attempt %d/%d): %s %s - %s",
                    attempt, self._max_retries, method, path, e,
                )
                last_exception = e
                if attempt < self._max_retries:
                    import asyncio
                    await asyncio.sleep(self._retry_interval)

        raise JavaApiClientError(
            f"Java API request failed after {self._max_retries} retries: "
            f"{method} {path}"
        ) from last_exception

    async def get_anomaly_rule(self, test_item_id: str) -> AnomalyRuleResponse:
        """查询指定诊疗项目的预警规则。

        Args:
            test_item_id: 诊疗项目ID（如 "GLU-001"）

        Returns:
            AnomalyRuleResponse: 预警规则配置

        Raises:
            JavaApiClientNotFoundError: 该诊疗项目未配置预警规则
            JavaApiClientError: 其他调用失败
        """
        path = f"/api/v1/anomaly/rules/{test_item_id}"
        logger.debug("Fetching anomaly rule for test_item_id=%s", test_item_id)
        data = await self._request("GET", path)
        return AnomalyRuleResponse(**data)

    async def create_anomaly_event(
        self, event: AnomalyEventCreateRequest,
    ) -> AnomalyEventResponse:
        """记录异常事件到 Java 端。

        Args:
            event: 异常事件创建请求

        Returns:
            AnomalyEventResponse: 创建的异常事件信息

        Raises:
            JavaApiClientError: 调用失败
        """
        path = "/api/v1/anomaly/events"
        logger.debug(
            "Creating anomaly event for rule_id=%s, test_item_id=%s",
            event.rule_id, event.test_item_id,
        )

        # 构建请求体，处理嵌套对象序列化
        payload: Dict[str, Any] = {
            "rule_id": event.rule_id,
            "test_item_id": event.test_item_id,
            "triggered_at": event.triggered_at,
            "severity": event.severity,
        }
        if event.moving_averages is not None:
            payload["moving_averages"] = event.moving_averages
        if event.deviation_points is not None:
            payload["deviation_points"] = [
                {
                    "index": dp.index,
                    "moving_average": dp.moving_average,
                    "upper_limit": dp.upper_limit,
                    "lower_limit": dp.lower_limit,
                    "direction": dp.direction,
                }
                for dp in event.deviation_points
            ]
        if event.message is not None:
            payload["message"] = event.message

        data = await self._request("POST", path, json_data=payload)
        return AnomalyEventResponse(**data)

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "JavaApiClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
