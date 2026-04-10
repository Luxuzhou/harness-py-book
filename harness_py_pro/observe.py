"""
可观测性
========
对标OpenHarness的insights + Hermes的usage_pricing。
结构化日志 + 运行时指标 + Session分析。

三个组件：
1. Logger — 结构化事件日志
2. Metrics — 运行时指标收集
3. SessionAnalyzer — 事后Session分析
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


# ============ 结构化日志 ============

class Logger:
    """
    结构化事件日志。

    所有事件写入jsonl文件，支持：
    - 工具调用追踪
    - 压缩事件
    - 错误记录
    - 性能计时
    """

    def __init__(self, log_dir: Path, session_id: str):
        self.log_dir = log_dir
        self.session_id = session_id
        self._path = log_dir / f'{session_id}.log.jsonl'
        self._lock = threading.Lock()
        log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, data: dict | None = None, level: str = 'info'):
        """写入一条日志。"""
        entry = {
            'ts': time.time(),
            'session': self.session_id[:12],
            'level': level,
            'event': event_type,
        }
        if data:
            entry['data'] = data
        try:
            with self._lock:
                with open(self._path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
        except OSError:
            pass

    def tool_start(self, tool_name: str, args: dict):
        self.log('tool_start', {'tool': tool_name, 'args_keys': list(args.keys())})

    def tool_end(self, tool_name: str, ok: bool, duration_ms: float, result_len: int):
        self.log('tool_end', {
            'tool': tool_name, 'ok': ok,
            'duration_ms': round(duration_ms, 1),
            'result_len': result_len,
        })

    def api_call(self, model: str, input_tokens: int, output_tokens: int, duration_ms: float):
        self.log('api_call', {
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'duration_ms': round(duration_ms, 1),
        })

    def compress(self, level: str, before_tokens: int, after_tokens: int):
        self.log('compress', {
            'level': level,
            'before': before_tokens,
            'after': after_tokens,
            'reduction_pct': round((1 - after_tokens / max(before_tokens, 1)) * 100, 1),
        })

    def guard_intervene(self, reason: str):
        self.log('guard', {'reason': reason}, level='warn')

    def hook_block(self, tool_name: str, reason: str):
        self.log('hook_block', {'tool': tool_name, 'reason': reason}, level='warn')

    def error(self, message: str, detail: str = ''):
        self.log('error', {'message': message, 'detail': detail[:500]}, level='error')


# ============ 运行时指标 ============

@dataclass
class Metrics:
    """
    运行时指标收集器。

    收集Agent运行期间的关键指标，用于事后分析。
    """
    # API指标
    api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    api_errors: int = 0
    api_total_latency_ms: float = 0.0

    # 工具指标
    tool_calls: int = 0
    tool_errors: int = 0
    tool_total_latency_ms: float = 0.0
    tool_by_name: dict[str, int] = field(default_factory=dict)

    # 压缩指标
    compressions: int = 0
    tokens_saved: int = 0

    # Guard指标
    guard_interventions: int = 0

    # Hook指标
    hook_blocks: int = 0
    hook_warnings: int = 0

    # 时间
    start_time: float = 0.0
    end_time: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_api_call(self, input_tokens: int, output_tokens: int, latency_ms: float):
        with self._lock:
            self.api_calls += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.api_total_latency_ms += latency_ms

    def record_tool_call(self, tool_name: str, ok: bool, latency_ms: float):
        with self._lock:
            self.tool_calls += 1
            if not ok:
                self.tool_errors += 1
            self.tool_total_latency_ms += latency_ms
            self.tool_by_name[tool_name] = self.tool_by_name.get(tool_name, 0) + 1

    def record_compression(self, tokens_before: int, tokens_after: int):
        with self._lock:
            self.compressions += 1
            self.tokens_saved += tokens_before - tokens_after

    @property
    def duration_seconds(self) -> float:
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def avg_api_latency_ms(self) -> float:
        return self.api_total_latency_ms / max(self.api_calls, 1)

    @property
    def avg_tool_latency_ms(self) -> float:
        return self.tool_total_latency_ms / max(self.tool_calls, 1)

    def summary(self) -> dict:
        with self._lock:
            return {
                'duration_seconds': round(self.duration_seconds, 1),
                'api': {
                    'calls': self.api_calls,
                    'input_tokens': self.total_input_tokens,
                    'output_tokens': self.total_output_tokens,
                    'errors': self.api_errors,
                    'avg_latency_ms': round(self.avg_api_latency_ms, 1),
                },
                'tools': {
                    'calls': self.tool_calls,
                    'errors': self.tool_errors,
                    'avg_latency_ms': round(self.avg_tool_latency_ms, 1),
                    'by_name': dict(sorted(self.tool_by_name.items(), key=lambda x: -x[1])),
                },
                'compression': {
                    'count': self.compressions,
                    'tokens_saved': self.tokens_saved,
                },
                'guard_interventions': self.guard_interventions,
                'hook_blocks': self.hook_blocks,
            }

    def format_report(self) -> str:
        s = self.summary()
        lines = [
            f'运行指标:',
            f'  时长: {s["duration_seconds"]}s',
            f'  API: {s["api"]["calls"]} calls, '
            f'in={s["api"]["input_tokens"]:,} out={s["api"]["output_tokens"]:,} '
            f'avg={s["api"]["avg_latency_ms"]:.0f}ms',
            f'  工具: {s["tools"]["calls"]} calls ({s["tools"]["errors"]} errors) '
            f'avg={s["tools"]["avg_latency_ms"]:.0f}ms',
        ]
        if s['tools']['by_name']:
            top = list(s['tools']['by_name'].items())[:5]
            lines.append(f'    Top: {", ".join(f"{n}={c}" for n, c in top)}')
        if s['compression']['count']:
            lines.append(f'  压缩: {s["compression"]["count"]}次 节省{s["compression"]["tokens_saved"]:,} tokens')
        if s['guard_interventions']:
            lines.append(f'  Guard介入: {s["guard_interventions"]}次')
        if s['hook_blocks']:
            lines.append(f'  Hook拦截: {s["hook_blocks"]}次')
        return '\n'.join(lines)


# ============ Session分析 ============

class SessionAnalyzer:
    """
    事后Session分析器。

    读取jsonl日志，生成分析报告。
    """

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._events: list[dict] = []

    def load(self):
        """加载日志文件。"""
        if not self.log_path.exists():
            return
        for line in self.log_path.read_text(encoding='utf-8').splitlines():
            try:
                self._events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def analyze(self) -> dict:
        """分析Session。"""
        if not self._events:
            self.load()

        api_calls = [e for e in self._events if e.get('event') == 'api_call']
        tool_calls = [e for e in self._events if e.get('event') == 'tool_end']
        compressions = [e for e in self._events if e.get('event') == 'compress']
        errors = [e for e in self._events if e.get('level') == 'error']
        warnings = [e for e in self._events if e.get('level') == 'warn']

        # 时间跨度
        timestamps = [e.get('ts', 0) for e in self._events if e.get('ts')]
        duration = max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 0

        # 工具使用分布
        tool_dist: dict[str, int] = {}
        for tc in tool_calls:
            name = tc.get('data', {}).get('tool', 'unknown')
            tool_dist[name] = tool_dist.get(name, 0) + 1

        # 工具耗时分布
        tool_latency: dict[str, list[float]] = {}
        for tc in tool_calls:
            name = tc.get('data', {}).get('tool', 'unknown')
            lat = tc.get('data', {}).get('duration_ms', 0)
            tool_latency.setdefault(name, []).append(lat)

        return {
            'total_events': len(self._events),
            'duration_seconds': round(duration, 1),
            'api_calls': len(api_calls),
            'tool_calls': len(tool_calls),
            'compressions': len(compressions),
            'errors': len(errors),
            'warnings': len(warnings),
            'tool_distribution': dict(sorted(tool_dist.items(), key=lambda x: -x[1])),
            'tool_avg_latency': {
                name: round(sum(lats) / len(lats), 1)
                for name, lats in tool_latency.items()
            },
            'total_input_tokens': sum(e.get('data', {}).get('input_tokens', 0) for e in api_calls),
            'total_output_tokens': sum(e.get('data', {}).get('output_tokens', 0) for e in api_calls),
        }

    def format_report(self) -> str:
        a = self.analyze()
        lines = [
            f'Session分析:',
            f'  事件总数: {a["total_events"]}',
            f'  时长: {a["duration_seconds"]}s',
            f'  API调用: {a["api_calls"]}',
            f'  工具调用: {a["tool_calls"]}',
            f'  压缩: {a["compressions"]}次',
            f'  错误: {a["errors"]} 警告: {a["warnings"]}',
            f'  Tokens: in={a["total_input_tokens"]:,} out={a["total_output_tokens"]:,}',
        ]
        if a['tool_distribution']:
            lines.append(f'  工具分布:')
            for name, count in list(a['tool_distribution'].items())[:8]:
                avg_lat = a['tool_avg_latency'].get(name, 0)
                lines.append(f'    {name}: {count}次 (avg {avg_lat:.0f}ms)')
        return '\n'.join(lines)
