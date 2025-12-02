"""
组管理器模块
"""
from typing import List, Dict, Optional, Set
from datetime import datetime
from src.models import (
    UserSubscription, OperationResult, BatchResult, 
    OperationType, SubscriptionType
)
from src.aws_client import AWSClient
from src.config import Config
from src.logger import get_logger


class GroupManager:
    """组管理器"""
    
    def __init__(self, aws_client: AWSClient, config: Config):
        self.aws_client = aws_client
        self.config = config
        self.logger = get_logger("group_manager")
        
        # 组名映射
        self.group_names = {
            'kiro': config.groups.kiro,
            'qdev': config.groups.qdev
        }
        
        # 缓存组信息
        self._group_cache = {}
        self._refresh_group_cache()
    
    def _refresh_group_cache(self):
        """刷新组缓存"""
        try:
            groups = self.aws_client.list_groups()
            self._group_cache = {}
            
            for group in groups:
                group_name = group.get('DisplayName', '')
                group_id = group.get('GroupId', '')
                
                if group_name in self.group_names.values():
                    self._group_cache[group_name] = {
                        'group_id': group_id,
                        'group_name': group_name,
                        'members': None  # 延迟加载
                    }
            
            self.logger.info(f"组缓存已刷新，找到{len(self._group_cache)}个相关组")
            
        except Exception as e:
            self.logger.error(f"刷新组缓存失败: {e}")
            self._group_cache = {}
    
    def get_group_members(self, group_name: str) -> List[str]:
        """
        获取组成员列表
        
        Args:
            group_name: 组名
            
        Returns:
            成员用户名列表
        """
        try:
            # 检查缓存
            if group_name not in self._group_cache:
                self.logger.warning(f"组不存在: {group_name}")
                return []
            
            group_info = self._group_cache[group_name]
            group_id = group_info['group_id']
            
            # 如果成员信息已缓存且较新，直接返回
            if group_info['members'] is not None:
                return group_info['members']
            
            # 获取组成员关系
            memberships = self.aws_client.list_group_memberships(group_id)
            
            # 获取所有用户信息用于查找用户名
            all_users = self.aws_client.list_users()
            user_id_to_username = {
                user.get('UserId'): user.get('UserName', '') 
                for user in all_users
            }
            
            # 提取成员用户名
            member_usernames = []
            for membership in memberships:
                member_id = membership.get('MemberId', {}).get('UserId')
                if member_id and member_id in user_id_to_username:
                    username = user_id_to_username[member_id]
                    if username:
                        member_usernames.append(username)
            
            # 更新缓存
            self._group_cache[group_name]['members'] = member_usernames
            
            self.logger.info(f"组{group_name}有{len(member_usernames)}个成员")
            return member_usernames
            
        except Exception as e:
            self.logger.error(f"获取组成员失败: {group_name} - {e}")
            return []
    
    def add_user_to_group(self, username: str, group_name: str) -> OperationResult:
        """
        将用户添加到组
        
        Args:
            username: 用户名
            group_name: 组名
            
        Returns:
            操作结果
        """
        try:
            # 检查组是否存在
            if group_name not in self._group_cache:
                message = f"组不存在: {group_name}"
                self.logger.error(message)
                return OperationResult(
                    operation_type=OperationType.ADD_TO_GROUP.value,
                    target=f"{group_name}({username})",
                    success=False,
                    message=message,
                    timestamp=datetime.now()
                )
            
            group_id = self._group_cache[group_name]['group_id']
            
            # 获取用户信息
            user_info = self.aws_client.get_user_by_username(username)
            if not user_info:
                message = f"用户不存在: {username}"
                self.logger.error(message)
                return OperationResult(
                    operation_type=OperationType.ADD_TO_GROUP.value,
                    target=f"{group_name}({username})",
                    success=False,
                    message=message,
                    timestamp=datetime.now()
                )
            
            user_id = user_info.get('UserId')
            
            # 检查用户是否已在组中
            membership_id = self.aws_client.check_user_in_group(user_id, group_id)
            if membership_id:
                message = f"用户已在组中: {username} -> {group_name}"
                self.logger.info(message)
                return OperationResult(
                    operation_type=OperationType.ADD_TO_GROUP.value,
                    target=f"{group_name}({username})",
                    success=True,
                    message=message,
                    timestamp=datetime.now()
                )
            
            # 添加用户到组
            result = self.aws_client.add_user_to_group(user_id, group_id)
            membership_id = result.get('MembershipId')
            
            # 清除缓存以便下次重新加载
            if group_name in self._group_cache:
                self._group_cache[group_name]['members'] = None
            
            message = f"用户成功添加到组: {username} -> {group_name} (MembershipId: {membership_id})"
            self.logger.log_group_operation(group_name, username, "添加", True, message)
            
            return OperationResult(
                operation_type=OperationType.ADD_TO_GROUP.value,
                target=f"{group_name}({username})",
                success=True,
                message=message,
                timestamp=datetime.now(),
                details={'membership_id': membership_id}
            )
            
        except Exception as e:
            message = f"添加用户到组失败: {username} -> {group_name} - {e}"
            self.logger.log_group_operation(group_name, username, "添加", False, str(e))
            
            return OperationResult(
                operation_type=OperationType.ADD_TO_GROUP.value,
                target=f"{group_name}({username})",
                success=False,
                message=message,
                timestamp=datetime.now()
            )
    
    def remove_user_from_group(self, username: str, group_name: str) -> OperationResult:
        """
        从组中移除用户
        
        Args:
            username: 用户名
            group_name: 组名
            
        Returns:
            操作结果
        """
        try:
            # 检查组是否存在
            if group_name not in self._group_cache:
                message = f"组不存在: {group_name}"
                self.logger.error(message)
                return OperationResult(
                    operation_type=OperationType.REMOVE_FROM_GROUP.value,
                    target=f"{group_name}({username})",
                    success=False,
                    message=message,
                    timestamp=datetime.now()
                )
            
            group_id = self._group_cache[group_name]['group_id']
            
            # 获取用户信息
            user_info = self.aws_client.get_user_by_username(username)
            if not user_info:
                message = f"用户不存在: {username}"
                self.logger.error(message)
                return OperationResult(
                    operation_type=OperationType.REMOVE_FROM_GROUP.value,
                    target=f"{group_name}({username})",
                    success=False,
                    message=message,
                    timestamp=datetime.now()
                )
            
            user_id = user_info.get('UserId')
            
            # 检查用户是否在组中
            membership_id = self.aws_client.check_user_in_group(user_id, group_id)
            if not membership_id:
                message = f"用户不在组中: {username} -> {group_name}"
                self.logger.info(message)
                return OperationResult(
                    operation_type=OperationType.REMOVE_FROM_GROUP.value,
                    target=f"{group_name}({username})",
                    success=True,
                    message=message,
                    timestamp=datetime.now()
                )
            
            # 从组中移除用户
            self.aws_client.remove_user_from_group(membership_id)
            
            # 清除缓存以便下次重新加载
            if group_name in self._group_cache:
                self._group_cache[group_name]['members'] = None
            
            message = f"用户成功从组中移除: {username} -> {group_name}"
            self.logger.log_group_operation(group_name, username, "移除", True, message)
            
            return OperationResult(
                operation_type=OperationType.REMOVE_FROM_GROUP.value,
                target=f"{group_name}({username})",
                success=True,
                message=message,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            message = f"从组中移除用户失败: {username} -> {group_name} - {e}"
            self.logger.log_group_operation(group_name, username, "移除", False, str(e))
            
            return OperationResult(
                operation_type=OperationType.REMOVE_FROM_GROUP.value,
                target=f"{group_name}({username})",
                success=False,
                message=message,
                timestamp=datetime.now()
            )
    
    def update_user_subscriptions(self, user: UserSubscription) -> OperationResult:
        """
        更新用户订阅关系
        
        Args:
            user: 用户订阅信息
            
        Returns:
            操作结果
        """
        username = user.get_username()
        target_groups = set(user.get_target_groups())
        all_managed_groups = set(self.group_names.values())
        
        operations = []
        all_success = True
        
        self.logger.info(f"更新用户订阅: {username} -> {user.subscription_type}")
        
        try:
            # 获取用户当前的组成员关系
            current_groups = set()
            user_info = self.aws_client.get_user_by_username(username)
            
            if user_info:
                user_id = user_info.get('UserId')
                memberships = self.aws_client.get_user_group_memberships(user_id)
                
                # 获取所有组信息用于查找组名
                all_groups = self.aws_client.list_groups()
                group_id_to_name = {
                    group.get('GroupId'): group.get('DisplayName', '') 
                    for group in all_groups
                }
                
                for membership in memberships:
                    group_id = membership.get('GroupId')
                    if group_id and group_id in group_id_to_name:
                        group_name = group_id_to_name[group_id]
                        if group_name in all_managed_groups:
                            current_groups.add(group_name)
            
            # 计算需要添加和移除的组
            groups_to_add = target_groups - current_groups
            groups_to_remove = (current_groups & all_managed_groups) - target_groups
            
            self.logger.info(f"当前组: {current_groups}")
            self.logger.info(f"目标组: {target_groups}")
            self.logger.info(f"需要添加: {groups_to_add}")
            self.logger.info(f"需要移除: {groups_to_remove}")
            
            # 添加用户到新组
            for group_name in groups_to_add:
                result = self.add_user_to_group(username, group_name)
                operations.append(result)
                if not result.success:
                    all_success = False
            
            # 从旧组中移除用户
            for group_name in groups_to_remove:
                result = self.remove_user_from_group(username, group_name)
                operations.append(result)
                if not result.success:
                    all_success = False
            
            # 如果没有任何操作
            if not operations:
                message = f"用户组成员关系无需更新: {username}"
                self.logger.info(message)
                return OperationResult(
                    operation_type="UPDATE_SUBSCRIPTIONS",
                    target=username,
                    success=True,
                    message=message,
                    timestamp=datetime.now()
                )
            
            # 汇总结果
            successful_ops = sum(1 for op in operations if op.success)
            total_ops = len(operations)
            
            if all_success:
                message = f"用户订阅更新成功: {username} - 完成{total_ops}个操作"
            else:
                message = f"用户订阅更新部分成功: {username} - {successful_ops}/{total_ops}个操作成功"
            
            return OperationResult(
                operation_type="UPDATE_SUBSCRIPTIONS",
                target=username,
                success=all_success,
                message=message,
                timestamp=datetime.now(),
                details={
                    'operations': [op.__dict__ for op in operations],
                    'groups_added': list(groups_to_add),
                    'groups_removed': list(groups_to_remove)
                }
            )
            
        except Exception as e:
            message = f"更新用户订阅失败: {username} - {e}"
            self.logger.error(message)
            
            return OperationResult(
                operation_type="UPDATE_SUBSCRIPTIONS",
                target=username,
                success=False,
                message=message,
                timestamp=datetime.now()
            )
    
    def batch_update_subscriptions(self, users: List[UserSubscription], 
                                  data_cache=None) -> BatchResult:
        """
        批量更新用户订阅（优化版本：使用共享缓存）
        
        Args:
            users: 用户订阅信息列表
            data_cache: 共享的数据缓存实例（可选）
            
        Returns:
            批量操作结果
            
        优化点：
        1. 使用缓存的用户组信息，避免重复API调用
        2. 提前从缓存获取所有用户的组信息
        3. 批量比较当前组和目标组，只对有差异的用户执行更新
        """
        operation_results = []
        successful_operations = 0
        failed_operations = 0
        
        self.logger.info(f"开始批量更新{len(users)}个用户的订阅关系")
        
        # 如果提供了共享缓存，使用缓存数据优化处理
        user_groups_map = {}
        if data_cache and data_cache.is_initialized():
            self.logger.info("使用共享缓存优化组订阅处理")
            cached_users = data_cache.get_all_users()
            user_groups_map = {u.username: set(u.groups) for u in cached_users}
            self.logger.info(f"从缓存获取到 {len(user_groups_map)} 个用户的组信息")
        
        # 批量处理用户
        skipped_count = 0
        for i, user in enumerate(users, 1):
            # 每处理30个用户输出一次进度
            if i % 30 == 0:
                self.logger.info(f"组订阅处理进度: {i}/{len(users)}")
            
            try:
                # 获取用户当前的组（从缓存或API）
                username = user.get_username()
                if username in user_groups_map:
                    current_groups = user_groups_map[username]
                else:
                    # 缓存中没有，需要调用API
                    current_groups_list = self.get_user_current_groups(username)
                    current_groups = set(current_groups_list)
                
                # 获取目标组
                target_groups = set(user.get_target_groups())
                
                # 只有需要更新时才调用API
                if current_groups != target_groups:
                    result = self.update_user_subscriptions(user)
                    operation_results.append(result)
                    
                    if result.success:
                        successful_operations += 1
                    else:
                        failed_operations += 1
                else:
                    # 无需更新，记录为成功
                    skipped_count += 1
                    self.logger.debug(f"用户 {username} 组订阅已是最新，跳过")
                    result = OperationResult(
                        operation_type="UPDATE_SUBSCRIPTIONS",
                        target=username,
                        success=True,
                        message="组订阅已是最新，无需更新",
                        timestamp=datetime.now()
                    )
                    operation_results.append(result)
                    successful_operations += 1
                    
            except Exception as e:
                error_result = OperationResult(
                    operation_type="UPDATE_SUBSCRIPTIONS",
                    target=user.get_username(),
                    success=False,
                    message=f"处理用户订阅时发生异常: {e}",
                    timestamp=datetime.now()
                )
                operation_results.append(error_result)
                failed_operations += 1
                
                self.logger.error(f"处理用户订阅{user.get_username()}时发生异常: {e}")
        
        if skipped_count > 0:
            self.logger.info(f"通过缓存判断，跳过 {skipped_count} 个无需更新组订阅的用户")
        
        batch_result = BatchResult(
            total_operations=len(users),
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            operation_results=operation_results
        )
        
        self.logger.info(f"批量订阅更新完成: 总数{batch_result.total_operations}, "
                        f"成功{batch_result.successful_operations}, "
                        f"失败{batch_result.failed_operations}, "
                        f"成功率{batch_result.success_rate:.1%}")
        
        return batch_result
    
    def get_group_statistics(self) -> Dict:
        """
        获取组统计信息
        
        Returns:
            组统计信息
        """
        try:
            stats = {
                'total_groups': len(self._group_cache),
                'group_members': {},
                'subscription_distribution': {}
            }
            
            # 统计每个组的成员数量
            for group_name in self._group_cache:
                members = self.get_group_members(group_name)
                stats['group_members'][group_name] = len(members)
            
            # 分析订阅分布（基于用户名模式）
            kiro_group = self.config.groups.kiro
            qdev_group = self.config.groups.qdev
            
            kiro_members = set(self.get_group_members(kiro_group)) if kiro_group in self._group_cache else set()
            qdev_members = set(self.get_group_members(qdev_group)) if qdev_group in self._group_cache else set()
            
            stats['subscription_distribution'] = {
                SubscriptionType.KIRO.value: len(kiro_members - qdev_members),
                SubscriptionType.QDEV.value: len(qdev_members - kiro_members),
                SubscriptionType.ALL.value: len(kiro_members & qdev_members),
                SubscriptionType.NONE.value: 0  # 无法从组信息推断
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取组统计信息失败: {e}")
            return {
                'total_groups': 0,
                'group_members': {},
                'subscription_distribution': {},
                'error': str(e)
            }
    
    def validate_group_configuration(self) -> List[str]:
        """
        验证组配置
        
        Returns:
            验证错误列表
        """
        errors = []
        
        # 检查配置的组是否存在
        for group_type, group_name in self.group_names.items():
            if group_name not in self._group_cache:
                errors.append(f"{group_type.upper()}组不存在: {group_name}")
        
        # 检查组名是否重复
        group_names_list = list(self.group_names.values())
        if len(group_names_list) != len(set(group_names_list)):
            errors.append("组名配置重复")
        
        # 检查组名格式
        for group_name in self.group_names.values():
            if not group_name or len(group_name.strip()) == 0:
                errors.append(f"组名不能为空: {group_name}")
        
        return errors
    
    def get_user_current_groups(self, username: str) -> List[str]:
        """
        获取用户当前所在的组
        
        Args:
            username: 用户名
            
        Returns:
            用户当前所在的组列表
        """
        try:
            user_info = self.aws_client.get_user_by_username(username)
            if not user_info:
                return []
            
            user_id = user_info.get('UserId')
            memberships = self.aws_client.get_user_group_memberships(user_id)
            
            # 获取所有组信息用于查找组名
            all_groups = self.aws_client.list_groups()
            group_id_to_name = {
                group.get('GroupId'): group.get('DisplayName', '') 
                for group in all_groups
            }
            
            current_groups = []
            for membership in memberships:
                group_id = membership.get('GroupId')
                if group_id and group_id in group_id_to_name:
                    group_name = group_id_to_name[group_id]
                    if group_name in self.group_names.values():
                        current_groups.append(group_name)
            
            return current_groups
            
        except Exception as e:
            self.logger.error(f"获取用户当前组失败: {username} - {e}")
            return []