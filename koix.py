"""KOIX App UART protocol driver for FutureBoard Lite (MicroPython)."""

import time

from machine import UART


class KOIXError(Exception):
    pass


class KOIX:
    SAFE = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    RXBUF_SIZE = 4096
    # KOIX 屏幕为 480x640 竖屏，十字光标固定在屏幕中心。
    SCREEN_W = 480
    SCREEN_H = 640
    # 各事件中充当“ID”的字段。没有列出的事件（OCR/QRCODE 等）没有 ID 概念。
    ID_FIELDS = {
        "FACE": "face_id",
        "OBJECT": "class_id",
        "CLASS": "class_id",
        "POSE": "pose_id",
        "GESTURE": "gesture_id",
        "APRILTAG": "tag_id",
        "COLOR": "color_id",
        "TRAFFIC_SIGN": "class_id",
    }
    # 推流模式下等待同一 seq 剩余目标帧到齐的最长时间。
    FRAME_SETTLE_MS = 100

    @classmethod
    def open(cls, port="uart0", wait_ms=10000, timeout=3000):
        """创建实例并反复尝试 CONNECT，直到成功或超过 wait_ms。

        失败时仍返回实例，last_error 保留最后一次失败原因，
        便于积木端通过 error() 读取，而不是让程序在初始化处崩溃。
        """
        koix = cls(port, timeout)
        koix.wait_connect(wait_ms)
        return koix

    def __init__(self, port="uart0", timeout=3000):
        uartid = int(port[-1])
        uarttx = 0
        uartrx = 0
        if port == "uart0":
            uarttx=43
            uartrx=44
        elif port == "uart1":
            uarttx=17
            uartrx=18
        uart_args = {
            "tx": uarttx,
            "rx": uartrx,
            "baudrate": 115200,
        }
        try:
            self.uart = UART(uartid, rxbuf=self.RXBUF_SIZE, **uart_args)
        except TypeError:
            # 部分 FutureBoard 固件未提供 rxbuf 参数，保持向后兼容。
            self.uart = UART(uartid, **uart_args)
        self.timeout = int(timeout)
        self.last = None
        self.last_error = None
        self.last_xywh = None
        self.last_event = ""
        self.last_targets = []
        self.latest_event_line = None
        self.latest_events = {}
        self._event_seq = None
        self._event_total = 0
        self.stream = []
        self._rx_buf = bytearray()
        self._stream_enabled = None
        self.bad_frame_count = 0

    @staticmethod
    def checksum(text):
        value = 0
        for byte in text.encode("utf-8"):
            value ^= byte
        return "%02X" % value

    @classmethod
    def encode_arg(cls, value):
        data = str(value).encode("utf-8")
        out = ""
        for byte in data:
            if byte in cls.SAFE:
                out += chr(byte)
            else:
                out += "%%%02X" % byte
        return out

    @staticmethod
    def decode_arg(value):
        data = bytearray()
        i = 0
        while i < len(value):
            if value[i] == "%" and i + 2 < len(value):
                try:
                    data.append(int(value[i + 1:i + 3], 16))
                    i += 3
                    continue
                except ValueError:
                    pass
            data.extend(value[i].encode("utf-8"))
            i += 1
        try:
            return data.decode("utf-8")
        except Exception:
            return str(data)

    @classmethod
    def frame(cls, command):
        command = command.strip()
        return "KOIX %s %s\r\n" % (command, cls.checksum(command))

    def _write(self, text):
        data = text.encode("utf-8")
        offset = 0
        empty_writes = 0
        while offset < len(data):
            written = self.uart.write(data[offset:])
            if written is None:
                written = 0
            written = int(written)
            if written <= 0:
                empty_writes += 1
                if empty_writes >= 20:
                    self.last_error = "UART_TX_TIMEOUT"
                    return False
                time.sleep_ms(1)
                continue
            if written > len(data) - offset:
                written = len(data) - offset
            offset += written
            empty_writes = 0
        return offset

    def _available(self):
        return self.uart.any() > 0

    def _receive(self):
        """Read currently available bytes without assuming they form a full line."""
        if not self._available():
            return 0
        raw = self.uart.read()
        if raw:
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            self._rx_buf.extend(raw)
            if len(self._rx_buf) > self.RXBUF_SIZE * 2:
                self._rx_buf = self._rx_buf[-self.RXBUF_SIZE:]
            return len(raw)
        return 0

    def _pop_line(self):
        """Return one complete CR/LF terminated line, or None if incomplete."""
        end = -1
        # CanMV MicroPython's bytearray.index() does not accept an integer,
        # unlike CPython.  Scan manually for portable CR/LF detection.
        for pos in range(len(self._rx_buf)):
            if self._rx_buf[pos] == 10 or self._rx_buf[pos] == 13:
                end = pos
                break
        if end < 0:
            return None
        raw = bytes(self._rx_buf[:end])
        consumed = end + 1
        if consumed < len(self._rx_buf):
            first = self._rx_buf[end]
            second = self._rx_buf[consumed]
            if (first == 13 and second == 10) or (first == 10 and second == 13):
                consumed += 1
        self._rx_buf = self._rx_buf[consumed:]
        try:
            return raw.decode("utf-8").strip()
        except Exception:
            return ""

    def parse(self, line):
        line = line.strip()
        # 缓冲溢出可能把损坏帧的尾部和下一条 KOIX 帧粘在一起。从最后一个
        # 帧头重新同步，至少可以保住最后一条完整帧。
        start = line.rfind("KOIX ")
        if start < 0:
            return None
        line = line[start:]
        body = line[5:]
        pos = body.rfind(" ")
        if pos < 0:
            self.last_error = "MALFORMED raw=%s" % line
            self.bad_frame_count += 1
            return None
        payload, received = body[:pos], body[pos + 1:].upper()
        expected = self.checksum(payload)
        if received != expected:
            self.last_error = "BAD_CHK received=%s expected=%s raw=%s" % (
                received, expected, line)
            self.bad_frame_count += 1
            return None
        parts = [self.decode_arg(item) for item in payload.split(" ")]
        result = {"type": parts[0], "data": parts[1:], "raw": payload}
        if parts[0] == "ERR":
            self.last_error = parts[1] if len(parts) > 1 else "UNKNOWN"
        elif parts[0] == "XYWH" and len(parts) >= 5:
            values = []
            for item in parts[1:]:
                try:
                    values.append(float(item) if "." in item else int(item))
                except ValueError:
                    values.append(item)
            self.last_xywh = values
        elif parts[0] not in ("OK", "VER"):
            fields = {}
            for item in parts[1:]:
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                try:
                    value = float(value) if "." in value else int(value)
                except ValueError:
                    pass
                fields[key] = value
            if fields:
                result["fields"] = fields
                if any(key in fields for key in ("seq", "index", "total")):
                    self._update_event(parts[0], fields)
                # Keep the most recent complete event line independently of
                # command responses. Streaming users read this cache directly.
                self.latest_event_line = result
                self.latest_events[parts[0]] = result
        self.last = result
        return result

    def _update_event(self, event, fields):
        """Assemble protocol 1.2 multi-target event frames by seq/index."""
        seq = fields.get("seq")
        total = fields.get("total", 0)
        if event != self.last_event or seq != self._event_seq:
            self.last_event = event
            self._event_seq = seq
            self.last_targets = []
        self._event_total = total
        if total == 0:
            self.last_targets = []
            self.last_xywh = None
            return
        index = fields.get("index", len(self.last_targets))
        if not isinstance(index, int) or index < 0:
            return
        while len(self.last_targets) <= index:
            self.last_targets.append(None)
        self.last_targets[index] = fields
        if index == 0 and all(key in fields for key in ("x", "y", "w", "h")):
            self.last_xywh = [fields["x"], fields["y"], fields["w"], fields["h"]]
            if "score" in fields:
                self.last_xywh.append(fields["score"])

    def poll(self):
        count = 0
        self._receive()
        while True:
            line = self._pop_line()
            if line is None:
                break
            if not line:
                continue
            result = self.parse(line)
            if result:
                self._append_stream(result)
                count += 1
        return count

    def command(self, command, wait=True):
        self.last_error = None
        if self._write(self.frame(command)) is False:
            return False
        if not wait:
            return True
        expected_type = command.split(" ", 1)[0].upper()
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < self.timeout:
            self._receive()
            line = self._pop_line()
            if line is not None:
                if not line:
                    continue
                result = self.parse(line)
                if not result:
                    continue
                if result["type"] == "XYWH" or "fields" in result:
                    self._append_stream(result)
                    continue
                if result["type"] == "ERR":
                    return False
                if result["type"] == "OK":
                    data = result.get("data", [])
                    response_type = data[0].upper() if data else ""
                    if response_type != expected_type:
                        self._append_stream(result)
                        continue
                elif result["type"] == "VER" and expected_type != "VER?":
                    self._append_stream(result)
                    continue
                self.last_error = None
                return result
            time.sleep_ms(10)
        self.last_error = "TIMEOUT"
        return False

    def _append_stream(self, result):
        self.stream.append(result)
        if len(self.stream) > 20:
            self.stream.pop(0)

    def _cmd(self, name, *args):
        values = [name]
        for arg in args:
            if arg is not None and str(arg) != "":
                values.append(self.encode_arg(arg))
        return self.command(" ".join(values))

    def version(self): return self._cmd("VER?")
    def capture(self, filename=""): return self._cmd("CAPTURE", filename)
    def app_list(self): return self._cmd("APP LIST")
    def app_current(self): return self._cmd("APP CURRENT")
    def _clear_event_cache(self):
        """切换 App 后清空旧识别结果，不丢弃尚未解析的串口数据。"""
        self.last_xywh = None
        self.last_event = ""
        self.last_targets = []
        self.latest_event_line = None
        self.latest_events = {}
        self._event_seq = None
        self._event_total = 0
        self.stream = []

    def app_switch(self, app_id):
        result = self._cmd("APP SWITCH", app_id)
        if result:
            self._clear_event_cache()
        return result
    def capabilities(self): return self._cmd("CAPS?")
    def latest(self, event=""):
        """读取推流缓存的最新事件行，不发送串口查询。"""
        if event:
            return self.latest_events.get(str(event).upper())
        return self.latest_event_line
    def latest_value(self, field, event=""):
        """读取最新事件行的一个字段；没有数据时返回空字符串。"""
        item = self.latest(event)
        if not item:
            return ""
        return item.get("fields", {}).get(str(field), "")
    def latest_targets(self, event=""):
        """读取当前 seq 已收到的全部目标缓存，不发送串口查询。"""
        if event and self.last_event != str(event).upper():
            return []
        return [item for item in self.last_targets if item is not None]
    def param_list(self): return self._cmd("PARAM LIST")
    def param_get(self, index): return self._cmd("PARAM GET", index)
    def param_set(self, index, value): return self._cmd("PARAM SET", index, value)
    def connect(self):
        result = self._cmd("CONNECT")
        if result:
            self._stream_enabled = True
        return result
    def set_stream(self, enabled):
        result = self._cmd("STREAM", 1 if enabled else 0)
        if result:
            self._stream_enabled = bool(enabled)
        return result
    def register(self, kind, feature_id, label=""):
        return self._cmd(str(kind).upper() + " REGISTER", feature_id, label)
    def set_label(self, kind, feature_id, label): return self._cmd(str(kind).upper() + " LABEL", feature_id, label)
    def labels(self, kind): return self._cmd(str(kind).upper() + " LABELS?")
    def clear(self, kind): return self._cmd(str(kind).upper() + " CLEAR")
    def class_learn(self, class_id, label=""):
        """将当前画面特征学习到指定分类 ID，label 为空时不发送。"""
        return self._cmd("CLASS LEARN", class_id, label)
    def class_id(self):
        """读取推流缓存中的当前分类 ID，不发送查询指令。"""
        return self.event_value("CLASS", 0, "class_id")
    def class_labels(self):
        """查询全部分类标签。"""
        return self.labels("CLASS")
    def class_clear(self):
        """清空全部分类样本和标签。"""
        return self.clear("CLASS")
    def webide_info(self): return self._cmd("WEBIDE INFO")
    def last_data(self): return self.last["data"] if self.last else []
    def event(self): return self.latest_event_line
    def target_count(self): return self._event_total
    def target_value(self, index, field):
        index = int(index)
        if index < 0 or index >= len(self.last_targets) or self.last_targets[index] is None:
            return ""
        return self.last_targets[index].get(str(field), "")
    def event_count(self, event):
        return self.target_count() if self.last_event == str(event).upper() else 0
    def event_value(self, event, index, field):
        if self.last_event != str(event).upper():
            return ""
        return self.target_value(index, field)
    def error(self): return self.last_error or ""
    def xywh(self, index):
        return self.last_xywh[int(index)] if self.last_xywh and int(index) < len(self.last_xywh) else 0

    # ------------------------------------------------------------------
    # 积木查询层：面向图形化积木的语义接口。
    # 约定：索引从 1 开始；查询方法永不抛异常，无数据返回 ""/0/False；
    # 通信类失败写入 last_error 供 error() 读取。
    # ------------------------------------------------------------------

    def wait_connect(self, wait_ms=10000):
        """反复 CONNECT 直到成功或超时，返回 bool。"""
        start = time.ticks_ms()
        while True:
            if self.connect():
                return True
            if time.ticks_diff(time.ticks_ms(), start) >= int(wait_ms):
                if not self.last_error:
                    self.last_error = "CONNECT_TIMEOUT"
                return False
            time.sleep_ms(200)

    def set_screen(self, width, height):
        """覆盖屏幕尺寸；十字光标始终取屏幕中心。"""
        width = int(width)
        height = int(height)
        if width <= 0 or height <= 0:
            self.last_error = "BAD_SCREEN_SIZE"
            return False
        self.SCREEN_W = width
        self.SCREEN_H = height
        return True

    def _targets_complete(self):
        if self._event_total <= 0:
            return True
        if len(self.last_targets) < self._event_total:
            return False
        for item in self.last_targets[:self._event_total]:
            if item is None:
                return False
        return True

    @staticmethod
    def _summary_seq(result):
        """从 `OK RESULT? app=.. event=.. seq=..` 摘要中取 seq，没有则 None。"""
        for item in result.get("data", []):
            if isinstance(item, str) and item.startswith("seq="):
                try:
                    return int(item[4:])
                except ValueError:
                    return None
        return None

    def _settle(self, event, want_seq, limit_ms):
        """在 limit_ms 内持续收帧，直到 event 匹配、seq 满足且目标齐全。"""
        start = time.ticks_ms()
        while True:
            self.poll()
            if self.last_event == event and self._targets_complete():
                if want_seq is None or self._event_seq == want_seq:
                    return True
            if time.ticks_diff(time.ticks_ms(), start) >= limit_ms:
                return False
            time.sleep_ms(5)

    def request(self, event):
        """刷新一次 event 的识别结果到缓存，成功返回 True。

        推流开启：清空串口积压并等待同一 seq 的目标帧到齐。
        推流关闭：发送 RESULT? 并等待摘要中 seq 对应的完整帧组。
        """
        event = str(event).upper()
        if self._stream_enabled:
            if self._settle(event, None, self.FRAME_SETTLE_MS):
                return True
            if self.last_event and self.last_event != event:
                self.last_error = "EVENT_MISMATCH current=%s" % self.last_event
            return False
        result = self.command("RESULT?")
        if not result:
            return False
        want_seq = self._summary_seq(result)
        if self._settle(event, want_seq, self.timeout):
            return True
        if not self.last_error:
            self.last_error = "RESULT_TIMEOUT"
        return False

    def targets(self, event):
        if self.last_event != str(event).upper():
            return []
        return [item for item in self.last_targets if item is not None]

    def detected(self, event):
        return len(self.targets(event)) > 0

    def count(self, event):
        return self.event_count(event)

    @staticmethod
    def _index(index):
        """1 起始索引转 0 起始，非法返回 None。"""
        try:
            value = int(index) - 1
        except (ValueError, TypeError):
            return None
        return value if value >= 0 else None

    @classmethod
    def normalize_id(cls, value):
        """把固件返回的各种 ID 形式统一为整数：3 / "3" / "face_003" -> 3，
        unknown / 空 -> 0（0 表示未学习）。无法解析的原样返回。"""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip()
        if text == "" or text.lower() == "unknown":
            return 0
        if text.isdigit():
            return int(text)
        tail = cls._trailing_int(text)
        return tail if tail is not None else value

    def _field(self, event, target, field):
        """读取目标字段，含派生字段 id/name/cx/cy。缺失返回空字符串。"""
        field = str(field)
        if field == "id":
            key = self.ID_FIELDS.get(event, "id")
            if key not in target:
                return ""
            return self.normalize_id(target[key])
        if field == "name":
            value = target.get("label", "")
            return value if value != "" else target.get("name", "")
        if field in ("cx", "cy"):
            pos = "x" if field == "cx" else "y"
            size = "w" if field == "cx" else "h"
            try:
                return int(target[pos] + target[size] / 2)
            except (KeyError, TypeError, ValueError):
                return ""
        return target.get(field, "")

    def value(self, event, index, field):
        """第 index（1 起始）个目标的字段。"""
        items = self.targets(event)
        pos = self._index(index)
        if pos is None or pos >= len(items):
            return ""
        return self._field(str(event).upper(), items[pos], field)

    def nearest_target(self, event):
        """十字光标落在框内的目标；多个命中时取框中心最靠近十字者。"""
        cx = self.SCREEN_W / 2
        cy = self.SCREEN_H / 2
        best = None
        best_dist = None
        for item in self.targets(event):
            try:
                x, y, w, h = item["x"], item["y"], item["w"], item["h"]
                inside = x <= cx <= x + w and y <= cy <= y + h
                if not inside:
                    continue
                dist = (x + w / 2 - cx) ** 2 + (y + h / 2 - cy) ** 2
            except (KeyError, TypeError):
                continue
            if best_dist is None or dist < best_dist:
                best = item
                best_dist = dist
        return best

    def center_detected(self, event):
        """十字光标处是否有目标——学习/录入前的前置条件。"""
        return self.nearest_target(event) is not None

    def nearest(self, event, field):
        item = self.nearest_target(event)
        if item is None:
            return ""
        return self._field(str(event).upper(), item, field)

    @staticmethod
    def _trailing_int(text):
        text = str(text)
        end = len(text)
        while end > 0 and text[end - 1].isdigit():
            end -= 1
        if end == len(text):
            return None
        return int(text[end:])

    def _id_match(self, event, target, ident):
        key = self.ID_FIELDS.get(event)
        if key is None:
            return False
        actual = target.get(key)
        if actual is None:
            return False
        # 两边都规整为整数后比较：face_003 == 3，unknown == 0。
        return self.normalize_id(actual) == self.normalize_id(ident)

    def id_targets(self, event, ident):
        event = str(event).upper()
        return [item for item in self.targets(event) if self._id_match(event, item, ident)]

    def id_exists(self, event, ident):
        return len(self.id_targets(event, ident)) > 0

    def id_count(self, event, ident):
        return len(self.id_targets(event, ident))

    def id_value(self, event, ident, index, field):
        """ID 为 ident 的第 index（1 起始）个目标的字段。"""
        items = self.id_targets(event, ident)
        pos = self._index(index)
        if pos is None or pos >= len(items):
            return ""
        return self._field(str(event).upper(), items[pos], field)

    # ---- 高级栏：把应答字典转成可直接显示的文本 ----

    @staticmethod
    def _response_text(result, command=""):
        """去掉应答中回显的指令词，把剩余数据用空格拼成一行文本。"""
        if not result:
            return ""
        data = list(result.get("data", []))
        if result.get("type") == "OK":
            echo = [item.upper() for item in str(command).split(" ") if item]
            while data and echo and str(data[0]).upper() == echo[0]:
                data.pop(0)
                echo.pop(0)
        return " ".join(str(item) for item in data)

    def version_text(self):
        return self._response_text(self.version(), "VER?")

    def caps_text(self):
        return self._response_text(self.capabilities(), "CAPS?")

    def param_text(self):
        return self._response_text(self.param_list(), "PARAM LIST")

    def param_value(self, index):
        """读取参数值；应答含 value= 字段时只返回该值，否则返回整行文本。"""
        result = self.param_get(index)
        if not result:
            return ""
        for item in result.get("data", []):
            if isinstance(item, str) and item.startswith("value="):
                return item[6:]
        return self._response_text(result, "PARAM GET")

    def send(self, command):
        """发送原始指令并返回应答文本，失败返回空字符串（原因见 error()）。"""
        command = str(command).strip()
        return self._response_text(self.command(command), command)

    # ---- 学习 / 命名 / 遗忘（按模型种类分派） ----

    def learn(self, kind, ident, label=""):
        kind = str(kind).upper()
        if kind == "CLASS":
            return self.class_learn(ident, label)
        return self.register(kind, ident, label)

    def rename(self, kind, ident, label):
        return self.set_label(kind, ident, label)

    def forget(self, kind):
        return self.clear(kind)

    # ---- 板载喇叭：指令应答只表示后台播放任务已接受 ----

    def tone(self, frequency, duration=0.5):
        return self._cmd("BUZZER TONE", frequency, duration)

    def note(self, note_name, duration=0.5):
        return self._cmd("BUZZER NOTE", note_name, duration)

    def rest(self, duration):
        return self._cmd("BUZZER REST", duration)

    def melody(self, music, tempo=120):
        return self._cmd("BUZZER MELODY", music, tempo)

    def melodies(self):
        return self._cmd("BUZZER MELODIES")

    def set_volume(self, volume):
        return self._cmd("BUZZER VOLUME", volume)

    def play_file(self, filename):
        return self._cmd("AUDIO PLAY", filename)

    def play_dir(self, directory, selection="ALL"):
        return self._cmd("AUDIO DIR", directory, selection)

    def audio_list(self, directory, offset=0, limit=8):
        return self._cmd("AUDIO LIST", directory, offset, limit)

    def audio_list_text(self, directory, offset=0, limit=8):
        return self._response_text(
            self.audio_list(directory, offset, limit), "AUDIO LIST")

    def audio_status(self):
        return self._cmd("AUDIO STATUS")

    def audio_stop(self):
        return self._cmd("AUDIO STOP")

    @staticmethod
    def _response_fields(result):
        """把 OK 响应中的 key=value 项转换成字典。"""
        fields = {}
        if not result:
            return fields
        for item in result.get("data", []):
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                fields[key] = value
        return fields

    def audio_state(self):
        return self._response_fields(self.audio_status()).get("state", "")

    def audio_busy(self):
        return self._response_fields(self.audio_status()).get("busy", "0") == "1"

    def audio_error(self):
        result = self.audio_status()
        if not result:
            return self.error()
        value = self._response_fields(result).get("error", "")
        return "" if value == "-" else value

    # 兼容已经使用 buzzer_* / audio_* 命名的程序。
    def buzzer_tone(self, frequency, duration=0.5):
        return self.tone(frequency, duration)

    def buzzer_note(self, note_name, duration=0.5):
        return self.note(note_name, duration)

    def buzzer_rest(self, duration):
        return self.rest(duration)

    def buzzer_melody_music(self, music_name):
        return self.melody(music_name)

    def buzzer_melody(self, music, bpm=120):
        return self.melody(music, bpm)

    def buzzer_volume(self, volume):
        return self.set_volume(volume)

    def buzzer_status(self):
        return self.audio_status()

    def buzzer_stop(self):
        return self.audio_stop()

    def audio_play(self, filename):
        return self.play_file(filename)

    def audio_dir(self, directory, selection="ALL"):
        return self.play_dir(directory, selection)

    # ---- KOIX 板载 4 颗 RGB 灯 ----

    @staticmethod
    def _rgb_color_arg(color):
        if isinstance(color, (tuple, list)) and len(color) == 3:
            return "{},{},{}".format(color[0], color[1], color[2])
        return color

    def rgb_all(self, color):
        return self._cmd("RGB ALL ON", self._rgb_color_arg(color))

    def rgb_off(self):
        return self._cmd("RGB ALL OFF")

    def rgb_pixel(self, index, color):
        return self._cmd("RGB PIXEL ON", index, self._rgb_color_arg(color))

    def rgb_pixel_off(self, index):
        return self._cmd("RGB PIXEL OFF", index)

    def rgb_animation(self, name, cycles=1):
        return self._cmd("RGB ANIMATION", name, cycles)

    def rgb_animations(self):
        return self._cmd("RGB ANIMATIONS")

    def rgb_stop(self):
        return self._cmd("RGB STOP")

    def rgb_status(self):
        return self._cmd("RGB STATUS")

    def rgb_state(self):
        return self._response_fields(self.rgb_status()).get("state", "")

    def rgb_busy(self):
        return self._response_fields(self.rgb_status()).get("busy", "0") == "1"

    def rgb_effect(self):
        value = self._response_fields(self.rgb_status()).get("effect", "")
        return "" if value == "-" else value

    def rgb_error(self):
        result = self.rgb_status()
        if not result:
            return self.error()
        value = self._response_fields(result).get("error", "")
        return "" if value == "-" else value

    # ---- KOIX 麦克风：后台录音并直接保存 WAV ----

    def record(self, duration=5, filename=""):
        return self._cmd("MIC RECORD", duration, filename)

    def sound_level(self):
        result = self._cmd("MIC LEVEL")
        if not result:
            return None
        data = result.get("data", [])
        try:
            if len(data) < 3 or data[0].upper() != "MIC" or data[1].upper() != "LEVEL":
                return None
            return int(data[2])
        except (ValueError, TypeError):
            return None

    def mic_busy(self):
        status = self._cmd("MIC STATUS")
        return self._response_fields(status).get("busy", "0") == "1"
