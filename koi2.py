from machine import UART, Pin
from readImg_uart import readImage
import time
import ujson
import ubinascii
import urequests
from board import *
__version__ = '1.0.6'

class KOI2:
    #basic
    def __init__(self,uart):
        uart_id = get_uart_id(uart)
        self.uart = UART(uart_id, baudrate=115200, tx = Pin(uarts[uart][1]), rx = Pin(uarts[uart][0]))
        self.xywh = [-1] * 4
        self.xy12 = [-1] * 4
        self.numberVal = -1
        self.strVal = None
        self.faceAttr = [-1]*13
        self.btnStateA = 0
        self.btnStateB = 0
        self.btnStateAB = 0
        self.classifierMap = {}
        self.classifierIndex = -1
        self.classifierConfidence = -1.0
        self.IDconfidence = -1 #图像检测置信度
        self.cloudFaceLocation = []
        self.cloudFaceLandmark4 = []
        self.cloudFaceLandmark72 = []
        self.cloudFaceLandmark150 = []
        self.cloudFaceCount = 0
        self.faceResponse = None

        self.updateTime = time.ticks_ms()

    def valReset(self):
        self.xywh = [-1] * 4
        self.xy12 = [-1] * 4
        self.numberVal = -1
        self.strVal = None
        self.faceAttr = [-1]*13
        self.classifierMap = {}
        self.classifierIndex = -1
        self.classifierConfidence = -1.0
        self.IDconfidence = -1
        self.cloudFaceLocation = []
        self.cloudFaceLandmark4 = []
        self.cloudFaceLandmark72 = []
        self.cloudFaceLandmark150 = []
        self.cloudFaceCount = 0
        self.faceResponse = None

    def read_from_uart(self):
        strModel = ['K81','K82','K84','K20','K85']
        numModel = ['K31','K83']
        try:
            if time.ticks_ms() - self.updateTime > 1000:
                self.valReset()
            data = self.uart.read()
            if data:
                transfer = data.decode().split('\r\n')
                index = 1
                while index <= len(transfer):
                    cmd = transfer[-index].split(" ")
                    if len(cmd) > 1:
                        break
                    index+=1
                if len(cmd) > 1:
                    self.updateTime = time.ticks_ms()
                    if cmd[0] in numModel:#face
                        if len(cmd) < 5:
                            return
                        self.xywh = [int(i) for i in cmd[1:5]]
                        self.numberVal = int(cmd[5])
                    elif cmd[0] == 'K86':
                        if len(cmd) < 6:
                            return
                        self.xywh = [int(i) for i in cmd[1:5]]
                        self.numberVal = int(cmd[5])
                        self.IDconfidence = int(cmd[6])
                    elif cmd[0] in strModel:#model type
                        if len(cmd) < 5:
                            return
                        self.xywh = [int(i) for i in cmd[1:5]]
                        self.strVal = cmd[5] 
                    elif cmd[0] == 'K42':#feature extraction
                        self.strVal = cmd[1]
                        self.numberVal = int(cmd[2])
                    elif cmd[0] == 'K15':#color blob
                        if len(cmd) < 5:
                            return
                        self.xywh = [int(i) for i in cmd[1:5]]
                    elif cmd[0] == 'K19':
                        if len(cmd) < 5:
                            return
                        self.xy12 = [int(i) for i in cmd[1:5]]
                    elif cmd[0] == 'K65':
                        self.strVal = '-'.join(cmd[1:])
                    elif cmd[0] == 'K34':
                        self.faceAttr = cmd[1:]
                        if len(cmd) < 5:
                            return
                        self.xywh = [int(i) for i in cmd[1:5]]
                    elif cmd[0] == 'K3':#btn
                        btnState =  int(cmd[1])
                        if btnState == 1:
                            self.btnStateA = 1
                        elif btnState == 2:
                            self.btnStateB = 1
                        elif btnState == 3:
                            self.btnStateAB = 1
                    elif cmd[0] == 'K50':  # 自定义分类返回：序号 + softmax 置信度
                        if len(cmd) >= 3:
                            self.classifierIndex = int(cmd[1])
                            self.classifierConfidence = float(cmd[2])
        except Exception as e:
            print(e)

    def getFirmwareVersion(self):
        """查询 KOI 固件版本，发送 K0 返回如 K0 v4.1.6-koi2"""
        self.uart.read()
        self.uart.write(b'K0\r\n')
        time.sleep_ms(100)
        data = self.uart.read()
        if not data:
            return None
        try:
            s = data.decode().strip()
            if s.startswith('K0 '):
                ver_str = s[3:].strip()
                if ver_str.startswith('v'):
                    ver_str = ver_str[1:].split('-')[0]
                return ver_str
        except Exception:
            pass
        return None

    def _parse_version(self, ver_str):
        """解析版本字符串 '4.1.6' -> (4, 1, 6)"""
        if not ver_str:
            return (0, 0, 0)
        try:
            parts = ver_str.split('.')
            return tuple(int(x) for x in parts[:3])
        except (ValueError, IndexError):
            return (0, 0, 0)

    def _check_custom_classifier_firmware(self):
        """检查固件版本是否支持自定义分类模式 (>= 4.1.6)"""
        ver = self.getFirmwareVersion()
        if ver is None:
            raise RuntimeError("Custom image classification requires KOI firmware v4.1.6 or later.")
        if self._parse_version(ver) < (4, 1, 6):
            raise RuntimeError("Custom image classification requires KOI firmware v4.1.6 or later.")

    def deinit(self):
        time.sleep(0.1)  # Give the thread some time to stop
        self.uart.deinit()
    
    def getBtnState(self,btn):
        if btn == 'A':
            if self.btnStateA:
                self.btnStateA = 0
                return True
        elif btn == 'B':
            if self.btnStateB:
                self.btnStateB = 0
                return True
        elif btn == 'AB':
            if self.btnStateAB:
                self.btnStateAB = 0
                return True
        return False

    #basic
    """
    参数说明：model
        设置模式，使用该函数之后会重启koi切换到对应模式。
        可选参数：
            无模式:0x0
            自定义模型:0x3
            人脸识别:0x9
            口罩识别:0x7
            色块追踪:0x10
            巡线追踪:0x20
            特征分类:0x5
            交通标志:0x1
            数字识别:0x4
            字母识别:0x6
            物体识别:0x2
            扫码识别:0x100
            自定义分类:0x31(49)
    """
    def setModel(self, model):
        # if model == 49:
        #     self._check_custom_classifier_firmware()
        if model == 0x9:
            self.numberVal = 0
        elif model == 0x4:
            self.numberVal = -1
        elif model == 0x5:
            self.numberVal = 5
        time.sleep(0.3)
        self.uart.write(b'K97 %d\r\n' % (model))
    
    def direction(self,dir):
        self.uart.write(b'K6 %d\r\n'%(dir))

    def mirror(self,enabled):
        self.uart.write(b'K7 %d\r\n'%(enabled))    

    def getImg(self):
        self.uart.write(b'K12\r\n')
        return readImage(self.uart)

    def getJpgBuf(self, clear_uart=True, display=0):
        """拍照并返回 jpg 二进制缓冲区。
        :param scale_down: 是否缩放图片，默认 True
        :param clear_uart: 拍照前是否清空串口残留数据
        :param display: 0：不显示，1：显示，2：显示并缩放
        """
        if clear_uart:
            while self.uart.any():
                self.uart.read()
                time.sleep_ms(5)
        img = self.getImg()
        if not img:
            return None
        jpg = img[0]
        if display == 1:
            try:
                fb.loadjpg(jpg, 0, 0, False)
            except Exception:
                pass
        elif display == 2:
            try:
                fb.loadjpg(jpg, 0, 0, True)
            except Exception:
                pass
        return jpg

    def requestFace(self, jpg_buf, url="https://kzone.kittenbot.cn/api/v1/image/face", token="WLVFZEY4", timeout=15):
        """上传 jpg 缓冲区做人脸识别，返回服务端 json。"""
        if jpg_buf is None:
            return None
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }
        img_b64 = ubinascii.b2a_base64(jpg_buf).decode().strip()
        payload = {"reqUrl": "detect", "img": img_b64}
        r = None
        try:
            r = urequests.post(url, data=ujson.dumps(payload), headers=headers, timeout=timeout)
            data = r.json()
            self.faceResponse = data
            self._updateFaceCache(data)
            return data
        finally:
            if r is not None:
                r.close()

    def getFaceResponse(self):
        return self.faceResponse

    def _faceResultList(self, face_json):
        if not isinstance(face_json, dict):
            return []
        result = face_json.get("result", {})
        if isinstance(result, dict) and "result" in result:
            result = result.get("result", {})
        if not isinstance(result, dict):
            return []
        face_list = result.get("face_list", [])
        if not isinstance(face_list, list):
            return []
        return face_list

    def _landmark150ToList(self, landmark150):
        if not isinstance(landmark150, dict):
            return []
        keys = []
        for k in landmark150.keys():
            try:
                keys.append((int(k), k))
            except Exception:
                keys.append((9999, k))
        keys.sort()
        out = []
        for _, k in keys:
            p = landmark150.get(k, {})
            if isinstance(p, dict):
                out.append([int(p.get("x", -1)), int(p.get("y", -1))])
        return out

    def _updateFaceCache(self, face_json):
        self.cloudFaceLocation = []
        self.cloudFaceLandmark4 = []
        self.cloudFaceLandmark72 = []
        self.cloudFaceLandmark150 = []
        self.cloudFaceCount = 0
        face_list = self._faceResultList(face_json)
        self.cloudFaceCount = len(face_list)
        for face in face_list:
            if not isinstance(face, dict):
                continue
            location = face.get("location", {})
            if not isinstance(location, dict):
                location = {}
            self.cloudFaceLocation.append([
                int(location.get("left", -1)),
                int(location.get("top", -1)),
                int(location.get("width", -1)),
                int(location.get("height", -1)),
            ])

            lm4 = []
            for p in face.get("landmark", []):
                if isinstance(p, dict):
                    lm4.append([int(p.get("x", -1)), int(p.get("y", -1))])
            self.cloudFaceLandmark4.append(lm4)

            lm72 = []
            for p in face.get("landmark72", []):
                if isinstance(p, dict):
                    lm72.append([int(p.get("x", -1)), int(p.get("y", -1))])
            self.cloudFaceLandmark72.append(lm72)

            self.cloudFaceLandmark150.append(self._landmark150ToList(face.get("landmark150", {})))

    def getFaceCoordinates(self, face_json):
        """兼容旧接口：从 requestFace 的返回 json 提取 [[x,y,w,h], ...]。"""
        self._updateFaceCache(face_json)
        return self.cloudFaceLocation

    def getFaceCoordinateValue(self, face_coordinates, face_index, coord_index):
        """兼容旧接口：按人脸序号和坐标序号读取值。"""
        try:
            return int(face_coordinates[int(face_index)][int(coord_index)])
        except Exception:
            return -1

    def getFaceLocation(self, face_index, coord_index):
        try:
            return int(self.cloudFaceLocation[int(face_index)][int(coord_index)])
        except Exception:
            return -1

    def getFaceLandmark4(self, face_index, point_index, coord_index):
        try:
            return int(self.cloudFaceLandmark4[int(face_index)][int(point_index)][int(coord_index)])
        except Exception:
            return -1

    def getFaceLandmark72(self, face_index, point_index, coord_index):
        try:
            idx = int(point_index) - 1
            return int(self.cloudFaceLandmark72[int(face_index)][idx][int(coord_index)])
        except Exception:
            return -1

    def getFaceLandmark150(self, face_index, point_index, coord_index):
        try:
            idx = int(point_index) - 1
            return int(self.cloudFaceLandmark150[int(face_index)][idx][int(coord_index)])
        except Exception:
            return -1

    def getFaceCount(self):
        try:
            return int(self.cloudFaceCount)
        except Exception:
            return 0

    #face
    def getFaceAttr(self,index):
        try:
            if index == 13:
                return int(self.faceAttr[8]) - int(self.faceAttr[9])
            return self.faceAttr[index]
        except Exception as e:
            print(e)
            return -1

    #audio
    def recorded(self,name,sec):
        self.uart.write(b'K61 %s %d\r\n'%(name,sec))

    def playAudio(self,name):
        self.uart.write(b'K62 %s\r\n'%(name))

    #color blob
    def colorCalibration(self):
        self.uart.write(b'K16\r\n')
    
    def colorSetting(self,v1,v2,v3,v4,v5,v6):
        self.uart.write(b'K17 %d %d %d %d %d %d\r\n'%(v1,v2,v3,v4,v5,v6))

    def colorSwitch(self,key):
        self.uart.write(b'K18 %d\r\n'%(key))

    #line blob
    def lineCalibration(self):
        self.uart.write(b'K16\r\n')
    
    def lineSetting(self,v1,v2,v3,v4,v5,v6):
        self.uart.write(b'K17 %d %d %d %d %d %d\r\n'%(v1,v2,v3,v4,v5,v6))

    def lineSwitch(self,key):
        self.uart.write(b'K18 %d\r\n'%(key))
    
    #classifier
    def classifierReset(self):
        self.uart.write(b'K45\r\n')

    def classifierAddTag(self,tag):
        self.uart.write(b'K41 %s\r\n'%(tag))

    def classifierSave(self,name):
        self.uart.write(b'K43 %s\r\n'%(name))

    def classifierLoad(self,name):
        self.uart.write(b'K44 %s\r\n'%(name))

    def loadClassifierModel(self, path_or_addr, type_val=1):
        """设置自定义分类模型来源
        :param type_val: 1=文件路径, 0=内存地址
        :param path_or_addr: 文件路径字符串或内存地址
        """
        self.uart.write(b'K49 %d %s\r\n' % (type_val, str(path_or_addr)))

    def setCustomClassifierMode(self):
        """切换为自定义分类模式 (K97 49)"""
        self.setModel(49)

    def getClassifierResult(self):
        """获取 K50 返回的分类结果 (index, confidence)"""
        return self.classifierIndex, int(self.classifierConfidence*100)

    def classifierGetMostSimilarResults(self):
        self.uart.write(b'K42\r\n')

    def setDetectionTarget(self,name):
        self.uart.write(b'K42 %s\r\n'%name)

    def getSimilarity(self):
        if self.numberVal == -1:
            x = -5
        else:
            x = self.numberVal
        return round((5-x)/5*100,2)
    
    #scan code
    def scanCodeSwitchType(self,type):
        self.uart.write(b'K21 %d\r\n'%(type))

    def setApriltagType(self,type):
        self.uart.write(b'K22 %d\r\n'%(type))

    #asr
    def asrSetKey(self,key):
        self.uart.write(b'K64 %s\r\n'%(key))

    #take a picture
    def takePic(self,path):
        self.uart.write(b'K2 %s\r\n'%(path))
    
    def displayPic(self,path,ms):
        self.uart.write(b'K1 %s %d\r\n'%(path,ms))

    # file operations
    def displayFileList(self,addr,page):
        self.uart.write(b'K8 %s %d\r\n'%(addr,page))

    def closeFileList(self):
        self.uart.write(b'K9\r\n')

    def deleteFile(self,path):
        self.uart.write(b'K10 %s\r\n'%(path))

    def copyFile(self,src_path,dst_path):
        self.uart.write(b'K11 %s %s\r\n'%(src_path,dst_path))
    
    #display text
    def displayText(self,x,y,delay,color,text):
        strColor = ','.join(str(i) for i in color)
        self.uart.write(b'K4 %d %d %d %s %s\r\n'%(x,y,delay,strColor,text))
    
    def initCustomModel(self,addr,anchor):
        addrType = 0
        if type(addr) == str:
            addrType = 1
        elif addr == int:
            addrType = 0
        anchorStr = ''
        for i in anchor:
            anchorStr += str(i)+','
        anchorStr = anchorStr[:-1]
        data = b'K87 %d %s %s\r\n'%(addrType,str(addr),anchorStr)
        self.uart.write(data)
