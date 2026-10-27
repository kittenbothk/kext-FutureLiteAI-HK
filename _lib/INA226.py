import board
from micropython import const

__version__ = "1.3.0"

# INA226 寄存器地址
_INA226_ADDRESS = const(0x40)
_INA226_CONF_REG = const(0x00)
_INA226_SHUNT_REG = const(0x01)
_INA226_BUS_REG = const(0x02)
_INA226_PWR_REG = const(0x03)
_INA226_CURRENT_REG = const(0x04)
_INA226_CAL_REG = const(0x05)
_INA226_MASK_EN_REG = const(0x06)
_INA226_ALERT_LIMIT_REG = const(0x07)
_INA226_MAN_ID_REG = const(0xFE)
_INA226_ID_REG = const(0xFF)

# 芯片识别值
_INA226_MAN_ID = const(0x5449)
_INA226_DIE_ID = const(0x226)

# 固定测量参数
_SHUNT_VOLTAGE_LSB_V = 0.0000025
_SHUNT_VOLTAGE_FULL_SCALE_V = 0.08192
_BUS_VOLTAGE_LSB_V = 0.00125
_CALIBRATION_FACTOR = 0.00512
_CALIBRATION_MAX = const(0x7FFF)

# 配置寄存器位
_INA226_RST = const(0x8000)
_INA226_AVG_MASK = const(0x0E00)
_INA226_VBUS_CT_MASK = const(0x01C0)
_INA226_VSH_CT_MASK = const(0x0038)
_INA226_MODE_MASK = const(0x0007)
_INA226_CVRF = const(0x0008)
_INA226_OVF = const(0x0004)

# 平均模式
AVERAGE_1 = const(0x0000)
AVERAGE_4 = const(0x0200)
AVERAGE_16 = const(0x0400)
AVERAGE_64 = const(0x0600)
AVERAGE_128 = const(0x0800)
AVERAGE_256 = const(0x0A00)
AVERAGE_512 = const(0x0C00)
AVERAGE_1024 = const(0x0E00)

# 转换时间编码（对应 140、204、332、588、1100、2116、4156、8244 µs）
CONV_TIME_140 = const(0)
CONV_TIME_204 = const(1)
CONV_TIME_332 = const(2)
CONV_TIME_588 = const(3)
CONV_TIME_1100 = const(4)
CONV_TIME_2116 = const(5)
CONV_TIME_4156 = const(6)
CONV_TIME_8244 = const(7)

# 测量模式
POWER_DOWN = const(0)
SHUNT_TRIGGERED = const(1)
BUS_TRIGGERED = const(2)
TRIGGERED = const(3)
SHUNT_CONTINUOUS = const(5)
BUS_CONTINUOUS = const(6)
CONTINUOUS = const(7)

__all__ = (
    "INA226",
    "AVERAGE_1", "AVERAGE_4", "AVERAGE_16", "AVERAGE_64",
    "AVERAGE_128", "AVERAGE_256", "AVERAGE_512", "AVERAGE_1024",
    "CONV_TIME_140", "CONV_TIME_204", "CONV_TIME_332", "CONV_TIME_588",
    "CONV_TIME_1100", "CONV_TIME_2116", "CONV_TIME_4156", "CONV_TIME_8244",
    "POWER_DOWN", "SHUNT_TRIGGERED", "BUS_TRIGGERED", "TRIGGERED",
    "SHUNT_CONTINUOUS", "BUS_CONTINUOUS", "CONTINUOUS",
)


class INA226:
    """INA226 电流、电压和功率监测器的 MicroPython 驱动。"""

    def __init__(self, address=_INA226_ADDRESS, shunt_resistor=0.1,
                 max_expected_current=0.8, i2c=None, i2c_retries=1,
                 averages=AVERAGE_64, current_deadband_ma=0.05):
        """
        Args:
            address: 7 位 I2C 地址；默认 0x40，传入 None 时自动识别。
            shunt_resistor: 分流电阻，单位 Ω。
            max_expected_current: 最大预期电流绝对值，单位 A。
            i2c: I2C 对象；默认使用 board.i2c。
            i2c_retries: I2C 失败后的重试次数。
            averages: 硬件平均采样次数；默认 64 次。
            current_deadband_ma: 电流显示迟滞，单位 mA；默认 0.05 mA。
        """
        if not isinstance(i2c_retries, int) or i2c_retries < 0:
            raise ValueError("i2c_retries must be a non-negative integer")

        if averages not in (AVERAGE_1, AVERAGE_4, AVERAGE_16, AVERAGE_64,
                            AVERAGE_128, AVERAGE_256, AVERAGE_512,
                            AVERAGE_1024):
            raise ValueError("invalid averaging setting")
        if current_deadband_ma < 0:
            raise ValueError("current_deadband_ma must not be negative")

        self._i2c = board.i2c if i2c is None else i2c
        self._i2c_retries = i2c_retries
        self._addr = address
        self._reg = bytearray(1)
        self._buf2 = bytearray(2)
        self._buf3 = bytearray(3)
        self._mode_before_power_down = CONTINUOUS
        self._averages = averages
        self._current_deadband_ma = current_deadband_ma
        self._stable_current_ma = None

        self._shunt_resistor = 0.0
        self._max_expected_current = 0.0
        self._current_lsb_a = 0.0
        self._power_lsb_w = 0.0
        self._cal_val = 0

        self._validate_address(address)
        self._validate_measurement_parameters(shunt_resistor,
                                              max_expected_current)
        self.init(shunt_resistor, max_expected_current)

    def init(self, shunt_resistor=None, max_expected_current=None):
        """识别并初始化芯片；通信失败时抛出 OSError。"""
        if self._addr is None:
            self._addr = self._find_address()
        else:
            self._check_device(self._addr)

        if shunt_resistor is None:
            shunt_resistor = self._shunt_resistor
        if max_expected_current is None:
            max_expected_current = self._max_expected_current

        self.reset()
        self.set_average(self._averages)
        self.configure_measurement(shunt_resistor, max_expected_current)
        return True

    @property
    def address(self):
        return self._addr

    @property
    def shunt_resistor(self):
        return self._shunt_resistor

    @property
    def max_expected_current(self):
        return self._max_expected_current

    @property
    def current_lsb_a(self):
        return self._current_lsb_a

    @property
    def power_lsb_w(self):
        return self._power_lsb_w

    @property
    def calibration_value(self):
        return self._cal_val

    @property
    def physical_current_limit_a(self):
        """由 INA226 分流输入范围和分流电阻决定的理论电流上限。"""
        return _SHUNT_VOLTAGE_FULL_SCALE_V / self._shunt_resistor

    def _validate_address(self, address):
        if address is not None and (not isinstance(address, int) or
                                    address < 0x08 or address > 0x77):
            raise ValueError("address must be a 7-bit I2C address")

    def _validate_measurement_parameters(self, resistor, current_range):
        if resistor is None or resistor <= 0:
            raise ValueError("shunt_resistor must be greater than 0")
        if current_range is None or current_range <= 0:
            raise ValueError("max_expected_current must be greater than 0")

        physical_limit = _SHUNT_VOLTAGE_FULL_SCALE_V / resistor
        if current_range > physical_limit * 1.000001:
            raise ValueError(
                "max_expected_current %.6g A exceeds the %.6g A limit "
                "for a %.6g ohm shunt" %
                (current_range, physical_limit, resistor)
            )

    def _find_address(self):
        """扫描 0x40～0x4F，并通过制造商 ID 和芯片 ID 识别器件。"""
        try:
            scan = self._i2c.scan
        except AttributeError:
            found = None
            candidates = [_INA226_ADDRESS, 0x44]
        else:
            # 总线故障产生的 OSError 必须原样向上传递。
            found = scan()
            candidates = []
            for address in (_INA226_ADDRESS, 0x44):
                if address in found:
                    candidates.append(address)
            for address in found:
                if 0x40 <= address <= 0x4F and address not in candidates:
                    candidates.append(address)

        for address in candidates:
            try:
                self._check_device(address)
                return address
            except (OSError, ValueError):
                pass

        if found is None:
            detail = "probed 0x40 and 0x44 (scan unavailable)"
        elif found:
            detail = "I2C scan: " + ", ".join(
                "0x%02X" % address for address in found
            )
        else:
            detail = "I2C scan: none"
        raise OSError(
            "INA226 not found; %s. Check 3.3V/GND/SDA/SCL and address."
            % detail
        )

    def _check_device(self, address):
        """确认指定地址上的器件是 INA226，不改变当前地址。"""
        old_address = self._addr
        self._addr = address
        try:
            manufacturer = self._read_register(_INA226_MAN_ID_REG)
            die_id = self._read_register(_INA226_ID_REG) >> 4
        finally:
            self._addr = old_address

        if manufacturer != _INA226_MAN_ID or die_id != _INA226_DIE_ID:
            raise ValueError("device at 0x%02X is not INA226" % address)

    def reset(self):
        """复位芯片。复位会清除校准寄存器。"""
        self._write_register(_INA226_CONF_REG, _INA226_RST)

    def configure_measurement(self, shunt_resistor, max_expected_current):
        """根据分流电阻和最大预期电流计算并写入标定参数。"""
        self._validate_measurement_parameters(shunt_resistor,
                                              max_expected_current)

        current_lsb = max_expected_current / 32768.0
        minimum_lsb_for_cal = (
            _CALIBRATION_FACTOR / (_CALIBRATION_MAX * shunt_resistor)
        )
        if current_lsb < minimum_lsb_for_cal:
            current_lsb = minimum_lsb_for_cal

        calibration = int(
            _CALIBRATION_FACTOR / (current_lsb * shunt_resistor)
        )
        if calibration < 1 or calibration > _CALIBRATION_MAX:
            raise ValueError("calibration value is outside 1..0x7FFF")

        # 使用实际写入的整数校准值反算 LSB，消除截断带来的比例误差。
        actual_current_lsb = (
            _CALIBRATION_FACTOR / (calibration * shunt_resistor)
        )

        self._shunt_resistor = shunt_resistor
        self._max_expected_current = max_expected_current
        self._cal_val = calibration
        self._current_lsb_a = actual_current_lsb
        self._power_lsb_w = 25.0 * actual_current_lsb
        self._stable_current_ma = None
        self._write_register(_INA226_CAL_REG, calibration)

    def set_resistor_range(self, resistor, current_range):
        """兼容旧版 API；推荐使用 configure_measurement()。"""
        self.configure_measurement(resistor, current_range)

    def _update_configuration(self, mask, value):
        configuration = self._read_register(_INA226_CONF_REG)
        configuration = (configuration & ~mask) | (value & mask)
        self._write_register(_INA226_CONF_REG, configuration)

    def set_average(self, averages):
        if averages not in (AVERAGE_1, AVERAGE_4, AVERAGE_16, AVERAGE_64,
                            AVERAGE_128, AVERAGE_256, AVERAGE_512,
                            AVERAGE_1024):
            raise ValueError("invalid averaging setting")
        self._averages = averages
        self._update_configuration(_INA226_AVG_MASK, averages)

    def _validate_conversion_time(self, conv_time):
        if not isinstance(conv_time, int) or conv_time < 0 or conv_time > 7:
            raise ValueError("invalid conversion time")

    def set_conversion_time(self, conv_time):
        """同时设置分流电压和总线电压转换时间。"""
        self._validate_conversion_time(conv_time)
        value = (conv_time << 6) | (conv_time << 3)
        self._update_configuration(
            _INA226_VBUS_CT_MASK | _INA226_VSH_CT_MASK, value
        )

    def set_bus_conversion_time(self, conv_time):
        self._validate_conversion_time(conv_time)
        self._update_configuration(_INA226_VBUS_CT_MASK, conv_time << 6)

    def set_shunt_conversion_time(self, conv_time):
        self._validate_conversion_time(conv_time)
        self._update_configuration(_INA226_VSH_CT_MASK, conv_time << 3)

    def set_measure_mode(self, mode):
        if not isinstance(mode, int) or mode < 0 or mode > 7:
            raise ValueError("invalid measurement mode")
        self._update_configuration(_INA226_MODE_MASK, mode)

    @property
    def shunt_voltage_v(self):
        return self._read_register_signed(_INA226_SHUNT_REG) * \
            _SHUNT_VOLTAGE_LSB_V

    @property
    def shunt_voltage_mv(self):
        return self.shunt_voltage_v * 1000.0

    @property
    def bus_voltage_v(self):
        return round(
            self._read_register(_INA226_BUS_REG) * _BUS_VOLTAGE_LSB_V, 2
        )

    @property
    def current_a(self):
        return self._read_register_signed(_INA226_CURRENT_REG) * \
            self._current_lsb_a

    @property
    def current_ma_raw(self):
        """未经显示迟滞处理的电流值，单位 mA。"""
        return self.current_a * 1000.0

    @property
    def current_ma(self):
        """适合直接显示的稳定电流值，保留两位小数。"""
        measured = round(self.current_ma_raw, 2)
        if (self._stable_current_ma is None or
                abs(measured - self._stable_current_ma) >=
                self._current_deadband_ma):
            self._stable_current_ma = measured
        return self._stable_current_ma

    def set_current_deadband(self, deadband_ma):
        """设置电流显示迟滞；传入 0 可关闭稳定处理。"""
        if deadband_ma < 0:
            raise ValueError("deadband_ma must not be negative")
        self._current_deadband_ma = deadband_ma
        self._stable_current_ma = None

    @property
    def power_w(self):
        return self._read_register(_INA226_PWR_REG) * self._power_lsb_w

    @property
    def power_mw(self):
        return self.power_w * 1000.0

    def read_all(self):
        """返回 (总线电压 V, 电流 A, 功率 W)。"""
        bus_voltage = self._read_register(_INA226_BUS_REG) * \
            _BUS_VOLTAGE_LSB_V
        current = self._read_register_signed(_INA226_CURRENT_REG) * \
            self._current_lsb_a
        power = self._read_register(_INA226_PWR_REG) * self._power_lsb_w
        return bus_voltage, current, power

    def is_conversion_ready(self):
        """读取转换就绪标志；读取 Mask/Enable 寄存器会清除此标志。"""
        return bool(self._read_register(_INA226_MASK_EN_REG) & _INA226_CVRF)

    @property
    def math_overflow(self):
        """电流或功率计算是否发生溢出。"""
        return bool(self._read_register(_INA226_MASK_EN_REG) & _INA226_OVF)

    def power_down(self):
        configuration = self._read_register(_INA226_CONF_REG)
        mode = configuration & _INA226_MODE_MASK
        if mode not in (0, 4):
            self._mode_before_power_down = mode
        configuration &= ~_INA226_MODE_MASK
        self._write_register(_INA226_CONF_REG, configuration)

    def power_up(self):
        self.set_measure_mode(self._mode_before_power_down)

    def _write_register(self, reg, value):
        if value < 0 or value > 0xFFFF:
            raise ValueError("register value must be a 16-bit unsigned integer")

        self._buf3[0] = reg
        self._buf3[1] = (value >> 8) & 0xFF
        self._buf3[2] = value & 0xFF
        for attempt in range(self._i2c_retries + 1):
            try:
                self._i2c.writeto(self._addr, self._buf3)
                return
            except OSError:
                if attempt >= self._i2c_retries:
                    raise

    def _read_register(self, reg):
        self._reg[0] = reg
        for attempt in range(self._i2c_retries + 1):
            try:
                self._i2c.writeto(self._addr, self._reg, False)
                self._i2c.readfrom_into(self._addr, self._buf2)
                return (self._buf2[0] << 8) | self._buf2[1]
            except OSError:
                if attempt >= self._i2c_retries:
                    raise

    def _read_register_signed(self, reg):
        value = self._read_register(reg)
        if value & 0x8000:
            value -= 0x10000
        return value
