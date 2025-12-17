"""
用户管理器模块
"""
from typing import List, Dict, Optional
from datetime import datetime
import threading
import concurrent.futures
from src.models import (
    UserSubscription, IAMUser, OperationResult, BatchResult, 
    OperationType
)
from src.aws_client import AWSClient, AWSClientError
from src.logger import get_logger
from src.data_cache import DataCache
from src.progress_tracker import ProgressTracker
from src.performance_metrics import PerformanceMetrics


class UserManager:
    """用户管理器"""
    
    def __init__(self, aws_client: AWSClient, config=None):
        self.aws_client = aws_client
        self.config = config
        self.logger = get_logger("user_manager")
        self.failed_users = []  # 存储失败用户记录
    
    def _extract_error_code(self, error: Exception) -> str:
        """
        从异常中提取错误代码
        
        Args:
            error: 异常对象
            
        Returns:
            错误代码字符串
        """
        error_str = str(error)
        # 尝试从AWSClientError中提取错误代码
        if "AWS API调用失败:" in error_str:
            parts = error_str.split(":")
            if len(parts) >= 2:
                return parts[1].strip().split("-")[0].strip()
        return "UNKNOWN_ERROR"
    
    def _suggest_fix(self, error: Exception) -> str:
        """
        根据错误类型生成修复建议
        
        Args:
            error: 异常对象
            
        Returns:
            修复建议字符串
        """
        error_str = str(error).lower()
        
        if "throttling" in error_str or "rate limit" in error_str:
            return "遇到AWS API速率限制，建议降低并发数或增加重试间隔"
        elif "validation" in error_str:
            return "数据验证失败，请检查用户数据格式是否正确"
        elif "conflict" in error_str:
            return "资源冲突，用户可能已存在或正在被其他操作修改"
        elif "access denied" in error_str or "permission" in error_str:
            return "权限不足，请检查AWS IAM权限配置"
        elif "not found" in error_str:
            return "资源不存在，用户或组可能已被删除"
        else:
            return "请检查错误日志获取详细信息，必要时联系管理员"
    
    def record_failed_user(self, user: UserSubscription, operation_type: str, 
                          error: Exception, retry_count: int = 0):
        """
        记录失败用户信息
        
        Args:
            user: 用户订阅信息
            operation_type: 操作类型（CREATE, UPDATE, DELETE等）
            error: 错误异常
            retry_count: 重试次数
        """
        from src.models import FailedUserRecord
        from datetime import datetime
        
        failed_record = FailedUserRecord(
            username=user.get_username(),
            operation_type=operation_type,
            error_message=str(error),
            error_code=self._extract_error_code(error),
            timestamp=datetime.now(),
            retry_count=retry_count,
            suggested_fix=self._suggest_fix(error)
        )
        
        self.failed_users.append(failed_record)
        self.logger.error(f"记录失败用户: {failed_record.username} - {failed_record.error_code}: {failed_record.error_message}")
    
    def get_failed_users(self):
        """获取失败用户列表"""
        return self.failed_users.copy()
    
    def clear_failed_users(self):
        """清空失败用户列表"""
        self.failed_users.clear()
    
    def _should_use_new_format(self) -> bool:
        """判断是否应该使用新的用户属性格式"""
        if self.config and hasattr(self.config, 'user_format'):
            return getattr(self.config.user_format, 'use_new_format', True)
        return True  # 默认使用新格式
    
    def get_existing_users(self, use_cache: bool = True) -> List[IAMUser]:
        """
        获取现有用户列表
        
        优化说明：
        - 使用DataCache批量获取所有数据，大幅减少API调用
        - 优化前：1 + N + N×M次API调用（N=用户数，M=组数）
        - 优化后：2 + M次API调用
        
        Args:
            use_cache: 是否使用缓存（默认True）
            
        Returns:
            IAM用户列表
        """
        try:
            if use_cache:
                # 使用DataCache批量获取
                cache = DataCache()
                cache.initialize(self.aws_client)
                iam_users = cache.get_all_users()
                self.logger.info(f"从缓存获取到{len(iam_users)}个现有用户")
                return iam_users
            else:
                # 保留原有逻辑作为备用（不推荐使用）
                self.logger.warning("使用旧的串行获取方式（性能较差）")
                aws_users = self.aws_client.list_users()
                iam_users = []
                
                for aws_user in aws_users:
                    # 获取用户的组成员关系
                    user_id = aws_user.get('UserId')
                    group_memberships = self.aws_client.get_user_group_memberships(user_id)
                    
                    # 提取组名列表
                    groups = []
                    for membership in group_memberships:
                        group_id = membership.get('GroupId')
                        if group_id:
                            # 获取组信息来得到组名
                            all_groups = self.aws_client.list_groups()
                            for group in all_groups:
                                if group.get('GroupId') == group_id:
                                    groups.append(group.get('DisplayName', ''))
                                    break
                    
                    # 提取用户信息
                    name_info = aws_user.get('Name', {})
                    emails = aws_user.get('Emails', [])
                    primary_email = ""
                    
                    for email in emails:
                        if email.get('Primary', False):
                            primary_email = email.get('Value', '')
                            break
                    
                    iam_user = IAMUser(
                        user_id=user_id,
                        username=aws_user.get('UserName', ''),
                        email=primary_email,
                        first_name=name_info.get('GivenName', ''),
                        last_name=name_info.get('FamilyName', ''),
                        display_name=aws_user.get('DisplayName', ''),
                        groups=groups
                    )
                    
                    iam_users.append(iam_user)
                
                self.logger.info(f"获取到{len(iam_users)}个现有用户")
                return iam_users
            
        except Exception as e:
            self.logger.error(f"获取现有用户失败: {e}")
            raise
    
    def create_user(self, user_data: UserSubscription) -> OperationResult:
        """
        创建用户
        
        Args:
            user_data: 用户订阅信息
            
        Returns:
            操作结果
        """
        try:
            username = user_data.get_username()
            
            # 检查用户是否已存在
            existing_user = self.aws_client.get_user_by_username(username)
            if existing_user:
                message = f"用户已存在: {username}"
                self.logger.warning(message)
                return OperationResult(
                    operation_type=OperationType.CREATE.value,
                    target=username,
                    success=False,
                    message=message,
                    timestamp=datetime.now()
                )
            
            # 构建用户数据（根据配置选择格式）
            if self._should_use_new_format():
                # 新格式：工号@haier-saml.com, 工号_中文姓名
                aws_user_data = {
                    'UserName': username,  # 工号@haier-saml.com
                    'DisplayName': f"{user_data.employee_id}_{user_data.name}",  # 工号_中文姓名
                    'Name': {
                        'GivenName': user_data.employee_id,  # 工号
                        'FamilyName': user_data.name  # 中文姓名
                    },
                    'Emails': [{
                        'Value': user_data.email,
                        'Primary': True,
                        'Type': 'work'
                    }]
                }
            else:
                # 旧格式：保持向后兼容
                aws_user_data = {
                    'UserName': username,
                    'DisplayName': f"{user_data.name} {user_data.name}",
                    'Name': {
                        'GivenName': user_data.name,
                        'FamilyName': user_data.name
                    },
                    'Emails': [{
                        'Value': user_data.email,
                        'Primary': True
                    }]
                }
            
            # 创建用户
            result = self.aws_client.create_user(aws_user_data)
            user_id = result.get('UserId')
            
            message = f"用户创建成功: {username} (ID: {user_id})"
            self.logger.log_user_operation(username, "创建", True, message)
            
            return OperationResult(
                operation_type=OperationType.CREATE.value,
                target=username,
                success=True,
                message=message,
                timestamp=datetime.now(),
                details={'user_id': user_id}
            )
            
        except Exception as e:
            message = f"用户创建失败: {user_data.get_username()} - {e}"
            self.logger.log_user_operation(user_data.get_username(), "创建", False, str(e))
            
            return OperationResult(
                operation_type=OperationType.CREATE.value,
                target=user_data.get_username(),
                success=False,
                message=message,
                timestamp=datetime.now()
            )
    
    def update_user(self, user_data: UserSubscription) -> OperationResult:
        """
        更新用户信息
        
        Args:
            user_data: 用户订阅信息
            
        Returns:
            操作结果
        """
        try:
            username = user_data.get_username()
            
            # 获取现有用户信息
            existing_user = self.aws_client.get_user_by_username(username)
            if not existing_user:
                message = f"用户不存在，无法更新: {username}"
                self.logger.warning(message)
                return OperationResult(
                    operation_type=OperationType.UPDATE.value,
                    target=username,
                    success=False,
                    message=message,
                    timestamp=datetime.now()
                )
            
            user_id = existing_user.get('UserId')
            
            # 检查是否需要更新
            current_display_name = existing_user.get('DisplayName', '')
            current_name = existing_user.get('Name', {})
            current_first_name = current_name.get('GivenName', '')
            current_last_name = current_name.get('FamilyName', '')
            current_emails = existing_user.get('Emails', [])
            current_primary_email = ""
            
            for email in current_emails:
                if email.get('Primary', False):
                    current_primary_email = email.get('Value', '')
                    break
            
            # 根据配置选择属性格式
            if self._should_use_new_format():
                # 新格式
                new_display_name = f"{user_data.employee_id}_{user_data.name}"
                new_first_name = user_data.employee_id  # 工号
                new_last_name = user_data.name  # 中文姓名
            else:
                # 旧格式
                new_display_name = f"{user_data.name} {user_data.name}"
                new_first_name = user_data.name
                new_last_name = user_data.name
            
            updates_needed = []
            
            # 使用operations方式更新，支持复杂的属性更新
            operations = []
            
            # 检查显示名称是否需要更新
            if current_display_name != new_display_name:
                operations.append({
                    'AttributePath': 'displayName',
                    'AttributeValue': new_display_name
                })
                updates_needed.append(f"显示名称: {current_display_name} -> {new_display_name}")
            
            # 检查First name是否需要更新
            if current_first_name != new_first_name:
                operations.append({
                    'AttributePath': 'name.givenName',
                    'AttributeValue': new_first_name
                })
                updates_needed.append(f"First name: {current_first_name} -> {new_first_name}")
            
            # 检查Last name是否需要更新
            if current_last_name != new_last_name:
                operations.append({
                    'AttributePath': 'name.familyName',
                    'AttributeValue': new_last_name
                })
                updates_needed.append(f"Last name: {current_last_name} -> {new_last_name}")
            
            # 检查邮箱是否需要更新（多值属性）
            if current_primary_email != user_data.email:
                operations.append({
                    'AttributePath': 'emails',
                    'AttributeValue': [{
                        'Value': user_data.email,
                        'Primary': True,
                        'Type': 'work'
                    }]
                })
                updates_needed.append(f"邮箱: {current_primary_email} -> {user_data.email}")
            
            # 如果没有需要更新的内容
            if not updates_needed:
                message = f"用户信息无需更新: {username}"
                self.logger.info(message)
                return OperationResult(
                    operation_type=OperationType.UPDATE.value,
                    target=username,
                    success=True,
                    message=message,
                    timestamp=datetime.now()
                )
            
            # 执行更新（使用operations方式支持复杂更新）
            self.aws_client.update_user_with_operations(user_id, operations)
            
            message = f"用户更新成功: {username} - {', '.join(updates_needed)}"
            self.logger.log_user_operation(username, "更新", True, message)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=username,
                success=True,
                message=message,
                timestamp=datetime.now(),
                details={'updates': updates_needed}
            )
            
        except Exception as e:
            message = f"用户更新失败: {user_data.get_username()} - {e}"
            self.logger.log_user_operation(user_data.get_username(), "更新", False, str(e))
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=user_data.get_username(),
                success=False,
                message=message,
                timestamp=datetime.now()
            )
    
    def batch_process_users(self, users: List[UserSubscription]) -> BatchResult:
        """
        批量处理用户
        
        Args:
            users: 用户订阅信息列表
            
        Returns:
            批量操作结果
        """
        operation_results = []
        successful_operations = 0
        failed_operations = 0
        
        self.logger.info(f"开始批量处理{len(users)}个用户")
        
        # 获取现有用户列表用于检查
        try:
            existing_users = self.get_existing_users()
            existing_usernames = {user.username for user in existing_users}
        except Exception as e:
            self.logger.error(f"获取现有用户列表失败: {e}")
            existing_usernames = set()
        
        for i, user in enumerate(users, 1):
            self.logger.info(f"处理用户 {i}/{len(users)}: {user.get_username()}")
            
            try:
                username = user.get_username()
                
                if username in existing_usernames:
                    # 用户已存在，执行更新
                    result = self.update_user(user)
                else:
                    # 用户不存在，执行创建
                    result = self.create_user(user)
                
                operation_results.append(result)
                
                if result.success:
                    successful_operations += 1
                else:
                    failed_operations += 1
                    
            except Exception as e:
                # 处理单个用户时的异常
                error_result = OperationResult(
                    operation_type="PROCESS",
                    target=user.get_username(),
                    success=False,
                    message=f"处理用户时发生异常: {e}",
                    timestamp=datetime.now()
                )
                operation_results.append(error_result)
                failed_operations += 1
                
                self.logger.error(f"处理用户{user.get_username()}时发生异常: {e}")
        
        batch_result = BatchResult(
            total_operations=len(users),
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            operation_results=operation_results
        )
        
        self.logger.info(f"批量处理完成: 总数{batch_result.total_operations}, "
                        f"成功{batch_result.successful_operations}, "
                        f"失败{batch_result.failed_operations}, "
                        f"成功率{batch_result.success_rate:.1%}")
        
        return batch_result
    
    def batch_process_users_concurrent(self, users: List[UserSubscription], 
                                      max_workers: int = 5,
                                      show_progress: bool = True,
                                      performance_metrics: PerformanceMetrics = None) -> BatchResult:
        """
        并发批量处理用户（优化版本）
        
        Args:
            users: 用户订阅信息列表
            max_workers: 最大并发线程数（默认5）
            show_progress: 是否显示进度
            performance_metrics: 性能指标收集器
            
        Returns:
            批量操作结果
        """
        operation_results = []
        successful_operations = 0
        failed_operations = 0
        
        self.logger.info(f"开始并发批量处理{len(users)}个用户，线程数: {max_workers}")
        
        # 获取现有用户列表用于检查
        try:
            existing_users = self.get_existing_users()
            existing_usernames = {user.username for user in existing_users}
        except Exception as e:
            self.logger.error(f"获取现有用户列表失败: {e}")
            existing_usernames = set()
        
        # 创建进度跟踪器
        progress_tracker = ProgressTracker(len(users), "用户处理", show_progress, self.config) if show_progress else None
        
        # 速率限制标志
        rate_limit_event = threading.Event()
        results_lock = threading.Lock()
        
        def process_single_user(user: UserSubscription) -> OperationResult:
            """处理单个用户（线程安全）"""
            try:
                # 检查速率限制标志
                if rate_limit_event.is_set():
                    import time
                    time.sleep(1)  # 降级后添加延迟
                
                username = user.get_username()
                
                if username in existing_usernames:
                    result = self.update_user(user)
                else:
                    result = self.create_user(user)
                
                # 记录性能指标
                if performance_metrics:
                    op_type = 'update' if username in existing_usernames else 'create'
                    performance_metrics.record_operation(op_type, result.success)
                
                return result
                
            except AWSClientError as e:
                # 检查是否为速率限制错误
                if self._is_rate_limit_error(e):
                    self.logger.warning(f"检测到速率限制错误: {e}")
                    rate_limit_event.set()  # 触发降级
                    raise
                else:
                    error_result = OperationResult(
                        operation_type="PROCESS",
                        target=user.get_username(),
                        success=False,
                        message=f"AWS错误: {e}",
                        timestamp=datetime.now()
                    )
                    if performance_metrics:
                        performance_metrics.record_operation('create', False)
                    return error_result
            
            except Exception as e:
                self.logger.error(f"处理用户{user.get_username()}时发生异常: {e}")
                error_result = OperationResult(
                    operation_type="PROCESS",
                    target=user.get_username(),
                    success=False,
                    message=f"处理用户时发生异常: {e}",
                    timestamp=datetime.now()
                )
                if performance_metrics:
                    performance_metrics.record_operation('create', False)
                return error_result
        
        # 使用ThreadPoolExecutor并发处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = []
            for user in users:
                if rate_limit_event.is_set():
                    # 检测到速率限制，停止提交新任务
                    self.logger.warning("检测到速率限制，停止提交新任务，切换到串行模式")
                    break
                future = executor.submit(process_single_user, user)
                futures.append((future, user))
            
            # 收集已提交任务的结果
            for future, user in futures:
                try:
                    # 使用配置中的超时时间
                    timeout = 60  # 默认值
                    if self.config and hasattr(self.config, 'timeouts'):
                        timeout = self.config.timeouts.user_operation
                    
                    result = future.result(timeout=timeout)
                    with results_lock:
                        operation_results.append(result)
                        if result.success:
                            successful_operations += 1
                        else:
                            failed_operations += 1
                    
                    if progress_tracker:
                        progress_tracker.update()
                
                except concurrent.futures.TimeoutError:
                    self.logger.error(f"处理用户{user.get_username()}超时")
                    error_result = OperationResult(
                        operation_type="PROCESS",
                        target=user.get_username(),
                        success=False,
                        message="处理超时",
                        timestamp=datetime.now()
                    )
                    with results_lock:
                        operation_results.append(error_result)
                        failed_operations += 1
                    
                    if progress_tracker:
                        progress_tracker.update()
                
                except Exception as e:
                    self.logger.error(f"获取用户{user.get_username()}处理结果失败: {e}")
                    if rate_limit_event.is_set():
                        # 速率限制错误，跳出循环
                        break
        
        # 如果触发了速率限制，串行处理剩余用户
        if rate_limit_event.is_set():
            remaining_users = users[len(operation_results):]
            if remaining_users:
                self.logger.info(f"串行处理剩余{len(remaining_users)}个用户")
                for user in remaining_users:
                    try:
                        result = process_single_user(user)
                        operation_results.append(result)
                        if result.success:
                            successful_operations += 1
                        else:
                            failed_operations += 1
                        
                        if progress_tracker:
                            progress_tracker.update()
                    
                    except Exception as e:
                        self.logger.error(f"串行处理用户{user.get_username()}失败: {e}")
                        error_result = OperationResult(
                            operation_type="PROCESS",
                            target=user.get_username(),
                            success=False,
                            message=f"串行处理失败: {e}",
                            timestamp=datetime.now()
                        )
                        operation_results.append(error_result)
                        failed_operations += 1
                        
                        if progress_tracker:
                            progress_tracker.update()
        
        # 完成进度显示
        if progress_tracker:
            progress_tracker.finish()
        
        batch_result = BatchResult(
            total_operations=len(users),
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            operation_results=operation_results
        )
        
        self.logger.info(f"并发批量处理完成: 总数{batch_result.total_operations}, "
                        f"成功{batch_result.successful_operations}, "
                        f"失败{batch_result.failed_operations}, "
                        f"成功率{batch_result.success_rate:.1%}")
        
        return batch_result
    
    def _is_rate_limit_error(self, exception: Exception) -> bool:
        """
        检测是否为速率限制错误
        
        Args:
            exception: 异常对象
            
        Returns:
            True如果是速率限制错误，否则False
        """
        error_codes = ['ThrottlingException', 'TooManyRequestsException', 'RequestLimitExceeded']
        if isinstance(exception, AWSClientError):
            error_str = str(exception)
            return any(code in error_str for code in error_codes)
        return False
    
    def find_user_by_employee_id(self, employee_id: str) -> Optional[IAMUser]:
        """
        根据员工号查找用户
        
        Args:
            employee_id: 员工号
            
        Returns:
            IAM用户信息，如果不存在返回None
        """
        username = f"{employee_id}@haier-saml.com"
        
        try:
            aws_user = self.aws_client.get_user_by_username(username)
            if not aws_user:
                return None
            
            # 转换为IAMUser对象
            user_id = aws_user.get('UserId')
            group_memberships = self.aws_client.get_user_group_memberships(user_id)
            
            groups = []
            for membership in group_memberships:
                group_id = membership.get('GroupId')
                if group_id:
                    all_groups = self.aws_client.list_groups()
                    for group in all_groups:
                        if group.get('GroupId') == group_id:
                            groups.append(group.get('DisplayName', ''))
                            break
            
            name_info = aws_user.get('Name', {})
            emails = aws_user.get('Emails', [])
            primary_email = ""
            
            for email in emails:
                if email.get('Primary', False):
                    primary_email = email.get('Value', '')
                    break
            
            return IAMUser(
                user_id=user_id,
                username=username,
                email=primary_email,
                first_name=name_info.get('GivenName', ''),
                last_name=name_info.get('FamilyName', ''),
                display_name=aws_user.get('DisplayName', ''),
                groups=groups
            )
            
        except Exception as e:
            self.logger.error(f"查找用户失败: {employee_id} - {e}")
            return None
    
    def get_user_statistics(self) -> Dict:
        """
        获取用户统计信息
        
        Returns:
            用户统计信息
        """
        try:
            users = self.get_existing_users()
            
            stats = {
                'total_users': len(users),
                'users_with_groups': 0,
                'users_without_groups': 0,
                'group_distribution': {},
                'email_domains': {}
            }
            
            for user in users:
                # 统计有组和无组的用户
                if user.groups:
                    stats['users_with_groups'] += 1
                    
                    # 统计组分布
                    for group in user.groups:
                        stats['group_distribution'][group] = stats['group_distribution'].get(group, 0) + 1
                else:
                    stats['users_without_groups'] += 1
                
                # 统计邮箱域名分布
                if user.email and '@' in user.email:
                    domain = user.email.split('@')[1]
                    stats['email_domains'][domain] = stats['email_domains'].get(domain, 0) + 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取用户统计信息失败: {e}")
            return {
                'total_users': 0,
                'users_with_groups': 0,
                'users_without_groups': 0,
                'group_distribution': {},
                'email_domains': {},
                'error': str(e)
            }
    
    def validate_user_format(self, user_data: UserSubscription) -> List[str]:
        """
        验证用户数据格式
        
        Args:
            user_data: 用户订阅信息
            
        Returns:
            验证错误列表
        """
        errors = []
        
        # 验证员工号格式
        if not user_data.employee_id:
            errors.append("员工号不能为空")
        elif len(user_data.employee_id) < 6 or len(user_data.employee_id) > 10:
            errors.append("员工号长度必须在6-10位之间")
        elif not (user_data.employee_id.isdigit() or 
                 (user_data.employee_id.isalnum() and any(c.isdigit() for c in user_data.employee_id))):
            errors.append("员工号必须为数字或字母数字组合")
        
        # 验证姓名
        if not user_data.name or len(user_data.name.strip()) < 2:
            errors.append("姓名不能为空且至少2个字符")
        
        # 验证邮箱格式
        if not user_data.email or '@' not in user_data.email:
            errors.append("邮箱格式无效")
        
        # 验证用户名格式
        username = user_data.get_username()
        if not username.endswith('@haier-saml.com'):
            errors.append("用户名格式错误，应为员工号@haier-saml.com")
        
        return errors
    
    def delete_user(self, user_data: UserSubscription) -> OperationResult:
        """
        删除用户
        
        Args:
            user_data: 用户订阅信息
            
        Returns:
            操作结果
        """
        try:
            username = user_data.get_username()
            
            # 获取用户信息
            existing_user = self.aws_client.get_user_by_username(username)
            if not existing_user:
                message = f"用户不存在，无法删除: {username}"
                self.logger.warning(message)
                return OperationResult(
                    operation_type=OperationType.DELETE.value,
                    target=username,
                    success=False,
                    message=message,
                    timestamp=datetime.now()
                )
            
            user_id = existing_user.get('UserId')
            
            # 先从所有组中移除用户
            try:
                memberships = self.aws_client.get_user_group_memberships(user_id)
                for membership in memberships:
                    membership_id = membership.get('MembershipId')
                    if membership_id:
                        self.aws_client.remove_user_from_group(membership_id)
                        self.logger.info(f"用户{username}已从组中移除")
            except Exception as e:
                self.logger.warning(f"移除用户组成员关系时出错: {e}")
            
            # 删除用户
            self.aws_client.delete_user(user_id)
            
            message = f"用户删除成功: {username} (ID: {user_id})"
            self.logger.log_user_operation(username, "删除", True, message)
            
            return OperationResult(
                operation_type=OperationType.DELETE.value,
                target=username,
                success=True,
                message=message,
                timestamp=datetime.now(),
                details={'user_id': user_id}
            )
            
        except Exception as e:
            message = f"用户删除失败: {user_data.get_username()} - {e}"
            self.logger.log_user_operation(user_data.get_username(), "删除", False, str(e))
            
            return OperationResult(
                operation_type=OperationType.DELETE.value,
                target=user_data.get_username(),
                success=False,
                message=message,
                timestamp=datetime.now()
            )
    
    def batch_delete_users(self, users: List[UserSubscription]) -> BatchResult:
        """
        批量删除用户
        
        Args:
            users: 用户订阅信息列表
            
        Returns:
            批量操作结果
        """
        operation_results = []
        successful_operations = 0
        failed_operations = 0
        
        self.logger.info(f"开始批量删除{len(users)}个用户")
        
        for i, user in enumerate(users, 1):
            self.logger.info(f"删除用户 {i}/{len(users)}: {user.get_username()}")
            
            try:
                result = self.delete_user(user)
                operation_results.append(result)
                
                if result.success:
                    successful_operations += 1
                else:
                    failed_operations += 1
                    
            except Exception as e:
                error_result = OperationResult(
                    operation_type=OperationType.DELETE.value,
                    target=user.get_username(),
                    success=False,
                    message=f"删除用户时发生异常: {e}",
                    timestamp=datetime.now()
                )
                operation_results.append(error_result)
                failed_operations += 1
                
                self.logger.error(f"删除用户{user.get_username()}时发生异常: {e}")
        
        batch_result = BatchResult(
            total_operations=len(users),
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            operation_results=operation_results
        )
        
        self.logger.info(f"批量删除完成: 总数{batch_result.total_operations}, "
                        f"成功{batch_result.successful_operations}, "
                        f"失败{batch_result.failed_operations}, "
                        f"成功率{batch_result.success_rate:.1%}")
        
        return batch_result
    
    def _is_rate_limit_error(self, exception: Exception) -> bool:
        """
        检测是否为速率限制错误
        
        Args:
            exception: 异常对象
            
        Returns:
            True如果是速率限制错误，否则False
        """
        error_codes = ['ThrottlingException', 'TooManyRequestsException', 'RequestLimitExceeded']
        if isinstance(exception, AWSClientError):
            error_str = str(exception)
            return any(code in error_str for code in error_codes)
        return False
    
    def batch_delete_users_concurrent(self, users: List[UserSubscription],
                                      max_workers: int = 5,
                                      show_progress: bool = True,
                                      performance_metrics: PerformanceMetrics = None) -> BatchResult:
        """
        并发批量删除用户（优化版本）
        
        Args:
            users: 用户订阅信息列表
            max_workers: 最大并发线程数（默认5）
            show_progress: 是否显示进度
            performance_metrics: 性能指标收集器
            
        Returns:
            批量操作结果
        """
        operation_results = []
        successful_operations = 0
        failed_operations = 0
        
        self.logger.info(f"开始并发批量删除{len(users)}个用户，线程数: {max_workers}")
        
        # 创建进度跟踪器
        progress_tracker = ProgressTracker(len(users), "用户删除", show_progress, self.config) if show_progress else None
        
        # 速率限制标志
        rate_limit_event = threading.Event()
        results_lock = threading.Lock()
        
        def process_single_delete(user: UserSubscription) -> OperationResult:
            """删除单个用户（线程安全）"""
            try:
                # 检查速率限制标志
                if rate_limit_event.is_set():
                    import time
                    time.sleep(1)  # 降级后添加延迟
                
                result = self.delete_user(user)
                
                # 记录性能指标
                if performance_metrics:
                    performance_metrics.record_operation('delete', result.success)
                
                return result
                
            except AWSClientError as e:
                # 检查是否为速率限制错误
                if self._is_rate_limit_error(e):
                    self.logger.warning(f"检测到速率限制错误: {e}")
                    rate_limit_event.set()  # 触发降级
                    raise
                else:
                    error_result = OperationResult(
                        operation_type=OperationType.DELETE.value,
                        target=user.get_username(),
                        success=False,
                        message=f"AWS错误: {e}",
                        timestamp=datetime.now()
                    )
                    if performance_metrics:
                        performance_metrics.record_operation('delete', False)
                    return error_result
            
            except Exception as e:
                self.logger.error(f"删除用户{user.get_username()}时发生异常: {e}")
                error_result = OperationResult(
                    operation_type=OperationType.DELETE.value,
                    target=user.get_username(),
                    success=False,
                    message=f"删除用户时发生异常: {e}",
                    timestamp=datetime.now()
                )
                if performance_metrics:
                    performance_metrics.record_operation('delete', False)
                return error_result
        
        # 使用ThreadPoolExecutor并发处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = []
            for user in users:
                if rate_limit_event.is_set():
                    # 检测到速率限制，停止提交新任务
                    self.logger.warning("检测到速率限制，停止提交新任务，切换到串行模式")
                    break
                future = executor.submit(process_single_delete, user)
                futures.append((future, user))
            
            # 收集已提交任务的结果
            for future, user in futures:
                try:
                    # 使用配置中的超时时间
                    timeout = 60  # 默认值
                    if self.config and hasattr(self.config, 'timeouts'):
                        timeout = self.config.timeouts.user_operation
                    
                    result = future.result(timeout=timeout)
                    with results_lock:
                        operation_results.append(result)
                        if result.success:
                            successful_operations += 1
                        else:
                            failed_operations += 1
                    
                    if progress_tracker:
                        progress_tracker.update()
                
                except concurrent.futures.TimeoutError:
                    self.logger.error(f"删除用户{user.get_username()}超时")
                    error_result = OperationResult(
                        operation_type=OperationType.DELETE.value,
                        target=user.get_username(),
                        success=False,
                        message="删除超时",
                        timestamp=datetime.now()
                    )
                    with results_lock:
                        operation_results.append(error_result)
                        failed_operations += 1
                    
                    if progress_tracker:
                        progress_tracker.update()
                
                except Exception as e:
                    self.logger.error(f"获取用户{user.get_username()}删除结果失败: {e}")
                    if rate_limit_event.is_set():
                        # 速率限制错误，跳出循环
                        break
        
        # 如果触发了速率限制，串行处理剩余用户
        if rate_limit_event.is_set():
            remaining_users = users[len(operation_results):]
            if remaining_users:
                self.logger.info(f"串行处理剩余{len(remaining_users)}个用户")
                for user in remaining_users:
                    try:
                        result = process_single_delete(user)
                        operation_results.append(result)
                        if result.success:
                            successful_operations += 1
                        else:
                            failed_operations += 1
                        
                        if progress_tracker:
                            progress_tracker.update()
                    
                    except Exception as e:
                        self.logger.error(f"串行删除用户{user.get_username()}失败: {e}")
                        error_result = OperationResult(
                            operation_type=OperationType.DELETE.value,
                            target=user.get_username(),
                            success=False,
                            message=f"串行删除失败: {e}",
                            timestamp=datetime.now()
                        )
                        operation_results.append(error_result)
                        failed_operations += 1
                        
                        if progress_tracker:
                            progress_tracker.update()
        
        # 完成进度显示
        if progress_tracker:
            progress_tracker.finish()
        
        batch_result = BatchResult(
            total_operations=len(users),
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            operation_results=operation_results
        )
        
        self.logger.info(f"并发批量删除完成: 总数{batch_result.total_operations}, "
                        f"成功{batch_result.successful_operations}, "
                        f"失败{batch_result.failed_operations}, "
                        f"成功率{batch_result.success_rate:.1%}")
        
        return batch_result
    
    def sync_users(self, csv_users: List[UserSubscription]) -> Dict:
        """
        同步用户：比较CSV用户与IAM用户，执行新增、删除、更新操作
        
        Args:
            csv_users: CSV文件中的用户列表
            
        Returns:
            同步操作结果
        """
        try:
            self.logger.info(f"开始用户同步，CSV中有{len(csv_users)}个用户")
            
            # 获取现有IAM用户
            iam_users = self.get_existing_users()
            self.logger.info(f"IAM中有{len(iam_users)}个用户")
            
            # 创建用户名映射
            csv_usernames = {user.get_username(): user for user in csv_users}
            iam_usernames = {user.username: user for user in iam_users}
            
            # 分析需要执行的操作
            users_to_create = []  # CSV中有，IAM中没有
            users_to_delete = []  # IAM中有，CSV中没有（仅海尔域用户）
            users_to_update = []  # 两边都有，需要更新
            
            # 找出需要创建的用户
            for username, csv_user in csv_usernames.items():
                if username not in iam_usernames:
                    users_to_create.append(csv_user)
                else:
                    # 检查是否需要更新（使用 _needs_update 方法进行完整检查）
                    iam_user = iam_usernames[username]
                    if self._needs_update(csv_user, iam_user):
                        users_to_update.append(csv_user)
            
            # 找出需要删除的用户（仅海尔域用户）
            for username, iam_user in iam_usernames.items():
                if (username not in csv_usernames and 
                    username.endswith('@haier-saml.com')):
                    # 创建一个临时的UserSubscription对象用于删除
                    employee_id = username.split('@')[0]
                    temp_user = UserSubscription(
                        employee_id=employee_id,
                        name=iam_user.display_name.split()[0] if iam_user.display_name else "Unknown",
                        email=iam_user.email,
                        subscription_type="取消订阅/不订阅"
                    )
                    users_to_delete.append(temp_user)
            
            sync_plan = {
                'users_to_create': users_to_create,
                'users_to_delete': users_to_delete,
                'users_to_update': users_to_update,
                'total_operations': len(users_to_create) + len(users_to_delete) + len(users_to_update)
            }
            
            self.logger.info(f"同步计划: 新增{len(users_to_create)}个, 删除{len(users_to_delete)}个, 更新{len(users_to_update)}个用户")
            
            return sync_plan
            
        except Exception as e:
            self.logger.error(f"用户同步分析失败: {e}")
            raise
    
    def _needs_update(self, csv_user: UserSubscription, iam_user: IAMUser) -> bool:
        """
        判断用户是否需要更新（使用缓存数据提前判断）
        
        Args:
            csv_user: CSV中的用户信息
            iam_user: IAM中的现有用户信息
            
        Returns:
            True如果需要更新，False如果无需更新
        """
        # 比较基本属性
        expected_username = csv_user.get_username()
        expected_email = csv_user.email
        expected_name = csv_user.name
        
        # 检查用户名是否匹配
        if iam_user.username != expected_username:
            return True
        
        # 检查邮箱是否匹配
        if iam_user.email != expected_email:
            return True
        
        # 检查显示名是否匹配（新格式）
        if self._should_use_new_format():
            expected_display_name = f"{csv_user.employee_id}_{expected_name}"
            if iam_user.display_name != expected_display_name:
                return True
        
        # 检查组订阅是否发生变更
        expected_groups = set(csv_user.get_target_groups())
        actual_groups = set(iam_user.groups)
        
        if expected_groups != actual_groups:
            self.logger.debug(f"用户 {expected_username} 的组订阅发生变更: "
                            f"期望={expected_groups}, 实际={actual_groups}")
            return True
        
        # 如果所有属性都匹配，则无需更新
        return False
    
    def execute_sync_plan(self, sync_plan: Dict, 
                         shared_cache: DataCache = None,
                         max_workers: int = 5, 
                         show_progress: bool = True,
                         performance_metrics: PerformanceMetrics = None) -> Dict:
        """
        执行同步计划（优化版本：使用共享缓存和并发处理）
        
        Args:
            sync_plan: 同步计划
            shared_cache: 共享的数据缓存实例（可选）
            max_workers: 最大并发线程数（默认5）
            show_progress: 是否显示进度
            performance_metrics: 性能指标收集器
            
        Returns:
            执行结果
            
        优化点：
        1. 使用共享DataCache实例，避免重复初始化
        2. 提前判断是否需要更新，避免不必要的API调用
        3. 批量操作使用同一个缓存
        """
        results = {
            'create_results': [],
            'delete_results': [],
            'update_results': [],
            'total_successful': 0,
            'total_failed': 0
        }
        
        try:
            # 如果提供了共享缓存，使用缓存数据过滤出真正需要更新的用户
            if shared_cache and shared_cache.is_initialized():
                self.logger.info("使用共享缓存优化用户更新判断")
                existing_users_map = {u.username: u for u in shared_cache.get_all_users()}
                
                # 过滤出真正需要更新的用户
                original_update_count = len(sync_plan['users_to_update'])
                users_need_update = []
                
                for user in sync_plan['users_to_update']:
                    existing = existing_users_map.get(user.get_username())
                    if existing and self._needs_update(user, existing):
                        users_need_update.append(user)
                        if performance_metrics:
                            performance_metrics.record_cache_hit()
                    elif existing:
                        # 无需更新，记录为成功操作
                        self.logger.debug(f"用户 {user.get_username()} 无需更新，跳过")
                        if performance_metrics:
                            performance_metrics.record_cache_hit()
                    else:
                        # 缓存中没有，需要更新
                        users_need_update.append(user)
                        if performance_metrics:
                            performance_metrics.record_cache_miss()
                
                skipped_count = original_update_count - len(users_need_update)
                if skipped_count > 0:
                    self.logger.info(f"通过缓存判断，跳过 {skipped_count} 个无需更新的用户")
                
                # 更新同步计划
                sync_plan['users_to_update'] = users_need_update
            
            # 执行创建操作（并发）
            if sync_plan['users_to_create']:
                self.logger.info(f"开始并发创建{len(sync_plan['users_to_create'])}个用户")
                if performance_metrics:
                    performance_metrics.start_phase("用户创建")
                
                create_batch_result = self.batch_process_users_concurrent(
                    sync_plan['users_to_create'],
                    max_workers=max_workers,
                    show_progress=show_progress,
                    performance_metrics=performance_metrics
                )
                results['create_results'] = create_batch_result.operation_results
                results['total_successful'] += create_batch_result.successful_operations
                results['total_failed'] += create_batch_result.failed_operations
                
                if performance_metrics:
                    performance_metrics.end_phase("用户创建")
            
            # 执行更新操作（并发）
            if sync_plan['users_to_update']:
                self.logger.info(f"开始并发更新{len(sync_plan['users_to_update'])}个用户")
                if performance_metrics:
                    performance_metrics.start_phase("用户更新")
                
                update_batch_result = self.batch_process_users_concurrent(
                    sync_plan['users_to_update'],
                    max_workers=max_workers,
                    show_progress=show_progress,
                    performance_metrics=performance_metrics
                )
                results['update_results'] = update_batch_result.operation_results
                results['total_successful'] += update_batch_result.successful_operations
                results['total_failed'] += update_batch_result.failed_operations
                
                if performance_metrics:
                    performance_metrics.end_phase("用户更新")
            
            # 执行删除操作（并发）
            if sync_plan['users_to_delete']:
                self.logger.info(f"开始并发删除{len(sync_plan['users_to_delete'])}个用户")
                if performance_metrics:
                    performance_metrics.start_phase("用户删除")
                
                delete_batch_result = self.batch_delete_users_concurrent(
                    sync_plan['users_to_delete'],
                    max_workers=max_workers,
                    show_progress=show_progress,
                    performance_metrics=performance_metrics
                )
                results['delete_results'] = delete_batch_result.operation_results
                results['total_successful'] += delete_batch_result.successful_operations
                results['total_failed'] += delete_batch_result.failed_operations
                
                if performance_metrics:
                    performance_metrics.end_phase("用户删除")
            
            success_rate = (results['total_successful'] / 
                          (results['total_successful'] + results['total_failed']) 
                          if (results['total_successful'] + results['total_failed']) > 0 else 1.0)
            
            results['success_rate'] = success_rate
            
            self.logger.info(f"用户同步完成: 总成功{results['total_successful']}, "
                           f"总失败{results['total_failed']}, 成功率{success_rate:.1%}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"执行用户同步失败: {e}")
            raise