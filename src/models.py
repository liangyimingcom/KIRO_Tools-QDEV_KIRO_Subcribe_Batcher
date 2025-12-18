"""
核心数据模型定义
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


class SubscriptionType(Enum):
    """订阅类型枚举"""
    KIRO = "KIRO订阅"
    QDEV = "QDEV订阅"
    ALL = "全部订阅"
    NONE = "取消订阅/不订阅"


class OperationType(Enum):
    """操作类型枚举"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ADD_TO_GROUP = "ADD_TO_GROUP"
    REMOVE_FROM_GROUP = "REMOVE_FROM_GROUP"


@dataclass
class UserSubscription:
    """用户订阅信息"""
    employee_id: str
    name: str
    email: str
    subscription_type: str
    _config: Optional[object] = None  # 配置对象（可选）
    
    def set_config(self, config):
        """设置配置对象"""
        self._config = config
    
    def get_username(self) -> str:
        """获取IAM Identity Center用户名"""
        if self._config and hasattr(self._config, 'user_format'):
            # 使用配置中的模板
            template = self._config.user_format.username_template
            return template.format(employee_id=self.employee_id)
        # 默认格式（向后兼容）
        return f"{self.employee_id}@haier-saml.com"
    
    def get_target_groups(self) -> List[str]:
        """根据订阅类型获取目标组列表"""
        # 获取组名（从配置或使用默认值）
        if self._config and hasattr(self._config, 'groups'):
            kiro_group = self._config.groups.kiro
            qdev_group = self._config.groups.qdev
        else:
            # 默认组名（向后兼容）
            kiro_group = "Group_KIRO_eu-central-1"
            qdev_group = "Group_QDEV_eu-central-1"
        
        if self.subscription_type == SubscriptionType.KIRO.value:
            return [kiro_group]
        elif self.subscription_type == SubscriptionType.QDEV.value:
            return [qdev_group]
        elif self.subscription_type == SubscriptionType.ALL.value:
            return [kiro_group, qdev_group]
        else:  # NONE
            return []
    
    def should_be_in_group(self, group_name: str) -> bool:
        """判断用户是否应该在指定组中"""
        return group_name in self.get_target_groups()


@dataclass
class IAMUser:
    """IAM Identity Center用户信息"""
    user_id: str
    username: str
    email: str
    first_name: str
    last_name: str
    display_name: str
    groups: List[str]
    
    def __post_init__(self):
        if self.groups is None:
            self.groups = []


@dataclass
class FailedUserRecord:
    """失败用户记录"""
    username: str
    operation_type: str  # CREATE, UPDATE, DELETE, ADD_TO_GROUP, REMOVE_FROM_GROUP
    error_message: str
    error_code: str  # 错误代码
    timestamp: datetime
    retry_count: int  # 重试次数
    suggested_fix: str  # 建议的修复措施
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class OperationResult:
    """操作结果"""
    operation_type: str
    target: str  # 用户名或组名
    success: bool
    message: str
    timestamp: datetime
    details: Optional[Dict] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class GroupVerification:
    """组验证结果"""
    group_name: str
    expected_members: List[str]
    actual_members: List[str]
    missing_members: List[str]
    extra_members: List[str]
    is_consistent: bool


@dataclass
class VerificationResult:
    """校验结果"""
    total_users: int
    matched_users: int
    mismatched_users: List[str]
    group_verification: Dict[str, GroupVerification]
    consistency_rate: float
    
    def __post_init__(self):
        if self.mismatched_users is None:
            self.mismatched_users = []
        if self.group_verification is None:
            self.group_verification = {}


@dataclass
class BatchResult:
    """批量操作结果"""
    total_operations: int
    successful_operations: int
    failed_operations: int
    operation_results: List[OperationResult]
    
    def __post_init__(self):
        if self.operation_results is None:
            self.operation_results = []
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations


@dataclass
class ValidationResult:
    """数据验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    valid_count: int = 0  # 有效记录数
    total_count: int = 0  # 总记录数
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)
    
    @property
    def error_count(self) -> int:
        """错误数量"""
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        """警告数量"""
        return len(self.warnings)
    
    @property
    def invalid_count(self) -> int:
        """无效记录数"""
        return self.total_count - self.valid_count if self.total_count > 0 else 0


@dataclass
class ComparisonResult:
    """对比结果"""
    csv_users_count: int
    iam_users_count: int
    matched_count: int
    new_users: List[str]
    updated_users: List[str]
    missing_users: List[str]
    
    def __post_init__(self):
        if self.new_users is None:
            self.new_users = []
        if self.updated_users is None:
            self.updated_users = []
        if self.missing_users is None:
            self.missing_users = []


@dataclass
class UserUpdateData:
    """用户更新数据"""
    user_id: str
    username: str
    operations: List[Dict]  # AWS API operations
    old_attributes: Dict
    new_attributes: Dict
    
    def __post_init__(self):
        if self.operations is None:
            self.operations = []
        if self.old_attributes is None:
            self.old_attributes = {}
        if self.new_attributes is None:
            self.new_attributes = {}
    
    def get_single_value_operations(self) -> List[Dict]:
        """返回单值属性更新操作"""
        single_value_ops = []
        for op in self.operations:
            attr_path = op.get("AttributePath", "")
            # 多值属性不包含索引路径
            if not any(mv_attr in attr_path for mv_attr in ["emails", "phoneNumbers", "addresses"]):
                single_value_ops.append(op)
        return single_value_ops
    
    def get_multi_value_operations(self) -> List[Dict]:
        """返回多值属性更新操作"""
        multi_value_ops = []
        for op in self.operations:
            attr_path = op.get("AttributePath", "")
            # 多值属性包含这些路径
            if any(mv_attr in attr_path for mv_attr in ["emails", "phoneNumbers", "addresses"]):
                multi_value_ops.append(op)
        return multi_value_ops


@dataclass
class UpgradePlan:
    """升级计划"""
    users_to_upgrade: List[tuple]  # List[Tuple[IAMUser, UserSubscription]]
    total_operations: int
    estimated_time: int  # 预估执行时间（秒）
    
    def __post_init__(self):
        if self.users_to_upgrade is None:
            self.users_to_upgrade = []
    
    def get_preview(self) -> str:
        """返回升级计划的预览文本"""
        preview = f"升级计划预览:\n"
        preview += f"  待升级用户数: {len(self.users_to_upgrade)}\n"
        preview += f"  总操作数: {self.total_operations}\n"
        preview += f"  预估时间: {self.estimated_time}秒\n\n"
        
        if self.users_to_upgrade:
            preview += "用户列表:\n"
            for i, (iam_user, csv_user) in enumerate(self.users_to_upgrade[:5]):
                preview += f"  {i+1}. {iam_user.username} -> {csv_user.get_username()}\n"
            
            if len(self.users_to_upgrade) > 5:
                preview += f"  ... 还有{len(self.users_to_upgrade) - 5}个用户\n"
        
        return preview


@dataclass
class UpgradeResult:
    """升级结果"""
    total_users: int
    successful_upgrades: int
    failed_upgrades: int
    upgrade_operations: List[OperationResult]
    upgrade_plan: Optional[UpgradePlan] = None
    
    def __post_init__(self):
        if self.upgrade_operations is None:
            self.upgrade_operations = []
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.successful_upgrades / self.total_users if self.total_users > 0 else 0.0