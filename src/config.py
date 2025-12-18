"""
配置管理模块
"""
import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AWSConfig:
    """AWS配置"""
    profile: str = "oversea1"
    region: str = "us-east-1"
    identity_center_instance_id: str = "ssoins-722353200eb6813f"


@dataclass
class GroupConfig:
    """组配置"""
    kiro: str = "Group_KIRO_eu-central-1"
    qdev: str = "Group_QDEV_eu-central-1"


@dataclass
class UserFormatConfig:
    """用户格式配置"""
    username_template: str = "{employee_id}@haier-saml.com"
    username_suffix: str = "@haier-saml.com"  # 用户名后缀，用于验证和过滤
    use_new_format: bool = True  # 是否使用新的用户属性格式


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file: str = "logs/subscription_manager.log"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    backoff_factor: float = 2.0
    initial_delay: float = 1.0


@dataclass
class TimeoutConfig:
    """超时配置"""
    report_generation: int = 120  # 报告生成超时（秒）
    user_operation: int = 60  # 用户操作超时（秒）


@dataclass
class ValidationConfig:
    """验证配置"""
    max_users_warning: int = 1000  # 用户数量警告阈值
    allowed_email_domains: list = None  # 允许的邮箱域名列表
    organization_name: str = "海尔"  # 组织名称
    
    def __post_init__(self):
        """初始化默认值"""
        if self.allowed_email_domains is None:
            # 默认的海尔域名列表（向后兼容）
            self.allowed_email_domains = [
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


@dataclass
class PerformanceConfig:
    """性能配置"""
    max_workers: int = 5  # 最大并发线程数
    max_workers_min: int = 1  # 最小并发线程数
    max_workers_max: int = 10  # 最大并发线程数
    auto_downgrade: bool = True  # 遇到速率限制自动降级
    show_progress: bool = True  # 显示进度信息
    progress_update_interval: float = 0.5  # 进度更新间隔（秒）


@dataclass
class Config:
    """主配置类"""
    aws: AWSConfig
    groups: GroupConfig
    user_format: UserFormatConfig
    logging: LoggingConfig
    retry: RetryConfig
    performance: PerformanceConfig
    timeouts: TimeoutConfig
    validation: ValidationConfig
    
    def __init__(self):
        self.aws = AWSConfig()
        self.groups = GroupConfig()
        self.user_format = UserFormatConfig()
        self.logging = LoggingConfig()
        self.retry = RetryConfig()
        self.performance = PerformanceConfig()
        self.timeouts = TimeoutConfig()
        self.validation = ValidationConfig()


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config.yaml"
        self.config = Config()
        self._load_config()
        self._apply_env_overrides()
    
    def _load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    self._update_config_from_dict(config_data)
            except Exception as e:
                print(f"警告：无法加载配置文件 {self.config_file}: {e}")
                print("使用默认配置")
    
    def _update_config_from_dict(self, config_data: Dict[str, Any]):
        """从字典更新配置"""
        if 'aws' in config_data:
            aws_config = config_data['aws']
            if 'profile' in aws_config:
                self.config.aws.profile = aws_config['profile']
            if 'region' in aws_config:
                self.config.aws.region = aws_config['region']
            if 'identity_center' in aws_config:
                ic_config = aws_config['identity_center']
                if 'instance_id' in ic_config:
                    self.config.aws.identity_center_instance_id = ic_config['instance_id']
        
        if 'groups' in config_data:
            groups_config = config_data['groups']
            if 'kiro' in groups_config:
                self.config.groups.kiro = groups_config['kiro']
            if 'qdev' in groups_config:
                self.config.groups.qdev = groups_config['qdev']
        
        if 'user_format' in config_data:
            user_format_config = config_data['user_format']
            if 'username_template' in user_format_config:
                self.config.user_format.username_template = user_format_config['username_template']
            if 'username_suffix' in user_format_config:
                self.config.user_format.username_suffix = user_format_config['username_suffix']
            if 'use_new_format' in user_format_config:
                self.config.user_format.use_new_format = user_format_config['use_new_format']
        
        if 'logging' in config_data:
            logging_config = config_data['logging']
            if 'level' in logging_config:
                self.config.logging.level = logging_config['level']
            if 'file' in logging_config:
                self.config.logging.file = logging_config['file']
            if 'format' in logging_config:
                self.config.logging.format = logging_config['format']
        
        if 'retry' in config_data:
            retry_config = config_data['retry']
            if 'max_attempts' in retry_config:
                self.config.retry.max_attempts = retry_config['max_attempts']
            if 'backoff_factor' in retry_config:
                self.config.retry.backoff_factor = retry_config['backoff_factor']
            if 'initial_delay' in retry_config:
                self.config.retry.initial_delay = retry_config['initial_delay']
        
        if 'performance' in config_data:
            perf_config = config_data['performance']
            if 'max_workers' in perf_config:
                self.config.performance.max_workers = perf_config['max_workers']
            if 'max_workers_min' in perf_config:
                self.config.performance.max_workers_min = perf_config['max_workers_min']
            if 'max_workers_max' in perf_config:
                self.config.performance.max_workers_max = perf_config['max_workers_max']
            if 'auto_downgrade' in perf_config:
                self.config.performance.auto_downgrade = perf_config['auto_downgrade']
            if 'show_progress' in perf_config:
                self.config.performance.show_progress = perf_config['show_progress']
            if 'progress_update_interval' in perf_config:
                self.config.performance.progress_update_interval = perf_config['progress_update_interval']
        
        if 'timeouts' in config_data:
            timeout_config = config_data['timeouts']
            if 'report_generation' in timeout_config:
                self.config.timeouts.report_generation = timeout_config['report_generation']
            if 'user_operation' in timeout_config:
                self.config.timeouts.user_operation = timeout_config['user_operation']
        
        if 'validation' in config_data:
            validation_config = config_data['validation']
            if 'max_users_warning' in validation_config:
                self.config.validation.max_users_warning = validation_config['max_users_warning']
            if 'allowed_email_domains' in validation_config:
                self.config.validation.allowed_email_domains = validation_config['allowed_email_domains']
            if 'organization_name' in validation_config:
                self.config.validation.organization_name = validation_config['organization_name']
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # AWS配置环境变量覆盖
        if os.getenv('AWS_PROFILE'):
            self.config.aws.profile = os.getenv('AWS_PROFILE')
        
        if os.getenv('AWS_REGION'):
            self.config.aws.region = os.getenv('AWS_REGION')
        
        if os.getenv('IAM_INSTANCE_ID'):
            self.config.aws.identity_center_instance_id = os.getenv('IAM_INSTANCE_ID')
        
        # 日志配置环境变量覆盖
        if os.getenv('LOG_LEVEL'):
            self.config.logging.level = os.getenv('LOG_LEVEL')
        
        if os.getenv('LOG_FILE'):
            self.config.logging.file = os.getenv('LOG_FILE')
    
    def get_config(self) -> Config:
        """获取配置对象"""
        return self.config
    
    def create_default_config_file(self):
        """创建默认配置文件"""
        default_config = {
            'aws': {
                'profile': 'oversea1',
                'region': 'us-east-1',
                'identity_center': {
                    'instance_id': 'ssoins-722353200eb6813f'
                }
            },
            'groups': {
                'kiro': 'Group_KIRO_eu-central-1',
                'qdev': 'Group_QDEV_eu-central-1'
            },
            'user_format': {
                'username_template': '{employee_id}@your-domain.com',
                'username_suffix': '@your-domain.com',
                'use_new_format': True
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/subscription_manager.log',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'retry': {
                'max_attempts': 3,
                'backoff_factor': 2.0,
                'initial_delay': 1.0
            },
            'performance': {
                'max_workers': 5,
                'max_workers_min': 1,
                'max_workers_max': 10,
                'auto_downgrade': True,
                'show_progress': True,
                'progress_update_interval': 0.5
            },
            'timeouts': {
                'report_generation': 120,
                'user_operation': 60
            },
            'validation': {
                'max_users_warning': 1000,
                'allowed_email_domains': [
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
                ],
                'organization_name': '组织'
            }
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
            print(f"已创建默认配置文件: {self.config_file}")
        except Exception as e:
            print(f"创建配置文件失败: {e}")
    
    def validate_config(self) -> bool:
        """验证配置有效性"""
        errors = []
        
        # 验证AWS配置
        if not self.config.aws.profile:
            errors.append("AWS profile不能为空")
        
        if not self.config.aws.region:
            errors.append("AWS region不能为空")
        
        if not self.config.aws.identity_center_instance_id:
            errors.append("IAM Identity Center实例ID不能为空")
        
        # 验证组配置
        if not self.config.groups.kiro:
            errors.append("KIRO组名不能为空")
        
        if not self.config.groups.qdev:
            errors.append("QDEV组名不能为空")
        
        # 验证重试配置
        if self.config.retry.max_attempts < 1:
            errors.append("最大重试次数必须大于0")
        
        if self.config.retry.backoff_factor < 1.0:
            errors.append("退避因子必须大于等于1.0")
        
        if errors:
            print("配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True