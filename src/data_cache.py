"""
数据缓存模块
用于批量获取和缓存AWS IAM Identity Center的用户和组信息
"""
import threading
from typing import List, Dict
from src.models import IAMUser
from src.logger import get_logger


class DataCache:
    """
    数据缓存类
    
    职责：
    1. 批量获取所有用户、组和组成员关系
    2. 缓存数据以避免重复API调用
    3. 提供线程安全的数据访问接口
    
    生命周期：在单次sync_users()调用内有效
    """
    
    def __init__(self):
        """初始化数据缓存"""
        self._users: List[IAMUser] = []
        self._group_id_to_name: Dict[str, str] = {}
        self._user_id_to_groups: Dict[str, List[str]] = {}
        self._lock = threading.Lock()
        self._initialized = False
        self.logger = get_logger("data_cache")
    
    def initialize(self, aws_client):
        """
        初始化缓存：批量获取所有数据
        
        优化策略：
        1. 一次性获取所有用户（1次API调用）
        2. 一次性获取所有组（1次API调用）
        3. 对每个组获取成员列表（N次API调用，N=组数量）
        4. 反向构建用户ID到组列表的映射
        
        Args:
            aws_client: AWS客户端实例
        """
        with self._lock:
            if self._initialized:
                self.logger.warning("缓存已初始化，跳过重复初始化")
                return
            
            self.logger.info("开始初始化数据缓存...")
            
            try:
                # 步骤1: 批量获取所有用户（1次API调用）
                self.logger.info("批量获取所有用户...")
                aws_users = aws_client.list_users()
                self.logger.info(f"获取到{len(aws_users)}个用户")
                
                # 步骤2: 批量获取所有组（1次API调用）
                self.logger.info("批量获取所有组...")
                aws_groups = aws_client.list_groups()
                self.logger.info(f"获取到{len(aws_groups)}个组")
                
                # 构建组ID到组名的映射
                for group in aws_groups:
                    group_id = group.get('GroupId')
                    group_name = group.get('DisplayName', '')
                    if group_id:
                        self._group_id_to_name[group_id] = group_name
                
                # 步骤3: 对每个组获取成员列表（N次API调用）
                self.logger.info("批量获取组成员关系...")
                for group in aws_groups:
                    group_id = group.get('GroupId')
                    group_name = group.get('DisplayName', '')
                    
                    if not group_id:
                        continue
                    
                    try:
                        # 获取该组的所有成员
                        memberships = aws_client.list_group_memberships(group_id)
                        
                        # 反向构建用户ID到组列表的映射
                        for membership in memberships:
                            member_id = membership.get('MemberId', {}).get('UserId')
                            if member_id:
                                if member_id not in self._user_id_to_groups:
                                    self._user_id_to_groups[member_id] = []
                                self._user_id_to_groups[member_id].append(group_name)
                    
                    except Exception as e:
                        self.logger.warning(f"获取组{group_name}的成员失败: {e}")
                
                # 步骤4: 构建IAMUser对象列表
                self.logger.info("构建用户对象列表...")
                for aws_user in aws_users:
                    user_id = aws_user.get('UserId')
                    username = aws_user.get('UserName', '')
                    
                    # 从缓存中获取用户的组列表
                    user_groups = self._user_id_to_groups.get(user_id, [])
                    
                    # 提取用户信息
                    name_info = aws_user.get('Name', {})
                    emails = aws_user.get('Emails', [])
                    primary_email = ""
                    
                    for email in emails:
                        if email.get('Primary', False):
                            primary_email = email.get('Value', '')
                            break
                    
                    # 创建IAMUser对象
                    iam_user = IAMUser(
                        user_id=user_id,
                        username=username,
                        email=primary_email,
                        first_name=name_info.get('GivenName', ''),
                        last_name=name_info.get('FamilyName', ''),
                        display_name=aws_user.get('DisplayName', ''),
                        groups=user_groups
                    )
                    
                    self._users.append(iam_user)
                
                self._initialized = True
                self.logger.info(f"数据缓存初始化完成: {len(self._users)}个用户, "
                               f"{len(self._group_id_to_name)}个组")
            
            except Exception as e:
                self.logger.error(f"数据缓存初始化失败: {e}")
                raise
    
    def get_user_groups(self, user_id: str) -> List[str]:
        """
        获取用户的组列表（从缓存）
        
        Args:
            user_id: 用户ID
            
        Returns:
            组名列表
        """
        with self._lock:
            return self._user_id_to_groups.get(user_id, []).copy()
    
    def get_group_name(self, group_id: str) -> str:
        """
        获取组名（从缓存）
        
        Args:
            group_id: 组ID
            
        Returns:
            组名，如果不存在返回空字符串
        """
        with self._lock:
            return self._group_id_to_name.get(group_id, '')
    
    def get_all_users(self) -> List[IAMUser]:
        """
        获取所有用户（从缓存）
        
        Returns:
            IAM用户列表
        """
        with self._lock:
            return self._users.copy()
    
    def is_initialized(self) -> bool:
        """
        检查缓存是否已初始化
        
        Returns:
            True如果已初始化，否则False
        """
        with self._lock:
            return self._initialized
    
    def clear(self):
        """清理缓存数据"""
        with self._lock:
            self._users.clear()
            self._group_id_to_name.clear()
            self._user_id_to_groups.clear()
            self._initialized = False
            self.logger.info("数据缓存已清理")
