# -*- coding: utf-8 -*-
"""
算账助手 - 微信PC客户端消息自动扫描器
使用wxauto4(免费版)/wxautox4(Plus版)实现微信群消息自动扫描和导入
"""

import re
import time
import hashlib
import threading
from datetime import datetime
from typing import List, Dict, Callable, Optional, Set


class WeChatScanner:
    """微信PC客户端消息自动扫描器"""

    def __init__(self):
        self.wx = None
        self.running = False
        self.scan_thread = None
        self.scan_interval = 10  # 默认10秒
        self.callback = None
        self._auto_restart = False
        self._msg_fingerprints: Set[str] = set()
        self._max_fingerprints = 20000
        self.scanned_count = 0
        self._wx_version = None  # 'free' or 'plus'
        self._wx_available = False
        self._last_sessions = []

    def init_wechat(self) -> tuple:
        """初始化微信连接（优先Plus版，回退免费版）"""
        # 尝试Plus版
        try:
            from wxautox4 import WeChat
            self.wx = WeChat()
            self._wx_version = 'plus'
            self._wx_available = True
            sessions = self._get_session_names()
            return True, f"微信连接成功(Plus版)，发现 {len(sessions)} 个会话"
        except ImportError:
            pass
        except Exception as e:
            err = str(e)
            if "找不到" in err or "窗口" in err or "未找到" in err:
                pass  # 微信没打开，继续尝试免费版
            else:
                pass  # 其他错误，继续尝试免费版

        # 尝试免费版
        try:
            from wxauto4 import WeChat
            self.wx = WeChat()
            self._wx_version = 'free'
            self._wx_available = True
            sessions = self._get_session_names()
            return True, f"微信连接成功(免费版)，发现 {len(sessions)} 个会话"
        except ImportError:
            return False, "请先安装wxauto4: pip install wxauto4\n或Plus版: pip install wxautox4"
        except Exception as e:
            err = str(e)
            if "找不到" in err or "窗口" in err or "未找到" in err:
                return False, "请先打开微信PC客户端并登录"
            return False, f"微信连接失败: {err}"

    def is_available(self) -> bool:
        return self._wx_available and self.wx is not None

    def get_version(self) -> str:
        return self._wx_version or "未连接"

    def _get_session_names(self) -> List[str]:
        """获取会话名称列表"""
        try:
            if not self.wx:
                return []
            sessions = self.wx.GetSession()
            if not sessions:
                return []
            names = []
            for s in sessions:
                if hasattr(s, 'info'):
                    names.append(s.info)
                elif hasattr(s, 'name'):
                    names.append(s.name)
                else:
                    names.append(str(s))
            return names
        except:
            return []

    def get_session_list(self) -> List[str]:
        """获取当前会话列表（带缓存）"""
        self._last_sessions = self._get_session_names()
        return self._last_sessions

    def scan_current_chat(self) -> List[Dict]:
        """扫描当前聊天窗口消息"""
        messages = []
        try:
            if not self.wx:
                return messages

            # 获取当前聊天信息
            chat_name = "微信消息"
            try:
                info = self.wx.ChatInfo()
                if isinstance(info, dict):
                    chat_name = info.get('chat_name', '微信消息')
            except:
                pass

            msgs = self.wx.GetAllMessage()
            if not msgs:
                return messages

            for msg in msgs:
                parsed = self._parse_message(msg, chat_name)
                if parsed:
                    messages.append(parsed)
        except:
            pass
        return messages

    def scan_all_chats(self, target_sessions: List[str] = None) -> List[Dict]:
        """
        扫描全部群聊的新消息
        P1-4: 增加 target_sessions 参数，支持只扫描指定群聊
        - target_sessions: None=扫描全部，否则只扫描指定的群聊名称列表
        """
        all_messages = []

        if not self.wx:
            return all_messages
        
        # P1-4: 获取会话列表，支持过滤
        if target_sessions:
            sessions = target_sessions  # 只扫描指定群聊
        else:
            sessions = self.get_session_list()
        
        if not sessions:
            return self.scan_current_chat()

        # 记住当前聊天名
        current_chat = None
        try:
            info = self.wx.ChatInfo()
            if isinstance(info, dict):
                current_chat = info.get('chat_name', '')
        except:
            pass

        for session_name in sessions:
            try:
                self.wx.ChatWith(who=session_name)
                time.sleep(0.3)  # 等待窗口加载

                msgs = self.wx.GetAllMessage()
                if msgs:
                    for msg in msgs:
                        parsed = self._parse_message(msg, session_name)
                        if parsed:
                            all_messages.append(parsed)
            except:
                continue

        # 切回原来的聊天
        if current_chat:
            try:
                self.wx.ChatWith(who=current_chat)
            except:
                pass

        return all_messages

    def _parse_message(self, msg, chat_name: str = "微信消息") -> Optional[Dict]:
        """解析wxauto消息对象"""
        try:
            # 过滤非文本消息
            msg_type = getattr(msg, 'type', '')
            if msg_type and msg_type != 'text' and msg_type != 'friend':
                # 跳过图片、系统消息等
                if msg_type in ('image', 'file', 'video', 'voice', 'system',
                                'TimeMessage', 'SysMessage', 'RecallMessage'):
                    return None

            content = getattr(msg, 'content', '')
            if not content or len(content.strip()) < 2:
                return None

            # 过滤系统消息关键词
            skip_keywords = ["撤回了一条消息", "加入了群聊", "修改群名为",
                             "邀请", "拍了拍", "红包", "以上是历史消息",
                             "收款到账", "微信转账", "位置分享"]
            if any(kw in content for kw in skip_keywords):
                return None

            sender = getattr(msg, 'sender', '') or ''
            if not sender:
                # 尝试从content中提取昵称
                match = re.match(r'^([^\n:：]{1,20})[：:]\s*(.+)', content, re.DOTALL)
                if match:
                    sender = match.group(1).strip()
                    content = match.group(2).strip()
                else:
                    sender = "未知"

            return {
                "group_name": chat_name,
                "nickname": sender,
                "content": content,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "raw": getattr(msg, 'raw', content),
            }
        except:
            return None

    def _msg_fingerprint(self, msg: Dict) -> str:
        """生成消息指纹用于去重"""
        key = f"{msg.get('group_name', '')}|{msg.get('nickname', '')}|{msg.get('content', '')[:100]}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()[:16]

    def start_scan(self, callback: Callable = None, interval: int = 10, target_sessions: List[str] = None):
        """开始自动扫描 P1-4: 支持 target_sessions 参数"""
        if self.running:
            return
        if not self._wx_available:
            return
        self.callback = callback
        self.scan_interval = max(5, interval)
        self._target_sessions = target_sessions  # P1-4: 保存目标群聊列表
        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
    
    def _get_target_sessions(self) -> List[str]:
        """P1-4: 获取目标群聊列表"""
        return getattr(self, '_target_sessions', None)

    def stop_scan(self):
        """停止扫描"""
        self.running = False
        self._auto_restart = False
        if self.scan_thread:
            self.scan_thread.join(timeout=3)
            self.scan_thread = None

    def enable_auto_restart(self, enabled: bool = True):
        """启用/禁用自动重启"""
        self._auto_restart = enabled

    def auto_restart_scan(self) -> bool:
        """自动重启扫描"""
        if self._auto_restart and not self.running and self._wx_available:
            try:
                self.running = True
                self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
                self.scan_thread.start()
                return True
            except:
                return False
        return False

    def _scan_loop(self):
        """扫描循环（带自动重启和错误退避）P1-4: 支持 target_sessions"""
        consecutive_errors = 0
        while self.running:
            try:
                # P1-4: 传入 target_sessions 参数
                target_sessions = self._get_target_sessions()
                messages = self.scan_all_chats(target_sessions=target_sessions)

                # 去重，只处理新消息
                new_count = 0
                for msg in messages:
                    fp = self._msg_fingerprint(msg)
                    if fp not in self._msg_fingerprints:
                        self._msg_fingerprints.add(fp)
                        self.scanned_count += 1
                        new_count += 1
                        if self.callback:
                            self.callback(msg)

                # 限制指纹集合大小
                if len(self._msg_fingerprints) > self._max_fingerprints:
                    keep = list(self._msg_fingerprints)[-self._max_fingerprints // 2:]
                    self._msg_fingerprints = set(keep)

                consecutive_errors = 0
            except:
                consecutive_errors += 1
                if consecutive_errors > 10:
                    time.sleep(self.scan_interval * 3)
                    consecutive_errors = 0

            time.sleep(self.scan_interval)

    def get_status(self) -> dict:
        """获取扫描状态"""
        return {
            "available": self._wx_available,
            "running": self.running,
            "version": self._wx_version or "未连接",
            "scanned_count": self.scanned_count,
            "scan_interval": self.scan_interval,
            "sessions": len(self._last_sessions),
        }
