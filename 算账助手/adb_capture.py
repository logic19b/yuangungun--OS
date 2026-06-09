# -*- coding: utf-8 -*-
"""
算账助手 - ADB微信消息捕获模块
支持Windows平台，默认检查常见ADB路径
"""

import os
import re
import subprocess
import time
from datetime import datetime
from typing import Optional, List, Callable
import threading


class ADBCapture:
    """ADB微信消息捕获器"""
    
    def __init__(self):
        self.adb_path = None
        self.connected = False
        self.device_id = None
        self.running = False
        self.poll_thread = None
        self.poll_interval = 5
        self.last_notification = ""
        self.captured_count = 0
        self.callback = None
        self._auto_restart = False
        self._find_adb()
    
    def _find_adb(self):
        """Windows下查找ADB"""
        possible_paths = []
        
        # 常见ADB安装路径
        if os.name == 'nt':
            program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
            program_files_x86 = os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
            
            possible_paths.extend([
                os.path.join(program_files, 'platform-tools', 'adb.exe'),
                os.path.join(program_files_x86, 'platform-tools', 'adb.exe'),
                os.path.join(program_files, 'Android', 'Platform Tools', 'adb.exe'),
                os.path.join(program_files_x86, 'Android', 'Platform Tools', 'adb.exe'),
                os.path.join(program_files, 'adb', 'adb.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk', 'platform-tools', 'adb.exe'),
            ])
        
        # 检查PATH中的adb
        path_env = os.environ.get('PATH', '')
        for path_dir in path_env.split(os.pathsep):
            adb_in_path = os.path.join(path_dir, 'adb.exe')
            if os.path.exists(adb_in_path):
                possible_paths.append(adb_in_path)
        
        # 检查是否存在
        for path in possible_paths:
            if os.path.exists(path):
                self.adb_path = path
                self.adb_available = True
                return
        
        # 尝试直接运行adb
        try:
            result = subprocess.run(['adb', 'version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                self.adb_path = 'adb'
                self.adb_available = True
                return
        except:
            pass
        
        self.adb_available = False
        self.adb_path = None
    
    def is_adb_available(self) -> bool:
        """检查ADB是否可用"""
        return self.adb_available
    
    def get_adb_path(self) -> str:
        """获取ADB路径"""
        return self.adb_path or "未找到"
    
    def connect(self) -> tuple:
        """连接设备"""
        if not self.adb_available:
            return False, "ADB不可用，请安装Android SDK Platform Tools"
        
        try:
            cmd = [self.adb_path, 'devices'] if self.adb_path != 'adb' else ['adb', 'devices']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return False, "ADB命令执行失败"
            
            lines = result.stdout.strip().split("\n")
            devices = []
            for line in lines[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        devices.append(parts[0])
            
            if not devices:
                return False, "未检测到设备，请确保手机已开启USB调试并授权"
            
            self.device_id = devices[0]
            self.connected = True
            return True, f"已连接: {self.device_id}"
            
        except subprocess.TimeoutExpired:
            return False, "ADB连接超时"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def disconnect(self):
        """断开连接"""
        self.stop_monitor()
        self.connected = False
        self.device_id = None
    
    def get_connection_status(self) -> dict:
        """获取连接状态"""
        return {
            "connected": self.connected,
            "device_id": self.device_id,
            "adb_path": self.get_adb_path(),
            "adb_available": self.adb_available,
            "running": self.running,
            "captured_count": self.captured_count,
        }
    
    def _run_adb_command(self, command: List[str], timeout: int = 10) -> Optional[str]:
        """执行ADB命令"""
        if not self.connected:
            return None
        
        try:
            full_command = []
            if self.adb_path and self.adb_path != 'adb':
                full_command.append(self.adb_path)
                if self.device_id:
                    full_command.extend(['-s', self.device_id])
            else:
                full_command.append('adb')
                if self.device_id:
                    full_command.extend(['-s', self.device_id])
            full_command.extend(command)
            
            result = subprocess.run(full_command, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception:
            return None
    
    def capture_notifications(self) -> List[dict]:
        """从通知栏捕获微信消息"""
        messages = []
        output = self._run_adb_command(["shell", "dumpsys", "notification", "--noredact"])
        if not output:
            return messages
        
        in_wechat = False
        current_title = ""
        current_text = ""
        
        for line in output.split("\n"):
            if "com.tencent.mm" in line or "weixin" in line.lower():
                in_wechat = True
            
            if in_wechat:
                if "android.title=" in line:
                    current_title = line.split("android.title=")[-1].strip()
                if "android.text=" in line:
                    current_text = line.split("android.text=")[-1].strip()
                    if current_title or current_text:
                        msg = self._parse_wechat_notification(current_title, current_text)
                        if msg:
                            messages.append(msg)
                        current_title = ""
                        current_text = ""
        
        return messages
    
    def _parse_wechat_notification(self, title: str, text: str) -> Optional[dict]:
        """解析微信通知"""
        if not text:
            return None
        
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        
        group_match = re.search(r"\[([^\]]+)\]\s*([^:]+):(.+)", text)
        if group_match:
            return {
                "group_name": group_match.group(1),
                "nickname": group_match.group(2).strip(),
                "content": group_match.group(3).strip(),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "raw": f"{title}|{text}",
            }
        
        simple_match = re.match(r"([^:]+):(.+)", text)
        if simple_match:
            return {
                "group_name": "微信通知",
                "nickname": simple_match.group(1).strip(),
                "content": simple_match.group(2).strip(),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "raw": f"{title}|{text}",
            }
        
        return {
            "group_name": "微信通知",
            "nickname": title or "未知",
            "content": text,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "raw": f"{title}|{text}",
        }
    
    def capture_screenshot(self) -> Optional[bytes]:
        """截取屏幕截图"""
        output = self._run_adb_command(["exec-out", "screencap", "-p"], timeout=15)
        if output:
            return output.encode('latin-1') if isinstance(output, str) else output
        return None
    
    def ocr_screenshot(self, screenshot_data: bytes) -> List[str]:
        """OCR识别截图"""
        try:
            from PIL import Image
            import pytesseract
            import io
            
            image = Image.open(io.BytesIO(screenshot_data))
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            lines = text.split("\n")
            return [line.strip() for line in lines if line.strip()]
        except ImportError:
            return ["[需要安装 Pillow 和 pytesseract]"]
        except Exception as e:
            return [f"[OCR错误: {str(e)}]"]
    
    def capture_and_ocr(self) -> List[dict]:
        """截屏+OCR捕获"""
        messages = []
        screenshot = self.capture_screenshot()
        if not screenshot:
            return messages
        
        lines = self.ocr_screenshot(screenshot)
        for line in lines:
            if self._looks_like_chat_message(line):
                msg = self._parse_chat_line(line)
                if msg:
                    messages.append(msg)
        return messages
    
    def _looks_like_chat_message(self, line: str) -> bool:
        """判断是否像聊天消息"""
        if re.search(r"\d{2}:\d{2}(?:\d{2})?", line):
            return True
        if re.match(r"[^:]+:.+", line):
            return True
        return False
    
    def _parse_chat_line(self, line: str) -> Optional[dict]:
        """解析聊天记录行"""
        match = re.match(r"\[?(\d{2}:\d{2}(?:\d{2})?)\]?\s*([^:]+):(.+)", line)
        if match:
            today = datetime.now().strftime("%Y-%m-%d")
            return {
                "group_name": "微信聊天",
                "nickname": match.group(2).strip(),
                "content": match.group(3).strip(),
                "time": f"{today} {match.group(1)}",
                "raw": line,
            }
        return None
    
    def start_monitor(self, callback: Callable = None, interval: int = 5):
        """开始监控"""
        if self.running:
            return
        self.callback = callback
        self.poll_interval = interval
        self.running = True
        self.poll_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.poll_thread.start()
    
    def stop_monitor(self):
        """停止监控"""
        self.running = False
        self._auto_restart = False
        if self.poll_thread:
            self.poll_thread.join(timeout=2)
            self.poll_thread = None
    
    def enable_auto_restart(self, enabled: bool = True):
        """启用/禁用自动重启"""
        self._auto_restart = enabled
    
    def _monitor_loop(self):
        """监控循环（带自动重启）"""
        consecutive_errors = 0
        while self.running:
            try:
                messages = self.capture_notifications()
                if not messages:
                    messages = self.capture_and_ocr()
                
                for msg in messages:
                    if msg["content"] != self.last_notification:
                        self.last_notification = msg["content"]
                        self.captured_count += 1
                        if self.callback:
                            self.callback(msg)
                consecutive_errors = 0  # 成功则重置
            except Exception:
                consecutive_errors += 1
                if consecutive_errors > 10:
                    # 连续10次错误，等久一点再重试
                    time.sleep(self.poll_interval * 2)
                    consecutive_errors = 0
            time.sleep(self.poll_interval)
    
    def auto_restart_monitor(self):
        """检查监控状态，若意外停止则自动重启"""
        if self._auto_restart and not self.running and self.connected:
            try:
                self.running = True
                self.poll_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.poll_thread.start()
                return True
            except Exception:
                return False
        return False
    
    def get_phone_screen_info(self) -> Optional[dict]:
        """获取手机屏幕信息"""
        output = self._run_adb_command(["shell", "wm", "size"])
        if output:
            match = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
            if match:
                return {"width": int(match.group(1)), "height": int(match.group(2))}
        return None
