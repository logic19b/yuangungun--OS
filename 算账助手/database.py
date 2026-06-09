# -*- coding: utf-8 -*-
"""算账助手 - 数据库层 v5
新增5个功能：
1. P0-1: pending状态（待处理）
2. P0-2: actual_amount字段（实下金额）
3. P1-1: 按群分块统计
4. P1-2: 大额订单标记
5. P2: partial状态（部分成功）
"""

import sqlite3
import os
import re
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from parser import MessageParser
from lottery_engine import DrawResult, Bet, PlayType, evaluate


@dataclass
class Order:
    id: int
    group_id: int
    group_name: str
    nickname: str
    time: str
    lottery_type: str
    content: str
    amount: float
    prize: str
    status: str
    raw_text: str
    # v5新增字段
    actual_amount: float = 0.0  # 实下金额
    is_large: int = 0  # 是否大额订单
    play_type: str = ''  # 玩法类型（组六/组三/双飞/定位/直选/豹子等）
    bet_numbers: str = ''  # 投注号码


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Win11: 存到 %APPDATA%
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            data_dir = os.path.join(appdata, "算账助手")
        else:
            data_dir = os.path.dirname(db_path)
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = db_path or os.path.join(data_dir, "accounts.db")
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库表，v5新增字段使用ALTER TABLE兼容旧版本"""
        conn = self._conn()
        c = conn.cursor()
        
        # 群组表
        c.execute("""CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        
        # 订单表 - v5改造：用ALTER TABLE新增字段，保留原有结构
        c.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, nickname TEXT, time TEXT,
            lottery_type TEXT, content TEXT, amount REAL DEFAULT 0,
            prize TEXT, status TEXT DEFAULT 'failed',
            raw_text TEXT, bet_numbers TEXT, period TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id))""")
        
        # v5新增字段检测与添加
        cursor_info = c.execute("PRAGMA table_info(orders)").fetchall()
        existing_cols = [col[1] for col in cursor_info]
        
        # actual_amount: 实下金额（非0时优先用于统计）
        if 'actual_amount' not in existing_cols:
            c.execute("ALTER TABLE orders ADD COLUMN actual_amount REAL DEFAULT 0")
        
        # is_large: 大额订单标记
        if 'is_large' not in existing_cols:
            c.execute("ALTER TABLE orders ADD COLUMN is_large INTEGER DEFAULT 0")
        
        # play_type: 玩法类型（组六/组三/双飞/定位/直选/豹子等）
        if 'play_type' not in existing_cols:
            c.execute("ALTER TABLE orders ADD COLUMN play_type TEXT DEFAULT ''")
        
        # bet_numbers: 投注号码
        if 'bet_numbers' not in existing_cols:
            c.execute("ALTER TABLE orders ADD COLUMN bet_numbers TEXT DEFAULT ''")
        
        # 期号表
        c.execute("""CREATE TABLE IF NOT EXISTS periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT UNIQUE NOT NULL, lottery_type TEXT,
            open_code TEXT, open_time TEXT, remark TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        
        # v7: 设置表(存自定义玩法分类等)
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        
        # 玩法规则表
        c.execute("""CREATE TABLE IF NOT EXISTS play_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            play_type TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            category TEXT DEFAULT '基础玩法',
            base_amount REAL DEFAULT 10.0,
            min_bet REAL DEFAULT 1.0,
            odds_type TEXT DEFAULT 'fixed',
            odds_value REAL DEFAULT 0.0,
            key_field TEXT DEFAULT '',
            key_value INTEGER DEFAULT 0,
            odds_json TEXT DEFAULT '',
            prize REAL DEFAULT 0.0,
            principal_json TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            remark TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        
        # 索引
        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_group ON orders(group_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_time ON orders(time)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_periods_period ON periods(period)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_play_rules_type ON play_rules(play_type)")
        
        # v5新增: 大额订单索引
        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_is_large ON orders(is_large)")
        
        conn.commit()
        conn.close()
        
        # 初始化默认规则（仅在表为空时）
        self._init_default_rules()

    # ── 规则默认值 ──
    def _init_default_rules(self):
        """首次运行时，将lottery_engine中的硬编码规则写入数据库"""
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM play_rules").fetchone()[0]
        if count > 0:
            conn.close()
            return
        # 从lottery_engine导入默认规则
        from lottery_engine import (
            ODDS, ZULIU_BAOHAO_ODDS, ZUSAN_BAOHAO_ODDS, FUSHI_ODDS,
            KUADU_ODDS, HEZHI_ODDS, ZULIU_DANTUO_ODDS, ZUSAN_DANTUO_ODDS,
            ZULIU_ZHANBIANLAI_PRINCIPAL, ZUSAN_ZHANBIANLAI_PRINCIPAL,
            ZULIU_ZHANBIANLAI_PRIZE, ZUSAN_ZHANBIANLAI_PRIZE,
            ZULIU_ZHIXUAN_FUSHI_PRINCIPAL, ZUSAN_ZHIXUAN_FUSHI_PRINCIPAL,
            ZHIXUAN_FUSHI_PRIZE, LIANGMA_DANTUO_PRINCIPAL, LIANGMA_DANTUO_PRIZE,
            MIN_BET_ZHIZU, MIN_BET_ZULIU_ZUSAN, MIN_BET_ZHANBIANLAI,
            MIN_BET_ZHIXUAN_FUSHI, BASE_NORMAL, BASE_ZHIXUAN,
            PlayType
        )
        import json

        rules = [
            # play_type, display_name, category, base_amount, min_bet, odds_type, odds_value, key_field, key_value, odds_json, prize, principal_json, sort_order, remark
            ("ZHIXUAN", "直选", "基础玩法", BASE_ZHIXUAN, MIN_BET_ZHIZU, "fixed", 900, "", 0, "", 0, "", 1, "3位直选，2元/注，900倍"),
            ("ZUSAN", "组三", "基础玩法", BASE_ZHIXUAN, MIN_BET_ZHIZU, "fixed", 300, "", 0, "", 0, "", 2, "3位组三，2元/注，300倍"),
            ("ZULIU", "组六", "基础玩法", BASE_ZHIXUAN, MIN_BET_ZHIZU, "fixed", 150, "", 0, "", 0, "", 3, "3位组六，2元/注，150倍"),
            ("DUDAN", "独胆", "基础玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 3.3, "", 0, "", 0, "", 4, "1码，10元/注，3.3倍"),
            ("YIMA_DINGWEI", "一码定位", "基础玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 9, "", 0, "", 0, "", 5, "1码指定位，10元/注，9倍"),
            ("ERMA_DINGWEI", "二码定位", "基础玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 90, "", 0, "", 0, "", 6, "2码指定位，10元/注，90倍"),
            ("LIANGMA_DUIZI", "两码对子", "基础玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 30, "", 0, "", 0, "", 7, "2码，10元/注，30倍"),
            ("LIANGMA_SHUANGFEI", "两码双飞", "基础玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 16, "", 0, "", 0, "", 8, "2码，10元/注，16倍"),
            ("ZULIU_BAOHAO", "组六包号", "包号/复式", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "by_key", 0, "码数", 0, json.dumps(ZULIU_BAOHAO_ODDS, ensure_ascii=False), 0, "", 9, "N码，按码数查赔率"),
            ("ZUSAN_BAOHAO", "组三包号", "包号/复式", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "by_key", 0, "码数", 0, json.dumps(ZUSAN_BAOHAO_ODDS, ensure_ascii=False), 0, "", 10, "N码，按码数查赔率"),
            ("FUSHI", "复式", "包号/复式", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "by_key", 0, "码数", 0, json.dumps(FUSHI_ODDS, ensure_ascii=False), 0, "", 11, "N码直选复式，按码数查赔率（组选结算）"),
            ("KUADU", "跨度", "查表玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "by_key", 0, "跨度值", 0, json.dumps(KUADU_ODDS, ensure_ascii=False), 0, "", 12, "选跨度值，按值查赔率"),
            ("HEZHI", "和值", "查表玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "by_key", 0, "和值", 0, json.dumps(HEZHI_ODDS, ensure_ascii=False), 0, "", 13, "选和值，按值查赔率"),
            ("ZULIU_DANTUO", "组六胆拖", "胆拖", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "by_key", 0, "拖码数", 0, json.dumps(ZULIU_DANTUO_ODDS, ensure_ascii=False), 0, "", 14, "1胆N拖，按拖码数查赔率"),
            ("ZUSAN_DANTUO", "组三胆拖", "胆拖", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "by_key", 0, "拖码数", 0, json.dumps(ZUSAN_DANTUO_ODDS, ensure_ascii=False), 0, "", 15, "1胆N拖，按拖码数查赔率"),
            ("DA", "大", "大小单双", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 1.8, "", 0, "", 0, "", 16, "和值≥14，1.8倍"),
            ("XIAO", "小", "大小单双", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 1.8, "", 0, "", 0, "", 17, "和值≤13，1.8倍"),
            ("DAN", "单", "大小单双", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 1.8, "", 0, "", 0, "", 18, "和值为奇，1.8倍"),
            ("SHUANG", "双", "大小单双", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 1.8, "", 0, "", 0, "", 19, "和值为偶，1.8倍"),
            ("QUANBAO_DUIZI", "全包对子", "基础玩法", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "fixed", 30, "", 0, "", 0, "", 20, "10元/注，30倍"),
            ("ZULIU_ZHANBIANLAI", "组六粘边赖", "粘边赖", BASE_NORMAL, MIN_BET_ZHANBIANLAI, "principal_table", 0, "码数", 0, "", ZULIU_ZHANBIANLAI_PRIZE, json.dumps(ZULIU_ZHANBIANLAI_PRINCIPAL, ensure_ascii=False), 21, "固定本金，固定奖金300"),
            ("ZUSAN_ZHANBIANLAI", "组三粘边赖", "粘边赖", BASE_NORMAL, MIN_BET_ZHANBIANLAI, "principal_table", 0, "码数", 0, "", ZUSAN_ZHANBIANLAI_PRIZE, json.dumps(ZUSAN_ZHANBIANLAI_PRINCIPAL, ensure_ascii=False), 22, "固定本金，固定奖金600"),
            ("ZULIU_ZHIXUAN_FUSHI", "组六直选复式", "直选复式", BASE_NORMAL, MIN_BET_ZHIXUAN_FUSHI, "principal_table", 0, "码数", 0, "", ZHIXUAN_FUSHI_PRIZE, json.dumps(ZULIU_ZHIXUAN_FUSHI_PRINCIPAL, ensure_ascii=False), 23, "固定本金，中则1800"),
            ("ZUSAN_ZHIXUAN_FUSHI", "组三直选复式", "直选复式", BASE_NORMAL, MIN_BET_ZHIXUAN_FUSHI, "principal_table", 0, "码数", 0, "", ZHIXUAN_FUSHI_PRIZE, json.dumps(ZUSAN_ZHIXUAN_FUSHI_PRINCIPAL, ensure_ascii=False), 24, "固定本金，中则1800"),
            ("LIANGMA_DANTUO", "两码胆拖", "胆拖", BASE_NORMAL, MIN_BET_ZULIU_ZUSAN, "principal_table", 0, "拖码数", 0, "", LIANGMA_DANTUO_PRIZE, json.dumps(LIANGMA_DANTUO_PRINCIPAL, ensure_ascii=False), 25, "2胆N拖，固定本金，中则300"),
        ]
        for r in rules:
            conn.execute("""INSERT OR IGNORE INTO play_rules
                (play_type,display_name,category,base_amount,min_bet,odds_type,
                 odds_value,key_field,key_value,odds_json,prize,principal_json,
                 sort_order,remark)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", r)
        conn.commit()
        conn.close()

    # ── 规则 CRUD ──
    def get_all_rules(self):
        """获取所有规则，按sort_order排序"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT id,play_type,display_name,category,base_amount,min_bet,"
            "odds_type,odds_value,key_field,key_value,odds_json,prize,"
            "principal_json,sort_order,is_active,remark "
            "FROM play_rules ORDER BY sort_order"
        ).fetchall()
        conn.close()
        return [{"id":r[0],"play_type":r[1],"display_name":r[2],"category":r[3],
                 "base_amount":r[4],"min_bet":r[5],"odds_type":r[6],
                 "odds_value":r[7],"key_field":r[8],"key_value":r[9],
                 "odds_json":r[10],"prize":r[11],"principal_json":r[12],
                 "sort_order":r[13],"is_active":r[14],"remark":r[15]} for r in rows]

    def get_rule(self, play_type: str):
        """获取单条规则"""
        conn = self._conn()
        row = conn.execute(
            "SELECT id,play_type,display_name,category,base_amount,min_bet,"
            "odds_type,odds_value,key_field,key_value,odds_json,prize,"
            "principal_json,sort_order,is_active,remark "
            "FROM play_rules WHERE play_type=?", (play_type,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {"id":row[0],"play_type":row[1],"display_name":row[2],"category":row[3],
                "base_amount":row[4],"min_bet":row[5],"odds_type":row[6],
                "odds_value":row[7],"key_field":row[8],"key_value":row[9],
                "odds_json":row[10],"prize":row[11],"principal_json":row[12],
                "sort_order":row[13],"is_active":row[14],"remark":row[15]}

    def update_rule(self, play_type: str, **kwargs):
        """更新规则字段"""
        if not kwargs:
            return False
        import json as _json
        # odds_json / principal_json 如果传入dict则自动序列化
        for k in ("odds_json", "principal_json"):
            if k in kwargs and isinstance(kwargs[k], dict):
                kwargs[k] = _json.dumps(kwargs[k], ensure_ascii=False)
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [play_type]
        conn = self._conn()
        n = conn.execute(f"UPDATE play_rules SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE play_type=?", vals).rowcount
        conn.commit()
        conn.close()
        return n > 0

    def add_rule(self, play_type: str, display_name: str, category: str = "自定义",
                 base_amount: float = 10.0, min_bet: float = 1.0,
                 odds_type: str = "fixed", odds_value: float = 0.0,
                 key_field: str = "", odds_json: str = "",
                 prize: float = 0.0, principal_json: str = "",
                 sort_order: int = 99, remark: str = ""):
        """添加新规则"""
        conn = self._conn()
        try:
            conn.execute("""INSERT INTO play_rules
                (play_type,display_name,category,base_amount,min_bet,odds_type,
                 odds_value,key_field,odds_json,prize,principal_json,sort_order,remark)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (play_type, display_name, category, base_amount, min_bet, odds_type,
                 odds_value, key_field, odds_json, prize, principal_json, sort_order, remark))
            conn.commit()
            conn.close()
            return True
        except Exception:
            conn.close()
            return False

    def delete_rule(self, play_type: str):
        """删除规则"""
        conn = self._conn()
        n = conn.execute("DELETE FROM play_rules WHERE play_type=?", (play_type,)).rowcount
        conn.commit()
        conn.close()
        return n > 0

    def get_rules_odds(self, play_type: str):
        """获取某玩法的赔率表（从数据库读取，返回dict或float）"""
        rule = self.get_rule(play_type)
        if not rule:
            return None
        import json as _json
        ot = rule["odds_type"]
        if ot == "fixed":
            return rule["odds_value"]
        elif ot in ("by_key", "principal_table"):
            raw = rule.get("odds_json") if ot == "by_key" else rule.get("principal_json")
            if raw:
                try:
                    d = _json.loads(raw)
                    return {int(k): v for k, v in d.items()}
                except Exception:
                    return {}
            return {}
        return None

    # ── 群组 ──
    def add_group(self, name: str) -> int:
        conn = self._conn()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO groups(name) VALUES(?)", (name,))
        c.execute("SELECT id FROM groups WHERE name=?", (name,))
        gid = c.fetchone()[0]
        conn.commit()
        conn.close()
        return gid

    def get_groups(self) -> List[Tuple[int, str]]:
        conn = self._conn()
        rows = conn.execute("SELECT id,name FROM groups ORDER BY name").fetchall()
        conn.close()
        return rows

    # ── 订单 ──
    # v5改造: add_order支持pending/actual_amount/is_large参数
    def add_order(self, group_id, nickname, time, lottery_type,
                  content, amount, prize, status, raw_text,
                  actual_amount: float = None, is_large: int = None,
                  play_type: str = '', bet_numbers: str = '') -> int:
        """
        添加订单 v5
        - actual_amount: 实下金额，非0时优先用于统计
        - is_large: 是否大额订单（需大于设置的大额阈值）
        - play_type: 玩法类型（组六/组三/双飞/定位/直选/豹子等）
        - bet_numbers: 投注号码
        """
        conn = self._conn()
        c = conn.cursor()
        
        # v5: 默认为pending状态（新订单需要确认）
        if status is None:
            status = 'pending'
        
        # actual_amount处理
        if actual_amount is None:
            actual_amount = 0.0
        
        # is_large处理（自动根据金额判断，可外部指定覆盖）
        if is_large is None:
            is_large = 0
        
        c.execute("""INSERT INTO orders(group_id,nickname,time,lottery_type,
            content,amount,prize,status,raw_text,actual_amount,is_large,play_type,bet_numbers)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (group_id, nickname, time, lottery_type,
                   content[:200], amount, prize, status, raw_text,
                   actual_amount, is_large, play_type, bet_numbers))
        oid = c.lastrowid
        conn.commit()
        conn.close()
        return oid

    # v5改造: get_orders支持pending和partial筛选
    def get_orders(self, group_name=None, status="all", keyword=None,
                   period=None, is_large=None, play_type=None,
                   limit=500, offset=0):
        """
        获取订单列表 v5
        - status支持: all/pending/success/failed/refund/void/partial
        - is_large: None=全部, 0=普通, 1=大额
        - play_type: None=全部, 指定玩法类型筛选（组六/组三/双飞/定位等）
        """
        conn = self._conn()
        conds, params = [], []
        if group_name and group_name != "所有群":
            conds.append("g.name=?"); params.append(group_name)
        
        # v5: 支持pending/partial状态筛选
        if status != "all":
            if status in ("success", "failed", "refund", "void", "pending", "partial"):
                conds.append("o.status=?"); params.append(status)
        
        if keyword:
            conds.append("(o.content LIKE ? OR o.nickname LIKE ? OR o.raw_text LIKE ?)")
            params.extend([f"%{keyword}%"] * 3)
        if period:
            conds.append("o.time LIKE ?"); params.append(f"{period}%")
        
        # v5: 大额筛选
        if is_large is not None:
            conds.append("o.is_large=?"); params.append(is_large)
        
        # v5: 玩法类型筛选 (v7: 多标签用LIKE匹配，避免"直复试"误匹配"复试")
        if play_type:
            conds.append("(',' || o.play_type || ',') LIKE ?")
            params.append(f"%,{play_type},%")
        
        where = " AND ".join(conds) if conds else "1=1"

        total = conn.execute(
            f"SELECT COUNT(*) FROM orders o LEFT JOIN groups g ON o.group_id=g.id WHERE {where}",
            params).fetchone()[0]

        # v5: 查询actual_amount和is_large字段
        rows = conn.execute(
            f"""SELECT o.id,o.group_id,g.name,o.nickname,o.time,
                o.lottery_type,o.content,o.amount,o.prize,o.status,o.raw_text,
                o.actual_amount,o.is_large,o.play_type,o.bet_numbers
                FROM orders o LEFT JOIN groups g ON o.group_id=g.id
                WHERE {where} ORDER BY o.id DESC LIMIT ? OFFSET ?""",
            params + [limit, offset]).fetchall()
        conn.close()
        
        # v5: Order构造支持actual_amount/is_large/play_type/bet_numbers
        orders = []
        for r in rows:
            orders.append(Order(
                id=r[0], group_id=r[1], group_name=r[2], nickname=r[3], time=r[4],
                lottery_type=r[5], content=r[6], amount=r[7], prize=r[8],
                status=r[9], raw_text=r[10],
                actual_amount=r[11] if len(r) > 11 else 0.0,
                is_large=r[12] if len(r) > 12 else 0,
                play_type=r[13] if len(r) > 13 else '',
                bet_numbers=r[14] if len(r) > 14 else ''
            ))
        return orders, total

    def delete_order(self, order_id: int) -> bool:
        conn = self._conn()
        n = conn.execute("DELETE FROM orders WHERE id=?", (order_id,)).rowcount
        conn.commit()
        conn.close()
        return n > 0

    # v5改造: update_order支持修改actual_amount/actual_amount_prize/pending状态
    def update_order(self, order_id: int, amount: float = None, prize: str = None,
                     status: str = None, actual_amount: float = None,
                     actual_amount_prize: str = None, is_large: int = None) -> bool:
        """
        更新订单 v5
        - status: 可更新为success/failed/pending/partial等
        - actual_amount: 实下金额
        - actual_amount_prize: 实下金额的中奖状态
        - is_large: 大额标记
        """
        conn = self._conn()
        sets, vals = [], []
        
        if amount is not None:
            sets.append("amount=?"); vals.append(amount)
        if prize is not None:
            sets.append("prize=?"); vals.append(prize)
        if status is not None:
            sets.append("status=?"); vals.append(status)
        if actual_amount is not None:
            sets.append("actual_amount=?"); vals.append(actual_amount)
        if actual_amount_prize is not None:
            sets.append("prize=?"); vals.append(actual_amount_prize)
        if is_large is not None:
            sets.append("is_large=?"); vals.append(is_large)
        
        if not sets:
            return False
        
        n = conn.execute(f"UPDATE orders SET {','.join(sets)} WHERE id=?",
                         vals + [order_id]).rowcount
        conn.commit()
        conn.close()
        return n > 0

    # v5新增: 批量更新订单状态（用于"确认下单"功能）
    def batch_update_status(self, order_ids: List[int], status: str) -> int:
        """批量更新订单状态"""
        if not order_ids:
            return 0
        placeholders = ','.join('?' * len(order_ids))
        conn = self._conn()
        n = conn.execute(f"UPDATE orders SET status=? WHERE id IN ({placeholders})",
                        [status] + order_ids).rowcount
        conn.commit()
        conn.close()
        return n

    # v5新增: 批量标记大额订单
    def mark_large_orders(self, threshold: float = 500) -> int:
        """
        批量标记大额订单
        将amount >= threshold的订单的is_large标记为1，其他为0
        返回标记的大额订单数量
        """
        conn = self._conn()
        # 先清零所有大额标记
        conn.execute("UPDATE orders SET is_large = 0")
        # 再标记超过阈值的
        n = conn.execute(
            "UPDATE orders SET is_large = 1 WHERE amount >= ? AND amount > 0",
            (threshold,)
        ).rowcount
        conn.commit()
        conn.close()
        return n

    def clear_all(self):
        conn = self._conn()
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM groups")
        conn.execute("DELETE FROM periods")
        conn.commit()
        conn.close()

    # ── 统计 ──
    # v5改造: get_statistics增加pending/partial统计
    def get_statistics(self, group_name=None, period=None):
        """
        获取统计 v5
        新增pending（待处理）和partial（部分成功）统计
        actual_amount优先于amount用于统计（非0时）
        """
        conn = self._conn()
        conds, params = [], []
        if group_name and group_name != "所有群":
            conds.append("g.name=?"); params.append(group_name)
        if period:
            conds.append("o.time LIKE ?"); params.append(f"{period}%")
        where = " AND ".join(conds) if conds else "1=1"
        
        # v5: 所有状态分组统计
        rows = conn.execute(
            f"SELECT status,COUNT(*),COALESCE(SUM(amount),0),COALESCE(SUM(actual_amount),0) FROM orders o LEFT JOIN groups g ON o.group_id=g.id WHERE {where} GROUP BY status",
            params).fetchall()
        
        # v5: 使用actual_amount计算总金额（非0时优先）
        success_amount_row = conn.execute(
            f"""SELECT COALESCE(SUM(CASE WHEN actual_amount > 0 THEN actual_amount ELSE amount END),0) 
                FROM orders o LEFT JOIN groups g ON o.group_id=g.id 
                WHERE o.status='success' AND {where}""",
            params).fetchone()
        
        conn.close()
        
        # v5: 扩展统计字典
        stats = {
            "success": 0, "failed": 0, "refund": 0, "void": 0,
            "pending": 0, "partial": 0,  # v5新增
            "total": 0, "success_amount": 0.0
        }
        for row in rows:
            st, cnt, amt, actual_amt = row
            if st in stats and st not in ("total", "success_amount"):
                stats[st] = cnt
            stats["total"] += cnt
        
        stats["success_amount"] = success_amount_row[0] if success_amount_row else 0.0
        
        # 有效统计 = 总数 - 作废 - 退码
        stats["effective"] = stats["total"] - stats.get("void", 0) - stats.get("refund", 0)
        
        # 盈亏（简单：成功金额暂作为下注额）
        stats["profit"] = stats["success_amount"]
        
        return stats

    # v5新增: 按群分块统计
    def get_per_group_statistics(self) -> List[Dict]:
        """
        按群分块统计 v5
        返回每个群的独立统计：success/failed/pending/partial/refund/void/total/amount
        """
        conn = self._conn()
        groups = conn.execute("SELECT id,name FROM groups ORDER BY name").fetchall()
        
        result = []
        for gid, gname in groups:
            # 各状态统计
            rows = conn.execute(
                """SELECT status,COUNT(*),
                   COALESCE(SUM(CASE WHEN actual_amount > 0 THEN actual_amount ELSE amount END),0)
                   FROM orders WHERE group_id=? GROUP BY status""",
                (gid,)).fetchall()
            
            group_stats = {
                "group_name": gname,
                "success": 0, "failed": 0, "refund": 0, "void": 0,
                "pending": 0, "partial": 0,
                "total": 0, "amount": 0.0
            }
            
            for st, cnt, amt in rows:
                if st in group_stats:
                    group_stats[st] = cnt
                group_stats["total"] += cnt
                if st in ("success", "pending", "partial"):
                    group_stats["amount"] += amt
            
            result.append(group_stats)
        
        conn.close()
        return result

    def get_profit_stats(self, period=None, group_name=None):
        """盈亏统计（排除作废和退码）"""
        conn = self._conn()
        conds, params = ["o.status='success'"], []
        if period:
            conds.append("o.time LIKE ?"); params.append(f"{period}%")
        if group_name and group_name != "所有群":
            conds.append("g.name=?"); params.append(group_name)
        where = " AND ".join(conds)
        rows = conn.execute(
            f"""SELECT o.nickname,g.name,
                COALESCE(SUM(CASE WHEN o.actual_amount > 0 THEN o.actual_amount ELSE o.amount END),0),
                COUNT(*)
                FROM orders o LEFT JOIN groups g ON o.group_id=g.id
                WHERE {where} GROUP BY o.nickname ORDER BY SUM(o.amount) DESC""",
            params).fetchall()

        # 作废和退码的统计（不计入盈亏，单独展示）
        void_conds = list(conds)
        void_conds[0] = "o.status IN ('void', 'refund')"
        void_where = " AND ".join(void_conds)
        void_rows = conn.execute(
            f"""SELECT o.nickname,g.name,o.status,
                COALESCE(SUM(CASE WHEN o.actual_amount > 0 THEN o.actual_amount ELSE o.amount END),0),
                COUNT(*)
                FROM orders o LEFT JOIN groups g ON o.group_id=g.id
                WHERE {void_where} GROUP BY o.nickname,o.status""",
            params).fetchall()
        conn.close()

        players, total_bet, total_count = [], 0, 0
        for row in rows:
            nick, grp, bet, cnt = row
            players.append({"nickname": nick, "group_name": grp,
                            "total_bet": bet or 0, "bet_count": cnt})
            total_bet += bet or 0
            total_count += cnt

        # 作废/退码明细
        void_details = []
        for row in void_rows:
            nick, grp, status, amt, cnt = row
            label = "作废" if status == "void" else "退码"
            void_details.append({"nickname": nick, "group_name": grp,
                                 "status_label": label, "amount": amt or 0, "count": cnt})

        return {"players": players, "total_bet": total_bet,
                "total_count": total_count, "player_count": len(players),
                "void_details": void_details}

    # ── 期号 ──
    def add_period(self, period, lottery_type, open_code, remark=""):
        conn = self._conn()
        conn.execute("""INSERT OR REPLACE INTO periods(period,lottery_type,open_code,open_time,remark)
            VALUES(?,?,?,?,?)""",
                     (period, lottery_type, open_code, datetime.now().isoformat(), remark))
        conn.commit()
        conn.close()
        return True

    def get_period(self, period):
        conn = self._conn()
        row = conn.execute(
            "SELECT id,period,lottery_type,open_code,open_time,remark FROM periods WHERE period=?",
            (period,)).fetchone()
        conn.close()
        if row:
            return {"id": row[0], "period": row[1], "lottery_type": row[2],
                    "open_code": row[3], "open_time": row[4], "remark": row[5]}
        return None

    def get_all_periods(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT id,period,lottery_type,open_code,open_time,remark FROM periods ORDER BY period DESC LIMIT 100"
        ).fetchall()
        conn.close()
        return [{"id": r[0], "period": r[1], "lottery_type": r[2],
                 "open_code": r[3], "open_time": r[4], "remark": r[5]} for r in rows]

    def delete_period(self, period):
        conn = self._conn()
        n = conn.execute("DELETE FROM periods WHERE period=?", (period,)).rowcount
        conn.commit()
        conn.close()
        return n > 0

    # ── 中奖计算（使用终极全玩法引擎）──
    def calculate_winnings(self, period=None):
        conn = self._conn()
        if period:
            row = conn.execute("SELECT period,lottery_type,open_code FROM periods WHERE period=?",
                               (period,)).fetchone()
        else:
            row = conn.execute("SELECT period,lottery_type,open_code FROM periods ORDER BY period DESC LIMIT 1").fetchone()
        if not row:
            conn.close()
            return {"error": "未找到开奖记录"}
        pcode, ltype, ocode = row

        # 解析开奖号码
        try:
            draw = DrawResult.from_string(ocode)
        except ValueError:
            conn.close()
            return {"error": f"开奖号码格式错误: {ocode}"}

        # v5: 只计算success和partial状态的订单
        orders = conn.execute(
            "SELECT id,nickname,content,amount,bet_numbers,prize,status FROM orders WHERE time LIKE ? AND status IN ('success', 'partial')",
            (f"{pcode}%",)).fetchall()
        parser = MessageParser()
        winners, losers, total_bet, total_prize = [], [], 0, 0
        for oid, nick, content, amount, bnums, prize, status in orders:
            # 解析投注信息
            bet = parser.parse_bet_from_message(content, amount)
            if bet is None and bnums:
                bet = parser._reconstruct_bet(bnums, "", amount)
            if bet is None:
                # v5: 使用actual_amount
                total_bet += amount
                losers.append({
                    "id": oid, "nickname": nick, "content": content,
                    "amount": amount, "bet_numbers": bnums or "",
                })
                continue

            # 引擎兑奖
            result = evaluate(bet, draw)
            # v5: 使用actual_amount计算
            total_bet += result.principal

            if result.is_win:
                total_prize += result.prize
                winners.append({
                    "id": oid, "nickname": nick, "content": content,
                    "amount": amount, "bet_numbers": bnums or "",
                    "play_type": bet.play_type.value,
                    "win_detail": result.detail,
                    "win_prize": result.prize,
                    "principal": result.principal,
                    "net_profit": result.net_profit,
                })
            else:
                losers.append({
                    "id": oid, "nickname": nick, "content": content,
                    "amount": amount, "bet_numbers": bnums or "",
                    "play_type": bet.play_type.value,
                })

            # 更新数据库中的号码信息
            new_bnums = parser.extract_bet_numbers(content)
            if new_bnums:
                conn.execute("UPDATE orders SET bet_numbers=? WHERE id=?", (new_bnums, oid))

        conn.commit()
        conn.close()
        return {"period": pcode, "lottery_type": ltype, "open_code": ocode,
                "total_orders": len(orders), "winners_count": len(winners),
                "losers_count": len(losers), "total_bet": total_bet,
                "total_prize": total_prize,
                "net_result": total_prize - total_bet,
                "winners": winners, "losers": losers}

    # ── 批量导入 ──
    # v5改造: 自动标记大额订单
    def import_text(self, text: str, group_name: str = "默认群",
                    large_threshold: float = 500) -> int:
        """
        从文本导入 v5
        - large_threshold: 大额订单阈值（默认500元）
        - 自动标记超过阈值的订单
        """
        lines = text.strip().split("\n")
        gid = self.add_group(group_name)
        parser = MessageParser()
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            time_match = re.search(r"\[?(20\d{2}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})\]?", line)
            time_str = time_match.group(1) if time_match else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            nick_match = re.search(r"\]?\s*([^\s\[\]:]+)[:：]", line)
            nickname = nick_match.group(1) if nick_match else "未知"
            content = line[nick_match.end():].lstrip(":： ").strip() if nick_match else line
            parsed = parser.parse_message(content)
            
            # v5: 金额用于判断大额
            amount = parsed["amount"]
            is_large = 1 if amount >= large_threshold else 0
            
            self.add_order(gid, nickname, time_str, parsed["lottery_type"],
                           content, amount, parsed["prize"],
                           parsed["status"], line,
                           actual_amount=0, is_large=is_large)
            count += 1
        return count

    def import_file(self, path: str, group_name: str = None, large_threshold: float = 500):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if not group_name:
            group_name = os.path.splitext(os.path.basename(path))[0]
        return self.import_text(text, group_name, large_threshold), group_name

    # v5新增: 获取/设置大额阈值配置
    def get_large_threshold(self) -> float:
        """获取大额订单阈值"""
        return 500.0  # 默认值

    def set_large_threshold(self, threshold: float):
        """设置大额订单阈值（可扩展为配置表存储）"""
        pass  # 暂时用硬编码，后续可加配置表

    # ── v7: 玩法分类管理 ──
    DEFAULT_PLAY_TYPES = ["组六", "组三", "直选", "组选", "直组", "复试", "直复试",
                          "复式", "双飞", "对子", "定位", "豹子", "独胆", "托胆", "和值"]

    def get_play_type_categories(self) -> list:
        """获取玩法分类列表（用户可自定义）"""
        import json
        conn = self._conn()
        row = conn.execute("SELECT value FROM settings WHERE key='play_type_categories'").fetchone()
        conn.close()
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, ValueError):
                pass
        return list(self.DEFAULT_PLAY_TYPES)

    def save_play_type_categories(self, categories: list):
        """保存玩法分类列表"""
        import json
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
                     ('play_type_categories', json.dumps(categories, ensure_ascii=False)))
        conn.commit()
        conn.close()
