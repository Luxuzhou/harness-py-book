"""
异常告警推送服务。

接受 AnomalyRecord，按通知策略分发到多个通道：
- log：结构化 JSONL 日志
- webhook：HTTP 回调（合规案例默认关闭，需通过策略开启）
- queue：本地队列（测试用）

策略按严重度与规则 ID 匹配。
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class NotificationChannel:
    """一个通知通道的声明。"""
    name: str
    kind: str  # log / webhook / queue / custom
    enabled: bool = True
    severities: Set[str] = field(default_factory=lambda: {'WARN', 'CRIT'})
    rule_filter: Optional[Set[str]] = None
    config: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable[[Dict[str, Any]], bool]] = None


class AnomalyNotifier:
    """
    异常告警调度器。

    典型用法：
        notifier = AnomalyNotifier(log_dir=Path('notifications'))
        notifier.add_channel(NotificationChannel('log', kind='log'))
        notifier.dispatch(anomaly_record)
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        default_channels: bool = True,
    ):
        self._channels: Dict[str, NotificationChannel] = {}
        self._local_queue: 'queue.Queue[Dict[str, Any]]' = queue.Queue()
        self._lock = threading.Lock()
        self._stats: Dict[str, int] = {
            'dispatched': 0,
            'filtered': 0,
            'failed': 0,
        }
        self.log_dir = log_dir
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
        if default_channels:
            self._install_default_channels()

    def _install_default_channels(self) -> None:
        self.add_channel(NotificationChannel(
            name='log_all', kind='log', enabled=True,
            severities={'INFO', 'WARN', 'CRIT'},
        ))
        self.add_channel(NotificationChannel(
            name='local_queue', kind='queue', enabled=True,
            severities={'WARN', 'CRIT'},
            handler=lambda ev: self._enqueue_local(ev),
        ))

    # --- 通道管理 ---

    def add_channel(self, channel: NotificationChannel) -> None:
        with self._lock:
            self._channels[channel.name] = channel

    def remove_channel(self, name: str) -> bool:
        with self._lock:
            return self._channels.pop(name, None) is not None

    def enable(self, name: str) -> bool:
        with self._lock:
            if name in self._channels:
                self._channels[name].enabled = True
                return True
            return False

    def disable(self, name: str) -> bool:
        with self._lock:
            if name in self._channels:
                self._channels[name].enabled = False
                return True
            return False

    def list_channels(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': c.name,
                'kind': c.kind,
                'enabled': c.enabled,
                'severities': sorted(c.severities),
                'rule_filter': sorted(c.rule_filter) if c.rule_filter else None,
            }
            for c in self._channels.values()
        ]

    # --- 分发 ---

    def dispatch(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        """
        分发一条异常记录到所有匹配的通道。

        返回 {channel_name: ok/failed/filtered}。
        """
        result: Dict[str, Any] = {}
        sev = anomaly.get('severity', 'INFO')
        rule_id = anomaly.get('rule_id', '')
        payload = self._build_payload(anomaly)

        with self._lock:
            channels = list(self._channels.values())

        for ch in channels:
            if not ch.enabled:
                result[ch.name] = 'disabled'
                continue
            if sev not in ch.severities:
                result[ch.name] = 'filtered_severity'
                self._stats['filtered'] += 1
                continue
            if ch.rule_filter is not None and rule_id not in ch.rule_filter:
                result[ch.name] = 'filtered_rule'
                self._stats['filtered'] += 1
                continue
            try:
                ok = self._deliver(ch, payload)
                if ok:
                    result[ch.name] = 'ok'
                    self._stats['dispatched'] += 1
                else:
                    result[ch.name] = 'failed'
                    self._stats['failed'] += 1
            except Exception as e:
                logger.warning('channel %s delivery raised: %s', ch.name, e)
                result[ch.name] = f'exception: {type(e).__name__}'
                self._stats['failed'] += 1
        return result

    def dispatch_batch(self, anomalies: List[Dict[str, Any]]) -> Dict[str, int]:
        for a in anomalies:
            self.dispatch(a)
        return dict(self._stats)

    # --- 通道 handler ---

    def _deliver(self, channel: NotificationChannel, payload: Dict[str, Any]) -> bool:
        if channel.kind == 'log':
            return self._deliver_log(channel, payload)
        if channel.kind == 'webhook':
            return self._deliver_webhook(channel, payload)
        if channel.kind == 'queue':
            if channel.handler:
                return channel.handler(payload)
            return self._enqueue_local(payload)
        if channel.kind == 'custom':
            if channel.handler:
                return bool(channel.handler(payload))
            return False
        return False

    def _deliver_log(self, channel: NotificationChannel, payload: Dict[str, Any]) -> bool:
        if not self.log_dir:
            logger.info('[notify:%s] %s', channel.name,
                         json.dumps(payload, ensure_ascii=False, default=str))
            return True
        path = self.log_dir / f'notify-{datetime.now().strftime("%Y-%m-%d")}.jsonl'
        try:
            with path.open('a', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
                f.write('\n')
            return True
        except OSError as e:
            logger.warning('log deliver failed: %s', e)
            return False

    def _deliver_webhook(
        self,
        channel: NotificationChannel,
        payload: Dict[str, Any],
    ) -> bool:
        """
        本案例默认网络隔离——webhook 只在配置显式开启时尝试。

        真实实现会使用 requests / httpx 发送 POST；这里只做占位，
        避免在合规沙箱中意外外联。
        """
        if not channel.config.get('allow_network', False):
            logger.info('webhook %s skipped (network isolated)', channel.name)
            return True
        url = channel.config.get('url')
        if not url:
            return False
        # 不实际发起请求——只记录意图
        logger.info('[webhook] would POST to %s with payload %s',
                     url, json.dumps(payload, ensure_ascii=False, default=str))
        return True

    def _enqueue_local(self, payload: Dict[str, Any]) -> bool:
        self._local_queue.put(payload)
        return True

    def _build_payload(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'notified_at': datetime.now().isoformat(),
            'anomaly_id': anomaly.get('anomaly_id'),
            'rule_id': anomaly.get('rule_id'),
            'severity': anomaly.get('severity'),
            'target_type': anomaly.get('target_type'),
            'target_id': anomaly.get('target_id'),
            'description': anomaly.get('description'),
        }

    # --- 本地队列消费接口 ---

    def poll_local(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        try:
            return self._local_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_local(self) -> List[Dict[str, Any]]:
        out = []
        while True:
            item = self.poll_local(timeout=0.01)
            if item is None:
                break
            out.append(item)
        return out

    def statistics(self) -> Dict[str, Any]:
        return {
            **dict(self._stats),
            'local_queue_size': self._local_queue.qsize(),
            'channels': self.list_channels(),
        }
