from future import MeowPin
import utime

__version__ = "0.0.1"

CMD_DELAY = 6000  # 每条命令后的等待时间（微秒）


class Mp3Command:
    """MP3 命令常量"""
    PLAY = 0
    PAUSE = 1
    STOP = 2
    PLAY_PAUSE = 3
    PREVIOUS_TRACK = 4
    NEXT_TRACK = 5


class SongMode:
    PLAY_ONCE = 0
    REPEAT = 1


class PlaylistMode:
    LOOP = 0
    RANDOM = 1


class MP3Player:
    """MP3 模块控制类（单线串行协议）"""

    def __init__(self, port, volume=15):
        """
        初始化引脚并设置音量
        :param port: 端口，如 'P1'~'P4'
        :param volume: 初始音量，默认 15
        """
        self.pin = MeowPin(port, "OUT")
        self.pin.setDigital(True)  # 初始化拉高
        self.reset_module()
        self.set_volume(volume)

    def _create_command(self, cmd, data_h, data_l):
        """构造16位命令字"""
        return ((cmd << 4) | data_h) << 8 | data_l

    def _send_byte(self, dat):
        """发送16位数据（单线协议）"""
        self.pin.setDigital(False)
        utime.sleep_us(5000)
        for _ in range(16):
            if dat & 0x8000:
                # 逻辑1: 高600us 低200us
                self.pin.setDigital(True)
                utime.sleep_us(600)
                self.pin.setDigital(False)
                utime.sleep_us(200)
            else:
                # 逻辑0: 高200us 低600us
                self.pin.setDigital(True)
                utime.sleep_us(200)
                self.pin.setDigital(False)
                utime.sleep_us(600)
            dat <<= 1
        self.pin.setDigital(True)
        utime.sleep_us(CMD_DELAY)

    def set_volume(self, volume):
        """设置音量 (0-30)"""
        volume = max(0, min(30, volume))
        command = self._create_command(0x04, 0x00, volume)
        self._send_byte(command)

    def send_command(self, cmd):
        """发送 MP3 命令（播放/暂停/停止等）"""
        if cmd == Mp3Command.PLAY:
            command = self._create_command(0x06, 0x01, 0x00)
        elif cmd == Mp3Command.PAUSE:
            command = self._create_command(0x06, 0x02, 0x00)
        elif cmd == Mp3Command.STOP:
            command = self._create_command(0x06, 0x03, 0x00)
        elif cmd == Mp3Command.PLAY_PAUSE:
            command = self._create_command(0x06, 0x05, 0x00)
        elif cmd == Mp3Command.PREVIOUS_TRACK:
            command = self._create_command(0x02, 0x00, 0x00)
        elif cmd == Mp3Command.NEXT_TRACK:
            command = self._create_command(0x01, 0x00, 0x00)
        else:
            return
        self._send_byte(command)

    def play_song(self, num, mode=SongMode.PLAY_ONCE):
        """按编号播放歌曲"""
        cmd = 0x0D if mode == SongMode.REPEAT else 0x03
        command = self._create_command(cmd, (num >> 8) & 0xFF, num & 0xFF)
        self._send_byte(command)

    def play_track(self, num):
        """单曲播放一次"""
        self.play_song(num, SongMode.PLAY_ONCE)

    def loop_track(self, num):
        """单曲循环播放"""
        self.play_song(num, SongMode.REPEAT)

    def previous_track(self):
        """上一曲"""
        self._send_byte(self._create_command(0x02, 0x00, 0x00))

    def next_track(self):
        """下一曲"""
        self._send_byte(self._create_command(0x01, 0x00, 0x00))

    def play(self):
        """播放"""
        self._send_byte(self._create_command(0x06, 0x01, 0x00))

    def pause(self):
        """暂停"""
        self._send_byte(self._create_command(0x06, 0x02, 0x00))

    def stop(self):
        """停止"""
        self._send_byte(self._create_command(0x06, 0x03, 0x00))

    def play_pause(self):
        """播放/暂停切换"""
        self._send_byte(self._create_command(0x06, 0x05, 0x00))

    def set_playlist_mode(self, mode):
        """设置播放列表模式（Loop 或 Random）"""
        if mode == PlaylistMode.LOOP:
            command = self._create_command(0x06, 0x06, 0x00)
        else:
            command = self._create_command(0x0A, 0x02, 0x00)
        self._send_byte(command)

    def reset_module(self):
        """复位模块"""
        self._send_byte(self._create_command(0x05, 0x05, 0x00))
        utime.sleep_ms(50)