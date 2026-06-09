# -*- coding: utf-8 -*-
"""
算账助手 - 消息解析器 v5.7
核心策略: 扫描+摘要优先+严格去重

v5.6→v5.7 改动:
1. 同义替换预处理: 祖→组, 租→组, 个→各, 纽→组, 上→打
2. 直选类增强: 多号+各X倍, 号码+X倍, 各一倍冗余格式
3. 飞类增强: 飞各X米, 飞个X米(个=各), 双飞X倍, XX飞Y元
4. 组选增强: 点分多号+各X组, 各X组计价, 五组/十组格式
5. 直组混合增强: 直组一倍(缺各字), 直租(别字), 直一米, 直组各X元
6. 星号定位: 25* 63* 格式(两码定位), 支持各X元
7. 豹子增强: 号码+X倍(如222 5倍=10米), 0夸识别
8. 胆码增强: 胆X+金额, 十位/百位+金额, 上=打(定位场景)
9. 注数增强: X注+号码+直Y毛, X注+号码列表
10. 组三两码/转: 两码组三转各一倍, 组3两码+X倍
11. 多单合并: 句号分隔多条子单分别解析求和
12. 纽六格式: 5位码+纽六+末尾金额(如组六34579...80)
13. 人工踢出: 复杂注数/截断/末尾修改→返回-1标记
14. 各一元直两元组: 各X元直Y元组混合格式
15. 逗号开头格式: 逗号开头+五组/十组

v5.5→v5.6 改动:
1. 百位/十位定位增强: 支持"百位3-5各10"格式
2. 胆码直选混合: "胆3直300"等组合格式
3. 组三组六各X组: "组六各20米组三各10米"格式支持

v5.4→v5.5 改动:
1. 复杂注数处理: 36注1组格式增强
2. 组六组三各X组三: 多组码混合模式
3. 单注金额模式: 各X元直Y元组混合

v5.3→v5.4 改动:
1. 超长上下文支持: 分块处理+流式API+进度回调
2. claimed去重优化: O(n²)→O(n log n), 排序+二分查找
3. parse_batch_message_stream(): 生成器, 支持超长文本逐块输出
4. 分块策略: 按福/体消息边界+重叠区去重, 单块≤5000字符
5. Importer支持进度回调: on_progress(current, total, message)
6. Importer分块导入: 超长文本分块处理, 不一次性加载全部到内存
"""

import re
import bisect
from typing import Dict, Optional, List, Tuple, Generator, Callable

CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19,
    "二十": 20, "三十": 30, "四十": 40, "五十": 50,
    "六十": 60, "七十": 70, "八十": 80, "九十": 90,
    "一百": 100, "两百": 200, "三百": 300, "五百": 500,
    "一千": 1000, "两千": 2000, "五千": 5000,
}

def parse_cn_num(text: str) -> Optional[int]:
    if not text: return None
    text = text.strip()
    if text in CN_NUM_MAP: return CN_NUM_MAP[text]
    if '十' in text:
        parts = text.split('十')
        tens = CN_NUM_MAP.get(parts[0], 1) if parts[0] else 1
        ones = CN_NUM_MAP.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    try: return int(text)
    except: return None

def _cn_num_or_digit(text: str) -> Optional[int]:
    v = parse_cn_num(text)
    if v is not None: return v
    try: return int(text)
    except: return None


class MessageParser:
    VOID_KEYWORDS = ["作废", "无效", "撤单", "取消", "撤销", "退码", "退款", "退还", "退回",
                     "不要了", "不要", "算了", "作废单", "废单", "废了"]

    def _is_after_sequence(self, text: str, pos: int) -> bool:
        """pos前面是否紧跟4位+数字(序列号)"""
        before = text[:pos].rstrip()
        return bool(re.search(r'\d{4,}$', before))

    def _count_3digit_nums(self, text: str) -> int:
        """统计文本中3位数字(投注号码)的数量"""
        return len(re.findall(r'(?<!\d)\d{3}(?!\d)', text))

    # ============================================================
    # parse_amount: 单条消息金额提取 (保留兼容)
    # ============================================================
    def parse_amount(self, text: str) -> float:
        if not text: return 0
        if any(k in text for k in self.VOID_KEYWORDS): return 0
        return self._extract_amount(text)

    def _extract_amount(self, text: str) -> float:
        """优先级链: 摘要 > 公式 > 组件 > 通用"""

        # ========== v5.7 同义替换预处理 ==========
        # 祖/租/纽 → 组 (别字/同音)
        text = re.sub(r'纽六', '组六', text)  # 纽六=组六
        text = re.sub(r'(?<=[^\w])祖(?=[^\w])', '组', text)  # 祖=组
        text = re.sub(r'(?<=[^\w])租(?=[^\w])', '组', text)  # 租=组
        # 个 → 各 (同义)
        text = re.sub(r'飞个', '飞各', text)  # 飞个=飞各
        text = re.sub(r'一值', '直', text)  # 一值=直(typo, 如"一值一组"="直一组")
        # 上 → 打 (定位场景同义)
        text = re.sub(r'百位(\d)\s*上', r'百位\1打', text)  # 百位X上=百位X打
        text = re.sub(r'十位(\d)\s*上', r'十位\1打', text)  # 十位X上=十位X打

        # P0: 括号金额
        m = re.search(r'[（(]\s*(\d+(?:\.\d+)?)\s*[元米块]?\s*[）)]', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P1: 🈴X
        m = re.search(r'🈴\s*(\d+(?:\.\d+)?)', text)
        if m: return float(m.group(1))

        # P2: 合计/共计/总计X (但如果后面有乘法公式如"合计486*0.5=243"，让P4处理)
        has_mul_formula = bool(re.search(r'\d+\s*[*/×xX]\s*\d+(?:\.\d+)?\s*=\s*\d+', text))
        if not has_mul_formula:
            for pat in [r'合计\s*(\d+(?:\.\d+)?)\s*[元米块]?',
                        r'共计\s*(\d+(?:\.\d+)?)\s*[元米块]?',
                        r'总计\s*(\d+(?:\.\d+)?)\s*[元米块]?']:
                m = re.search(pat, text)
                if m:
                    v = float(m.group(1))
                    if 0.1 <= v <= 100000: return v

        # P3: 记X / 计X (但如果后面有乘法公式，让P4处理)
        if not has_mul_formula:
            m = re.search(r'[记计]\s*(\d+(?:\.\d+)?)', text)
            if m:
                v = float(m.group(1))
                if 0.1 <= v <= 100000: return v

        # P4: 乘法 X*Y=Z
        m = re.search(r'(\d+)\s*[*/×xX]\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)', text)
        if m: return float(m.group(3))

        # P4b: 加法 X+Y=Z (如 "21+12=33")
        m = re.search(r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)', text)
        if m: return float(m.group(3))

        # P5: X注各Y毛单共Z米
        m = re.search(r'(\d+)\s*注\s*各\s*[零一二两三四五六七八九十\d]+\s*毛\s*(?:单\s*)?(?:共|合计)\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m: return float(m.group(2))

        # P5.5: 直X倍组Y倍共Z / 直X倍组Y倍Z / 直X倍组Y倍(无共，自己算)
        m = re.search(r'直\s*(\d+(?:\.\d+)?)\s*倍\s*组\s*(\d+(?:\.\d+)?)\s*倍\s*共?\s*(\d+(?:\.\d+)?)', text)
        if m:
            # 有共Z → 用Z
            v = float(m.group(3))
            if 0.1 <= v <= 100000: return v
        m = re.search(r'直\s*(\d+(?:\.\d+)?)\s*倍\s*组\s*(\d+(?:\.\d+)?)\s*倍', text)
        if m:
            # 无共Z → 直倍×2+组倍×2
            zhi = float(m.group(1))
            zu = float(m.group(2))
            return zhi * 2 + zu * 2

        # P6前置: 共X直各Y毛/元 (如 "福共486直各五毛" — 486注×0.5=243)
        # 如果"共X"后面紧跟"直各"/"直组各"，则按倍数模式处理，不走P6
        m = re.search(r'共\s*(\d+(?:\.\d+)?)\s*直各\s*([零一二两三四五六七八九十\d]+)\s*[毛元米块]', text)
        if m:
            count = int(float(m.group(1)))
            per = _cn_num_or_digit(m.group(2))
            suffix = text[m.start():m.end()]
            if per is not None and count > 0:
                if '毛' in suffix:
                    return count * per * 0.1
                else:
                    return count * per

        # P6: 共X(元/米/块)? — "共"后单位可选，但要求后面不是纯数字(避免匹配"共2965 003")
        # 也不能是"共X注"格式(由P16处理)
        m = re.search(r'共\s*(\d+(?:\.\d+)?)\s*[元米块]?(?!\s*\d)(?!.*注)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P7: X注底共W元
        m = re.search(r'\d+\s*注\s*底.*?共\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m: return float(m.group(1))

        # P8: 复试/复式X单Y
        m = re.search(r'复[试式]\s*[零一二两三四五六七八九十\d]+\s*单\s*(\d+)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P9a: 单选X倍Y (如 "单选3倍12")
        m = re.search(r'单选\s*(\d+)\s*倍\s*(\d+)', text)
        if m:
            v = float(m.group(2))
            if 0.1 <= v <= 100000: return v

        # P9a2: 直X倍 (如 "697直4倍" = 4倍×2元=8元)
        # 支持"直选"格式(无空格)
        m = re.search(r'(\d{3})\s*直(?:选)?\s*(\d+)\s*倍', text)
        if m:
            v = int(m.group(2)) * 2
            if 0.1 <= v <= 100000: return v

        # P9a3: 各X直 (如 "297 682 785 各2直" = 3号×2×2元=12)
        m = re.search(r'((?:\d{3}\s*)+)\s*各\s*(\d+)\s*直', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            zhi = int(m.group(2))
            v = count * zhi * 2
            if 0.1 <= v <= 100000: return v

        # P9b: 毒/独胆X打Y元 (如 "毒5打2000" "独胆3打50元")
        m = re.search(r'(?:毒|独胆)\s*\d+\s*打\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P9b2: 独胆X，[彩种]Y米 (如 "独胆3，福200米" — 无"打"字，金额在彩种后)
        if re.search(r'(?:毒|独胆|独\d)', text):
            m2 = re.search(r'(?:体|福|体福|福体)\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
            if m2:
                v = float(m2.group(1))
                if 0.1 <= v <= 100000: return v

        # P9b3: 独X [Y...] 各Z元 (如 "体独0 1 各300元" — 2个胆各300=600)
        m = re.search(r'(?:毒|独胆|独)\s*\d[\d\s]*各\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m:
            # 数独胆个数
            prefix = text[:m.start()]
            du_part = text[m.start():text.index('各', m.start())]
            nums = re.findall(r'\d', du_part)
            count = max(len(nums), 1)
            v = float(m.group(1)) * count
            if 0.1 <= v <= 100000: return v

        # P9b4: X毒Y (如 "8毒50" — 号码在前，毒在后，金额=50)
        m = re.search(r'\d\s*毒\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P9b5: 独胆X一百 / 独胆X Y百 (如 "体彩排三独胆3一百" — 100)
        m = re.search(r'(?:独胆|独)\s*\d+\s*[，,]?\s*([零一二两三四五六七八九十百]+)\s*[元米块]?', text)
        if m:
            v = _cn_num_or_digit(m.group(1))
            if v is not None and 0.1 <= v <= 100000: return v

        # P9c: X米直Y米组 (如 "812 813 357一米直三米组" — 直1米+组3米=12)
        # 中文版: 一米直三米组
        m = re.search(r'([零一二两三四五六七八九十]{1,2})\s*米\s*直\s*([零一二两三四五六七八九十]{1,2})\s*米\s*组', text)
        if m:
            zhi_mi = parse_cn_num(m.group(1))
            zu_mi = parse_cn_num(m.group(2))
            if zhi_mi is not None and zu_mi is not None:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
                num_count = max(len(nums), 1)
                return num_count * (zhi_mi + zu_mi)
        # 阿拉伯版: 2米直3米组
        m = re.search(r'(\d{1,2})\s*米\s*直\s*(\d{1,2})\s*米\s*组', text)
        if m:
            zhi_mi = int(m.group(1))
            zu_mi = int(m.group(2))
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            return num_count * (zhi_mi + zu_mi)
        # 混合版: 3米直五米组 / 三米直5米组 (阿拉伯+中文混合)
        m = re.search(r'([零一二两三四五六七八九十\d]{1,2})\s*米\s*直\s*([零一二两三四五六七八九十\d]{1,2})\s*米\s*组', text)
        if m:
            zhi_raw = m.group(1)
            zu_raw = m.group(2)
            zhi_mi = _cn_num_or_digit(zhi_raw)
            zu_mi = _cn_num_or_digit(zu_raw)
            if zhi_mi is not None and zu_mi is not None:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
                num_count = max(len(nums), 1)
                return num_count * (zhi_mi + zu_mi)

        # P9d: 直组各X元/毛/米 (如 "502.507 直组各2元" — 直+组各2倍=8元/号)
        # "直组各"表示直选和组选各下X倍(2X米)，"各一元"=各一倍=4米/号
        m = re.search(r'直组各\s*([零一二两三四五六七八九十\d]+)\s*[元米块毛]', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            suffix = text[m.start():m.end()]
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            if per is not None and num_count > 0:
                if '毛' in suffix:
                    return num_count * per * 0.1 * 2  # 直+组各X毛
                else:
                    return num_count * per * 4  # 直各per倍(2per)+组各per倍(2per)=4per米/号

        # P9e: 直组X毛/元/米 — "直组"后跟金额 = 直+组合计X per号 per彩种
        # (如 "福直组0.5米" — 直+组合计0.5, "647直组一米" — 直+组合计1米)
        # 注意: "五毛直组"格式(金额在前)由NV14处理
        m = re.search(r'直组\s*([零一二两三四五六七八九十\d]+(?:\.\d+)?)\s*[毛元米块]', text)
        if m:
            per_raw = m.group(1)
            per = _cn_num_or_digit(per_raw)
            suffix = text[m.start():m.end()]
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            if per is not None:
                if '毛' in suffix:
                    return num_count * per * 0.1  # 直+组合计X毛 per号
                else:
                    return num_count * per  # 直+组合计X元/米 per号

        # P9f: 组各X米/元 (如 "459..559..组各6米" — 2组×6米=12)
        m = re.search(r'组各\s*(\d+(?:\.\d+)?)\s*[元米块毛]', text)
        if m:
            per = float(m.group(1))
            suffix = text[m.start():m.end()]
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            if '毛' in suffix:
                return num_count * per * 0.1
            else:
                return num_count * per

        # P9g: 直各X毛/元 (如 "486直各五毛" — 486注×0.5=243)
        m = re.search(r'直各\s*([零一二两三四五六七八九十\d]+)\s*[毛元米块]', text)
        if m:
            per_raw = m.group(1)
            per = _cn_num_or_digit(per_raw)
            suffix = text[m.start():m.end()]
            # 尝试从前面获取注数
            before = text[:m.start()]
            # 检查"共X注"或"X注"
            zhu_m = re.search(r'(?:共\s*)?(\d+)\s*注', before)
            if zhu_m:
                count = int(zhu_m.group(1))
            else:
                # 数前面的3位号码
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
                count = max(len(nums), 1)
            if per is not None and count > 0:
                if '毛' in suffix:
                    return count * per * 0.1
                else:
                    return count * per

        # P9g2: 组X米 (如 "组1米4" — 组选1米×号码数=4)
        m = re.search(r'组\s*([零一二两三四五六七八九十\d]+)\s*米\s*(\d+(?:\.\d+)?)', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            total = float(m.group(2))
            if per is not None:
                return total  # 组1米4 → 总4米

        # P9g3: 组X米 (无后缀总额, 如 "组1米" — 号码数×1米)
        m = re.search(r'组\s*([零一二两三四五六七八九十\d]+)\s*米(?!\s*\d)', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            if per is not None and num_count > 0:
                return num_count * per

        # P9g4: 十二倍/十五倍等中文倍数 (如 "666十二倍" — 12倍×2元=24)
        m = re.search(r'\d{3}\s*([零一二两三四五六七八九十百]+)\s*倍', text)
        if m:
            bei = parse_cn_num(m.group(1))
            if bei is not None and bei > 0:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
                num_count = max(len(nums), 1)
                return num_count * bei * 2

        # P9g5: 组六组三各X，Y (如 "02359组六组三各20，40" — Y是总额; 必须有逗号分隔)
        m = re.search(r'组六组三各\s*(\d+(?:\.\d+)?)\s*[，,]\s*(\d+(?:\.\d+)?)', text)
        if m:
            v1 = float(m.group(1))
            v2 = float(m.group(2))
            if v1 > 0 and v2 > 0:  # 确保两个数字都>0
                return float(m.group(2))  # 第二个数字是总额

        # P9g5b: 组六组三各X元 (如 "体12组六组三各10元" — 组六10+组三10=20)
        m = re.search(r'组六组三各\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m:
            per = float(m.group(1))
            return per * 2  # 组六+组三各per
        m = re.search(r'组三组六各\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m:
            per = float(m.group(1))
            return per * 2

        # P9g6: X码组三各Y元 (如 "0234568，3456789福彩组三各十元" — 2组×10=20)
        m = re.search(r'组三各\s*([零一二两三四五六七八九十\d]+)\s*[元米块毛]', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            suffix = text[m.start():m.end()]
            before = text[:m.start()]
            # 数前面的X码组合（5-7位数字）
            combos = re.findall(r'(?<!\d)\d{5,7}(?!\d)', before)
            combo_count = max(len(combos), 1)
            if per is not None and combo_count > 0:
                if '毛' in suffix:
                    return combo_count * per * 0.1
                return combo_count * per

        # P9g7: 组六一倍 (如 "013458组六一倍" — 号码数×2元=12)
        m = re.search(r'组六\s*一倍', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            combos = re.findall(r'(?<!\d)\d{5,7}(?!\d)', before[-60:])
            count = max(len(nums), len(combos), 1)
            return count * 2

        # P9g8: 组六/组三 X码打Y元 (如 "福彩组六 23469打200" — 200元)
        # 支持中文金额: 打四十, 打二十块钱, 打十倍, 打两倍, 打一百块钱
        m = re.search(r'组[三六]\s*\d+\s*打\s*([零一二两三四五六七八九十百\d]+)\s*(?:块钱|元|米|块|倍)?', text)
        if m:
            v = _cn_num_or_digit(m.group(1))
            if v is not None and 0.1 <= v <= 100000:
                suffix = text[m.start():m.end()]
                if '倍' in suffix:
                    return v * 2  # X倍 → X*2米
                return v
        # 阿拉伯数字版: 组六0467打40
        m = re.search(r'组[三六]\s*\d+\s*打\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v
        # 号码+组六/组三打+金额(无米后缀, 如 "12508 福组六打20" "12508排列三组六打30")
        m = re.search(r'组[三六]\s*打\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P9g9: 各打一倍组选/直选 (如 "977，121，836各打一倍直选" — 3号×2=6)
        m = re.search(r'各打一倍\s*(?:组选|直选|单选)', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-80:])
            num_count = max(len(nums), 1)
            return num_count * 2

        # P9g10: X飞Y元 (如 "14.13.18飞20" — 双飞20元，后缀可选)
        # 但要避免匹配"双飞38-50"这种格式(双飞+号码+金额)
        # 检查是否是"双飞"格式(双飞+两码)
        if re.search(r'双飞\s*\d{2}', text):
            # "双飞"格式: "双飞38-50" → 50(默认一倍=10元/组)
            m = re.search(r'双飞\s*\d{2}\s*[-—–,]\s*(\d+)', text)
            if m:
                v = float(m.group(1))
                if 0.1 <= v <= 100000: return v
            # "双飞" + 号码 + 金额/百 (如 "双飞57一百" "福：67双飞一百")
            m = re.search(r'双飞\s*\d{2}\s*([零一二两三四五六七八九十百\d]+)\s*[元米块]?', text)
            if m:
                v = _cn_num_or_digit(m.group(1))
                if v is not None and 0.1 <= v <= 100000: return v
        else:
            # 普通"飞"格式
            m = re.search(r'飞\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
            if m:
                v = float(m.group(1))
                if 0.1 <= v <= 100000: return v
        m = re.search(r'复[试式]\s*\d+\s*打\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P9i: 5位数字-组六X米 (如 "78043-组六福10米" — 组六10米)
        m = re.search(r'\d{3,5}\s*[-—–]\s*组六\s*(?:[体福]\s*)?(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P9j: 组选X注打Y元 (如 "福彩组选75注打一元" — 75注×1元=75)
        m = re.search(r'组选\s*(\d+)\s*注\s*打\s*([零一二两三四五六七八九十\d]+)\s*[元米块毛]', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                suffix = text[m.start():m.end()]
                if '毛' in suffix:
                    return count * per * 0.1
                return count * per

        # P9k: X注打一元直选 (如 "福256注打一元直选" — 256×1=256)
        m = re.search(r'(\d+)\s*注\s*打\s*([零一二两三四五六七八九十\d]+)\s*[元米块毛]?\s*直选', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                suffix = text[m.start():m.end()]
                if '毛' in suffix:
                    return count * per * 0.1
                return count * per

        # P9l: 一单一 (如 "福753/496/553一单一" — 默认一单一组=4/号)
        m = re.search(r'一单一(?!组)', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
            count = max(len(nums), 1)
            return count * 4  # 一单一组=4元/号

        # P9m: 组X各一倍 (如 "福组413.315.417.416.476.756各一倍" — 组一倍=2米/号)
        m = re.search(r'组\s*([\d，,、.\s]+?)\s*各一倍', text)
        if m:
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(1))
            count = max(len(nums), 1)
            return count * 2  # 组一倍=2米

        # P9n: 组三组六各X (多组码, 如 "体235789，145679，124689，组三组六各200" — 3组×400=1200)
        m = re.search(r'([\d，,、\s]+?)\s*组三组六各\s*(\d+(?:\.\d+)?)', text)
        if m:
            combos = re.findall(r'(?<!\d)\d{5,7}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            per = float(m.group(2))
            return combo_count * per * 2  # 组三+组六各per
        m = re.search(r'([\d，,、\s]+?)\s*组六组三各\s*(\d+(?:\.\d+)?)', text)
        if m:
            combos = re.findall(r'(?<!\d)\d{5,7}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            per = float(m.group(2))
            return combo_count * per * 2

        # P9o: X百单Y组 (如 "体212一百单五十组" — 100×2+50×2=300)
        # 中文数字版本: 一百单五十组, 五十单二十组 etc.
        m = re.search(r'([零一二两三四五六七八九十百]+)\s*单\s*([零一二两三四五六七八九十百]+)\s*组', text)
        if m:
            x = parse_cn_num(m.group(1))
            y = parse_cn_num(m.group(2))
            if x is not None and y is not None and x > 0 and y > 0:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                # 如果是"号码+X单Y组"格式, 乘号码数; 否则直接算
                return (x + y) * 2 * max(len(nums), 1)

        # P9o2: 阿拉伯数字+百单 (如 "212一百单五十组" — 一百=100单, 五十=50组)
        # 已被P9o覆盖(中文数字版本)

        # P9p: X组六各Y (如 "12364 12369 组六各100" — 2组×100=200)
        m = re.search(r'([\d\s]+?)\s*组六各\s*(\d+(?:\.\d+)?)', text)
        if m:
            combos = re.findall(r'(?<!\d)\d{5}(?!\d)', m.group(1))
            if not combos:
                combos = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            per = float(m.group(2))
            return combo_count * per

        # P9q: X体彩组三，十元 / X体彩组六，十元 (如 "3456789体彩组三，十元" — 10)
        m = re.search(r'组[三六]\s*[，,]\s*([零一二两三四五六七八九十\d]+)\s*[元米块]', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            if per is not None:
                return per

        # P9r: N码+组六/组三+金额 (如 "35789组六100" "124569组三200组六100" "福组六5689五十")
        # 支持: 五码/六码/七码/八码+组六+阿拉伯或中文金额
        # 也支持: "福组六0123467七码，200" (带码数标记和逗号)
        # 也支持: "013456福组100" ("福组"=福组六简写)
        # 先尝试带中文金额
        m = re.search(r'(?:福|体)?\s*组[六3]\s*[\d,，]*\s*(?:[四五六七八]码)?\s*[，,]?\s*([零一二两三四五六七八九十百]+)\s*[元米块]?$', text)
        if m:
            v = parse_cn_num(m.group(1))
            if v is not None and 0.1 <= v <= 100000:
                return v
        # N码+组六+阿拉伯金额 (号码在前,金额在后)
        m = re.search(r'[福体]?\s*(?:组[六3])?\s*\d{4,9}\s*(?:[四五六七八]码)?\s*[，,]?\s*组[六3]\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v
        # 纯号码+组六+阿拉伯金额 (无福/体前缀)
        m = re.search(r'\b\d{4,9}\s*组[六3]\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v
        # 号码+组六+中文金额 (如 "4568组六一百" "福组六5689五十")
        m = re.search(r'(?:福|体)?\s*(?:\d{3,9}\s*)?组[六3]\s*([零一二两三四五六七八九十百]+)\s*[元米块]?', text)
        if m:
            v = parse_cn_num(m.group(1))
            if v is not None and 0.1 <= v <= 100000:
                return v
        # 组六+号码+X码+阿拉伯金额 (如 "福组六0123467七码，200")
        m = re.search(r'[福体]?\s*组[六3]\s*\d{4,9}\s*[四五六七八]码\s*[，,]?\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v
        # "福组"+金额 (福组=福组六简写)
        m = re.search(r'福组\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v
        # 组三+金额+组六+金额 (先组三后组六, 如 "124569组三200组六100")
        m = re.search(r'组三\s*(\d+(?:\.\d+)?)\s*组六\s*(\d+(?:\.\d+)?)', text)
        if m:
            v1 = float(m.group(1))
            v2 = float(m.group(2))
            if 0.1 <= v1 <= 100000 and 0.1 <= v2 <= 100000:
                return v1 + v2
        # 组六+金额+组三+金额 (先组六后组三, 同上反向)
        m = re.search(r'组六\s*(\d+(?:\.\d+)?)\s*组三\s*(\d+(?:\.\d+)?)', text)
        if m:
            v1 = float(m.group(1))
            v2 = float(m.group(2))
            if 0.1 <= v1 <= 100000 and 0.1 <= v2 <= 100000:
                return v1 + v2

        # P9s: 直选+中文倍数 (如 "952福直三十倍" → 30×2=60)
        m = re.search(r'(\d{3})\s*[福体]?\s*直(?:选)?\s*([零一二两三四五六七八九十百]+)\s*倍', text)
        if m:
            v = parse_cn_num(m.group(2))
            if v is not None and v > 0:
                return v * 2
        # 多码+直选+倍数 (如 "福直 235,236,245,256,367。一倍")
        m = re.search(r'直(?:选)?\s*[\d,，、\s。]+?([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            v = _cn_num_or_digit(m.group(1))
            if v is not None and v > 0:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
                return v * 2 * max(len(nums), 1)

        # P9t: 复试/复式+金额 (无"单"字, 如 "福 409直复试600" "福复试六码125789 下2000")
        m = re.search(r'复[试式]\s*(?:[四五六七八]码\s*)?\d+\s*[，,下]?\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v
        # 直复试+金额 (如 "福 409直复试600")
        m = re.search(r'直?复[试式]\s*(\d{2,})', text)
        if m:
            ns = m.group(1)
            v = float(ns)
            if len(ns) >= 3 and 0.1 <= v <= 100000:
                return v

        # P9u: 个位定位 (如 "9个位20 7个位200 2个位30" → 20+200+30=250)
        ge_total = 0
        for m in re.finditer(r'(\d)\s*个位\s*(\d+(?:\.\d+)?)\s*[元米块]?', text):
            ge_total += float(m.group(2))
        if ge_total > 0 and ge_total <= 100000:
            return ge_total

        # P9v: 豹子列表+X单 (如 "000 111 222...999三单" → 10号×3×2=60)
        m = re.search(r'((?:000|111|222|333|444|555|666|777|888|999)[\s,，、]*)+([零一二两三四五六七八九十\d]+)\s*单', text)
        if m:
            before = text[:m.start()]
            baozi_nums = re.findall(r'(?:000|111|222|333|444|555|666|777|888|999)', text[:m.end()])
            cn = _cn_num_or_digit(m.group(2))
            if cn is not None and len(baozi_nums) > 0:
                return cn * 2 * len(baozi_nums)

        # P9w: 多组两码双飞 (如 "福35.38.36.34.37.31双五十" → 6组×50=300)
        m = re.search(r'([\d\s.,，、]+?)\s*双\s*([零一二两三四五六七八九十百\d]+)', text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if pairs and per is not None and per > 0:
                return len(pairs) * per

        # P9x: 多号+X单 (无组无金额, 如 "395五单" → 5×2=10, "702三单 720三单 072三单" → 分开处理)
        m = re.search(r'(\d{3})\s*([零一二两三四五六七八九十]+)\s*单(?!\\s*组)', text)
        if m:
            cn = parse_cn_num(m.group(2))
            if cn is not None and cn > 0:
                # 单号+X单
                return cn * 2

        # P9y: 组选+3码+倍数 (如 "福彩组144.两倍" → 组选144 两倍=4)
        m = re.search(r'组选?\s*(\d{3})\s*[.,，]\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            v = _cn_num_or_digit(m.group(2))
            if v is not None and v > 0:
                return v * 2

        # P9z: 各一组+金额在括号 (如 "体彩各一组 269，535，919(6" → 3号×2×1=6)
        m = re.search(r'各一组\s*[\d\s,，.、]+\s*[（(]\s*(\d+(?:\.\d+)?)\s*[）)]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9za: 0跨+金额 (如 "福0跨20" → 20)
        m = re.search(r'[零0]\s*跨\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zb: 打团+倍数 (如 "福 049，089，打团一倍" → 2号×2=4)
        m = re.search(r'打团\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            v = _cn_num_or_digit(m.group(1))
            if v is not None and v > 0:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
                return v * 2 * max(len(nums), 1)

        # P9zc: X注+五单 (如 "146 164 346...福48五单" → 48注×5×2=480)
        m = re.search(r'[福体]?\s*(\d+)\s*([零一二两三四五六七八九十]+)\s*单', text)
        if m:
            zhu = int(m.group(1))
            cn = parse_cn_num(m.group(2))
            if zhu >= 5 and cn is not None and cn > 0:
                return zhu * cn * 2

        # P9zd: 两码+各1组 (如 "福677-266各1组" → 2号×1×2=4)
        m = re.search(r'(\d{3})\s*[-—–]\s*(\d{3})\s*各\s*(\d+)\s*组', text)
        if m:
            per = int(m.group(3))
            return 2 * per * 2  # 2个号码×每组2元×N组

        # P9ze: 五码组六+大额 (如 "福10546组六600" → 600)
        m = re.search(r'[福体]?\s*(\d{5})\s*组[六3]\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(2))
            if 0.1 <= v <= 100000:
                return v

        # P9zf: 逗号开头+组六/五组 (如 "，456五组福" → 3号×5×2=30)
        m = re.search(r'[，,]\s*(\d{3})\s*([零一二两三四五六七八九十]+)\s*组', text)
        if m:
            cn = parse_cn_num(m.group(2))
            if cn is not None and cn > 0:
                return cn * 2

        # P9zg: 点分号码+组六各X+组三各Y (如 "02359. 12359.组六各50.组三各10")
        # 可能带前缀数字(如 "1 02359. 12359.组六各50.组三各10")
        m = re.search(r'(?:\d+\s+)?([\d.\s]+\d)\s*[.。]?\s*组六\s*各?\s*(\d+(?:\.\d+)?)\s*[.。]?\s*组三\s*各?\s*(\d+(?:\.\d+)?)', text)
        if m:
            nums_part = m.group(1)
            zu6_val = float(m.group(2))
            zu3_val = float(m.group(3))
            # 计算点分号码的数量（每个点分项是一个N码号码）
            num_list = re.findall(r'\d{3,}', nums_part)
            n = len(num_list)
            if n > 0 and 0.1 <= zu6_val <= 100000 and 0.1 <= zu3_val <= 100000:
                return n * (zu6_val + zu3_val)

        # P9zh: 空格/点分号码+各X+叹号/福计 (如 "福 024 049 348 148 469各12！福计" → 5×12=60)
        m = re.search(r'[福体]?\s*([\d\s.]+\d)\s*各\s*(\d+(?:\.\d+)?)\s*[!！]', text)
        if m:
            nums_part = m.group(1)
            val = float(m.group(2))
            num_list = re.findall(r'(?<!\d)\d{3}(?!\d)', nums_part)
            n = len(num_list)
            if n > 0 and 0.1 <= val <= 100000:
                return n * val

        # P9zi: 转一圈/转一转 (如 "126转一圈福" → 3码全排列=6注×2=12)
        m = re.search(r'(\d{3})\s*转(?:一圈|一转)', text)
        if m:
            return 6 * 2  # 3码全排列=6注×2

        # P9zj: 各打组选X倍 (如 "福彩078.178.278.各打组选50倍" → N号×50×2)
        # 支持句号分隔多组(如"...各打组选50倍。...各打组选25倍")
        total_zj = 0
        for m in re.finditer(r'([\d.\s,，]+)\s*各打\s*(?:组选|直选)?\s*(\d+(?:\.\d+)?)\s*倍', text):
            nums_part = m.group(1)
            bei = float(m.group(2))
            num_list = re.findall(r'(?<!\d)\d{3}(?!\d)', nums_part)
            n = len(num_list)
            if n > 0 and 0.1 <= bei <= 10000:
                total_zj += n * bei * 2
        if total_zj > 0:
            return total_zj

        # P9zk: 号码+福+X单+金额 (如 "864福50单100" → 100, 50单表示50注单式)
        m = re.search(r'\d{3}\s*[福体]\s*\d+\s*单\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zl: 福彩3D+号码+X倍直选 (如 "福彩3D 147 5倍直选" → 5×2=10)
        m = re.search(r'[福体]彩3?D?\s*\d{3}\s*(\d+)\s*倍\s*直选', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 10000:
                return v * 2

        # P9zm: +号分隔号码+一组福 (如 "121+124一组福" → 2号×2=4)
        m = re.search(r'(\d{3})\+(\d{3})\s*一组', text)
        if m:
            return 2 * 2  # 2个号码×2

        # P9zn: 3码+中文数字+组 (如 "058五组" → 5×2=10, "234福三十组" → 30×2=60)
        m = re.search(r'(?:\d{3}\s*[福体]?\s*)([零一二两三四五六七八九十百]+)\s*组\s*[福体]?$', text)
        if m:
            v = parse_cn_num(m.group(1))
            if v is not None and v > 0:
                return v * 2
        # 也匹配: 号码+福+中文数字+组 (如 "234福三十组" → 30×2=60)
        # 注意: 排除"一组+金额"格式(如"634 549 福一组4"应走P9zw)
        m = re.search(r'\d{3}\s*[福体]\s*([零一二两三四五六七八九十百]+)\s*组\s*(?:[福体]|\s*$)', text)
        if m:
            v = parse_cn_num(m.group(1))
            if v is not None and v > 0:
                return v * 2

        # P9zo: 福+号码+组选+中文倍数 (如 "福 426 组选五倍" → 5×2=10)
        m = re.search(r'[福体]\s*\d{3}\s*组选\s*([零一二两三四五六七八九十百]+)\s*倍', text)
        if m:
            v = parse_cn_num(m.group(1))
            if v is not None and v > 0:
                return v * 2

        # P9zp: 号码-金额+组六 (如 "13568-40组六" → 40)
        m = re.search(r'\d{4,}\s*[-—]\s*(\d+)\s*组[六3]', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zq: 福彩+组选+倍数+号码列表 (如 "福彩组选两倍146 245 267" → 3号×2×2=12)
        m = re.search(r'[福体]彩\s*组选\s*([零一二两三四五六七八九十\d]+)\s*倍\s*([\d\s]+)', text)
        if m:
            bei = _cn_num_or_digit(m.group(1))
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(2))
            if bei is not None and bei > 0 and len(nums) > 0:
                return len(nums) * bei * 2

        # P9zr: 号码列表+福+各+中文数字+组 (如 "456-234福各十五组" → 2号×15×2=60)
        m = re.search(r'([\d\-]+)\s*[福体]\s*各\s*([零一二两三四五六七八九十百]+)\s*组', text)
        if m:
            cn = parse_cn_num(m.group(2))
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(1))
            if cn is not None and cn > 0 and len(nums) > 0:
                return len(nums) * cn * 2

        # P9zs: 豹子+打+X注 (如 "福彩555打10注" → 10注=10倍=10×2=20)
        m = re.search(r'[福体]彩\s*(\d)\1\1\s*打\s*(\d+)\s*注', text)
        if m:
            v = float(m.group(2))
            if 0.1 <= v <= 10000:
                return v * 2

        # P9zt2: X包+金额+福 (如 "6包30福" → 包30=30米)
        m = re.search(r'\d+\s*包\s*(\d+)\s*[福体]', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zu: 福彩+直选+号码+X注 (如 "福彩直选460五注" → 五注=五倍=5×2=10)
        m = re.search(r'[福体]彩\s*直选\s*\d{3}\s*([零一二两三四五六七八九十]+)\s*注', text)
        if m:
            v = parse_cn_num(m.group(1))
            if v is not None and v > 0:
                return v * 2

        # P9zv: 直各X倍组各Y倍+金额 (如 "501+228 直各三倍组各一倍 16" → 16)
        m = re.search(r'直各\s*[零一二两三四五六七八九十\d]+\s*倍\s*组各\s*[零一二两三四五六七八九十\d]+\s*倍\s*(\d+)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zw: 号码列表+福/体+一组+金额 (如 "634 549 福一组4" → 4)
        m = re.search(r'[\d\s,，]+\d\s*[福体]\s*一组\s*(\d+)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zx: 福+号码列表+直X元组Y元 (如 "福 136-356-147-367-457-468 直一元组一元" → 6号×2=12)
        m = re.search(r'[福体]\s*([\d\-]+)\s*直\s*([零一二两三四五六七八九十\d]+)\s*元\s*组\s*([零一二两三四五六七八九十\d]+)\s*元', text)
        if m:
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(1))
            v1 = _cn_num_or_digit(m.group(2))
            v2 = _cn_num_or_digit(m.group(3))
            if len(nums) > 0 and v1 is not None and v2 is not None:
                return len(nums) * (v1 + v2)

        # P9zy: 号码+X组+X直 (如 "386，，，10组10直" → 10×2+10×2=40)
        m = re.search(r'\d{3}[\s,，.、]*?(\d+)\s*组\s*(\d+)\s*直', text)
        if m:
            zu = float(m.group(1))
            zhi = float(m.group(2))
            return zu * 2 + zhi * 2

        # P9zz: 独胆+金额 (如 "7独胆1000" → 1000, "8独胆500" → 500)
        m = re.search(r'\d\s*独胆\s*(\d+)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zza: 毒+数字+金额 (毒=独胆, 如 "体 毒 8 五十米" → 50)
        m = re.search(r'[福体]\s*毒\s*\d\s*([零一二两三四五六七八九十百]+)\s*米', text)
        if m:
            v = parse_cn_num(m.group(1))
            if v is not None and v > 0:
                return v

        # P9zzb: 百/十/个位+X点+金额 (如 "百位9点50" → 50, 点=下=下注)
        m = re.search(r'[百十个]\s*位\s*\d+\s*点\s*(\d+)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zzc: X码组六各下+金额 (如 "024679 012469六码组六各下50" → 2码×50=100)
        m = re.search(r'([\d\s]+)\s*[四五六七八]码\s*组六\s*各下\s*(\d+)', text)
        if m:
            nums = re.findall(r'\d{4,}', m.group(1))
            v = float(m.group(2))
            if len(nums) > 0 and 0.1 <= v <= 100000:
                return len(nums) * v

        # P9zzd: 号码列表+福组选各一组 (如 "759 523 520 243福组选各一组" → 4号×2=8)
        m = re.search(r'([\d\s,，]+)\s*[福体]\s*组选\s*各\s*一组', text)
        if m:
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(1))
            if len(nums) > 0:
                return len(nums) * 2

        # P9zze: 号码列表+福彩直组+每注一倍 (如 "023，326，994，368，449，福彩直组。每注一倍" → 5号×4=20)
        m = re.search(r'([\d，,、\s]+)\s*[福体]彩?\s*直组', text)
        if m:
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(1))
            if len(nums) > 0:
                return len(nums) * 4

        # P9zzf: 号码列表+排三/排列三/体三/体3+直选+X倍 (如 "排三直选2倍" → 7号×2×2=28)
        m = re.search(r'([\d\s]+)\s*(?:排三|排列三|体三|体3)\s*直选\s*(\d+)\s*倍', text)
        if m:
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', m.group(1))
            bei = float(m.group(2))
            if len(nums) > 0 and bei > 0:
                return len(nums) * bei * 2

        # P9zzg: 点分号码+组六各+中文数字+福 (如 "01457.145678组六各十福" → 2×10=20)
        m = re.search(r'([\d.]+)\s*组六\s*各\s*([零一二两三四五六七八九十百]+)\s*[福体]', text)
        if m:
            nums = re.findall(r'\d{3,}', m.group(1))
            cn = parse_cn_num(m.group(2))
            if len(nums) > 0 and cn is not None and cn > 0:
                return len(nums) * cn

        # P9zzh: 组六组三各X+号码列表 (如 "体彩组六组三各10 24679 35678" → 2码×(10+10)=40)
        m = re.search(r'组六组三各\s*(\d+(?:\.\d+)?)\s*([\d\s]+)', text)
        if m:
            val = float(m.group(1))
            nums = re.findall(r'(?<!\d)\d{4,}(?!\d)', m.group(2))
            if len(nums) > 0 and 0.1 <= val <= 100000:
                return len(nums) * val * 2

        # P9zzi: 福彩+3码+复试+X倍 (如 "福彩248复试两倍" → 20)
        m = re.search(r'[福体]彩\s*\d{3}\s*复试\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            bei = _cn_num_or_digit(m.group(1))
            if bei is not None and bei > 0:
                return bei * 10  # 复试=组选+直选混合, 两倍=20

        # P9zzj: 独胆+金额 (如 "8 独 100" → 100, 独=独胆)
        m = re.search(r'\d\s*独\s+(\d+)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # P9zzl: 两码列表+双飞一个+金额 (如 "24 26 27双飞一个10" → 3组×10=30)
        m = re.search(r'([\d\s]+)\s*双飞\s*一个\s*(\d+)', text)
        if m:
            nums = re.findall(r'(?<!\d)\d{2}(?!\d)', m.group(1))
            val = float(m.group(2))
            if len(nums) > 0 and 0.1 <= val <= 100000:
                return len(nums) * val

        # P9zzm: 福三D/3D+组六+号码=倍数 (如 "福 三D 组六3578=2倍" → 20)
        # =X倍: X倍=20米 (2倍=20, 1倍=10)
        m = re.search(r'[福体]\s*(?:三D|3D)\s*组六\s*(\d+)\s*=\s*(\d+)\s*倍', text)
        if m:
            bei = int(m.group(2))
            if bei > 0:
                return bei * 10  # =X倍 = X×10米

        # P9zzn: 直组+号码+各X元 (如 "福直组818各一元" → 直2+组2=4)
        # 直组各X元: X元=X倍=2X米, 直+组=4X米/号
        m = re.search(r'[福体]?\s*直[组租]\s*(\d{3})\s*各\s*([零一二两三四五六七八九十\d]+)\s*[元米块]', text)
        if m:
            per = _cn_num_or_digit(m.group(2))
            if per is not None and per > 0:
                return per * 4  # 直各per倍(2per)+组各per倍(2per)=4per米

        # P9zzo: 纯号码列表默认一倍直 (如 "013 015 018" → 3×2=6)
        # 仅含3位号码和空格/逗号，无其他文字
        stripped = text.strip()
        if re.match(r'^[\d\s,，]+$', stripped):
            nums = re.findall(r'\d{3}', stripped)
            if len(nums) >= 2:
                return len(nums) * 2  # 每号一倍直=2米

        # P10: 组六/组三金额 (上限2000, 排除"组六+号码+打+金额"格式)
        zu_total = 0
        for m in re.finditer(r'组三\s*(?:全包\s*)?(\d+)', text):
            # 排除"组三XXX打Y"格式（XXX是号码不是金额）
            after = text[m.end():m.end()+5]
            if re.match(r'\s*打', after):
                continue
            # 排除3位以上号码（组三后的3位数字是号码不是金额）
            ns = m.group(1)
            if len(ns) >= 3:
                continue
            v = float(ns)
            if 0.1 <= v <= 2000: zu_total += v
        for m in re.finditer(r'组六\s*(?:全包\s*)?(\d+)', text):
            # 排除"组六XXX打Y"格式
            after = text[m.end():m.end()+5]
            if re.match(r'\s*打', after):
                continue
            # 排除3位以上号码（组六后的3位以上数字是号码不是金额）
            ns = m.group(1)
            if len(ns) >= 3:
                continue
            v = float(ns)
            if 0.1 <= v <= 2000: zu_total += v
        if zu_total > 0: return zu_total

        # P11: 双飞
        sf = self._parse_shuangfei(text)
        if sf > 0: return sf

        # P12: 豹子
        bz = self._parse_baozi(text)
        if bz > 0: return bz

        # P13: 定位
        dw = self._parse_dingwei(text)
        if dw > 0: return dw

        # P13.5: 百X十Y个Z 复式 (排列3/3D/福彩3D)
        m = re.search(r'百\s*\d+\s*十\s*\d+\s*个\s*\d+\s*(?:排|[体福])?\s*(?:\d+\s*倍\s*)?(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v
        # 百X十Y个Z 无金额后缀(紧跟倍数后的数字就是金额)
        m = re.search(r'百\s*\d+\s*十\s*\d+\s*个\s*\d+\s*(?:排|[体福])?\s*\d+\s*倍\s*(\d+)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # P14: 外围
        m = re.search(r'外围[^\n]*?(\d+)\s*[米元块]', text)
        if m: return float(m.group(1))

        # P15: X单Y组 (含直)
        dz = self._parse_dan_zu(text)
        if dz > 0: return dz

        # P16: X注各Y单/毛/直
        m = re.search(r'共?\s*(\d+)\s*注\s*(?:直\s*)?各\s*(?:打\s*)?([零一二两三四五六七八九十\d]+)\s*[单毛直元]', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                suffix = text[m.start():m.end()]
                if '毛' in suffix:
                    return count * per * 0.1
                if '元' in suffix:
                    return count * per * 1  # X注各Y元 = X*Y
                return count * per * 2

        # P16b: X注直Y米 (如 "633注直选，直6米" = 633×6, "644注，直2米" = 644×2)
        m = re.search(r'(\d+)\s*注.*?直\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m:
            count = int(m.group(1))
            per = float(m.group(2))
            if count > 0 and per > 0:
                return count * per

        # P16c: X注直选一倍 / X注直一倍 = X*2
        m = re.search(r'(\d+)\s*注\s*直(?:选)?\s*一倍', text)
        if m:
            count = int(m.group(1))
            if count > 0:
                return count * 2

        # P16d: X注二倍 = X*4 (直选二倍)
        m = re.search(r'(\d+)\s*注\s*二倍', text)
        if m:
            count = int(m.group(1))
            if count > 0:
                return count * 4

        # P16d2: X注直选Y / X注直Y = X*Y (如 "100注直选2" → 100×2=200)
        m = re.search(r'(\d+)\s*注\s*直(?:选)?\s*(\d+)', text)
        if m:
            count = int(m.group(1))
            per = int(m.group(2))
            if count > 0 and per > 0:
                return count * per

        # P16e: X注直一元 / X注一元直 = X*1
        m = re.search(r'(\d+)\s*注\s*(?:直\s*)?一元', text)
        if m:
            count = int(m.group(1))
            if count > 0:
                return count * 1
        m = re.search(r'(\d+)\s*注\s*一元\s*直', text)
        if m:
            count = int(m.group(1))
            if count > 0:
                return count * 1

        # P16f: X注直Y毛 / X注直选Y毛 = X*Y*0.1
        m = re.search(r'(\d+)\s*注\s*直(?:选)?\s*([零一二两三四五六七八九十\d]+)\s*毛', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                return count * per * 0.1

        # P16g: X注Y毛 (无直/组前缀) = X*Y*0.1
        m = re.search(r'(\d+)\s*注\s*([零一二两三四五六七八九十\d]+)\s*毛', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                return count * per * 0.1

        # P16h: X注直选Y米 = X*Y
        m = re.search(r'(\d+)\s*注\s*直选\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m:
            count = int(m.group(1))
            per = float(m.group(2))
            if count > 0 and per > 0:
                return count * per

        # P16i: X注组选Y倍 = X*Y*2
        m = re.search(r'(\d+)\s*注\s*组选\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                return count * per * 2

        # P16j: X注直Y元 = X*Y
        m = re.search(r'(\d+)\s*注\s*直\s*(\d+(?:\.\d+)?)\s*元', text)
        if m:
            count = int(m.group(1))
            per = float(m.group(2))
            if count > 0 and per > 0:
                return count * per

        # (共X注各Y单)
        m = re.search(r'[（(]\s*共\s*(\d+)\s*注\s*各\s*([零一二两三四五六七八九十\d]+)\s*单\s*[）)]', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                return count * per * 2

        # (共X注)Y单
        m = re.search(r'[（(]\s*共\s*(\d+)\s*注\s*[）)]\s*([零一二两三四五六七八九十\d]+)\s*单', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                return count * per * 2

        # P17: 各X元/米
        m = re.search(r'各\s*(\d+(?:\.\d+)?)\s*[元米块]', text)
        if m: return float(m.group(1))

        # P18: 直接金额 X元/X米/X块
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*[元米块]', text):
            ns = m.group(1)
            v = float(ns)
            if not (0.1 <= v <= 100000): continue
            # 3位整数>=100在投注号码上下文→跳过
            if len(ns) == 3 and ns.isdigit() and v >= 100:
                before = text[:m.start()]
                if re.search(r'\d{3}\s*$', before): continue
                if re.search(r'[福体]\s*$', before): continue
            return v

        # P19: X毛
        m = re.search(r'(\d+(?:\.\d+)?)\s*毛', text)
        if m: return float(m.group(1)) * 0.1

        # ========== v5.7 新增规则 ==========
        # NV1: 句号分隔多单合并 (如 "004...两组。双飞，09五倍，组三一倍" → 求和)
        if '。' in text or '．' in text:
            # 检查是否是复杂多单合并场景
            parts = re.split(r'[。．]', text)
            if len(parts) >= 2:
                total_sum = 0
                for part in parts:
                    part = part.strip()
                    if not part: continue
                    # 递归解析每部分
                    sub_amount = self._extract_amount(part)
                    if sub_amount > 0:
                        total_sum += sub_amount
                if total_sum > 0:
                    return total_sum

        # NV2: 多号+各X倍计价 (如 "094，147，263各一倍" → 3×2=6)
        # 支持逗号/点号分隔的3位号码列表
        m = re.search(r'((?:\d{3}[，,、.\s]+?)+\d{3})\s*各\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            bei = _cn_num_or_digit(m.group(2))
            if count > 0 and bei is not None and bei > 0:
                return count * bei * 2  # 各X倍 = X*2元/号

        # NV3: 号码+X倍(无"各", 如 "222 5倍" → 2×5=10)
        m = re.search(r'(?<!\d)(\d)\1{2}\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            bei = _cn_num_or_digit(m.group(2))
            if bei is not None and bei > 0:
                return 2 * bei  # 豹子号码×X倍=2×X

        # NV4: 直选一倍冗余 (如 "527 526 542各一倍" → 号码数×2)
        # 检测"一倍"紧跟在号码列表后面，且前面无"各"
        m = re.search(r'((?:\d{3}[，,、.\s]+?)+\d{3})\s*一倍', text)
        if m:
            # 排除已有"各X倍"的情况
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            if count > 0:
                # 检查是否前面有"各"
                before = text[:m.start()]
                if '各' not in before and '各' not in m.group(0)[:-2]:
                    return count * 2

        # NV5: 飞各X米 / 飞个X米 (个=各) / 飞各X倍
        m = re.search(r'飞\s*各?\s*([零一二两三四五六七八九十\d]+)\s*[米元块倍]', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            suffix = text[m.start():m.end()]
            if per is not None and per > 0:
                before = text[:m.start()]
                pairs = re.findall(r'\d{2}', before)
                if '倍' in suffix:
                    # 飞各X倍: 飞一倍=10米, X倍=X*10米/对
                    if pairs:
                        return len(pairs) * per * 10
                    return per * 10  # 单个飞
                if pairs:
                    return len(pairs) * per
                return per  # 单个飞，默认1组

        # NV6: 双飞X倍 (如 "双飞09五倍" → 10×5=50)
        m = re.search(r'双飞[^\d]*(\d{2})[^\d]*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            bei = _cn_num_or_digit(m.group(2))
            if bei is not None and bei > 0:
                return 10 * bei  # 双飞一倍=10米

        # NV7: 双飞X/Y (无备注默认一倍，如 "双飞12/15" → 2×10=20)
        m = re.search(r'双飞\s*([\d/，,、\s]+)', text)
        if m:
            pairs_str = m.group(1)
            # 检查是否有金额或倍数
            after = text[m.end():m.end()+30]
            has_amount = bool(re.search(r'[\d]+(?:[倍米元块毛]|$)', after))
            if not has_amount:
                pairs = re.findall(r'\d{2}', pairs_str)
                return len(pairs) * 10  # 默认一倍=10米

        # NV8: 点分多号+各X组 (如 "049.149.247各三组" → 3×3×2=18)
        # 支持点号分隔的3位号码 (点号后可无空格)
        m = re.search(r'(\d{3}(?:[.．]\s*\d{3})+[.．]?)\s*各\s*([零一二两三四五六七八九十\d]+)\s*组', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            zu = _cn_num_or_digit(m.group(2))
            if count > 0 and zu is not None and zu > 0:
                return count * zu * 2  # 各X组 = X*2米/号

        # NV9: 逗号开头+五组/十组 (如 "，016 034...五组" → 号数×5×2)
        if text.strip().startswith(('，', ',')):
            # 提取号码列表
            nums = re.findall(r'\d{3}', text)
            count = len(nums)
            for zu_pat in [r'([零一二两三四五六七八九十\d]+)\s*组', r'(\d+)\s*组']:
                m = re.search(zu_pat, text)
                if m:
                    zu = _cn_num_or_digit(m.group(1)) if zu_pat.startswith(r'([零') else int(m.group(1))
                    if zu is not None and zu > 0:
                        return count * zu * 2

        # NV10: 五组/十组格式 (无"各"，如 "016 034五组" → 号数×5×2)
        m = re.search(r'((?:\d{3}[，,、.\s]+?)+\d{3})\s*([五六七八九十零一二三四]?)\s*组', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            zu_raw = m.group(2)
            if zu_raw:
                zu = parse_cn_num(zu_raw) if zu_raw else 5
            else:
                zu = 5  # 默认5组
            if count > 0 and zu is not None and zu > 0:
                return count * zu * 2

        # NV11: 直组一倍/直组X倍 (缺"各"字，如 "634 614 683直组一倍" → 3号×4=12)
        # 支持"直租"=直组, 支持"直组各"和"直租各"格式, 支持短横线分隔号码
        m = re.search(r'((?:\d{3}[，,、.\s\-]+?)+\d{3})\s*[，,、.\s\-]*\s*直[组租][各]?\s*([零一二两三四五六七八九十\d]*)\s*倍', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            bei_raw = m.group(2)
            bei = _cn_num_or_digit(bei_raw) if bei_raw else 1
            if count > 0 and bei is not None and bei > 0:
                return count * bei * 4  # 直+组各X倍 = X*4元/号

        # NV11b: 单个号码+直组各倍 (如 "052直租各五倍" → 1号×5×2=10)
        m = re.search(r'(\d{3})\s*直[组租][各]?\s*([零一二两三四五六七八九十\d]*)\s*倍', text)
        if m:
            bei_raw = m.group(2)
            bei = _cn_num_or_digit(bei_raw) if bei_raw else 1
            if bei is not None and bei > 0:
                return bei * 4  # 直+组各X倍 = X*4元/号

        # NV12: 直租=直组 (别字), 支持短横线分隔
        m = re.search(r'((?:\d{3}[，,、.\s\-]+?)+\d{3})\s*[，,、.\s\-]*\s*直租\s*([零一二两三四五六七八九十\d]*)\s*倍', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            bei_raw = m.group(2)
            bei = _cn_num_or_digit(bei_raw) if bei_raw else 1
            if count > 0 and bei is not None and bei > 0:
                return count * bei * 4

        # NV13: 直一米 (直选1米，如 "388 555 559直一米" → 3×1=3)
        m = re.search(r'((?:\d{3}[，,、.\s]+?)+\d{3})\s*直\s*([零一二两三四五六七八九十\d]+)\s*米', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            mi = _cn_num_or_digit(m.group(2))
            if count > 0 and mi is not None and mi > 0:
                return count * mi

        # NV14: 直组各X元 + 号码 (如 "直组818各一元" → 直2+组2=4)
        # 直组各X元: X元=X倍=2X米, 直+组=4X米/号
        # 注意: P9zzn优先处理"福直组+号码+各X元"格式，此处处理号码在前的情况
        m = re.search(r'直[组租][各]?\s*([零一二两三四五六七八九十\d]+)\s*[元米块]', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            if per is not None and per > 0:
                # 检查前面是否有号码
                before = text[:m.start()]
                nums = re.findall(r'\d{3}', before)
                count = max(len(nums), 1)
                return count * per * 4  # 直各per倍(2per)+组各per倍(2per)=4per米/号

        # NV14b: X毛/元直组 (金额在前, 如 "五毛直组" — 直0.5+组0.5=1米/号)
        m = re.search(r'([零一二两三四五六七八九十\d]+)\s*[毛元米块]\s*直组', text)
        if m:
            per_raw = m.group(1)
            per = _cn_num_or_digit(per_raw)
            suffix = text[m.start():m.end()]
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            if per is not None and per > 0:
                if '毛' in suffix:
                    return num_count * per * 0.1 * 2  # 直0.5+组0.5 各X毛
                else:
                    return num_count * per * 2  # 直X+组X 各X元/米

        # NV14c: 两位码+飞各X倍 (如 "57 59 56飞各5倍" — 3对×5×10=150)
        # 飞一倍=10米(5注组三×2), X倍=X*10米/对
        m = re.search(r'((?:\d{2}[\s,，、]+)*\d{2})\s*飞\s*各?\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            bei = _cn_num_or_digit(m.group(2))
            if pairs and bei is not None and bei > 0:
                return len(pairs) * bei * 10  # 飞一倍=10米

        # NV14d: 各打X倍直选 各Y组选 (如 "967 767 956各打五倍直选 各五组选" — 3号×(5×2+5×2)=60)
        m = re.search(r'各打\s*([零一二两三四五六七八九十\d]+)\s*倍?\s*直选\s*各\s*([零一二两三四五六七八九十\d]+)\s*倍?\s*组选', text)
        if m:
            zhi_bei = _cn_num_or_digit(m.group(1))
            zu_bei = _cn_num_or_digit(m.group(2))
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-80:])
            num_count = max(len(nums), 1)
            if zhi_bei is not None and zu_bei is not None and zhi_bei > 0 and zu_bei > 0:
                return num_count * (zhi_bei * 2 + zu_bei * 2)

        # NV14e: /分隔号码+组各一倍 (如 "478/428组各一倍" — 直组各一倍=4米/号, 2号×4=8)
        m = re.search(r'(\d{3}(?:[/／]\d{3})+)\s*组各\s*([零一二两三四五六七八九十\d]*)\s*倍', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            bei_raw = m.group(2)
            bei = _cn_num_or_digit(bei_raw) if bei_raw else 1
            if count > 0 and bei is not None and bei > 0:
                return count * bei * 4  # 组各一倍=直+组各1=4米/号

        # NV15: 星号定位 (25* 63* 格式，两码定位)
        m = re.search(r'((?:\d{2}[*xX×]\s*)+)\s*各\s*([零一二两三四五六七八九十\d]+)\s*[元米块]', text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            count = len(pairs)
            per = _cn_num_or_digit(m.group(2))
            if count > 0 and per is not None and per > 0:
                return count * per

        # NV16: 各X元+组三倍混合 (如 "014 123 124 135 234组三倍" → 30)
        # 先找组三倍
        m = re.search(r'组三\s*倍', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'\d{3}', before)
            count = max(len(nums), 1)
            # 检查前面是否有"各X元"
            m2 = re.search(r'各\s*(\d+)\s*[元米块]', before)
            if m2:
                return int(m2.group(1)) * count
            else:
                return count * 3 * 2  # 组三倍默认=3×2=6/号

        # NV17: 两码组三转各一倍 (如 "12/15/...转一直" → 16×2=32)
        m = re.search(r'([\d/，,、\s]+?)\s*转\s*各?\s*一\s*倍', text)
        if m:
            pairs_str = m.group(1)
            pairs = re.findall(r'\d{2}', pairs_str)
            count = len(pairs)
            if count > 0:
                return count * 16  # 一倍=16米

        # NV18: 组3两码+X倍 (如 "96组3两码，10倍" → 10×10=100)
        m = re.search(r'(\d{2})\s*组[三3]\s*两码[^\d]*(\d+)\s*倍', text)
        if m:
            bei = int(m.group(2))
            return bei * 10  # 组三两码一倍=10米

        # NV19: 胆X+金额 (如 "胆3三百" → 300)
        m = re.search(r'胆\s*(\d)\s*([零一二两三四五六七八九十百]+)', text)
        if m:
            amount = _cn_num_or_digit(m.group(2))
            if amount is not None and amount > 0:
                return amount

        # NV20: 十位/百位+金额 (如 "十位8五十米" → 50)
        m = re.search(r'[十百个]位\s*(\d)\s*([零一二两三四五六七八九十百\d]+)\s*[元米块]?', text)
        if m:
            amount = _cn_num_or_digit(m.group(2))
            if amount is not None and amount > 0:
                return amount

        # NV21+NV22: 多定位求和 (如 "百位3-5各10 百位9上30" → 20+30=50)
        dw_total = 0
        has_dw = False
        for m in re.finditer(r'百位\s*\d\s*[-–—]\s*\d\s*各\s*(\d+)', text):
            dw_total += 2 * int(m.group(1))
            has_dw = True
        for m in re.finditer(r'百位\s*\d\s*(?:上|打)\s*(\d+)', text):
            dw_total += float(m.group(1))
            has_dw = True
        for m in re.finditer(r'[十百个]位\s*\d\s*([零一二两三四五六七八九十百\d]+)\s*[元米块]', text):
            v = _cn_num_or_digit(m.group(1))
            if v is not None and v > 0:
                dw_total += v
                has_dw = True
        if has_dw and dw_total > 0:
            return dw_total

        # NV23: X注+号码列表+直Y毛 (如 "279注，直五毛" → 279×0.5=139.5)
        m = re.search(r'(\d+)\s*注[^\d]*直\s*([零一二两三四五六七八九十\d]+)\s*毛', text)
        if m:
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if count > 0 and per is not None:
                return count * per * 0.1

        # NV24: X注+号码列表 (如 "9注 138 358 356" → 9×2=18)
        m = re.search(r'(\d+)\s*注\s+((?:\d{3}[，,、\s]+?)+)', text)
        if m:
            count = int(m.group(1))
            nums = re.findall(r'\d{3}', m.group(2))
            num_count = max(len(nums), 1)
            return num_count * 2  # 默认一倍=2元

        # NV25: 复杂注数踢出 (如 "体36注）1组 017...347...789" → 返回-1)
        # 检测疑似复杂注数格式
        m = re.search(r'[(（]\s*\d+\s*注[^\d]{0,5}\d+\s*组', text)
        if m:
            # 检查是否有多组号码
            before = text[:m.start()]
            nums = re.findall(r'\d{3}', text[m.end():])
            if len(nums) > 3:  # 超过3个号码，疑似复杂人工单
                return -1  # 标记人工处理

        # NV26: 纽六格式 (5-6位码+纽六+末尾金额，如 "组六34579...80" → 80, "组六125679...30" → 30)
        # 注意：需要放在组六各X组三各Y之后，避免被覆盖
        m = re.search(r'(?:纽六|组六)\s*(\d{5,6})\s*[.．…]+\s*(\d+)', text)
        if m:
            return float(m.group(2))

        # NV27: 组六各X组三各Y / 组六各X组三Y元 (如 "组六各20组三十元" → 20+10=30)
        # 支持中文数字: 组六各二十组三十元
        # 两种子模式: (a) 组三各Y (b) 组三Y元
        # (a) 组三各Y
        m = re.search(r'组六各\s*([零一二两三四五六七八九十\d]+)\s*(?:[米元块])?\s*组三各\s*([零一二两三四五六七八九十\d]+)', text)
        if m:
            v1 = _cn_num_or_digit(m.group(1))
            v2 = _cn_num_or_digit(m.group(2))
            if v1 is not None and v2 is not None:
                # 计算号码数
                before = text[:m.start()]
                nums_4d = re.findall(r'(?<!\d)\d{4,}(?!\d)', before)
                num_count = max(len(nums_4d), 1)
                return float(v1) * num_count + float(v2) * num_count
        # (b) 组三Y元 (无各, 如 "组六各二十组三十元" → 4码×20 + 4码×10)
        m = re.search(r'组六各\s*([零一二两三四五六七八九十\d]+)\s*(?:[米元块])?\s*组三\s*([零一二两三四五六七八九十\d]+)\s*[元米块]?', text)
        if m:
            v1 = _cn_num_or_digit(m.group(1))
            v2 = _cn_num_or_digit(m.group(2))
            if v1 is not None and v2 is not None:
                before = text[:m.start()]
                nums_4d = re.findall(r'(?<!\d)\d{4,}(?!\d)', before)
                num_count = max(len(nums_4d), 1)
                return float(v1) * num_count + float(v2) * num_count

        # NV28: 各一元直两元组 (如 "各一元直两元组" → 1+2×2=6)
        m = re.search(r'各\s*([零一二两三四五六七八九十\d]+)\s*[元米块]\s*直\s*([零一二两三四五六七八九十\d]+)\s*[元米块]\s*组', text)
        if m:
            per1 = _cn_num_or_digit(m.group(1))
            per2 = _cn_num_or_digit(m.group(2))
            if per1 is not None and per2 is not None:
                before = text[:m.start()]
                nums = re.findall(r'\d{3}', before)
                count = max(len(nums), 1)
                return count * (per1 + per2 * 2)

        # NV29: 末尾人工修改金额 (如 "...直组一倍68" → 68)
        # 检测号码列表后紧跟"直组"+"倍数"+数字的模式
        m = re.search(r'(?:[\d]{3}[，,、.\s\-]*)*\d{3}\s*[，,、.\s\-]*\s*直[组租]?\s*\d*\s*倍\s*(\d+)', text)
        if m:
            amount = int(m.group(1))
            # 检查是否是疑似人工修改金额(数字较小，如68, 50等)
            if 10 <= amount <= 500:
                return float(amount)

        # NV29.5: 组3，组6 1倍 / 组3组6混合倍 (如 "2536 组3，组6 1倍" → 组三12+组六8=20)
        # N码+组三+组六+各X倍（或共用倍数）: 组三C(n,2)注 + 组六C(n,3)注
        m = re.search(r'组\s*3\s*[，,]?\s*组\s*6\s*([零一二两三四五六七八九十\d]*)\s*倍', text)
        if m:
            bei_raw = m.group(1) if m.group(1) else '1'
            bei = _cn_num_or_digit(bei_raw)
            if bei is None:
                bei = 1
            before = text[:m.start()]
            # 找号码(3-6位), 提取位数
            digit_nums = re.findall(r'(?<!\d)(\d{3,6})(?!\d)', before)
            if digit_nums:
                from math import comb
                total = 0
                for dn in digit_nums:
                    n = len(set(dn))  # 去重数字个数
                    if n >= 3:
                        total += comb(n, 2) * bei * 2  # 组三: C(n,2)注 × 倍 × 2米
                        total += comb(n, 3) * bei * 2  # 组六: C(n,3)注 × 倍 × 2米
                if total > 0:
                    return total
            # fallback: 旧逻辑
            nums = re.findall(r'(?<!\d)\d{3,4}(?!\d)', before)
            count = max(len(nums), 1)
            return count * bei * 2 * 2  # 组三+组六各一倍 = 4倍基准

        # NV29.6: 各一，组 / 各一，租 (如 "体005.050.500.各一，组" → 3号×2=6)
        # 逗号隔开"各一"和"组"=各一组
        m = re.search(r'各\s*一\s*[，,]\s*[组租]', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
            count = max(len(nums), 1)
            return count * 2  # 各一组=各一倍=2米/号

        # NV30: 号码列表截断检测 (检测到"..."后面没有金额)
        m = re.search(r'\d{3}\s*[.．…]{2,}\s*$', text)
        if m:
            # 号码列表截断到末尾，疑似人工操作
            return -1  # 标记人工处理

        # NV31: 各28祖2直 (祖=组，如 "379.479各28祖2直" → 组2+直2=28+? 需计算)
        m = re.search(r'各\s*(\d+)\s*祖\s*(\d+)\s*直', text)
        if m:
            zu = int(m.group(1))
            zhi = int(m.group(2))
            before = text[:m.start()]
            nums = re.findall(r'\d{3}', before)
            count = max(len(nums), 1)
            return count * (zu + zhi)  # 组+直

        # NV32b: 豹子+0夸组合 (如 "福222十元零夸二十" → 豹子10+0夸20=30)
        # 检测豹子号码+金额 和 0夸+金额 (必须放在NV32之前)
        m = re.search(r'(\d{3})\s*([零一二两三四五六七八九十]+)\s*元?\s*零\s*夸\s*([零一二两三四五六七八九十]+)\s*元?', text)
        if m:
            amount1 = parse_cn_num(m.group(2)) or 0
            amount2 = parse_cn_num(m.group(3)) or 0
            if amount1 > 0 and amount2 > 0:
                return amount1 + amount2
        
        # NV32: 0夸识别 (夸=最大号-最小号, 0夸=豹子)
        m = re.search(r'零\s*夸', text)
        if m:
            # 0夸 = 豹子 = 2×2=4元/组
            before = text[:m.start()]
            nums = re.findall(r'\d{3}', before)
            count = max(len(nums), 1)
            # 检查是否有金额
            after = text[m.end():m.end()+20]
            m2 = re.search(r'(\d+)\s*[元米块]?', after)
            if m2:
                return float(m2.group(1))
            return count * 4  # 默认豹子一倍

        # NV33: 号码+直Y米组 (如 "502.507直三米组" → 2×(3+3)=12)
        m = re.search(r'(\d{3}[.．]\s*\d{3})\s*直\s*([零一二两三四五六七八九十\d]+)\s*米\s*组', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = max(len(nums), 1)
            mi = _cn_num_or_digit(m.group(2))
            if mi is not None:
                return count * mi * 2  # 直+组各X

        # NV34: X元直Y元组 (如 "各一元直两元组" → 1+2×2=6)
        m = re.search(r'各\s*(\d+)\s*[元米块]\s*直\s*(\d+)\s*[元米块]\s*组', text)
        if m:
            per1 = int(m.group(1))
            per2 = int(m.group(2))
            before = text[:m.start()]
            nums = re.findall(r'\d{3}', before)
            count = max(len(nums), 1)
            return count * (per1 + per2 * 2)

        # NV35: 号码+直X组Y (如 "764直40组10" → 直40+组10=50; "747直10组5" → 直10+组5=15)
        # 支持号码+直X组Y + 总金额(如 "764直40组10 100" → 100)
        m = re.search(r'(\d{3})\s*直\s*(\d+(?:\.\d+)?)\s*组\s*(\d+(?:\.\d+)?)', text)
        if m:
            zhi = float(m.group(2))
            zu = float(m.group(3))
            # 检查后面是否有总额覆盖
            after = text[m.end():m.end()+20]
            m2 = re.search(r'\s+(\d+(?:\.\d+)?)\s*[元米块]?', after)
            if m2:
                v = float(m2.group(1))
                if v > zhi + zu and v <= 100000:
                    return v
            return zhi + zu

        # NV36: 豹子包X块钱 (如 "豹子包四十块钱" → 40)
        m = re.search(r'豹子\s*包?\s*([零一二两三四五六七八九十百\d]+)\s*(?:块钱|元|米|块)', text)
        if m:
            v = _cn_num_or_digit(m.group(1))
            if v is not None and v > 0:
                return v

        # NV37: X码组6+金额 (如 "1479 福4码组6---40" → 40; "福4码组六---40" → 40)
        m = re.search(r'[四五六七八]?\s*码\s*组\s*[六6]\s*[-—–－]+\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # NV38: 号码+直X组Y+彩种+总金额 (如 "619 796直20组5福100" → 100)
        m = re.search(r'直\s*(\d+(?:\.\d+)?)\s*组\s*(\d+(?:\.\d+)?)\s*[福体]\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(3))
            if 0.1 <= v <= 100000:
                return v

        # NV39: 号码+组六+直复试+X倍 (如 "1587组六直复试3倍" → 复试3倍需查表)
        # 简化: "直复试X倍" → 总额=复试金额×X
        m = re.search(r'组六\s*直?复[试式]\s*([零一二两三四五六七八九十\d]+)\s*倍', text)
        if m:
            bei = _cn_num_or_digit(m.group(1))
            if bei is not None and bei > 0:
                before = text[:m.start()]
                # 查前面的号码码数
                combos = re.findall(r'(?<!\d)\d{4,7}(?!\d)', before)
                if combos:
                    # 简化处理: 返回倍数×2(最小估计)
                    return bei * 2
                return bei * 2

        # NV40: 各2O单5组 (O=零, 如 "534.535各2O单5组" → 2号×20×2+5×2=90? 或 100?)
        # "2O" = "20"的OCR错误, O出现在数字和中文之间
        text_ocr = re.sub(r'(\d)O(?=[单组倍毛元米块])', r'\g<1>0', text)
        text_ocr = re.sub(r'(\d)O(\d)', r'\g<1>0\2', text_ocr)
        text_ocr = re.sub(r'O(\d)', r'0\1', text_ocr)
        if text_ocr != text:
            # 先检查逗号后的总额
            m_total = re.search(r'[，,]\s*(\d+(?:\.\d+)?)\s*[元米块]?$', text_ocr)
            if m_total:
                v = float(m_total.group(1))
                if 0.1 <= v <= 100000:
                    return v
            m = re.search(r'各\s*(\d+)\s*单\s*(\d+)\s*组', text_ocr)
            if m:
                dan = int(m.group(1))
                zu = int(m.group(2))
                before = text_ocr[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                count = max(len(nums), 1)
                return count * (dan * 2 + zu * 2)

        # NV41: X/Y倍组 (如 "114/2倍组 144/3倍组" → 2+3=5, 各×2=10)
        m = re.search(r'(\d{3})\s*/\s*(\d+)\s*倍\s*组', text)
        if m:
            bei = int(m.group(2))
            return bei * 2

        # NV42: N码+组六各打X (如 "0129.01269.012569组六各打50" → 3组×50=150)
        m = re.search(r'([\d.\s]+)\s*组六\s*各打\s*(\d+(?:\.\d+)?)', text)
        if m:
            combos = re.findall(r'(?<!\d)\d{4,9}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            per = float(m.group(2))
            return combo_count * per

        # NV43: 单选X组选Y倍 (如 "福彩809单选10组选10倍" → 10+10×2=30? 或 直10+组10×2=30)
        m = re.search(r'单选\s*(\d+(?:\.\d+)?)\s*组选\s*(\d+(?:\.\d+)?)\s*倍', text)
        if m:
            zhi = float(m.group(1))
            zu_bei = float(m.group(2))
            return zhi + zu_bei * 2

        # NV44: 一元直组 / X元直组 (如 "807 809一元直组4" → 直1+组1=2米/号, 2号×2=4)
        # X元直组 = 直X+组X = 2X米/号; 如果后面有总额则用总额
        m = re.search(r'([零一二两三四五六七八九十\d]+)\s*元\s*直组\s*(\d+(?:\.\d+)?)?', text)
        if m:
            per = _cn_num_or_digit(m.group(1))
            total_override = m.group(2)
            if total_override and float(total_override) > 0:
                return float(total_override)
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            if per is not None and per > 0:
                return num_count * per * 2  # 直X+组X 各X元/米

        # NV45: (组选)一组 (如 "270(组选)一组 281(组选)一组" → 多个×2)
        m = re.search(r'\d{3}\s*[（(]\s*组选\s*[）)]\s*一组', text)
        if m:
            all_groups = re.findall(r'\d{3}\s*[（(]\s*组选\s*[）)]\s*一组', text)
            return len(all_groups) * 2

        # NV46: 双飞+号码+各+金额 (如 "双飞78、各100" → 100)
        m = re.search(r'双飞\s*[\d、，,.\s]+\s*各\s*(\d+(?:\.\d+)?)\s*[元米块]?', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # NV46b: XX双飞+中文金额 (如 "67双飞一百" → 100)
        m = re.search(r'\d{2}\s*双飞\s*([零一二两三四五六七八九十百\d]+)\s*[元米块]?', text)
        if m:
            v = _cn_num_or_digit(m.group(1))
            if v is not None and 0.1 <= v <= 100000:
                return v

        # NV47: 三码组3 (如 "059 三码组3" → 组三3码)
        m = re.search(r'三码\s*组\s*[三3]', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
            count = max(len(nums), 1)
            after = text[m.end():m.end()+20]
            m2 = re.search(r'(\d+)\s*[元米块]?', after)
            if m2:
                return float(m2.group(1))
            return count * 2

        # NV48: 各1组 (如 "556.173.317.375 福各1组8" → 4号×2=8)
        m = re.search(r'各\s*1?\s*组\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # NV49: 共X注Y单 (如 "福共102注二单" → 102×2×2=408)
        m = re.search(r'共\s*(\d+)\s*注\s*([零一二两三四五六七八九十\d]+)\s*单', text)
        if m:
            count = int(m.group(1))
            bei = _cn_num_or_digit(m.group(2))
            if count > 0 and bei is not None and bei > 0:
                return count * bei * 2

        # NV50: .分隔+码数标记+组六+金额 (如 "福.五码.24569.组六200" → 200)
        m = re.search(r'[福体]?\s*[\.,，]\s*[四五六七八]码\s*[\.,，]?\s*\d+\s*[\.,，]?\s*组[六3]\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # NV51: 组三组六+N码+各X (如 "组三组六56789各10" → 组三10+组六10=20)
        m = re.search(r'组三组六\s*\d+\s*各\s*(\d+(?:\.\d+)?)', text)
        if m:
            per = float(m.group(1))
            return per * 2

        # NV52: 号码+复式+X倍 (如 "906 956体复式二十倍" → 2号×20×2=80)
        m = re.search(r'((?:\d{3}[\s,，、]+)*\d{3})\s*[福体]?\s*复[试式]\s*([零一二两三四五六七八九十百\d]+)\s*倍', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            count = max(len(nums), 1)
            bei = _cn_num_or_digit(m.group(2))
            if bei is not None and bei > 0:
                return count * bei * 2

        # NV53: 多号码+各X组+金额 (如 "体238..138..127..各二组64" → 64)
        m = re.search(r'各\s*[二两三四五六七八九十\d]+\s*组\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # NV54: 号码+直X组Y (无号分隔, 如 "213 764直20组5" → 直20+组5=25)
        # 如果NV35没匹配到(号码和直组之间有空格)
        m = re.search(r'((?:\d{3}[\s]+)+\d{3}?)\s*直\s*(\d+(?:\.\d+)?)\s*组\s*(\d+(?:\.\d+)?)', text)
        if m:
            zhi = float(m.group(2))
            zu = float(m.group(3))
            return zhi + zu

        # NV55: 组6️⃣X (emoji分隔, 如 "体23678组6️⃣300" → 300)
        # 先清除emoji变体选择器和keycap组合符, 再匹配
        _text_clean = re.sub(r'[\ufe0e\ufe0f\u20e3]', '', text)  # 移除VS15/VS16/keycap
        m = re.search(r'组\s*[六63]\s*(\d+(?:\.\d+)?)', _text_clean)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # NV56: .七码.+组六+金额 (如 "体.七码.3456789.组六 1000" → 1000)
        m = re.search(r'[福体]?\s*[\.,，]?\s*[四五六七八]码\s*[\.,，]?\s*\d+\s*[\.,，]?\s*组[六3]\s*(\d+(?:\.\d+)?)', text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                return v

        # NV57: 组六+N码+各打X (如 "体 组六0239 0679各打50" → 2×50=100)
        m = re.search(r'组[六3]\s*([\d\s]+?)\s*各打\s*(\d+(?:\.\d+)?)', text)
        if m:
            combos = re.findall(r'(?<!\d)\d{4,9}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            per = float(m.group(2))
            return combo_count * per

        # NV58: X当一 (两当一=两单一组=6米, 五当一=五单一组=12米, 一当一=一单一组=4米)
        # 含义: X注直选+1注组选 = (X+1)×2米
        cn_map58 = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100}
        # 带彩种前缀: 福214两当一, 福609一当一, 福045五当一
        m = re.search(r'(?:福|体)?\s*\d{3}\s*([五两三四六七八九十百一\d]+)\s*当\s*一', text)
        if m:
            val_str = m.group(1)
            val = cn_map58.get(val_str, 0)
            if val == 0 and val_str.isdigit(): val = int(val_str)
            if val > 0: return float((val + 1) * 2)
        # 纯X当一: 244两当一
        m = re.search(r'\d{3}\s*([五两三四六七八九十百一\d]+)\s*当\s*一', text)
        if m:
            val_str = m.group(1)
            val = cn_map58.get(val_str, 0)
            if val == 0 and val_str.isdigit(): val = int(val_str)
            if val > 0: return float((val + 1) * 2)
        # 每组X当一
        m = re.search(r'每组\s*([五两三四六七八九十百一\d]+)\s*当\s*一', text)
        if m:
            val_str = m.group(1)
            val = cn_map58.get(val_str, 0)
            if val == 0 and val_str.isdigit(): val = int(val_str)
            if val > 0: return float((val + 1) * 2)

        # NV59: 一码定位+佰(百位)/十位/个位 (如 "一码定位百位十位个位7各100" → 3位×100=300)
        m = re.search(r'一码定位[佰百]位[十]?位?[个]?位?\s*(\d+)\s*各\s*(\d+)', text)
        if m:
            digit = m.group(1)
            per = float(m.group(2))
            # Count how many positions mentioned
            pos_count = 0
            if re.search(r'[佰百]位', text): pos_count += 1
            if re.search(r'十位', text): pos_count += 1
            if re.search(r'个位', text): pos_count += 1
            return max(pos_count, 1) * per
        # 一码定位百位十位个位X各Y (expanded form)
        m = re.search(r'一码定位\s*(?:[佰百]位)?\s*(?:十位)?\s*(?:个位)?\s*(\d+)\s*各\s*(\d+)', text)
        if m and '一码定位' in text:
            per = float(m.group(2))
            pos_count = 0
            if re.search(r'[佰百]位', text): pos_count += 1
            if re.search(r'十位', text): pos_count += 1
            if re.search(r'个位', text): pos_count += 1
            return max(pos_count, 1) * per
        # 一码定位：百位X，十位Y，个位Z，各一百米/各W米 (with Chinese amounts)
        cn_amt59 = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100}
        m = re.search(r'一码定位[：:]', text)
        if m:
            # Count positions and extract amount
            pos_count = 0
            if re.search(r'[佰百]位', text): pos_count += 1
            if re.search(r'十位', text): pos_count += 1
            if re.search(r'个位', text): pos_count += 1
            if pos_count == 0: pos_count = 1
            # Try "各N百米" or "各一百米" or "各N米"
            m_amt = re.search(r'各\s*(\d+)\s*[百]?\s*[元米]', text)
            if m_amt:
                per = float(m_amt.group(1))
                return pos_count * per
            # Chinese: 各一百米
            m_amt = re.search(r'各\s*([一二两三四五六七八九十百]+)\s*[百]?\s*[元米]', text)
            if m_amt:
                per_str = m_amt.group(1)
                per = cn_amt59.get(per_str, 0)
                if per == 0:
                    per = 100 if '百' in per_str else 0
                if per > 0:
                    return pos_count * per

        # NV60: *分隔号码+各一组+金额 (如 "407*704*各一组4" → 4)
        m = re.search(r'([\d*]+\*[\d*]+)\s*各一组\s*(\d+)', text)
        if m:
            return float(m.group(2))

        # NV61: 福直+号码+倍数 (如 "福直178.187.718.768.789。五倍" → 5号×5倍×2=50)
        m = re.search(r'直\s*([\d.]+\d)\s*[。.]*\s*([五两三四六七八九十百\d]+)\s*倍', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            beishu_str = m.group(2)
            cn_map = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
            beishu = cn_map.get(beishu_str, 0)
            if beishu == 0:
                beishu = int(beishu_str) if beishu_str.isdigit() else 0
            if beishu > 0:
                return num_count * beishu * 2

        # NV62: 独胆+金额 (如 "独胆9 福50" → 50)
        m = re.search(r'独[胆旦]\s*\d+\s+[福体]\s*(\d+)', text)
        if m:
            return float(m.group(1))
        # 独旦X买Y (如 "独旦5买20" → 20)
        m = re.search(r'独旦\s*\d+\s*买\s*(\d+)', text)
        if m:
            return float(m.group(1))

        # NV63: 个位X一百Y/一百五 (如 "个位7一百五" → 150)
        m = re.search(r'个位\s*\d+\s*一百\s*([五两三四六七八九十百\d]*)\s*[元米]?', text)
        if m:
            base = 100
            extra_str = m.group(1)
            cn_map = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
            extra = cn_map.get(extra_str, 0)
            return base + extra * 10 if extra > 0 else base

        # NV64: 两位码+各+数+一码定位 (如 "01各30一码定位" → 2码×30=60)
        m = re.search(r'(\d{2})\s*各\s*(\d+)\s*一码定位', text)
        if m:
            return float(m.group(2)) * 2

        # NV65: 和值X Y (如 "和值13 100" → 100)
        m = re.search(r'和值\s*\d+\s+(\d+)', text)
        if m:
            return float(m.group(1))

        # NV66: 多组码+组六+各+金额 (如 "12467 124678.组六各50" → 2×50=100, "1358 1479福组六各100" → 200)
        m = re.search(r'([\d\s.]+)\s*[福体]?\s*组六\s*各\s*(\d+)', text)
        if m and re.search(r'\d{4,9}', m.group(1)):
            combos = re.findall(r'(?<!\d)\d{4,9}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            per = float(m.group(2))
            return combo_count * per

        # NV67: 豹子打团 (豹子全包, 1×2=2米默认; 有金额用金额)
        m = re.search(r'豹子打团[，,]?\s*(\d+)', text)
        if m:
            return float(m.group(1))
        # 豹子打团无金额 → 默认2米
        if re.search(r'豹子打团', text):
            return 2.0

        # NV68: 号码+组三+金额 (3位码如 "836组三100" → 100, 4位码如 "0356组三200" → 200)
        m = re.search(r'(\d{3,4})\s*组三\s*(\d+)', text)
        if m:
            return float(m.group(2))
        # 两位码组三 (如 "05.08.04组三各100" → 3×100=300)
        m = re.search(r'([\d.]+(?:\.\d{2})+)\s*组三\s*各\s*(\d+)', text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            pair_count = max(len(pairs), 1)
            per = float(m.group(2))
            return pair_count * per

        # NV69: 定位十位X+金额 (如 "定位十位5，一百米" → 100)
        cn_amt69 = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100}
        m = re.search(r'定位\s*十位\s*\d+\s*[，,]?\s*(\d+)\s*[元米]', text)
        if m:
            return float(m.group(1))
        m = re.search(r'定位\s*十位\s*\d+\s*[，,]?\s*([一二两三四五六七八九十百]+)\s*[元米]', text)
        if m:
            amt_str = m.group(1)
            amt = cn_amt69.get(amt_str, 0)
            if amt == 0 and '百' in amt_str: amt = 100
            if amt > 0: return float(amt)
        # 定位十位X买Y (如 "体彩定十位0买20" → 20)
        m = re.search(r'定十位\s*\d+\s*买\s*(\d+)', text)
        if m:
            return float(m.group(1))

        # NV70: 各三组/各N组 (如 "562 560各三组" → 2号×3×2=12)
        cn_map70 = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
        m = re.search(r'([\d\s]+?)\s*各\s*(\d+)\s*组\b', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            groups = int(m.group(2))
            return num_count * groups * 2
        # 中文: 各三组/各五组
        m = re.search(r'([\d\s]+?)\s*各\s*([五两三四六七八九十百\d]+)\s*组\b', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            grp_str = m.group(2)
            groups = cn_map70.get(grp_str, 0)
            if groups == 0 and grp_str.isdigit(): groups = int(grp_str)
            if groups > 0:
                return num_count * groups * 2

        # NV71: 对子全包 (有金额用金额; 无金额默认100米: 10个对子×10米/倍=100米)
        m = re.search(r'对子(?:组三)?全包\s*(\d+)', text)
        if m:
            return float(m.group(1))
        # 对子全包无金额 → 默认100米 (00-99共10个对子, 一倍=10米, 全包=100米)
        if re.search(r'对子(?:组三)?全包', text):
            return 100.0

        # NV72: 号码-1组 (如 "福009-1组" → 2)
        m = re.search(r'(\d{3})\s*[-—–]\s*(\d+)\s*组', text)
        if m:
            groups = int(m.group(2))
            return groups * 2

        # NV73: 独胆+号码+各X倍 (如 "福独2，1各4倍" → 独胆2和1各4倍=2×4×2=16)
        m = re.search(r'独\s*([\d,，]+)\s*各\s*(\d+)\s*倍', text)
        if m:
            digits = re.findall(r'\d', m.group(1))
            digit_count = max(len(digits), 1)
            beishu = int(m.group(2))
            return digit_count * beishu * 2

        # NV74: 多号码+各打Y组 (如 "134...789各打5组" → 号码数×5×2)
        m = re.search(r'([\d\s]+\d)\s*各打\s*(\d+)\s*组\b', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            groups = int(m.group(2))
            return num_count * groups * 2
        # "共N注各打X组" (如 "共42注各打5组" → 42×5×2=420)
        m = re.search(r'共\s*(\d+)\s*注\s*各打\s*(\d+)\s*组', text)
        if m:
            zhushu = int(m.group(1))
            groups = int(m.group(2))
            return zhushu * groups * 2

        # NV75: 体+号码+组各一元/组各X元 (如 "586 体组各一元" → 号码数×1×2)
        m = re.search(r'([\d\s]+\d)\s*体?\s*组各\s*一元', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            return num_count * 2
        m = re.search(r'([\d\s]+\d)\s*体?\s*组各\s*(\d+)\s*元', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            per = float(m.group(2))
            return num_count * per * 2

        # NV76: 组三各十/各X (如 "体1347 1358组三各十" → 2×10×2=40)
        m = re.search(r'([\d\s]+\d)\s*组三\s*各\s*([五两三四六七八九十百\d]+)', text)
        if m:
            combos = re.findall(r'(?<!\d)\d{4,9}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            beishu_str = m.group(2)
            cn_map = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
            beishu = cn_map.get(beishu_str, 0)
            if beishu == 0 and beishu_str.isdigit():
                beishu = int(beishu_str)
            if beishu > 0:
                return combo_count * beishu * 2

        # NV77: 号码+组六+体/福+金额 (如 "123478组六体50" → 50)
        m = re.search(r'(\d{5,9})\s*组六\s*[体福]?\s*(\d+)', text)
        if m:
            return float(m.group(2))

        # NV78: ★X★一直一组+金额 (★35★ already stripped by earlier rules, but handle case)
        m = re.search(r'一直一组\s*(\d+)', text)
        if m:
            return float(m.group(1))

        # NV79: 013458组三200 (号码+组三+金额 without 各)
        m = re.search(r'(\d{5,9})\s*组三\s*(\d+)', text)
        if m:
            return float(m.group(2))

        # NV80: ★号码★ pattern (★35★ → remove stars for number extraction)
        _clean = re.sub(r'[★☆※]', '', text)
        if _clean != text:
            result = self._extract_amount(_clean)
            if result > 0:
                return result

        # NV81: 组选组三各1元 (如 "福255 266 288 299 334 335 组选组三各1元")
        m = re.search(r'([\d\s]+\d)\s*组选组三\s*各\s*(\d+)\s*[元米]?', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            per = float(m.group(2))
            return num_count * per

        # NV82: 24579**2479组六10组三10 (**separated codes)
        m = re.search(r'(\d{4,5})\s*\*\*\s*(\d{4})\s*组六\s*(\d+)\s*组三\s*(\d+)', text)
        if m:
            return float(m.group(3)) + float(m.group(4))

        # NV83: 296 福直共X (如 "296 福直共4" → 4)
        m = re.search(r'\d{3}\s*福?\s*直\s*共\s*(\d+)', text)
        if m:
            return float(m.group(1))

        # NV84: 各一元组共X (如 "各一元组共17元" → 17)
        m = re.search(r'各一元组共\s*(\d+)\s*元', text)
        if m:
            return float(m.group(1))

        # NV85: 各一元直组共X (如 "福各一元直组共72元" → 72)
        m = re.search(r'各一元直组共\s*(\d+)\s*元', text)
        if m:
            return float(m.group(1))

        # NV86: 每组一当一组 (如 "851 857 751每组一当一组" → 3号×1组×2=6)
        m = re.search(r'([\d\s]+\d)\s*每组一当一组', text)
        if m:
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            return num_count * 2

        # NV87: 一码定位佰个位0各五十元100 (如 "福一码定位佰个位0各五十元100" → 100)
        m = re.search(r'一码定位[佰百]个位\s*\d+\s*各[五十两]+\s*元?\s*(\d+)', text)
        if m:
            return float(m.group(1))

        # NV88: *直选N注+金额 (如 "福*直选400注：003，004..." → 400注×2=800)
        m = re.search(r'\*?\s*直选\s*(\d+)\s*注', text)
        if m:
            zhushu = int(m.group(1))
            # Check for per-note amount
            m_per = re.search(r'各?\s*([五两三四六七八九十百\d]+)\s*[毛元米]', text)
            if m_per:
                per_str = m_per.group(1)
                cn_map88 = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100,'毛':0.1}
                per = cn_map88.get(per_str, 0)
                if per == 0 and per_str.isdigit(): per = int(per_str)
                if per > 0: return zhushu * per * 2
            # Default: each注=2米
            return zhushu * 2

        return 0

    # ============================================================
    # 子模式解析
    # ============================================================
    def _parse_shuangfei(self, text: str) -> float:
        total = 0
        # ========== v5.7 增强 ==========
        # 同义替换预处理 (仅在子方法中临时替换)
        _text = text
        _text = re.sub(r'飞个', '飞各', _text)  # 个=各
        
        # X，Y，Z...组三双飞各W → 号码数×(W组三+W双飞) = 号码数×2W
        m = re.search(r'([\d，,、\s.]+?)\s*组三双飞各\s*(\d+(?:\.\d+)?)', _text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            pair_count = max(len(pairs), 1)
            per = float(m.group(2))
            return pair_count * per * 2  # 组三+双飞各per
        m = re.search(r'([\d，,、\s.]+?)\s*双飞组三各\s*(\d+(?:\.\d+)?)', _text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            pair_count = max(len(pairs), 1)
            per = float(m.group(2))
            return pair_count * per * 2
        # X.Y.Z.双飞各W → 号码数×W
        m = re.search(r'([\d，,、\s.]+?)\s*双飞各\s*(\d+(?:\.\d+)?)', _text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            pair_count = max(len(pairs), 1)
            per = float(m.group(2))
            return pair_count * per
        # X 双飞 Y元 (如 "38 双飞 50" — 号码+双飞+金额)
        for m in re.finditer(r'(\d{2})\s*双飞\s*(\d+(?:\.\d+)?)\s*[元米块]?', _text):
            total += float(m.group(2))
        if total > 0: return total
        # 双飞XY-Z元
        for m in re.finditer(r'双飞\s*[\d,，、\s]+?\s*[-—–]\s*(\d+(?:\.\d+)?)\s*[元米块]', _text):
            total += float(m.group(1))
        if total > 0: return total
        # XY飞Z元
        for m in re.finditer(r'(\d{2})\s*飞\s*(\d+(?:\.\d+)?)\s*[元米块]', _text):
            total += float(m.group(2))
        if total > 0: return total
        # 双飞XX各Z元
        for m in re.finditer(r'双飞\s*([\d,，、\s]+?)\s*各\s*(\d+(?:\.\d+)?)\s*[元米块]', _text):
            pairs = re.findall(r'\d{2}', m.group(1))
            total += len(pairs) * float(m.group(2))
        if total > 0: return total
        # XX飞Z元 (simple)
        for m in re.finditer(r'(\d{2})\s*飞\s*(\d+(?:\.\d+)?)\s*[元米块]', _text):
            total += float(m.group(2))
        if total > 0: return total
        # ========== v5.7 新增 ==========
        # 飞各X米 / 飞个X米 (已在_extract_amount处理，此处作为备用)
        m = re.search(r'飞\s*各?\s*(\d+(?:\.\d+)?)\s*[米元块]', _text)
        if m:
            return float(m.group(1))
        # 双飞X倍 (如 "双飞09五倍" → 10×5=50)
        m = re.search(r'双飞[^\d]*(\d{2})[^\d]*([零一二两三四五六七八九十\d]+)\s*倍', _text)
        if m:
            bei = _cn_num_or_digit(m.group(2))
            if bei is not None and bei > 0:
                return 10 * bei  # 双飞一倍=10米
        # 双飞12/15格式(无金额默认一倍)
        m = re.search(r'双飞\s*([\d/，,、\s]+?)(?:\s*[,，]\s*|\s+)(?!\d+\s*倍)', _text)
        if m:
            pairs_str = m.group(1)
            # 检查是否真的没有金额
            after = _text[_text.find('双飞') + 2:_text.find('双飞') + 20]
            has_amount = bool(re.search(r'\d+\s*[倍米元块]', after))
            if not has_amount:
                pairs = re.findall(r'\d{2}', pairs_str)
                return len(pairs) * 10  # 默认一倍=10米
        # 飞各X米 + 多个号码
        m = re.search(r'([\d，,、\s]+?)\s*飞\s*各?\s*(\d+(?:\.\d+)?)\s*[米元块]', _text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            if pairs:
                per = float(m.group(2))
                return len(pairs) * per
        return 0

    def _parse_baozi(self, text: str) -> float:
        # ========== v5.7 增强 ==========
        # 同义替换预处理
        _text = re.sub(r'零\s*夸', '豹子', text)  # 0夸=豹子
        
        m = re.search(r'豹子\s*全包\s*(\d+)', _text)
        if m: return float(m.group(1))
        # "豹子两倍" → 豹子全包20×2=40
        m = re.search(r'豹子\s*([零一二两三四五六七八九十\d]+)\s*倍', _text)
        if m:
            bei = _cn_num_or_digit(m.group(1))
            if bei is not None and bei > 0:
                return 20 * bei  # 豹子全包=20元/倍
        m = re.search(r'豹子[^\d]*?(\d+(?:\.\d+)?)\s*[元米块]', _text)
        if m: return float(m.group(1))
        m = re.search(r'豹子\s*(\d+)\s*倍\s*(\d+)', _text)
        if m: return float(m.group(2))
        # ========== v5.7 新增 ==========
        # 号码+X倍(如 "222 5倍" → 豹子2×5=10)
        m = re.search(r'(?<!\d)(\d)\1{2}\s*([零一二两三四五六七八九十\d]+)\s*倍', _text)
        if m:
            bei = _cn_num_or_digit(m.group(2))
            if bei is not None and bei > 0:
                return 2 * bei  # 豹子号码×X倍=2×X
        # 豹子+十元 (如 "福222十元零夸二十" → 豹子10米)
        m = re.search(r'豹子\s*(\d+)\s*[元米块]', _text)
        if m: return float(m.group(1))
        # 豹子X (无单位，如 "豹子20" → 20)
        m = re.search(r'豹子\s*(\d+)', _text)
        if m:
            v = float(m.group(1))
            if v >= 10:  # 豹子金额通常>=10
                return v
        return 0

    def _parse_dingwei(self, text: str) -> float:
        total = 0

        # ========== v5.7 增强 ==========
        # 同义替换: 上→打
        _text = re.sub(r'([十百个]位)(\d)\s*上\s*(\d+)', r'\1\2打\3', text)
        
        # === 星号定位 (两码定位) ===
        # "25* 63* 27* 61* 各十元" → 4号×10=40
        m = re.search(r'((?:\d{2}[*xX×]\s*)+)\s*各\s*([零一二两三四五六七八九十\d]+)\s*[元米块]', _text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(1))
            count = len(pairs)
            per = _cn_num_or_digit(m.group(2))
            if count > 0 and per is not None and per > 0:
                return count * per
        # "25* 63*" → 两码定位默认一倍=10元
        m = re.search(r'(\d{2}[*xX×]\s*)+', _text)
        if m:
            pairs = re.findall(r'\d{2}', m.group(0))
            if pairs and len(pairs) >= 2:
                # 检查后面是否有金额
                after = _text[m.end():m.end()+20]
                if not re.search(r'\d+\s*[元米块倍]', after):
                    return len(pairs) * 10  # 默认一倍=10米

        # === 两码定位 ===
        # "百位23十位8两码定位20" → 20 (金额在"两码定位"后面，优先匹配)
        m = re.search(r'百位\s*\d+\s*十位\s*\d+\s*两码定位\s*(\d+(?:\.\d+)?)', _text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v
        # "1百位，3十位，50两码定位" → 50 (金额在"两码定位"前面，逗号分隔格式)
        m = re.search(r'(\d+(?:\.\d+)?)\s*两码定位', _text)
        if m:
            # 确认前面有百/十/个位的上下文
            before = _text[:m.start()]
            if re.search(r'[百十个]位', before):
                v = float(m.group(1))
                if 0.1 <= v <= 100000: return v
        # "两码定位十位38个位690各10" → 2×3×10=60
        m = re.search(r'两码定位\s*[十百]位\s*(\d+)\s*个位\s*(\d+)\s*各\s*(\d+)', _text)
        if m:
            return len(m.group(1)) * len(m.group(2)) * float(m.group(3))
        # "两码定位百位X十位Y各Z"
        m = re.search(r'两码定位\s*百位\s*(\d+)\s*十位\s*(\d+)\s*各\s*(\d+)', _text)
        if m:
            return len(m.group(1)) * len(m.group(2)) * float(m.group(3))
        # "两码定位十位X个位Y各Z" (无"百位"前缀)
        m = re.search(r'两码定位\s*十位\s*(\d+)\s*个位\s*(\d+)\s*各\s*(\d+)', _text)
        if m:
            return len(m.group(1)) * len(m.group(2)) * float(m.group(3))
        # 通用 "两码定位 ... X元/米"
        m = re.search(r'两码定位\s*[^\d]*?(\d+(?:\.\d+)?)\s*[元米块]', _text)
        if m:
            v = float(m.group(1))
            if 0.1 <= v <= 100000: return v

        # === 一码定位 ===
        # "福一码定位十位1，3各一百米" → 2个位×100=200
        m = re.search(r'一码定位\s*[：:]*\s*[十百个]位\s*([\d，,、\s]+?)\s*各\s*([零一二两三四五六七八九十百\d]+)\s*[元米块]', _text)
        if m:
            digits = re.findall(r'\d', m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and len(digits) > 0:
                return len(digits) * per
        # "一码定位十位13个20" → 十位1和3各20=40 (digits紧跟位,个=amount)
        m = re.search(r'一码定位\s*[十百个]位\s*(\d{2,})\s*个\s*(\d+)', _text)
        if m:
            return len(m.group(1)) * float(m.group(2))
        # "十位38各50" → 一码定位，2位各50=100
        m = re.search(r'([十百个]位)\s*(\d{2,})\s*各\s*(\d+(?:\.\d+)?)\s*[元米块]?', _text)
        if m:
            digit_count = len(m.group(2))
            per = float(m.group(3))
            return digit_count * per
        # ========== v5.7 新增 ==========
        # "百位3-5各10" → 2×10=20 (表示百位3和5两个位置)
        # "百位9上30" / "百位9打30" → 30
        # ★ 循环求和：多条定位叠加（如 "百位3-5各10 百位9上30" → 20+30=50）
        dw_total = 0
        has_dw = False
        for m in re.finditer(r'百位\s*\d\s*[-–—]\s*\d\s*各\s*(\d+)', _text):
            dw_total += 2 * int(m.group(1))
            has_dw = True
        for m in re.finditer(r'百位\s*\d\s*(?:上|打)\s*(\d+)', _text):
            dw_total += float(m.group(1))
            has_dw = True
        for m in re.finditer(r'[十百个]位\s*\d\s*([零一二两三四五六七八九十百\d]+)\s*[元米块]', _text):
            v = _cn_num_or_digit(m.group(1))
            if v is not None and v > 0:
                dw_total += v
                has_dw = True
        if has_dw and dw_total > 0:
            return dw_total

        # "十位8五十米" / "百位9打30" 单条兜底 (无单位时也匹配)
        m = re.search(r'[十百个]位\s*(\d)\s*([零一二两三四五六七八九十百\d]+)\s*[元米块]?', _text)
        if m:
            amount = _cn_num_or_digit(m.group(2))
            if amount is not None and amount > 0:
                return amount

        # === 通用定位 ===
        # 一码定位 ... X元/米
        m = re.search(r'一码定位\s*[百十个位\d]+\s*(\d+(?:\.\d+)?)\s*[元米块]', _text)
        if m: return float(m.group(1))
        # 百位/十位/个位 X 元
        for m in re.finditer(r'[百十个]位\s*\d+\s*(\d+)\s*[佰百]元', _text):
            total += float(m.group(1)) * 100
        # 定位各X元
        m = re.search(r'定位\s*[：:]*\s*[^\d]*?各\s*(\d+(?:\.\d+)?)\s*[元米块]', _text)
        if m: return float(m.group(1))
        # 个位X二百元 / 十位X五十元 (定位金额)
        m = re.search(r'[个十百]位\s*\d+\s*[，,]?\s*(\d+)\s*[元米块]', _text)
        if m:
            v = float(m.group(1))
            if v >= 10: return v
        # X码定位 ... X元
        m = re.search(r'定位[：:]*\s*[^\d]*?(\d+(?:\.\d+)?)\s*[元米块]', _text)
        if m:
            v = float(m.group(1))
            if v >= 10: return v
        return total

    def _parse_dan_zu(self, text: str) -> float:
        """X单Y组金额 - 严格序列号过滤"""
        # 前置检查: 如果有"X注各Y单"模式, 不要在dan_zu里匹配零散的"X单"
        has_zhu_pattern = bool(re.search(r'\d+\s*注\s*各', text)) or bool(re.search(r'共\s*\d+\s*注', text))

        # 1. X单Y组+记/计Z
        m = re.search(r'[零一二两三四五六七八九十\d]+\s*[单直]\s*[零一二两三四五六七八九十\d]+\s*组\s*[记计]\s*(\d+)', text)
        if m: return float(m.group(1))

        # 2. 各X单Y组+Z (strict: Z must not be sequence number; 4位+排除, 3位不排除因为组后一定是金额)
        m = re.search(r'各\s*[零一二两三四五六七八九十\d]+\s*[单直]\s*[零一二两三四五六七八九十\d]+\s*组\s*(\d+(?:\.\d+)?)', text)
        if m:
            ns = m.group(1)
            v = float(ns)
            if len(ns) >= 4 and ns.isdigit(): pass  # sequence number
            elif 0.1 <= v <= 5000: return v

        # 3. X单Y组+Z (strict: 4位+排除, 3位不排除)
        m = re.search(r'(?<!各)\s*([零一二两三四五六七八九十]+)\s*[单直]\s*([零一二两三四五六七八九十]+)\s*组\s*(\d+(?:\.\d+)?)', text)
        if m:
            ns = m.group(3)
            v = float(ns)
            if len(ns) >= 4 and ns.isdigit(): pass
            elif 0.1 <= v <= 5000: return v

        # 4. X单+Z (strict: 4+位=序列号, 3位>=100=号码)
        m = re.search(r'([零一二两三四五六七八九十]+)\s*[单直]\s*(\d+)', text)
        if m:
            ns = m.group(2)
            v = float(ns)
            if len(ns) >= 4 and ns.isdigit(): pass
            elif len(ns) == 3 and ns.isdigit() and v >= 100: pass
            elif 0.1 <= v <= 5000: return v

        # 5. 一单一组 (with number count)
        m = re.search(r'一单一组|一直一组|1单1组|1单一组', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
            count = max(len(nums), 1)
            after = text[m.end():]
            am = re.match(r'\s*(\d+)', after)
            if am:
                ns = am.group(1)
                v = float(ns)
                if len(ns) >= 4 and ns.isdigit(): pass
                elif not (len(ns) == 3 and ns.isdigit() and v >= 100):
                    if 0.1 <= v <= 10000: return v
            return 4 * count

        # 6. 通用 X单Y组 计算模式 - 支持阿拉伯数字和中文数字
        # 单=2元/注, 组=2元/注, 总价=(X+Y)*2
        cn = '零一二两三四五六七八九十'
        # 6a: 阿拉伯数字版本 (3单2组, 10单5组 etc.)
        m = re.search(r'(\d+)\s*[单直]\s*(\d+)\s*组', text)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            if 1 <= x <= 99 and 1 <= y <= 99:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                after = text[m.end():]
                am = re.match(r'\s*(\d+)', after)
                if am:
                    ns = am.group(1)
                    v = float(ns)
                    if len(ns) >= 4 and ns.isdigit(): pass
                    elif not (len(ns) == 3 and ns.isdigit() and v >= 100):
                        if 0.1 <= v <= 10000: return v
                return (x + y) * 2 * max(len(nums), 1)
        # 6b: 中文数字版本 (五单二组, 三单一组 etc.) - 替代原硬编码price_map
        m = re.search(r'([零一二两三四五六七八九十百]+)\s*[单直]\s*([零一二两三四五六七八九十百]+)\s*组', text)
        if m:
            x = parse_cn_num(m.group(1))
            y = parse_cn_num(m.group(2))
            if x is not None and y is not None and 1 <= x <= 99 and 1 <= y <= 99:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                after = text[m.end():]
                am = re.match(r'\s*(\d+)', after)
                if am:
                    ns = am.group(1)
                    v = float(ns)
                    if len(ns) >= 4 and ns.isdigit(): pass
                    elif not (len(ns) == 3 and ns.isdigit() and v >= 100):
                        if 0.1 <= v <= 10000: return v
                return (x + y) * 2 * max(len(nums), 1)

        # 7. 一直一组
        m = re.search(r'一直一组|直一组', text)
        if m:
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
            return 4 * max(len(nums), 1)

        # 9. X单 (无组) + 金额
        m = re.search(r'([零一二两三四五六七八九十\d]+)\s*单\s*(\d+)', text)
        if m and not has_zhu_pattern:
            ns = m.group(2)
            v = float(ns)
            if len(ns) >= 4 and ns.isdigit(): return 0
            if len(ns) == 3 and ns.isdigit() and v >= 100: return 0
            if 0.1 <= v <= 5000: return v

        # 10. X单 (无金额, 按号码数×2元/单)
        m = re.search(r'([零一二两三四五六七八九十\d]+)\s*单', text)
        if m and not has_zhu_pattern:
            cn = _cn_num_or_digit(m.group(1))
            if cn is not None and cn > 0:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                return cn * 2 * max(len(nums), 1)

        return 0

    # ============================================================
    # parse_batch_message: 扫描模式
    # ============================================================
    def parse_batch_message(self, text: str) -> List[Dict]:
        """扫描文本中的所有订单, 摘要优先, 严格去重, 玩法自动分类"""
        text = text.strip()
        if not text: return []

        results = []

        # Step 1: 按福/体分割
        segments = re.split(r'(?=[福体][\s\d彩种：:，,一二两三四五六七八九十*])', text)

        for seg in segments:
            seg = seg.strip()
            if not seg: continue
            if len(seg) < 2: continue

            lottery_type = self.parse_lottery_type(seg)

            # Step 2: 在每个segment内扫描所有金额
            found = self._scan_amounts(seg)
            detected_tags = self._detect_play_type(seg)  # v7: 多标签检测
            for amt, pt in found:
                # v7: 合并 _scan_amounts 和 _detect_play_type 的标签
                if pt and detected_tags:
                    seen = set()
                    merged = []
                    for t in (detected_tags + ',' + pt).split(','):
                        if t and t not in seen:
                            seen.add(t)
                            merged.append(t)
                    play_type = ','.join(merged)
                else:
                    play_type = pt or detected_tags
                results.append({
                    "lottery_type": lottery_type,
                    "amount": amt,
                    "prize": "",
                    "status": "success",
                    "bet_numbers": "",
                    "play_type": play_type,
                })

        if not results:
            amount = self.parse_amount(text)
            if amount > 0:
                results.append({
                    "lottery_type": self.parse_lottery_type(text),
                    "amount": amount, "prize": "", "status": "success",
                    "bet_numbers": "", "play_type": self._detect_play_type(text),
                })

        return results

    # ============================================================
    # 超长上下文: 分块处理 + 流式API
    # ============================================================
    CHUNK_SIZE = 5000   # 单块最大字符数

    def _split_into_chunks(self, text: str) -> List[Tuple[str, int]]:
        """将超长文本按消息边界分块, 返回 [(chunk_text, global_offset), ...]

        分块策略:
        1. 有换行时按换行符分割(微信正常导出)
        2. 无换行时按福/体segment边界分割, 不会截断消息
        3. 每块不超过CHUNK_SIZE
        """
        if len(text) <= self.CHUNK_SIZE:
            return [(text, 0)]

        chunks = []

        if '\n' in text:
            # 有换行: 按行分块
            lines = text.split('\n')
            current_chunk = []
            current_len = 0
            offset = 0
            for line in lines:
                line_len = len(line) + 1
                if current_len + line_len > self.CHUNK_SIZE and current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append((chunk_text, offset))
                    offset += current_len
                    current_chunk = []
                    current_len = 0
                current_chunk.append(line)
                current_len += line_len
            if current_chunk:
                chunks.append(('\n'.join(current_chunk), offset))
        else:
            # 无换行: 按福/体segment边界分块, 无重叠
            segments = re.split(r'(?=[福体][\s\d彩种：:，,一二两三四五六七八九十*])', text)
            current_parts = []
            current_len = 0
            offset = 0
            for seg in segments:
                seg_len = len(seg)
                if current_len + seg_len > self.CHUNK_SIZE and current_parts:
                    chunk_text = ''.join(current_parts)
                    chunks.append((chunk_text, offset))
                    offset += current_len
                    current_parts = []
                    current_len = 0
                current_parts.append(seg)
                current_len += seg_len
            if current_parts:
                chunks.append((''.join(current_parts), offset))

        return chunks

    def _deduplicate_by_position(self, results: List[Dict],
                                  text: str, chunk_offset: int) -> List[Dict]:
        """基于文本位置去重: 同一chunk_offset附近(±200字符)内相同金额+玩法的只保留一个"""
        if not results:
            return results

        # 用 (金额, 玩法, 彩种) 作为key, 相同key只保留第一个
        seen = set()
        deduped = []
        for r in results:
            key = (round(r.get("amount", 0), 2),
                   r.get("play_type", ""),
                   r.get("lottery_type", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped

    def parse_batch_message_stream(self, text: str,
                                    on_progress: Callable[[int, int, str], None] = None
                                    ) -> Generator[Dict, None, None]:
        """流式解析超长文本, 逐块yield订单

        Args:
            text: 超长聊天文本
            on_progress: 进度回调 (current_chunk, total_chunks, message)
        Yields:
            Dict: 单条订单结果
        """
        text = text.strip()
        if not text:
            return

        # 短文本直接处理
        if len(text) <= self.CHUNK_SIZE:
            for r in self.parse_batch_message(text):
                yield r
            return

        # 分块
        chunks = self._split_into_chunks(text)
        total_chunks = len(chunks)

        for i, (chunk_text, offset) in enumerate(chunks):
            if on_progress:
                on_progress(i + 1, total_chunks, f"正在解析第 {i+1}/{total_chunks} 块...")

            # 按segment边界分块，不会截断消息，无需去重
            for r in self.parse_batch_message(chunk_text):
                yield r

    def parse_large_text(self, text: str,
                         on_progress: Callable[[int, int, str], None] = None
                         ) -> List[Dict]:
        """解析超长文本(非流式), 返回全部结果

        适用于不需要流式处理的场景(如文件导入)
        """
        return list(self.parse_batch_message_stream(text, on_progress))

    def _scan_amounts(self, text: str) -> List[Tuple[float, str]]:
        """扫描文本中所有金额, 返回 [(amount, play_type), ...]"""
        found = []
        # 已使用的文本范围 - 排序区间, O(n log n)去重
        _claimed_starts = []  # 排序的start列表
        _claimed_ends = []    # 对应的end列表

        def is_claimed(start: int, end: int) -> bool:
            if not _claimed_starts:
                return False
            # 二分查找: 找到第一个start >= start的位置
            idx = bisect.bisect_left(_claimed_starts, start)
            # 检查idx-1: 前一个区间的end可能覆盖start
            if idx > 0 and _claimed_ends[idx - 1] > start:
                return True
            # 检查idx: 当前区间的start可能被end覆盖
            if idx < len(_claimed_starts) and end > _claimed_starts[idx]:
                return True
            return False

        def claim(start: int, end: int, radius_before: int = 0):
            cs = max(0, start - radius_before)
            ce = end
            # 插入排序保持_starts有序
            idx = bisect.bisect_left(_claimed_starts, cs)
            # 检查是否可以合并相邻区间
            merge_start = cs
            merge_end = ce
            # 向左合并
            if idx > 0 and _claimed_ends[idx - 1] >= cs:
                merge_start = _claimed_starts[idx - 1]
                merge_end = max(merge_end, _claimed_ends[idx - 1])
                idx -= 1
            # 向右合并
            remove_end = idx + 1
            while remove_end < len(_claimed_starts) and _claimed_starts[remove_end] <= ce:
                merge_end = max(merge_end, _claimed_ends[remove_end])
                remove_end += 1
            # 替换/插入
            if remove_end > idx + 1 or (idx < len(_claimed_starts) and _claimed_starts[idx] <= cs):
                # 有合并, 先删除被合并的区间
                del _claimed_starts[idx:remove_end]
                del _claimed_ends[idx:remove_end]
            _claimed_starts.insert(idx, merge_start)
            _claimed_ends.insert(idx, merge_end)

        # ========== Phase 1: 最高优先级 - 摘要标记 ==========

        # 🈴X (覆盖前方200字符)
        for m in re.finditer(r'🈴\s*(\d+(?:\.\d+)?)', text):
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=200)

        # 合计/共计/总计X (覆盖前方150字符)
        for m in re.finditer(r'(?:合计|共计|总计)\s*(\d+(?:\.\d+)?)\s*[元米块]?', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=150)

        # (X) 括号金额 (覆盖前方50字符)
        for m in re.finditer(r'[（(]\s*(\d+(?:\.\d+)?)\s*[元米块]?\s*[）)]', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=50)

        # 记X/计X (覆盖前方80字符)
        for m in re.finditer(r'[记计]\s*(\d+(?:\.\d+)?)', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=80)

        # ========== Phase 2: 公式类 ==========

        # X*Y=Z (支持小数)
        for m in re.finditer(r'(\d+)\s*[*/×xX]\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(3)), ""))
            claim(m.start(), m.end(), radius_before=30)

        # X+Y=Z (加法算术)
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(3)), ""))
            claim(m.start(), m.end(), radius_before=30)

        # 直X倍组Y倍共Z
        for m in re.finditer(r'直\s*\d+\s*倍\s*组\s*\d+\s*倍\s*共?\s*(\d+(?:\.\d+)?)', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=50)

        # X注各Y毛单共Z米
        for m in re.finditer(r'(\d+)\s*注\s*各\s*[零一二两三四五六七八九十\d]+\s*毛\s*(?:单\s*)?(?:共|合计)\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(2)), ""))
            claim(m.start(), m.end(), radius_before=100)

        # X注底共W元
        for m in re.finditer(r'(\d+)\s*注\s*底.*?共\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(2)), ""))
            claim(m.start(), m.end(), radius_before=50)

        # 共X(元/米/块)? — 单位可选，但不匹配"共2965 003"这类紧跟数字的
        for m in re.finditer(r'共\s*(\d+(?:\.\d+)?)\s*[元米块]?(?!\s*\d)', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=80)

        # X注各Y单/毛/直 (无元/米)
        for m in re.finditer(r'共?\s*(\d+)\s*注\s*(?:直\s*)?各\s*(?:打\s*)?([零一二两三四五六七八九十\d]+)\s*[单毛直元]', text):
            if is_claimed(m.start(), m.end()): continue
            count = int(m.group(1))
            per = _cn_num_or_digit(m.group(2))
            if per is not None and count > 0:
                suffix = text[m.start():m.end()]
                if '毛' in suffix:
                    amt = count * per * 0.1
                elif '元' in suffix:
                    amt = count * per * 1
                else:
                    amt = count * per * 2
                found.append((amt, ""))
                claim(m.start(), m.end(), radius_before=50)

        # X注直Y米 (如 "633注直选，直6米")
        for m in re.finditer(r'(\d+)\s*注.*?直\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            count = int(m.group(1))
            per = float(m.group(2))
            if count > 0 and per > 0:
                amt = count * per
                found.append((amt, "直选"))
                claim(m.start(), m.end(), radius_before=50)

        # (共X注各Y单) or (共X注)Y单
        for m in re.finditer(r'[（(]\s*共\s*(\d+)\s*注\s*(?:各\s*)?([零一二两三四五六七八九十\d]*)\s*单?\s*[）)]\s*([零一二两三四五六七八九十\d]*)\s*单', text):
            if is_claimed(m.start(), m.end()): continue
            count = int(m.group(1))
            per_str = m.group(2) or m.group(3)
            per = _cn_num_or_digit(per_str) if per_str else 1
            if per is not None and count > 0:
                found.append((count * per * 2, ""))
                claim(m.start(), m.end(), radius_before=50)

        # ========== Phase 3: 组件类 (仅在未被摘要覆盖的区域) ==========

        # ★ 优先匹配: 组六/组三+号码+打+金额 (比普通组六/组三更精确，必须先执行)
        # 中文版: 组六0467打四十 → 40, 组三689打十块钱 → 10
        for m in re.finditer(r'组[三六]\s*\d+\s*打\s*([零一二两三四五六七八九十百\d]+)\s*(?:块钱|元|米|块|倍)?', text):
            if is_claimed(m.start(), m.end()): continue
            v = _cn_num_or_digit(m.group(1))
            suffix = text[m.start():m.end()]
            if v is not None and 0.1 <= v <= 100000:
                if '倍' in suffix:
                    v = v * 2
                found.append((float(v), "组六" if '组六' in text[m.start():m.end()] else "组三"))
                claim(m.start(), m.end(), radius_before=10)
        # 阿拉伯版: 组六0467打40, 组六1468打200
        for m in re.finditer(r'组[三六]\s*\d+\s*打\s*(\d+(?:\.\d+)?)\s*[元米块]?', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, "组六" if '组六' in text[m.start():m.end()] else "组三"))
                claim(m.start(), m.end(), radius_before=10)

        # ★ 直复试/直选/复试 组六 X倍Y米 — 末尾金额优先，倍数不算独立金额
        # 如 "631直复试组六5倍60米" → 60米 (不是5+60=65)
        for m in re.finditer(r'(?:直复试|直选复试|复[试式])\s*组[三六]\s*\d+\s*倍\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, "组六" if '组六' in text[m.start():m.end()] else "组三"))
                claim(m.start(), m.end(), radius_before=30)

        # 组六X + 组三Y (按proximity分组，排除已被"打"格式claim的区域)
        zu_matches = []
        for m in re.finditer(r'组六\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            ns = m.group(1)
            # 排除3位以上号码
            if len(ns) >= 3:
                continue
            # 排除"组六XXX打Y"格式
            after = text[m.end():m.end()+5]
            if re.match(r'\s*打', after):
                continue
            # 排除"组六X倍Y米"格式 (倍数不是金额)
            after2 = text[m.end():m.end()+8]
            if re.match(r'\s*倍\s*\d', after2):
                continue
            v = float(ns)
            if 0.1 <= v <= 2000:
                zu_matches.append((m.start(), m.end(), v, "组六"))
        for m in re.finditer(r'组三\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            ns = m.group(1)
            # 排除3位以上号码
            if len(ns) >= 3:
                continue
            # 排除"组三XXX打Y"格式
            after = text[m.end():m.end()+5]
            if re.match(r'\s*打', after):
                continue
            v = float(ns)
            if 0.1 <= v <= 2000:
                zu_matches.append((m.start(), m.end(), v, "组三"))

        if zu_matches:
            zu_matches.sort()
            # Group by proximity (within 30 chars)
            groups = []
            cur = [zu_matches[0]]
            for zm in zu_matches[1:]:
                if zm[0] - cur[-1][1] <= 30:
                    cur.append(zm)
                else:
                    groups.append(cur)
                    cur = [zm]
            groups.append(cur)
            for g in groups:
                total = sum(x[2] for x in g)
                if total > 0:
                    found.append((total, g[0][3]))
                    for x in g:
                        claim(x[0], x[1], radius_before=3)

        # 双飞

        for m in re.finditer(r'双飞\s*[\d,，、\s]+?\s*[-—–]\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), "双飞"))
            claim(m.start(), m.end(), radius_before=20)
        for m in re.finditer(r'(\d{2})\s*飞\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(2)), "双飞"))
            claim(m.start(), m.end(), radius_before=10)

        # 豹子
        m = re.search(r'豹子\s*全包\s*(\d+)', text)
        if m and not is_claimed(m.start(), m.end()):
            found.append((float(m.group(1)), "豹子"))
            claim(m.start(), m.end(), radius_before=10)

        # 定位 (有"定位"或"百位/十位/个位+金额"都触发)
        dw = self._parse_dingwei(text)
        if dw > 0:
            # 找定位/百位/十位/个位关键词位置
            m = re.search(r'定位|[百十个]位\s*\d', text)
            if m and not is_claimed(m.start(), m.end()):
                found.append((dw, "定位"))
                claim(m.start(), m.end(), radius_before=30)

        # 复试/复式
        for m in re.finditer(r'复[试式]\s*[零一二两三四五六七八九十\d]+\s*单\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, "复式"))
                claim(m.start(), m.end(), radius_before=20)

        # 百X十Y个Z 复式 (排列3/3D)
        for m in re.finditer(r'百\s*\d+\s*十\s*\d+\s*个\s*\d+\s*(?:排|[体福])?\s*(?:\d+\s*倍\s*)?(\d+(?:\.\d+)?)\s*[元米块]?', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, "复式"))
                claim(m.start(), m.end(), radius_before=30)
        for m in re.finditer(r'百\s*\d+\s*十\s*\d+\s*个\s*\d+\s*(?:排|[体福])?\s*\d+\s*倍\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, "复式"))
                claim(m.start(), m.end(), radius_before=30)

        # 单选X倍Y
        for m in re.finditer(r'单选\s*(\d+)\s*倍\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(2)), "直选"))
            claim(m.start(), m.end(), radius_before=15)

        # 直X倍 (如 "697直4倍")
        for m in re.finditer(r'\d{3}\s*直\s*(\d+)\s*倍', text):
            if is_claimed(m.start(), m.end()): continue
            v = int(m.group(1)) * 2
            if 0.1 <= v <= 100000:
                found.append((v, "直选"))
                claim(m.start(), m.end(), radius_before=15)

        # 各X直 (如 "297 682 785 各2直")
        for m in re.finditer(r'((?:\d{3}\s*)+)\s*各\s*(\d+)\s*直', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            count = len(nums)
            zhi = int(m.group(2))
            v = count * zhi * 2
            if 0.1 <= v <= 100000:
                found.append((v, "直选"))
                claim(m.start(), m.end(), radius_before=20)

        # 毒/独胆X打Y元
        for m in re.finditer(r'(?:毒|独胆)\s*\d+\s*打\s*(\d+(?:\.\d+)?)\s*[元米块]?', text):
            if is_claimed(m.start(), m.end()): continue
            v = float(m.group(1))
            if 0.1 <= v <= 100000:
                found.append((v, "独胆"))
                claim(m.start(), m.end(), radius_before=15)

        # 独胆X，[彩种]Y米 (无"打"字)
        if re.search(r'(?:毒|独胆)', text):
            for m in re.finditer(r'(?:体|福|体福|福体)\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
                if is_claimed(m.start(), m.end()): continue
                v = float(m.group(1))
                if 0.1 <= v <= 100000:
                    found.append((v, "独胆"))
                    claim(m.start(), m.end(), radius_before=15)

        # P9b3_scan: 独X [Y...] 各Z元 (如 "体独0 1 各300元" — 2个胆各300=600)
        for m in re.finditer(r'(?:毒|独胆|独)\s*\d[\d\s]*各\s*(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            du_part = text[m.start():text.index('各', m.start())]
            nums = re.findall(r'\d', du_part)
            count = max(len(nums), 1)
            v = float(m.group(1)) * count
            if 0.1 <= v <= 100000:
                found.append((v, "独胆"))
                claim(m.start(), m.end(), radius_before=15)

        # P9c_scan: X米直Y米组 (如 "812 813 357一米直三米组" — 直1米+组3米=12)
        # 中文版
        for m in re.finditer(r'([零一二两三四五六七八九十]{1,2})\s*米\s*直\s*([零一二两三四五六七八九十]{1,2})\s*米\s*组', text):
            if is_claimed(m.start(), m.end()): continue
            zhi_mi = parse_cn_num(m.group(1))
            zu_mi = parse_cn_num(m.group(2))
            if zhi_mi is not None and zu_mi is not None:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
                num_count = max(len(nums), 1)
                amt = num_count * (zhi_mi + zu_mi)
                if 0.1 <= amt <= 100000:
                    found.append((amt, "组选"))
                    claim(m.start(), m.end(), radius_before=30)
        # 阿拉伯版
        for m in re.finditer(r'(\d{1,2})\s*米\s*直\s*(\d{1,2})\s*米\s*组', text):
            if is_claimed(m.start(), m.end()): continue
            zhi_mi = int(m.group(1))
            zu_mi = int(m.group(2))
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before[-60:])
            num_count = max(len(nums), 1)
            amt = num_count * (zhi_mi + zu_mi)
            if 0.1 <= amt <= 100000:
                found.append((amt, "组选"))
                claim(m.start(), m.end(), radius_before=30)

        # ========== Phase 3.5: NV58-NV88 规则同步 ==========

        # NV58: X当一 (两当一=6米, 五当一=12米, 一当一=4米; 含义: X注直+1注组=(X+1)*2)
        cn_map58s = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100}
        for m in re.finditer(r'(?:福|体)?\s*\d{3}\s*([五两三四六七八九十百一\d]+)\s*当\s*一', text):
            if is_claimed(m.start(), m.end()): continue
            val_str = m.group(1)
            val = cn_map58s.get(val_str, 0)
            if val == 0 and val_str.isdigit(): val = int(val_str)
            if val > 0:
                found.append((float((val + 1) * 2), ""))
                claim(m.start(), m.end(), radius_before=10)
        for m in re.finditer(r'\d{3}\s*([五两三四六七八九十百一\d]+)\s*当\s*一', text):
            if is_claimed(m.start(), m.end()): continue
            val_str = m.group(1)
            val = cn_map58s.get(val_str, 0)
            if val == 0 and val_str.isdigit(): val = int(val_str)
            if val > 0:
                found.append((float((val + 1) * 2), ""))
                claim(m.start(), m.end(), radius_before=10)

        # NV60: X毛直 (如 "三毛直" → 3*0.1*2=0.6)
        cn_map60s = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
        for m in re.finditer(r'([五两三四六七八九十\d]+)\s*毛\s*直', text):
            if is_claimed(m.start(), m.end()): continue
            val_str = m.group(1)
            val = cn_map60s.get(val_str, 0)
            if val == 0 and val_str.isdigit(): val = int(val_str)
            if val > 0:
                found.append((val * 0.1 * 2, "直选"))
                claim(m.start(), m.end(), radius_before=10)

        # NV61: 飞X米/飞一倍 (两位码飞=10米/倍)
        for m in re.finditer(r'(\d{2})\s*飞\s*(\d+)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(2)), "双飞"))
            claim(m.start(), m.end(), radius_before=10)
        for m in re.finditer(r'(\d{2})\s*飞\s*一倍', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((10.0, "双飞"))
            claim(m.start(), m.end(), radius_before=10)
        # X飞Y米 (如 "15飞20米")
        for m in re.finditer(r'(\d+)\s*飞\s*(\d+)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(2)), "双飞"))
            claim(m.start(), m.end(), radius_before=10)

        # NV62: 独胆+金额 (如 "独胆9 福50")
        for m in re.finditer(r'独[胆旦]\s*\d+\s+[福体]\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), "独胆"))
            claim(m.start(), m.end(), radius_before=15)
        for m in re.finditer(r'独旦\s*\d+\s*买\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), "独胆"))
            claim(m.start(), m.end(), radius_before=15)

        # NV64: 两位码+各+数+一码定位
        for m in re.finditer(r'(\d{2})\s*各\s*(\d+)\s*一码定位', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(2)) * 2, "定位"))
            claim(m.start(), m.end(), radius_before=10)

        # NV65: 和值X Y
        for m in re.finditer(r'和值\s*\d+\s+(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), ""))
            claim(m.start(), m.end(), radius_before=10)

        # NV67: 豹子打团 (有金额用金额, 无金额默认2米)
        for m in re.finditer(r'豹子打团[，,]?\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), "豹子"))
            claim(m.start(), m.end(), radius_before=10)
        for m in re.finditer(r'豹子打团', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((2.0, "豹子"))
            claim(m.start(), m.end(), radius_before=10)

        # NV70: 各N组 (如 "562 560各三组" → 2号×3×2=12)
        cn_map70s = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
        for m in re.finditer(r'([\d\s]+?)\s*各\s*(\d+)\s*组\b', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            groups = int(m.group(2))
            found.append((num_count * groups * 2.0, ""))
            claim(m.start(), m.end(), radius_before=20)
        for m in re.finditer(r'([\d\s]+?)\s*各\s*([五两三四六七八九十百\d]+)\s*组\b', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            grp_str = m.group(2)
            groups = cn_map70s.get(grp_str, 0)
            if groups == 0 and grp_str.isdigit(): groups = int(grp_str)
            if groups > 0:
                found.append((num_count * groups * 2.0, ""))
                claim(m.start(), m.end(), radius_before=20)

        # NV71: 对子全包 (有金额用金额, 无金额默认100米)
        for m in re.finditer(r'对子(?:组三)?全包\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), ""))
            claim(m.start(), m.end(), radius_before=10)
        for m in re.finditer(r'对子(?:组三)?全包', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((100.0, ""))
            claim(m.start(), m.end(), radius_before=10)

        # NV72: 号码-N组 (如 "福009-1组" → 2)
        for m in re.finditer(r'(\d{3})\s*[-—–]\s*(\d+)\s*组', text):
            if is_claimed(m.start(), m.end()): continue
            groups = int(m.group(2))
            found.append((groups * 2.0, ""))
            claim(m.start(), m.end(), radius_before=10)

        # NV73: 独胆+各X倍
        for m in re.finditer(r'独\s*([\d,，]+)\s*各\s*(\d+)\s*倍', text):
            if is_claimed(m.start(), m.end()): continue
            digits = re.findall(r'\d', m.group(1))
            digit_count = max(len(digits), 1)
            beishu = int(m.group(2))
            found.append((digit_count * beishu * 2.0, "独胆"))
            claim(m.start(), m.end(), radius_before=15)

        # NV74: 各打Y组 / 共N注各打X组
        for m in re.finditer(r'([\d\s]+\d)\s*各打\s*(\d+)\s*组\b', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            groups = int(m.group(2))
            found.append((num_count * groups * 2.0, ""))
            claim(m.start(), m.end(), radius_before=20)
        for m in re.finditer(r'共\s*(\d+)\s*注\s*各打\s*(\d+)\s*组', text):
            if is_claimed(m.start(), m.end()): continue
            zhushu = int(m.group(1))
            groups = int(m.group(2))
            found.append((zhushu * groups * 2.0, ""))
            claim(m.start(), m.end(), radius_before=20)

        # NV75: 体+号码+组各X元
        for m in re.finditer(r'([\d\s]+\d)\s*体?\s*组各\s*一元', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            found.append((num_count * 2.0, ""))
            claim(m.start(), m.end(), radius_before=20)
        for m in re.finditer(r'([\d\s]+\d)\s*体?\s*组各\s*(\d+)\s*元', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            per = float(m.group(2))
            found.append((num_count * per * 2.0, ""))
            claim(m.start(), m.end(), radius_before=20)

        # NV76: 组三各X (如 "体1347 1358组三各十" → 2×10×2=40)
        cn_map76s = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
        for m in re.finditer(r'([\d\s]+\d)\s*组三\s*各\s*([五两三四六七八九十百\d]+)', text):
            if is_claimed(m.start(), m.end()): continue
            combos = re.findall(r'(?<!\d)\d{4,9}(?!\d)', m.group(1))
            combo_count = max(len(combos), 1)
            beishu_str = m.group(2)
            beishu = cn_map76s.get(beishu_str, 0)
            if beishu == 0 and beishu_str.isdigit(): beishu = int(beishu_str)
            if beishu > 0:
                found.append((combo_count * beishu * 2.0, "组三"))
                claim(m.start(), m.end(), radius_before=20)

        # NV78: 一直一组+金额
        for m in re.finditer(r'一直一组\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), ""))
            claim(m.start(), m.end(), radius_before=15)

        # NV81: 组选组三各X元
        for m in re.finditer(r'([\d\s]+\d)\s*组选组三\s*各\s*(\d+)\s*[元米]?', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            per = float(m.group(2))
            found.append((num_count * per, "组三"))
            claim(m.start(), m.end(), radius_before=20)

        # NV82: **分隔码组六+组三
        for m in re.finditer(r'(\d{4,5})\s*\*\*\s*(\d{4})\s*组六\s*(\d+)\s*组三\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(3)) + float(m.group(4)), ""))
            claim(m.start(), m.end(), radius_before=20)

        # NV83: X直共Y (如 "296 福直共4" → 4)
        for m in re.finditer(r'\d{3}\s*福?\s*直\s*共\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), "直选"))
            claim(m.start(), m.end(), radius_before=10)

        # NV84: 各一元组共X
        for m in re.finditer(r'各一元组共\s*(\d+)\s*元', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), ""))
            claim(m.start(), m.end(), radius_before=30)

        # NV85: 各一元直组共X
        for m in re.finditer(r'各一元直组共\s*(\d+)\s*元', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), ""))
            claim(m.start(), m.end(), radius_before=30)

        # NV86: 每组一当一组
        for m in re.finditer(r'([\d\s]+\d)\s*每组一当一组', text):
            if is_claimed(m.start(), m.end()): continue
            nums = re.findall(r'\d{3}', m.group(1))
            num_count = max(len(nums), 1)
            found.append((num_count * 2.0, ""))
            claim(m.start(), m.end(), radius_before=20)

        # NV88: 直选N注 (如 "福*直选400注" → 400×2=800)
        for m in re.finditer(r'\*?\s*直选\s*(\d+)\s*注', text):
            if is_claimed(m.start(), m.end()): continue
            zhushu = int(m.group(1))
            found.append((zhushu * 2.0, "直选"))
            claim(m.start(), m.end(), radius_before=15)

        # ========== Phase 4: 单组模式 ==========

        # ★ 点分/逗分/空格号码+X单 (如 "873.682.265十单" → 3号×10×2=60)
        for m in re.finditer(r'([\d\s.,，、\-—–]+?\d{3})\s*([零一二两三四五六七八九十百\d]+)\s*单(?!\s*组|\s*[元米块])', text):
            if is_claimed(m.start(), m.end()): continue
            cn = _cn_num_or_digit(m.group(2))
            if cn is not None and cn > 0:
                nums_part = m.group(1)
                nums = re.findall(r'\d{3}', nums_part)
                num_count = max(len(nums), 1)
                amt = cn * 2 * num_count
                if 0.1 <= amt <= 100000:
                    found.append((amt, ""))
                    claim(m.start(), m.end(), radius_before=len(nums_part)+5)

        # X单Y组+记/计Z
        for m in re.finditer(r'[零一二两三四五六七八九十\d]+\s*[单直]\s*[零一二两三四五六七八九十\d]+\s*组\s*[记计]\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            found.append((float(m.group(1)), ""))
            claim(m.start(), m.end(), radius_before=80)

        # 各X单Y组+Z
        for m in re.finditer(r'各\s*[零一二两三四五六七八九十\d]+\s*[单直]\s*[零一二两三四五六七八九十\d]+\s*组\s*(\d+(?:\.\d+)?)', text):
            if is_claimed(m.start(), m.end()): continue
            ns = m.group(1)
            v = float(ns)
            if len(ns) >= 4 and ns.isdigit(): continue  # sequence number
            if 0.1 <= v <= 5000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=60)

        # X单Y组+Z (非各)
        for m in re.finditer(r'(?<!各)\s*([零一二两三四五六七八九十]+)\s*[单直]\s*([零一二两三四五六七八九十]+)\s*组\s*(\d+(?:\.\d+)?)', text):
            if is_claimed(m.start(), m.end()): continue
            ns = m.group(3)
            v = float(ns)
            if len(ns) >= 4 and ns.isdigit(): continue
            if 0.1 <= v <= 5000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=60)

        # X单+Z
        for m in re.finditer(r'([零一二两三四五六七八九十]+)\s*[单直]\s*(\d+)', text):
            if is_claimed(m.start(), m.end()): continue
            ns = m.group(2)
            v = float(ns)
            if len(ns) >= 4 and ns.isdigit(): continue
            if len(ns) == 3 and ns.isdigit() and v >= 100: continue
            if 0.1 <= v <= 5000:
                found.append((v, ""))
                claim(m.start(), m.end(), radius_before=30)

        # 一单一组 (count 3-digit nums before)
        for m in re.finditer(r'一单一组|一直一组|1单1组|1单一组', text):
            if is_claimed(m.start(), m.end()): continue
            before = text[:m.start()]
            nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
            count = max(len(nums), 1)
            after = text[m.end():]
            am = re.match(r'\s*(\d+)', after)
            amt = 4 * count
            if am:
                ns = am.group(1)
                v = float(ns)
                if len(ns) < 4 and not (len(ns) == 3 and ns.isdigit() and v >= 100):
                    if 0.1 <= v <= 10000: amt = v
            found.append((amt, ""))
            claim(m.start(), m.end(), radius_before=20)

        # 固定价格模式
        price_map = [
            (r'一单两组|一直两组', 6), (r'一单三组|一直三组', 8),
            (r'两单一组|二单一组', 6), (r'两单二组|二单二组', 8),
            (r'三单两组|三单二组', 10), (r'三单一组', 8),
            (r'四单一组', 10), (r'五单一组', 12),
            (r'六单一组', 14), (r'七单一组', 16),
            (r'八单二组|八单两组', 20), (r'八单一组', 18),
            (r'九单一组', 20), (r'十单一组', 22),
            (r'二十单一组', 42), (r'三十单一组', 62),
            (r'五十单五十组', 200), (r'五单五组', 20),
            (r'五单二组', 14), (r'五单三组', 16),
            (r'四单二组|四单两组', 12), (r'三单五组', 16),
            (r'十单五组', 30), (r'十单十组', 40),
            (r'二单三组', 10), (r'七单三组', 20),
            (r'五单十组', 30), (r'二十五单十组', 70),
        ]
        for pat, price in price_map:
            for m in re.finditer(pat, text):
                if is_claimed(m.start(), m.end()): continue
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                after = text[m.end():]
                am = re.match(r'\s*(\d+)', after)
                amt = price * max(len(nums), 1)
                if am:
                    ns = am.group(1)
                    v = float(ns)
                    if len(ns) < 4 and not (len(ns) == 3 and ns.isdigit() and v >= 100):
                        if 0.1 <= v <= 10000: amt = v
                found.append((amt, ""))
                claim(m.start(), m.end(), radius_before=20)

        # X单Y组(无后缀金额) - 计算模式
        for m in re.finditer(r'([零一二两三四五六七八九十]+)\s*[单直]\s*([零一二两三四五六七八九十]+)\s*组', text):
            if is_claimed(m.start(), m.end()): continue
            x = parse_cn_num(m.group(1))
            y = parse_cn_num(m.group(2))
            if x is not None and y is not None:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                amt = (x + y) * 2 * max(len(nums), 1)
                if amt > 0:
                    found.append((amt, ""))
                    claim(m.start(), m.end(), radius_before=20)

        # X单(无组, 无金额) - 按号码数×2元
        for m in re.finditer(r'([零一二两三四五六七八九十\d]+)\s*单(?!\s*组|\s*[元米块]|\s*\d)', text):
            if is_claimed(m.start(), m.end()): continue
            cn = _cn_num_or_digit(m.group(1))
            if cn is not None and cn > 0:
                before = text[:m.start()]
                nums = re.findall(r'(?<!\d)\d{3}(?!\d)', before)
                amt = cn * 2 * max(len(nums), 1)
                if amt > 0:
                    found.append((amt, ""))
                    claim(m.start(), m.end(), radius_before=10)

        # ========== Phase 5: 直接金额 X元/米/块 ==========
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*[元米块]', text):
            if is_claimed(m.start(), m.end()): continue
            ns = m.group(1)
            v = float(ns)
            if not (0.1 <= v <= 100000): continue
            if len(ns) == 3 and ns.isdigit() and v >= 100:
                before = text[:m.start()]
                if re.search(r'\d{3}\s*$', before): continue
                if re.search(r'[福体]\s*$', before): continue
            found.append((v, ""))
            claim(m.start(), m.end(), radius_before=20)

        return found

    # ============================================================
    # 其他方法
    # ============================================================
    def parse_lottery_type(self, text: str) -> str:
        if re.search(r'体福|福体', text): return "体福"
        if re.search(r'体[彩种]?|排列[35]|排(?=\s*\d+\s*倍)|大乐透|七星', text): return "体"
        if re.search(r'福[彩种]?|双色球|3D|快乐8|时时彩|褔', text): return "福"
        return ""

    def _detect_play_type(self, text: str) -> str:
        """v7: 玩法自动分类，支持多标签(逗号分隔)
        一条消息可同时属于多个玩法，如'组三10米组六20米'→'组三,组六'
        """
        cn_num = r'[一两二三四五六七八九十\d]+'
        tags = []

        # === 1. 复式(百十个) ===
        if re.search(r'百\s*\d+\s*十\s*\d+\s*个\s*\d+', text):
            tags.append("复式")

        # === 2. 直复试 ===
        if re.search(r'直复试|直选复试', text):
            tags.append("直复试")

        # === 3. 直组 (含隐式) ===
        if re.search(r'直组|直租', text):
            tags.append("直组")
        elif re.search(cn_num + r'\s*当\s*一', text):
            tags.append("直组")
        elif re.search(r'一\s*单\s*一\s*组', text):
            tags.append("直组")
        elif re.search(cn_num + r'\s*单\s*一?\s*组', text):
            tags.append("直组")
        elif re.search(r'每组.*' + cn_num + r'\s*当', text):
            tags.append("直组")
        elif re.search(r'直\s*共', text):
            tags.append("直组")
        elif re.search(r'每\s*组\s*' + cn_num + r'\s*当', text):
            tags.append("直组")

        # === 4. 复试/复式 (不含直复试和复式百十个) ===
        if re.search(r'复[试式]', text) and "直复试" not in tags and "复式" not in tags:
            tags.append("复试")

        # === 5. 直选 ===
        if re.search(r'直选|单选', text):
            tags.append("直选")
        elif re.search(cn_num + r'\s*单(?!\s*一?\s*组)', text) and "复试" not in tags:
            tags.append("直选")
        elif re.search(r'一\s*单(?!\s*一\s*组)', text) and "复试" not in tags:
            tags.append("直选")
        elif re.search(r'各\s*' + cn_num + r'\s*单(?!\s*组)', text):
            tags.append("直选")
        # 隐式: "直6元"/"直3米" → 直选 (非直组/直复试)
        elif re.search(r'直\s*\d+\s*[元米块]', text) and "直组" not in tags:
            tags.append("直选")

        # === 6. 组六 ===
        if re.search(r'组六|组陆|祖六|租六|纽六', text):
            tags.append("组六")

        # === 7. 组三 (显式关键词) ===
        if re.search(r'组三|祖三|租三|纽三', text):
            tags.append("组三")

        # === 8. 组选 ===
        if re.search(r'组选|祖选|租选', text):
            tags.append("组选")
        elif re.search(r'一?\s*组(?!六|三|选)', text) and "直组" not in tags:
            tags.append("组选")
        # 隐式: "组2元"/"组3米" → 组选 (非组六/组三/直组)
        elif re.search(r'组\s*\d+\s*[元米块]', text) and "组选" not in tags \
                and "组六" not in tags and "组三" not in tags and "直组" not in tags:
            tags.append("组选")

        # === 9. 对子 ===
        if re.search(r'对子', text):
            tags.append("对子")

        # === 10. 双飞 ===
        if re.search(r'双飞', text):
            tags.append("双飞")

        # === 11. 定位 (含百十个位+星号标记+两码/一码定位) ===
        if re.search(r'定位|两码定位|一码定位|二码定位', text):
            tags.append("定位")
        elif re.search(r'[百十个]位\s*\d', text):
            tags.append("定位")
        elif re.search(r'\d{2}\s*\*', text):
            tags.append("定位")

        # === 12. 豹子 (含包豹子) ===
        if re.search(r'豹子|包豹子', text):
            tags.append("豹子")

        # === 13. 和值 (v7新增) ===
        if re.search(r'和值', text):
            tags.append("和值")

        # === 14. 托胆 ===
        if re.search(r'托胆', text):
            tags.append("托胆")
        elif re.search(r'[2二两]\s*胆', text):
            tags.append("托胆")

        # === 15. 独胆 ===
        if re.search(r'独胆|一码|毒胆|毒\s|独\s*\d', text):
            tags.append("独胆")
        if re.search(r'[1一]\s*胆', text) and "独胆" not in tags:
            tags.append("独胆")

        # === 16. 带对子号码→组三 (v7: 隐式检测) ===
        # 三位数中有重复数字的 → 组三 (排除金额: 各/打/共/计/元/米/块后的数字)
        if "组三" not in tags and "豹子" not in tags:
            nums = re.findall(r'(?<![各打共计元米块])(?<!\d)(\d{3})(?![\d米元块倍注个])', text)
            for num in nums:
                d = list(num)
                if d[0] == d[1] or d[1] == d[2] or d[0] == d[2]:
                    tags.append("组三")
                    break

        return ",".join(tags) if tags else ""

    def parse_message(self, text: str) -> Dict:
        amount = self.parse_amount(text)
        return {"lottery_type": self.parse_lottery_type(text), "amount": amount,
                "prize": "", "status": "success" if amount > 0 else "failed",
                "bet_numbers": "", "play_type": self._detect_play_type(text)}

    def parse_chat_line(self, line: str) -> Dict:
        result = {"time": "", "nickname": "未知", "content": line, "raw": line}
        m = re.search(r"\[?(20\d{2}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})\]?", line)
        search_start = 0
        if m:
            result["time"] = m.group(1).replace("/", "-")
            search_start = m.end()
            result["content"] = line[m.end():].strip()
        # 从时间戳之后搜索昵称: xxx
        m2 = re.search(r"\]?\s*([^\s\[\]:：]+)[:：]\s*", line[search_start:])
        if m2:
            result["nickname"] = m2.group(1)
            result["content"] = line[search_start:][m2.end():].strip()
        return result


class Importer:
    def __init__(self, db=None):
        self.db = db
        self.parser = MessageParser()
        self._cancelled = False  # 支持取消

    def cancel(self):
        """取消正在进行的导入"""
        self._cancelled = True

    def import_from_text(self, text: str, group_name: str = "默认群",
                         on_progress: Callable[[int, int, str], None] = None) -> int:
        """导入文本, 支持进度回调和取消

        Args:
            text: 聊天记录文本
            group_name: 群名
            on_progress: 进度回调 (current, total, message)
        Returns:
            导入的订单数
        """
        from datetime import datetime
        self._cancelled = False

        lines = text.strip().split("\n")
        total_lines = len(lines)
        count = 0
        group_id = self.db.add_group(group_name) if self.db else 0

        # 单行文本(无换行): 使用超长上下文分块处理
        if total_lines <= 1:
            content = lines[0] if lines else text
            if on_progress:
                on_progress(0, 1, "正在解析超长文本...")

            for batch in self.parser.parse_batch_message_stream(
                content,
                on_progress=lambda c, t, m: on_progress(c, t, m) if on_progress else None
            ):
                if self._cancelled:
                    break
                if self.db:
                    self.db.add_order(group_id=group_id, nickname="未知",
                                     time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                     lottery_type=batch.get("lottery_type", ""),
                                     content=content[:200], amount=batch.get("amount", 0),
                                     prize="", status="success", raw_text=content[:500],
                                     play_type=batch.get("play_type", ""),
                                     bet_numbers=batch.get("bet_numbers", ""))
                count += 1

            if on_progress:
                on_progress(1, 1, f"完成, 共 {count} 条")
            return count

        # 多行文本: 逐行处理, 带进度
        for i, line in enumerate(lines):
            if self._cancelled:
                break

            line = line.strip()
            if not line: continue

            # 进度回调(每10行报告一次, 减少开销)
            if on_progress and (i % 10 == 0 or i == total_lines - 1):
                on_progress(i + 1, total_lines, f"正在处理第 {i+1}/{total_lines} 行...")

            parsed = self.parser.parse_chat_line(line)
            content = parsed["content"]
            for batch in self.parser.parse_batch_message(content):
                if self.db:
                    time_str = parsed["time"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.db.add_order(group_id=group_id, nickname=parsed["nickname"],
                                     time=time_str, lottery_type=batch.get("lottery_type", ""),
                                     content=content[:200], amount=batch.get("amount", 0),
                                     prize="", status="success", raw_text=line[:500],
                                     play_type=batch.get("play_type", ""),
                                     bet_numbers=batch.get("bet_numbers", ""))
                count += 1

        if on_progress:
            on_progress(total_lines, total_lines, f"完成, 共 {count} 条")
        return count

    def import_from_file(self, file_path: str, group_name: str = None,
                         on_progress: Callable[[int, int, str], None] = None) -> Tuple[int, str]:
        """从文件导入, 支持进度回调"""
        import os
        text = None
        for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(file_path, "r", encoding=enc) as f: text = f.read()
                break
            except: continue
        if text is None: text = ""
        if not group_name: group_name = os.path.splitext(os.path.basename(file_path))[0]
        return self.import_from_text(text, group_name, on_progress), group_name
