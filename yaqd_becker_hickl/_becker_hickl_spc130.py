__all__ = ["BeckerHicklSpc130"]

import asyncio
from typing import Dict, Any, List, TYPE_CHECKING
from ctypes import (
    byref,
    c_char_p,
    c_long,
    c_float,
    c_short,
    create_string_buffer,
    Structure,
)

if not TYPE_CHECKING:
    from ctypes import WinDLL
else:
    WinDLL = None  # type: ignore

import numpy as np
from yaqd_core import HasMapping, HasMeasureTrigger, IsSensor, IsDaemon

COLLECT_TIME = 15
TAC_RANGE = 8
TAC_GAIN = 9
FREQ_DIV = 5
RATE_COUNT_TIME = 40
ADC_RESOLUTION = 13


class MEM_INFO(Structure):
    _fields_ = [
        ("max_block_no", c_long),
        ("blocks_per_frame", c_long),
        ("frames_per_page", c_long),
        ("maxpage", c_long),
        ("block_length", c_long),
    ]

    def __repr__(self):
        return "\n".join(
            f"{field_name}: {getattr(self, field_name)}" for field_name, _ in self._fields_
        )


class RATE_VALUES(Structure):
    _fields_ = [("sync", c_float), ("cfd", c_float), ("tac", c_float), ("adc", c_float)]

    def __repr__(self):
        return "\n".join(
            f"{field_name}: {getattr(self, field_name)}" for field_name, _ in self._fields_
        )


class BeckerHicklSpc130(HasMapping, HasMeasureTrigger, IsSensor, IsDaemon):
    _kind = "becker-hickl-spc130"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        # TODO Config handle?
        self.handle = c_short(0)
        # TODO maybe try search paths instead of hard coded
        self.dll = WinDLL(r"C:\Program Files (x86)\BH\SPCM\DLL\spcm64.dll")

        ini_path = config["ini_file_path"]
        ini_p = c_char_p(ini_path.encode())
        err = self.dll.SPC_init(ini_p)
        self.handle_error(err)

        self.mem_info = MEM_INFO()
        err = self.dll.SPC_configure_memory(0, -1, 0, byref(self.mem_info))
        self.handle_error(err)
        self.size = (
            self.mem_info.blocks_per_frame
            * self.mem_info.frames_per_page
            * self.mem_info.block_length
        )
        err = self.dll.SPC_set_page(-1, 0)
        self.handle_error(err)

        self._channel_names = ["histogram", "sync_rate", "cfd_rate", "tac_rate", "adc_rate"]
        self._channel_mappings = {"histogram": ["time"]}
        self._compute_mapping()
        self._mapping_units = {"time": "ns"}
        self._channel_units = {
            "histogram": "counts",
            "sync_rate": "counts/sec",
            "cfd_rate": "counts/sec",
            "tac_rate": "counts/sec",
            "adc_rate": "counts/sec",
        }
        self._channel_shapes = {
            "histogram": (self.size,),
            "sync_rate": (),
            "cfd_rate": (),
            "tac_rate": (),
            "adc_rate": (),
        }

    def handle_error(self, errno, raise_=True):
        if errno != 0:
            errmsg = create_string_buffer(100)
            self.dll.SPC_get_error_string(errno, byref(errmsg), 99)
            self.logger.error(f"{errno}: {errmsg.value.decode()}")
            if raise_:
                raise RuntimeError(f"{errno}: {errmsg.value.decode()}")

    def _compute_mapping(self):
        tac_range = self.get_tac_range()
        tac_gain = self.get_tac_gain()
        self._mappings = {"time": np.linspace(0, tac_range / tac_gain, self.size)}

    async def _measure(self):
        err = self.dll.SPC_fill_memory(self.handle, 0, 0, 0)
        self.handle_error(err, raise_=False)
        # Wait for memory fill to complete
        await self._wait_for_status(0x8000)

        err = self.dll.SPC_clear_rates(self.handle)
        self.handle_error(err, raise_=False)
        err = self.dll.SPC_start_measurement(self.handle)
        self.handle_error(err, raise_=False)

        rate_vals = RATE_VALUES()
        # Ensure rates are done reading
        while self.dll.SPC_read_rates(self.handle, byref(rate_vals)) == -30:
            await asyncio.sleep(0.1)
        # Ensure histogram is done collecting
        await self._wait_for_status(0x80)

        arr = np.zeros(self.size, dtype="<H")
        err = self.dll.SPC_read_data_page(self.handle, 0, 0, byref(np.ctypeslib.as_ctypes(arr)))
        self.handle_error(err, raise_=False)

        return {
            "histogram": arr,
            "sync_rate": rate_vals.sync,
            "cfd_rate": rate_vals.cfd,
            "tac_rate": rate_vals.tac,
            "adc_rate": rate_vals.adc,
        }

    async def _wait_for_status(self, mask):
        state = c_short(0)
        masked_state = mask
        while masked_state:
            err = self.dll.SPC_test_state(self.handle, byref(state))
            self.handle_error(err, raise_=False)
            masked_state = mask & state.value
            await asyncio.sleep(0.1)

    def get_collect_time(self) -> float:
        f = c_float(0)
        err = self.dll.SPC_get_parameter(self.handle, COLLECT_TIME, byref(f))
        self.handle_error(err)
        return f.value

    def set_collect_time(self, time: float):
        err = self.dll.SPC_set_parameter(self.handle, COLLECT_TIME, c_float(time))
        self.handle_error(err)

    def get_collect_time_units(self) -> str:
        return "s"

    def get_collect_time_limits(self) -> List[float]:
        return [0.0001, 100000.0]

    def get_tac_range(self) -> float:
        f = c_float(0)
        err = self.dll.SPC_get_parameter(self.handle, TAC_RANGE, byref(f))
        self.handle_error(err)
        return f.value

    def set_tac_range(self, time: float):
        err = self.dll.SPC_set_parameter(self.handle, TAC_RANGE, c_float(time))
        self.handle_error(err)
        self._compute_mapping()

    def get_tac_range_units(self) -> str:
        return "ns"

    def get_tac_range_limits(self) -> List[float]:
        return [50.0, 5000.0]

    def get_tac_gain(self) -> int:
        f = c_float(0)
        err = self.dll.SPC_get_parameter(self.handle, TAC_GAIN, byref(f))
        self.handle_error(err)
        return int(f.value)

    def set_tac_gain(self, gain: int):
        err = self.dll.SPC_set_parameter(self.handle, TAC_GAIN, c_float(float(gain)))
        self.handle_error(err)
        self._compute_mapping()

    def get_tac_gain_limits(self) -> List[int]:
        return [1, 15]

    def get_freq_div(self) -> str:
        f = c_float(0)
        err = self.dll.SPC_get_parameter(self.handle, FREQ_DIV, byref(f))
        self.handle_error(err)
        for i in self.get_freq_div_options():
            if abs(f.value - float(i)) < 0.01:
                return i
        raise ValueError(f"Unknown frequency_divisor time {int(f.value)}")

    def set_freq_div(self, divisor: str):
        if divisor not in self.get_freq_div_options():
            raise ValueError(f"{divisor} not in {self.get_freq_div_options()}")
        err = self.dll.SPC_set_parameter(self.handle, FREQ_DIV, c_float(float(divisor)))
        self.handle_error(err)

    def get_freq_div_options(self) -> List[str]:
        return ["1", "2", "4"]

    def get_rate_count_time(self) -> str:
        f = c_float(0)
        err = self.dll.SPC_get_parameter(self.handle, RATE_COUNT_TIME, byref(f))
        self.handle_error(err)
        for i in self.get_rate_count_time_options():
            if abs(f.value - float(i)) < 0.01:
                return i
        raise ValueError(f"Unknown rate count time {f.value}")

    def set_rate_count_time(self, time: str):
        if time not in self.get_rate_count_time_options():
            raise ValueError(f"{time} not in {self.get_rate_count_time_options()}")
        err = self.dll.SPC_set_parameter(self.handle, RATE_COUNT_TIME, c_float(float(time)))
        self.handle_error(err)

    def get_rate_count_time_options(self) -> List[str]:
        return ["0.05", "0.1", "0.25", "1.0"]
