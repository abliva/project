"""
安全过滤器
负责敏感词检测、权限检查、输出内容规范等安全功能
确保AI助手的安全合规运行
"""

import re
import json
import string
from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import safety_config


@dataclass
class SafetyCheckResult:
    """
    安全检查结果数据类
    """
    is_safe: bool                           # 是否通过安全检查
    risk_level: str = "low"                 # 风险等级: low, medium, high, critical
    blocked_content: str = ""               # 被拦截的内容片段
    violation_type: str = ""                # 违规类型: sensitive_word, permission, format, etc.
    filtered_text: str = ""                 # 过滤后的文本（如果适用）
    suggestions: List[str] = field(default_factory=list)  # 修改建议
    details: Dict[str, Any] = field(default_factory=dict)
    check_time: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_safe": self.is_safe,
            "risk_level": self.risk_level,
            "blocked_content": self.blocked_content[:100] if self.blocked_content else "",
            "violation_type": self.violation_type,
            "has_suggestions": len(self.suggestions) > 0,
            "suggestions_count": len(self.suggestions),
            "check_time": self.check_time
        }


class SafetyFilter:
    """
    安全过滤器核心类

    功能：
    1. 敏感词过滤 - 检测并屏蔽违规词汇
    2. 权限检查 - 验证操作权限和访问控制
    3. 输出内容规范 - 确保输出符合安全标准
    4. 输入验证 - 检查恶意输入和注入攻击
    5. 日志记录 - 记录所有安全相关事件
    """

    # 危险模式匹配规则（用于检测注入攻击等）
    DANGEROUS_PATTERNS = [
        (r"(?i)(drop|delete|truncate)\s+(table|database)", "SQL注入"),
        (r"(?i)<script[^>]*>.*?</script>", "XSS脚本注入"),
        (r"(?i)(eval|exec|system)\s*\(", "代码执行"),
        (r"(\.\.\/|\.\.\\\\)", "路径遍历"),
        (r"(?i)(union\s+select|or\s+1\s*=\s*1)", "SQL注入变体"),
    ]

    # 个人信息识别模式
    PII_PATTERNS = [
        (r"\d{11}", "手机号码"),                    # 手机号
        (r"\d{17}[\dXx]", "身份证号"),              # 身份证号
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱地址"),
        (r"\d{16,19}", "银行卡号"),                  # 银行卡
        (r"(微信|QQ|支付宝)[号：:]\s*\d+", "社交账号"), # 社交账号
    ]

    def __init__(self):
        """初始化安全过滤器"""
        # 敏感词集合（使用set提高查找效率）
        self.sensitive_words: Set[str] = set()
        
        # 自定义敏感词黑名单
        self._blacklist: Set[str] = set()
        
        # 白名单（允许的词汇，优先级高于黑名单）
        self._whitelist: Set[str] = set()
        
        # 安全事件日志
        self.security_log: List[Dict[str, Any]] = []
        
        # 统计信息
        self.stats = {
            "total_checks": 0,
            "blocked_count": 0,
            "warning_count": 0,
            "passed_count": 0
        }

        # 加载配置的敏感词
        self._load_sensitive_words()

        print(f"✓ 安全过滤器初始化完成 | 已加载 {len(self.sensitive_words)} 个敏感词")

    def _load_sensitive_words(self):
        """加载敏感词列表"""
        # 加载配置文件中的自定义敏感词
        for word in safety_config.custom_sensitive_words:
            if word:
                self.sensitive_words.add(word.strip())
                self._blacklist.add(word.strip())

        # 尝试从外部文件加载更多敏感词
        if safety_config.sensitive_words_file and os.path.exists(safety_config.sensitive_words_file):
            try:
                with open(safety_config.sensitive_words_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith('#'):
                            self.sensitive_words.add(word)
                            self._blacklist.add(word)
                print(f"  从文件加载额外敏感词: {safety_config.sensitive_words_file}")
            except Exception as e:
                print(f"  ⚠ 加载敏感词文件失败: {e}")

    def check_input(self, user_input: str, check_types: List[str] = None) -> SafetyCheckResult:
        """
        检查用户输入的安全性

        Args:
            user_input: 用户输入文本
            check_types: 要执行的检查类型列表，默认全部检查
                        可选值: ['sensitive_words', 'injection', 'pii', 'format']

        Returns:
            安全检查结果
        """
        self.stats["total_checks"] += 1
        
        if check_types is None:
            check_types = ['sensitive_words', 'injection', 'pii', 'format']

        results = []

        # 1. 敏感词检查
        if 'sensitive_words' in check_types and safety_config.enable_content_filter:
            result = self._check_sensitive_words(user_input)
            results.append(result)

        # 2. 注入攻击检查
        if 'injection' in check_types:
            result = self._check_injection_attacks(user_input)
            results.append(result)

        # 3. 个人信息检查
        if 'pii' in check_types:
            result = self._check_pii(user_input)
            results.append(result)

        # 4. 格式和长度检查
        if 'format' in check_types:
            result = self._check_format(user_input)
            results.append(result)

        # 聚合所有检查结果
        final_result = self._aggregate_check_results(results)

        # 记录日志
        if not final_result.is_safe or final_result.risk_level != "low":
            self._log_security_event("input_check", user_input, final_result)

        return final_result

    def check_output(self, output_text: str) -> SafetyCheckResult:
        """
        检查AI输出的安全性

        Args:
            output_text: AI生成的输出文本

        Returns:
            安全检查结果
        """
        self.stats["total_checks"] += 1

        results = []

        # 输出也需要进行敏感词检查
        if safety_config.enable_content_filter:
            result = self._check_sensitive_words(output_text)
            results.append(result)

        # 检查输出长度限制
        if len(output_text) > safety_config.max_output_length:
            results.append(SafetyCheckResult(
                is_safe=False,
                risk_level="medium",
                violation_type="length_limit",
                blocked_content=output_text[:50],
                suggestions=[f"输出长度超过限制 ({len(output_text)} > {safety_config.max_output_length})"]
            ))

        # 检查输出格式规范
        result = self._check_output_rules(output_text)
        results.append(result)

        final_result = self._aggregate_check_results(results)

        if not final_result.is_safe:
            self._log_security_event("output_check", output_text[:200], final_result)

        return final_result

    def filter_text(self, text: str, replace_char: str = "*") -> str:
        """
        过滤文本中的敏感内容

        Args:
            text: 原始文本
            replace_char: 替换字符

        Returns:
            过滤后的文本
        """
        filtered_text = text

        # 替换敏感词
        for word in sorted(self.sensitive_words, key=len, reverse=True):
            if word.lower() in filtered_text.lower():
                # 保持原始大小写格式的替换
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                filtered_text = pattern.sub(replace_char * len(word), filtered_text)

        return filtered_text

    def _check_sensitive_words(self, text: str) -> SafetyCheckResult:
        """
        检查敏感词

        Args:
            text: 待检查文本

        Returns:
            检查结果
        """
        found_words = []
        text_lower = text.lower()

        for word in self.sensitive_words:
            # 检查白名单
            if word in self._whitelist:
                continue
            
            # 在文本中查找敏感词
            if word.lower() in text_lower:
                found_words.append(word)

        if found_words:
            # 根据发现的敏感词数量确定风险等级
            risk_level = "high" if len(found_words) >= 3 else ("medium" if len(found_words) >= 2 else "low")
            
            return SafetyCheckResult(
                is_safe=False,
                risk_level=risk_level,
                violation_type="sensitive_word",
                blocked_content=", ".join(found_words),
                filtered_text=self.filter_text(text),
                suggestions=[
                    "请修改您的表述，避免使用不当词汇",
                    "如需帮助，请尝试用其他方式描述您的需求"
                ],
                details={"found_words": found_words}
            )

        return SafetyCheckResult(is_safe=True)

    def _check_injection_attacks(self, text: str) -> SafetyCheckResult:
        """
        检查注入攻击模式

        Args:
            text: 待检查文本

        Returns:
            检查结果
        """
        for pattern, attack_type in self.DANGEROUS_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return SafetyCheckResult(
                    is_safe=False,
                    risk_level="critical",
                    violation_type="injection",
                    blocked_content=match.group(),
                    suggestions=[
                        f"检测到潜在的{attack_type}攻击",
                        "请勿在输入中包含代码或特殊命令"
                    ],
                    details={"attack_type": attack_type}
                )

        return SafetyCheckResult(is_safe=True)

    def _check_pii(self, text: str) -> SafetyCheckResult:
        """
        检查个人信息(PII)

        Args:
            text: 待检查文本

        Returns:
            检查结果
        """
        found_pii = []

        for pattern, pii_type in self.PII_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                # 对匹配到的PII进行脱敏显示
                for match in matches[:3]:  # 最多显示3个
                    masked = match[:3] + "***" + match[-2:] if len(match) > 5 else "***"
                    found_pii.append(f"{pii_type}: {masked}")

        if found_pii:
            return SafetyCheckResult(
                is_safe=False,
                risk_level="medium",
                violation_type="pii_detected",
                blocked_content="; ".join(found_pii),
                suggestions=[
                    "检测到可能的个人隐私信息",
                    "为了保护隐私，请不要在对话中分享敏感个人信息"
                ],
                details={"pii_types": [p[0] for p in found_pii]}
            )

        return SafetyCheckResult(is_safe=True)

    def _check_format(self, text: str) -> SafetyCheckResult:
        """
        检查文本格式

        Args:
            text: 待检查文本

        Returns:
            检查结果
        """
        issues = []

        # 检查是否为空
        if not text or not text.strip():
            issues.append("输入为空")

        # 检查长度
        if len(text) > 50000:  # 单次输入上限
            issues.append("输入过长")

        # 检查是否只包含特殊字符
        if text and all(c in string.punctuation + string.whitespace for c in text):
            issues.append("输入包含无效字符")

        if issues:
            return SafetyCheckResult(
                is_safe=len(issues) < 2,  # 允许轻微问题
                risk_level="low",
                violation_type="format_issue",
                blocked_content="; ".join(issues),
                suggestions=issues
            )

        return SafetyCheckResult(is_safe=True)

    def _check_output_rules(self, text: str) -> SafetyCheckResult:
        """
        检查输出是否符合规范

        Args:
            text: 输出文本

        Returns:
            检查结果
        """
        violations = []

        # 检查基本规则
        rules = safety_config.output_rules
        
        # 示例规则检查（实际应用中可以更复杂）
        if "不得生成违法内容" in rules:
            # 这里可以添加更具体的违法内容检测逻辑
            pass

        if violations:
            return SafetyCheckResult(
                is_safe=False,
                risk_level="low",
                violation_type="output_rule",
                suggestions=violations
            )

        return SafetyCheckResult(is_safe=True)

    def _aggregate_check_results(self, results: List[SafetyCheckResult]) -> SafetyCheckResult:
        """
        聚合多个检查结果

        Args:
            results: 多个检查结果列表

        Returns:
            最终聚合结果
        """
        if not results:
            return SafetyCheckResult(is_safe=True)

        # 找到最严重的结果
        risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        unsafe_results = [r for r in results if not r.is_safe]
        
        if not unsafe_results:
            # 所有检查都通过
            self.stats["passed_count"] += 1
            return SafetyCheckResult(is_safe=True, risk_level="low")
        
        # 选择风险等级最高的结果作为最终结果
        most_severe = max(unsafe_results, key=lambda r: risk_order.get(r.risk_level, 0))
        
        # 合并所有建议
        all_suggestions = []
        for r in unsafe_results:
            all_suggestions.extend(r.suggestions)
        
        most_severe.suggestions = list(set(all_suggestions))  # 去重
        
        # 更新统计
        if most_severe.risk_level in ["high", "critical"]:
            self.stats["blocked_count"] += 1
        else:
            self.stats["warning_count"] += 1

        return most_severe

    def _log_security_event(self, event_type: str, content: str, result: SafetyCheckResult):
        """
        记录安全事件

        Args:
            event_type: 事件类型
            content: 相关内容（截断）
            result: 检查结果
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "is_safe": result.is_safe,
            "risk_level": result.risk_level,
            "violation_type": result.violation_type,
            "content_preview": content[:100] if content else ""
        }
        
        self.security_log.append(event)
        
        # 保留最近1000条日志
        if len(self.security_log) > 1000:
            self.security_log = self.security_log[-1000:]

    def add_to_blacklist(self, word: str):
        """
        添加词汇到黑名单

        Args:
            word: 要添加的词汇
        """
        if word:
            word = word.strip()
            self._blacklist.add(word)
            self.sensitive_words.add(word)
            print(f"🚫 已添加到黑名单: {word}")

    def add_to_whitelist(self, word: str):
        """
        添加词汇到白名单（允许该词汇）

        Args:
            word: 要添加的词汇
        """
        if word:
            word = word.strip()
            self._whitelist.add(word)
            print(f"✅ 已添加到白名单: {word}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取安全统计信息"""
        return {
            **self.stats,
            "sensitive_words_count": len(self.sensitive_words),
            "blacklist_size": len(self._blacklist),
            "whitelist_size": len(self._whitelist),
            "security_events": len(self.security_log),
            "recent_blocked_rate": (
                self.stats["blocked_count"] / self.stats["total_checks"] * 100
                if self.stats["total_checks"] > 0 else 0
            )
        }

    def export_log(self, filepath: str) -> bool:
        """
        导出安全日志

        Args:
            filepath: 导出文件路径

        Returns:
            是否导出成功
        """
        try:
            log_data = {
                "export_time": datetime.now().isoformat(),
                "statistics": self.get_statistics(),
                "events": self.security_log[-100:]  # 最近100条
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 安全日志已导出到: {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ 导出日志失败: {e}")
            return False


if __name__ == "__main__":
    # 测试安全过滤器
    safety_filter = SafetyFilter()

    # 测试用例
    test_cases = [
        ("正常查询天气", "正常输入"),
        ("我想了解一些暴力内容", "包含敏感词"),
        ("SELECT * FROM users; DROP TABLE", "SQL注入"),
        ("我的手机号是13812345678", "包含手机号"),
        ("<script>alert('xss')</script>", "XSS攻击"),
        ("帮我写一封邮件给zhangsan@example.com", "包含邮箱"),
    ]

    print("\n===== 安全过滤测试 =====\n")
    
    for input_text, description in test_cases:
        result = safety_filter.check_input(input_text)
        status = "✓ 通过" if result.is_safe else f"✗ 拦截 [{result.violation_type}]"
        print(f"[{status}] {description}")
        print(f"   输入: {input_text[:40]}...")
        if not result.is_safe:
            print(f"   原因: {result.blocked_content}")
            if result.suggestions:
                print(f"   建议: {result.suggestions[0]}")
        print()

    # 显示统计信息
    stats = safety_filter.get_statistics()
    print("\n安全统计:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
