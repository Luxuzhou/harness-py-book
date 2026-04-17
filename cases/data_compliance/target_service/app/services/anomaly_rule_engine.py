"""
异常规则引擎。

接受一批 lab_result / instrument 记录，按预配置的规则集做匹配，
触发的规则把 AnomalyRecord 写入 AnomalyRepository。

规则 DSL 类型：
- threshold：value 超过静态上下限
- relative：value 偏离历史均值 k * stdev
- pattern：连续 N 次异常 / 连续 N 次同方向漂移
- instrument_due：仪器到期未校准
- missing_field：必填字段缺失
- blacklist：值命中黑名单

规则可以通过 JSON/YAML 加载，也可以通过代码 register_rule 注册。
"""

from __future__ import annotations

import logging
import re
import statistics as stats_module
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional

from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.instrument_repository import InstrumentRepository
from app.repositories.lab_result_repository import LabResultRepository

logger = logging.getLogger(__name__)


RuleFunc = Callable[[Dict[str, Any], 'RuleContext'], Optional[Dict[str, Any]]]


@dataclass
class RuleContext:
    """规则执行时的上下文（可用于跨记录的统计判断）。"""
    lab_repo: Optional[LabResultRepository] = None
    instrument_repo: Optional[InstrumentRepository] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyRule:
    """
    一条异常规则的元信息。

    fields:
      rule_id     唯一 ID
      name        可读名称
      rule_type   threshold / relative / pattern / instrument_due /
                  missing_field / blacklist / custom
      target_type lab_result / instrument / patient / pathway
      severity    INFO / WARN / CRIT
      enabled     是否启用
      match_fn    实际执行逻辑；返回 anomaly dict 或 None
      config      规则配置（各类型 schema 不同）
    """
    rule_id: str
    name: str
    rule_type: str
    target_type: str
    severity: str
    enabled: bool
    match_fn: RuleFunc
    config: Dict[str, Any] = field(default_factory=dict)


class AnomalyRuleEngine:
    """异常规则引擎主对象。"""

    def __init__(
        self,
        anomaly_repo: AnomalyRepository,
        lab_repo: Optional[LabResultRepository] = None,
        instrument_repo: Optional[InstrumentRepository] = None,
    ):
        self.anomaly_repo = anomaly_repo
        self.lab_repo = lab_repo
        self.instrument_repo = instrument_repo
        self._rules: Dict[str, AnomalyRule] = {}

    # --- 规则注册 ---

    def register_rule(self, rule: AnomalyRule) -> None:
        if rule.rule_id in self._rules:
            logger.warning('replacing existing rule %s', rule.rule_id)
        self._rules[rule.rule_id] = rule

    def disable_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            return True
        return False

    def list_rules(self, target_type: Optional[str] = None) -> List[AnomalyRule]:
        rules = list(self._rules.values())
        if target_type:
            rules = [r for r in rules if r.target_type == target_type]
        return rules

    def load_from_config(self, config: List[Dict[str, Any]]) -> int:
        """
        从 JSON/dict 列表加载规则。

        每条 config 至少包含 rule_id, name, rule_type, target_type,
        severity 字段；其余字段进入 config dict。
        """
        count = 0
        for raw in config:
            try:
                rule = self._build_rule(raw)
                self.register_rule(rule)
                count += 1
            except Exception as e:
                logger.warning('skip rule %s: %s', raw.get('rule_id'), e)
        logger.info('loaded %d rules', count)
        return count

    def _build_rule(self, raw: Dict[str, Any]) -> AnomalyRule:
        rule_type = raw['rule_type']
        if rule_type == 'threshold':
            fn = _make_threshold_rule(raw)
        elif rule_type == 'relative':
            fn = _make_relative_rule(raw)
        elif rule_type == 'pattern':
            fn = _make_pattern_rule(raw)
        elif rule_type == 'instrument_due':
            fn = _make_instrument_due_rule(raw)
        elif rule_type == 'missing_field':
            fn = _make_missing_field_rule(raw)
        elif rule_type == 'blacklist':
            fn = _make_blacklist_rule(raw)
        else:
            raise ValueError(f'unknown rule_type: {rule_type}')
        return AnomalyRule(
            rule_id=raw['rule_id'],
            name=raw.get('name', raw['rule_id']),
            rule_type=rule_type,
            target_type=raw.get('target_type', 'lab_result'),
            severity=raw.get('severity', 'WARN'),
            enabled=raw.get('enabled', True),
            match_fn=fn,
            config={k: v for k, v in raw.items()
                    if k not in {'rule_id', 'name', 'rule_type',
                                 'target_type', 'severity', 'enabled'}},
        )

    # --- 执行 ---

    def evaluate_record(
        self,
        record: Dict[str, Any],
        target_type: str,
    ) -> List[Dict[str, Any]]:
        """对单条记录运行所有启用的对应目标类型规则，返回命中的异常列表。"""
        ctx = RuleContext(
            lab_repo=self.lab_repo,
            instrument_repo=self.instrument_repo,
        )
        triggered = []
        for rule in self._rules.values():
            if not rule.enabled or rule.target_type != target_type:
                continue
            try:
                hit = rule.match_fn(record, ctx)
            except Exception as e:
                logger.warning('rule %s raised %s', rule.rule_id, e)
                continue
            if hit is None:
                continue
            description = hit.get('description') or rule.name
            metadata = hit.get('metadata', {})
            anomaly = self.anomaly_repo.open_anomaly(
                rule_id=rule.rule_id,
                target_type=target_type,
                target_id=self._extract_target_id(record, target_type),
                severity=rule.severity,
                description=description,
                metadata={**metadata, 'record_snapshot': record},
            )
            triggered.append(anomaly)
        return triggered

    def evaluate_batch(
        self,
        records: Iterable[Dict[str, Any]],
        target_type: str,
    ) -> Dict[str, Any]:
        """批量评估。返回 (扫描条数, 触发条数, 按规则归组)。"""
        scanned = 0
        triggered = 0
        per_rule: Dict[str, int] = {}
        for r in records:
            scanned += 1
            hits = self.evaluate_record(r, target_type)
            triggered += len(hits)
            for h in hits:
                per_rule[h['rule_id']] = per_rule.get(h['rule_id'], 0) + 1
        return {
            'scanned': scanned,
            'triggered': triggered,
            'by_rule': per_rule,
        }

    @staticmethod
    def _extract_target_id(record: Dict[str, Any], target_type: str) -> str:
        if target_type == 'lab_result':
            return str(record.get('result_id', ''))
        if target_type == 'instrument':
            return str(record.get('department_id', record.get('instrument_id', '')))
        if target_type == 'patient':
            return str(record.get('patient_id', ''))
        if target_type == 'pathway':
            return str(record.get('pathway_id', ''))
        return str(record.get('id', ''))


# ---------- 规则构造器 ----------

def _make_threshold_rule(cfg: Dict[str, Any]) -> RuleFunc:
    field_name = cfg.get('field', 'value')
    step_code = cfg.get('step_code')
    low = cfg.get('low')
    high = cfg.get('high')

    def fn(rec: Dict[str, Any], ctx: RuleContext) -> Optional[Dict[str, Any]]:
        if step_code and rec.get('step_code') != step_code:
            return None
        v = rec.get(field_name)
        if not isinstance(v, (int, float)):
            return None
        if low is not None and v < low:
            return {
                'description': f'{field_name}={v} 低于下限 {low}',
                'metadata': {'value': v, 'low': low, 'high': high},
            }
        if high is not None and v > high:
            return {
                'description': f'{field_name}={v} 超过上限 {high}',
                'metadata': {'value': v, 'low': low, 'high': high},
            }
        return None
    return fn


def _make_relative_rule(cfg: Dict[str, Any]) -> RuleFunc:
    field_name = cfg.get('field', 'value')
    step_code = cfg.get('step_code')
    sigma = cfg.get('sigma', 3.0)
    min_samples = cfg.get('min_samples', 30)

    def fn(rec: Dict[str, Any], ctx: RuleContext) -> Optional[Dict[str, Any]]:
        if step_code and rec.get('step_code') != step_code:
            return None
        v = rec.get(field_name)
        if not isinstance(v, (int, float)) or not ctx.lab_repo:
            return None
        stats = ctx.lab_repo.value_statistics(
            step_code or rec.get('step_code', ''),
        )
        if stats.get('count', 0) < min_samples:
            return None
        mean = stats['mean']
        stdev = stats['stdev']
        if stdev == 0:
            return None
        z = (v - mean) / stdev
        if abs(z) >= sigma:
            direction = '偏高' if z > 0 else '偏低'
            return {
                'description': (
                    f'{field_name}={v} 相对均值 {mean} 偏离 {abs(round(z, 2))}σ'
                    f'（{direction}）'),
                'metadata': {'value': v, 'mean': mean, 'stdev': stdev,
                             'z_score': round(z, 3)},
            }
        return None
    return fn


def _make_pattern_rule(cfg: Dict[str, Any]) -> RuleFunc:
    """
    连续 N 次同向漂移 / 连续 N 次异常标志。

    cfg.pattern_type: consecutive_abnormal / consecutive_drift
    cfg.n: 连续次数阈值
    """
    pattern_type = cfg.get('pattern_type', 'consecutive_abnormal')
    n = cfg.get('n', 5)
    step_code = cfg.get('step_code')

    def fn(rec: Dict[str, Any], ctx: RuleContext) -> Optional[Dict[str, Any]]:
        if step_code and rec.get('step_code') != step_code:
            return None
        if not ctx.lab_repo:
            return None
        patient_id = rec.get('patient_id')
        if not patient_id:
            return None
        history = ctx.lab_repo.list_by_patient(patient_id)
        if len(history) < n:
            return None
        recent = history[:n]  # list_by_patient 已按 visit_date desc
        if pattern_type == 'consecutive_abnormal':
            all_abnormal = all(
                r.get('flag') and r['flag'] != 'N' for r in recent
            )
            if all_abnormal:
                return {
                    'description': f'连续 {n} 次检验标记为异常',
                    'metadata': {'pattern': pattern_type, 'n': n,
                                 'recent_flags': [r.get('flag') for r in recent]},
                }
        elif pattern_type == 'consecutive_drift':
            values = [r.get('value') for r in recent
                      if isinstance(r.get('value'), (int, float))]
            if len(values) < n:
                return None
            diffs = [values[i] - values[i + 1] for i in range(len(values) - 1)]
            if all(d > 0 for d in diffs) or all(d < 0 for d in diffs):
                direction = '上升' if diffs[0] > 0 else '下降'
                return {
                    'description': f'连续 {n} 次单调{direction}',
                    'metadata': {'pattern': pattern_type, 'n': n,
                                 'recent_values': values},
                }
        return None
    return fn


def _make_instrument_due_rule(cfg: Dict[str, Any]) -> RuleFunc:
    days_ahead = cfg.get('days_ahead', 7)

    def fn(rec: Dict[str, Any], ctx: RuleContext) -> Optional[Dict[str, Any]]:
        next_cal = rec.get('next_calibration')
        if not next_cal:
            return None
        try:
            d = datetime.strptime(str(next_cal)[:10], '%Y-%m-%d').date()
        except Exception:
            return None
        today = datetime.now().date()
        delta = (d - today).days
        if delta < 0:
            return {
                'description': f'仪器校准已过期 {-delta} 天',
                'metadata': {'next_calibration': str(next_cal), 'overdue_days': -delta},
            }
        if delta <= days_ahead:
            return {
                'description': f'仪器将在 {delta} 天内到期',
                'metadata': {'next_calibration': str(next_cal), 'days_left': delta},
            }
        return None
    return fn


def _make_missing_field_rule(cfg: Dict[str, Any]) -> RuleFunc:
    required_fields: List[str] = cfg.get('fields', [])

    def fn(rec: Dict[str, Any], ctx: RuleContext) -> Optional[Dict[str, Any]]:
        missing = [f for f in required_fields
                   if not rec.get(f) and rec.get(f) != 0]
        if missing:
            return {
                'description': f'必填字段缺失：{", ".join(missing)}',
                'metadata': {'missing_fields': missing},
            }
        return None
    return fn


def _make_blacklist_rule(cfg: Dict[str, Any]) -> RuleFunc:
    field_name = cfg.get('field', 'value')
    blacklist = set(cfg.get('values', []))
    regex_str = cfg.get('regex')
    regex = re.compile(regex_str) if regex_str else None

    def fn(rec: Dict[str, Any], ctx: RuleContext) -> Optional[Dict[str, Any]]:
        v = rec.get(field_name)
        if v in blacklist:
            return {
                'description': f'{field_name}={v} 命中黑名单',
                'metadata': {'value': v, 'blacklist_hit': True},
            }
        if regex and isinstance(v, str) and regex.search(v):
            return {
                'description': f'{field_name}={v} 命中正则黑名单 {regex_str}',
                'metadata': {'value': v, 'regex_hit': True},
            }
        return None
    return fn


# ---------- 预置规则集 ----------

DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        'rule_id': 'LR-TP-HIGH',
        'name': '总蛋白超高',
        'rule_type': 'threshold',
        'target_type': 'lab_result',
        'severity': 'WARN',
        'field': 'value', 'step_code': 'TP', 'low': None, 'high': 85,
    },
    {
        'rule_id': 'LR-TP-LOW',
        'name': '总蛋白偏低',
        'rule_type': 'threshold',
        'target_type': 'lab_result',
        'severity': 'WARN',
        'field': 'value', 'step_code': 'TP', 'low': 55, 'high': None,
    },
    {
        'rule_id': 'LR-ALT-HIGH',
        'name': '丙氨酸氨基转移酶显著升高',
        'rule_type': 'threshold',
        'target_type': 'lab_result',
        'severity': 'CRIT',
        'field': 'value', 'step_code': 'ALT', 'low': None, 'high': 200,
    },
    {
        'rule_id': 'LR-DRIFT',
        'name': '连续5次同向漂移',
        'rule_type': 'pattern',
        'target_type': 'lab_result',
        'severity': 'WARN',
        'pattern_type': 'consecutive_drift', 'n': 5,
    },
    {
        'rule_id': 'LR-RELATIVE',
        'name': '相对均值 3σ 偏离',
        'rule_type': 'relative',
        'target_type': 'lab_result',
        'severity': 'WARN',
        'sigma': 3.0, 'min_samples': 30,
    },
    {
        'rule_id': 'INS-DUE',
        'name': '仪器即将到期',
        'rule_type': 'instrument_due',
        'target_type': 'instrument',
        'severity': 'WARN',
        'days_ahead': 7,
    },
    {
        'rule_id': 'LR-MISSING',
        'name': '检验结果必填字段缺失',
        'rule_type': 'missing_field',
        'target_type': 'lab_result',
        'severity': 'INFO',
        'fields': ['patient_id', 'step_code', 'value', 'unit'],
    },
]


def load_default_rules(engine: AnomalyRuleEngine) -> int:
    return engine.load_from_config(DEFAULT_RULES)
