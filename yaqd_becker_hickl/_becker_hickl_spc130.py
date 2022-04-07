__all__ = ["BeckerHicklSpc130"]

import asyncio
from typing import Dict, Any, List

from yaqd_core import IsDaemon


class BeckerHicklSpc130(IsDaemon):
    _kind = "becker-hickl-spc130"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        ...

    async def _measure(self):
        ...

    def get_collect_time(self) -> float:
        return ...

    def set_collect_time(self, time: float):
        ...

    def get_collect_time_units(self) -> str:
        return "s"

    def get_collect_time_limits(self) -> List[float]:
        return [0.0001, 100000.0]

    def get_tac_range(self) -> float:
        return ...

    def set_tac_range(self, time: float):
        ...

    def get_tac_range_units(self) -> str:
        return "ns"

    def get_tac_range_limits(self) -> List[float]:
        return [50.0, 5000.0]

    def get_tac_gain(self) -> int:
        return ...

    def set_tac_gain(self, gain: int):
        ...

    def get_tac_gain_limits(self) -> List[int]:
        return [1, 15]

    def get_freq_div(self) -> str:
        return ...

    def set_freq_div(self, divisor: str):
        if divisor not in self.get_freq_div_options():
            raise ValueError(f"{divisor} not in {self.get_freq_div_options()}")

    def get_freq_div_options(self) -> List[str]:
        return ["1", "2", "4"]

    def get_rate_count_time(self) -> str:
        return ...

    def set_rate_count_time(self, time: str):
        if time not in self.get_rate_count_time_options():
            raise ValueError(f"{time} not in {self.get_rate_count_time_options()}")

    def get_rate_count_time_options(self) -> List[str]:
        return ["0.05", "0.1", "0.25", "1.0"]
