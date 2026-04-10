from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class CostTracker:
    total_units: int = 0
    events: list[str] = field(default_factory=list)

    def record(self, label: str, units: int) -> None:
        self.total_units += units
        self.events.append(f'{label}:{units}')
    
    def summary(self) -> dict[str, int]:
        """返回按标签分类的总消耗统计"""
        result: dict[str, int] = {}
        for event in self.events:
            if ':' in event:
                label, units_str = event.split(':', 1)
                try:
                    units = int(units_str)
                    result[label] = result.get(label, 0) + units
                except ValueError:
                    # 忽略格式错误的记录
                    continue
        return result
