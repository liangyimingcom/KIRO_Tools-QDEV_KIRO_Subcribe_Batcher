"""
数据验证器模块
"""
import re
from typing import List
from src.models import UserSubscription, ValidationResult, SubscriptionType
from src.logger import get_logger


class DataValidator:
    """数据验证器"""
    
    def __init__(self, config=None):
        self.logger = get_logger("data_validator")
        self.config = config
        
        # 邮箱正则表达式
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        
        # 员工号正则表达式（支持数字、字母、下划线、连字符，3-20位）
        self.employee_id_pattern = re.compile(r'^[A-Za-z0-9_-]{3,20}$')
        
        # 有效的订阅类型
        self.valid_subscription_types = {
            SubscriptionType.KIRO.value,
            SubscriptionType.QDEV.value,
            SubscriptionType.ALL.value,
            SubscriptionType.NONE.value
        }
    
    def validate_user_data(self, users) -> ValidationResult:
        """
        验证用户数据完整性
        
        Args:
            users: 用户订阅信息（单个UserSubscription对象或列表）
            
        Returns:
            验证结果
        """
        # 支持单个用户或用户列表
        if isinstance(users, UserSubscription):
            users = [users]
        elif not isinstance(users, list):
            result = ValidationResult(is_valid=False, errors=[], warnings=[])
            result.add_error("输入必须是UserSubscription对象或列表")
            return result
        
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not users:
            result.add_error("用户列表为空")
            return result
        
        # 用于检查重复的集合
        seen_employee_ids = set()
        seen_emails = set()
        
        for i, user in enumerate(users):
            user_prefix = f"用户{i+1}({user.employee_id})"
            
            # 验证员工号
            if not self.validate_employee_id(user.employee_id):
                result.add_error(f"{user_prefix}: 员工号格式无效 '{user.employee_id}'")
            
            # 检查员工号重复
            if user.employee_id in seen_employee_ids:
                result.add_error(f"{user_prefix}: 员工号重复 '{user.employee_id}'")
            else:
                seen_employee_ids.add(user.employee_id)
            
            # 验证姓名
            if not self.validate_name(user.name):
                result.add_error(f"{user_prefix}: 姓名无效 '{user.name}'")
            
            # 验证邮箱
            if not self.validate_email(user.email):
                result.add_error(f"{user_prefix}: 邮箱格式无效 '{user.email}'")
            
            # 检查邮箱重复
            if user.email in seen_emails:
                result.add_warning(f"{user_prefix}: 邮箱重复 '{user.email}'")
            else:
                seen_emails.add(user.email)
            
            # 验证订阅类型
            if not self.validate_subscription_type(user.subscription_type):
                result.add_error(f"{user_prefix}: 订阅类型无效 '{user.subscription_type}'")
            
            # 验证邮箱域名
            if user.email and not self.validate_email_domain(user.email):
                result.add_warning(f"{user_prefix}: 邮箱域名可能不是海尔域名 '{user.email}'")
        
        # 统计信息
        total_users = len(users)
        valid_users = total_users - len([e for e in result.errors if "用户" in e])
        
        # 设置便捷属性
        result.total_count = total_users
        result.valid_count = valid_users
        
        self.logger.log_validation_result("用户数据", total_users, valid_users, result.errors)
        
        return result
    
    def validate_employee_id(self, employee_id: str) -> bool:
        """
        验证员工号格式
        
        Args:
            employee_id: 员工号
            
        Returns:
            是否有效
        """
        if not employee_id:
            return False
        
        # 去除空格
        employee_id = employee_id.strip()
        
        # 使用正则表达式验证格式
        return bool(self.employee_id_pattern.match(employee_id))
    
    def validate_name(self, name: str) -> bool:
        """
        验证姓名
        
        Args:
            name: 姓名
            
        Returns:
            是否有效
        """
        if not name:
            return False
        
        name = name.strip()
        
        # 检查长度
        if len(name) < 1 or len(name) > 30:
            return False
        
        # 检查是否包含中文字符
        #chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        #if not chinese_pattern.search(name):
        #    return False
        
        # 检查是否包含无效字符
        #invalid_chars = ['<', '>', '&', '"', "'", '\\', '/', '|']
        #if any(char in name for char in invalid_chars):
        #    return False
        
        return True
    
    def validate_email(self, email: str) -> bool:
        """
        验证邮箱格式
        
        Args:
            email: 邮箱地址
            
        Returns:
            是否有效
        """
        if not email:
            return False
        
        email = email.strip().lower()
        
        # 基本格式验证
        if not self.email_pattern.match(email):
            return False
        
        # 检查长度
        if len(email) > 254:  # RFC 5321 限制
            return False
        
        # 检查本地部分长度
        local_part = email.split('@')[0]
        if len(local_part) > 64:  # RFC 5321 限制
            return False
        
        return True
    
    def validate_email_domain(self, email: str) -> bool:
        """
        验证邮箱域名是否为海尔域名
        
        Args:
            email: 邮箱地址
            
        Returns:
            是否为海尔域名
        """
        if not email:
            return False
        
        email = email.strip().lower()
        
        # 海尔相关域名
        haier_domains = [
            'haier.com',
            'haier1.com',
            'haier2.com',
            'haier3.com',
            'haier.com.new',
            'haier.com.new1',
            'haier.com.new2',
            'haier.com.new3',
            'haiergroup.com',
            'haier.net',
            'casarte.com',
            'leader.com.cn'
        ]
        
        domain = email.split('@')[1] if '@' in email else ''
        
        return any(domain.endswith(haier_domain) for haier_domain in haier_domains)
    
    def validate_subscription_type(self, subscription_type: str) -> bool:
        """
        验证订阅类型
        
        Args:
            subscription_type: 订阅类型
            
        Returns:
            是否有效
        """
        if not subscription_type:
            return False
        
        subscription_type = subscription_type.strip()
        
        return subscription_type in self.valid_subscription_types
    
    def validate_batch_data(self, users: List[UserSubscription]) -> ValidationResult:
        """
        批量验证用户数据
        
        Args:
            users: 用户订阅信息列表
            
        Returns:
            验证结果
        """
        result = self.validate_user_data(users)
        
        # 获取最大用户警告阈值（从配置或使用默认值）
        max_users_warning = 1000  # 默认值
        if self.config and hasattr(self.config, 'validation'):
            max_users_warning = self.config.validation.max_users_warning
        
        # 额外的批量验证逻辑
        if len(users) > max_users_warning:
            result.add_warning(f"用户数量较多({len(users)})，处理可能需要较长时间")
        
        # 统计订阅类型分布
        subscription_stats = {}
        for user in users:
            subscription_type = user.subscription_type
            subscription_stats[subscription_type] = subscription_stats.get(subscription_type, 0) + 1
        
        # 记录统计信息
        self.logger.info("订阅类型统计:")
        for sub_type, count in subscription_stats.items():
            self.logger.info(f"  {sub_type}: {count}人")
        
        # 检查是否有异常的订阅分布
        total_users = len(users)
        if total_users > 0:
            none_subscription_ratio = subscription_stats.get(SubscriptionType.NONE.value, 0) / total_users
            if none_subscription_ratio > 0.5:
                result.add_warning(f"取消订阅的用户比例较高({none_subscription_ratio:.1%})，请确认数据正确性")
        
        return result
    
    def get_validation_summary(self, result: ValidationResult) -> str:
        """
        获取验证结果摘要
        
        Args:
            result: 验证结果
            
        Returns:
            验证摘要文本
        """
        summary = []
        
        if result.is_valid:
            summary.append("✅ 数据验证通过")
        else:
            summary.append("❌ 数据验证失败")
        
        if result.errors:
            summary.append(f"错误数量: {len(result.errors)}")
            summary.append("主要错误:")
            for error in result.errors[:3]:  # 只显示前3个错误
                summary.append(f"  - {error}")
            if len(result.errors) > 3:
                summary.append(f"  - 还有{len(result.errors) - 3}个错误...")
        
        if result.warnings:
            summary.append(f"警告数量: {len(result.warnings)}")
            summary.append("主要警告:")
            for warning in result.warnings[:3]:  # 只显示前3个警告
                summary.append(f"  - {warning}")
            if len(result.warnings) > 3:
                summary.append(f"  - 还有{len(result.warnings) - 3}个警告...")
        
        return "\n".join(summary)
    
    def fix_common_issues(self, users: List[UserSubscription]) -> List[UserSubscription]:
        """
        修复常见的数据问题
        
        Args:
            users: 用户订阅信息列表
            
        Returns:
            修复后的用户列表
        """
        fixed_users = []
        
        for user in users:
            # 创建用户副本
            fixed_user = UserSubscription(
                employee_id=user.employee_id.strip() if user.employee_id else "",
                name=user.name.strip() if user.name else "",
                email=user.email.strip().lower() if user.email else "",
                subscription_type=user.subscription_type.strip() if user.subscription_type else ""
            )
            
            # 修复订阅类型的常见错误
            subscription_fixes = {
                "kiro订阅": SubscriptionType.KIRO.value,
                "KIRO": SubscriptionType.KIRO.value,
                "qdev订阅": SubscriptionType.QDEV.value,
                "QDEV": SubscriptionType.QDEV.value,
                "全部": SubscriptionType.ALL.value,
                "全订阅": SubscriptionType.ALL.value,
                "取消": SubscriptionType.NONE.value,
                "不订阅": SubscriptionType.NONE.value,
                "无": SubscriptionType.NONE.value
            }
            
            if fixed_user.subscription_type in subscription_fixes:
                fixed_user.subscription_type = subscription_fixes[fixed_user.subscription_type]
                self.logger.info(f"修复订阅类型: {user.subscription_type} -> {fixed_user.subscription_type}")
            
            fixed_users.append(fixed_user)
        
        return fixed_users