"""
AWS客户端封装模块
"""
import boto3
import time
from typing import List, Dict, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from src.config import Config
from src.logger import get_logger


class AWSClientError(Exception):
    """AWS客户端异常"""
    pass


class AWSClient:
    """AWS IAM Identity Center客户端封装"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger("aws_client")
        
        # 初始化AWS会话和客户端
        self.session = None
        self.sso_admin_client = None
        self.identity_store_client = None
        
        self._initialize_clients()
    
    def _initialize_clients(self):
        """初始化AWS客户端"""
        try:
            # 创建AWS会话
            self.session = boto3.Session(
                profile_name=self.config.aws.profile,
                region_name=self.config.aws.region
            )
            
            # 创建SSO Admin客户端（用于管理权限集和账户分配）
            self.sso_admin_client = self.session.client('sso-admin')
            
            # 创建Identity Store客户端（用于管理用户和组）
            self.identity_store_client = self.session.client('identitystore')
            
            # 获取Identity Store ID
            self.identity_store_id = self._get_identity_store_id()
            
            self.logger.info(f"AWS客户端初始化成功，Identity Store ID: {self.identity_store_id}")
            
        except NoCredentialsError:
            error_msg = f"AWS凭证未配置，请检查profile '{self.config.aws.profile}'"
            self.logger.error(error_msg)
            raise AWSClientError(error_msg)
        except Exception as e:
            error_msg = f"AWS客户端初始化失败: {e}"
            self.logger.error(error_msg)
            raise AWSClientError(error_msg)
    
    def _get_identity_store_id(self) -> str:
        """获取Identity Store ID"""
        try:
            response = self.sso_admin_client.list_instances()
            instances = response.get('Instances', [])
            
            # 查找匹配的实例
            for instance in instances:
                if instance['InstanceArn'].endswith(self.config.aws.identity_center_instance_id):
                    return instance['IdentityStoreId']
            
            # 如果没有找到匹配的实例，使用第一个实例
            if instances:
                identity_store_id = instances[0]['IdentityStoreId']
                self.logger.warning(f"未找到匹配的实例，使用第一个实例: {identity_store_id}")
                return identity_store_id
            
            raise AWSClientError("未找到任何Identity Center实例")
            
        except ClientError as e:
            error_msg = f"获取Identity Store ID失败: {e}"
            self.logger.error(error_msg)
            raise AWSClientError(error_msg)
    
    def _is_rate_limit_error(self, error: ClientError) -> bool:
        """
        检测是否为速率限制错误
        
        Args:
            error: ClientError异常
            
        Returns:
            是否为速率限制错误
        """
        error_code = error.response.get('Error', {}).get('Code', '')
        rate_limit_codes = [
            'ThrottlingException',
            'TooManyRequestsException',
            'RequestLimitExceeded',
            'Throttling',
            'SlowDown'
        ]
        return error_code in rate_limit_codes
    
    def call_aws_api_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs) -> Any:
        """
        带重试的AWS API调用（专门处理速率限制）
        
        Args:
            api_func: 要调用的API函数
            *args: 位置参数
            max_retries: 最大重试次数（默认3次）
            **kwargs: 关键字参数
            
        Returns:
            API调用结果
            
        Raises:
            AWSClientError: API调用失败
        """
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result = api_func(*args, **kwargs)
                response_time = time.time() - start_time
                
                # 记录成功的API调用
                api_name = getattr(api_func, '__name__', 'unknown_api')
                self.logger.debug(f"API调用成功: {api_name}, 耗时: {response_time:.2f}秒")
                
                return result
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))
                
                # 检测是否为速率限制错误
                if self._is_rate_limit_error(e):
                    if attempt < max_retries - 1:
                        # 使用指数退避策略：1s, 2s, 4s
                        wait_time = 2 ** attempt
                        self.logger.warning(
                            f"遇到AWS API速率限制 ({error_code})，"
                            f"等待{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(
                            f"重试{max_retries}次后仍遇到速率限制: {error_code} - {error_message}"
                        )
                        raise AWSClientError(
                            f"AWS API速率限制，重试{max_retries}次后失败: {error_code} - {error_message}"
                        )
                else:
                    # 非速率限制错误，直接抛出
                    self.logger.error(f"AWS API调用失败: {error_code} - {error_message}")
                    raise AWSClientError(f"AWS API调用失败: {error_code} - {error_message}")
                    
            except Exception as e:
                self.logger.error(f"AWS API调用异常: {e}")
                raise AWSClientError(f"AWS API调用异常: {e}")
        
        # 理论上不会到达这里，但为了安全起见
        raise AWSClientError(f"AWS API调用失败，已重试{max_retries}次")
    
    def _retry_api_call(self, func, *args, **kwargs) -> Any:
        """
        带重试机制的API调用
        
        Args:
            func: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            API调用结果
        """
        max_attempts = self.config.retry.max_attempts
        backoff_factor = self.config.retry.backoff_factor
        initial_delay = self.config.retry.initial_delay
        
        for attempt in range(max_attempts):
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                
                self.logger.log_aws_api_call(func.__name__, True, response_time)
                return result
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))
                
                # 某些错误不需要重试
                non_retryable_errors = [
                    'ValidationException',
                    'ResourceNotFoundException',
                    'ConflictException',
                    'AccessDeniedException'
                ]
                
                if error_code in non_retryable_errors or attempt == max_attempts - 1:
                    self.logger.log_aws_api_call(func.__name__, False, error=f"{error_code}: {error_message}")
                    raise AWSClientError(f"AWS API调用失败: {error_code} - {error_message}")
                
                # 计算重试延迟
                delay = initial_delay * (backoff_factor ** attempt)
                self.logger.warning(f"API调用失败，{delay}秒后重试 (尝试 {attempt + 1}/{max_attempts}): {error_code}")
                time.sleep(delay)
                
            except Exception as e:
                if attempt == max_attempts - 1:
                    self.logger.log_aws_api_call(func.__name__, False, error=str(e))
                    raise AWSClientError(f"AWS API调用异常: {e}")
                
                delay = initial_delay * (backoff_factor ** attempt)
                self.logger.warning(f"API调用异常，{delay}秒后重试 (尝试 {attempt + 1}/{max_attempts}): {e}")
                time.sleep(delay)
    
    def list_users(self) -> List[Dict]:
        """
        列出所有用户
        
        Returns:
            用户列表
        """
        def _list_users():
            users = []
            paginator = self.identity_store_client.get_paginator('list_users')
            
            for page in paginator.paginate(IdentityStoreId=self.identity_store_id):
                users.extend(page.get('Users', []))
            
            return users
        
        return self._retry_api_call(_list_users)
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        根据用户名获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            用户信息，如果不存在返回None
        """
        def _get_user():
            try:
                response = self.identity_store_client.get_user_id(
                    IdentityStoreId=self.identity_store_id,
                    AlternateIdentifier={
                        'UniqueAttribute': {
                            'AttributePath': 'userName',
                            'AttributeValue': username
                        }
                    }
                )
                
                user_id = response['UserId']
                
                # 获取完整用户信息
                user_response = self.identity_store_client.describe_user(
                    IdentityStoreId=self.identity_store_id,
                    UserId=user_id
                )
                
                return user_response
                
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ResourceNotFoundException':
                    return None
                raise
        
        return self._retry_api_call(_get_user)
    
    def create_user(self, user_data: Dict) -> Dict:
        """
        创建用户
        
        Args:
            user_data: 用户数据
            
        Returns:
            创建结果
        """
        def _create_user():
            return self.identity_store_client.create_user(
                IdentityStoreId=self.identity_store_id,
                **user_data
            )
        
        return self._retry_api_call(_create_user)
    
    def update_user(self, user_id: str, user_data: Dict) -> Dict:
        """
        更新用户信息
        
        Args:
            user_id: 用户ID
            user_data: 更新的用户数据
            
        Returns:
            更新结果
        """
        def _update_user():
            # 构建更新操作列表
            operations = []
            
            for key, value in user_data.items():
                operations.append({
                    'AttributePath': key,
                    'AttributeValue': value
                })
            
            return self.identity_store_client.update_user(
                IdentityStoreId=self.identity_store_id,
                UserId=user_id,
                Operations=operations
            )
        
        return self._retry_api_call(_update_user)
    
    def update_user_with_operations(self, user_id: str, operations: List[Dict]) -> Dict:
        """
        使用操作列表更新用户信息（支持复杂的多值属性更新）
        
        Args:
            user_id: 用户ID
            operations: 更新操作列表
            
        Returns:
            更新结果
        """
        def _update_user_with_operations():
            return self.identity_store_client.update_user(
                IdentityStoreId=self.identity_store_id,
                UserId=user_id,
                Operations=operations
            )
        
        return self._retry_api_call(_update_user_with_operations)
    
    def describe_user(self, user_id: str) -> Dict:
        """
        获取用户详细信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户详细信息
        """
        def _describe_user():
            return self.identity_store_client.describe_user(
                IdentityStoreId=self.identity_store_id,
                UserId=user_id
            )
        
        return self._retry_api_call(_describe_user)
    
    def list_groups(self) -> List[Dict]:
        """
        列出所有组
        
        Returns:
            组列表
        """
        def _list_groups():
            groups = []
            paginator = self.identity_store_client.get_paginator('list_groups')
            
            for page in paginator.paginate(IdentityStoreId=self.identity_store_id):
                groups.extend(page.get('Groups', []))
            
            return groups
        
        return self._retry_api_call(_list_groups)
    
    def get_group_by_name(self, group_name: str) -> Optional[Dict]:
        """
        根据组名获取组信息
        
        Args:
            group_name: 组名
            
        Returns:
            组信息，如果不存在返回None
        """
        groups = self.list_groups()
        
        for group in groups:
            if group.get('DisplayName') == group_name:
                return group
        
        return None
    
    def list_group_memberships(self, group_id: str) -> List[Dict]:
        """
        列出组成员
        
        Args:
            group_id: 组ID
            
        Returns:
            组成员列表
        """
        def _list_group_memberships():
            memberships = []
            paginator = self.identity_store_client.get_paginator('list_group_memberships')
            
            for page in paginator.paginate(
                IdentityStoreId=self.identity_store_id,
                GroupId=group_id
            ):
                memberships.extend(page.get('GroupMemberships', []))
            
            return memberships
        
        return self._retry_api_call(_list_group_memberships)
    
    def add_user_to_group(self, user_id: str, group_id: str) -> Dict:
        """
        将用户添加到组
        
        Args:
            user_id: 用户ID
            group_id: 组ID
            
        Returns:
            操作结果
        """
        def _add_user_to_group():
            return self.identity_store_client.create_group_membership(
                IdentityStoreId=self.identity_store_id,
                GroupId=group_id,
                MemberId={
                    'UserId': user_id
                }
            )
        
        return self._retry_api_call(_add_user_to_group)
    
    def remove_user_from_group(self, membership_id: str) -> Dict:
        """
        从组中移除用户
        
        Args:
            membership_id: 成员关系ID
            
        Returns:
            操作结果
        """
        def _remove_user_from_group():
            return self.identity_store_client.delete_group_membership(
                IdentityStoreId=self.identity_store_id,
                MembershipId=membership_id
            )
        
        return self._retry_api_call(_remove_user_from_group)
    
    def get_user_group_memberships(self, user_id: str) -> List[Dict]:
        """
        获取用户的组成员关系
        
        Args:
            user_id: 用户ID
            
        Returns:
            组成员关系列表
        """
        def _get_user_group_memberships():
            memberships = []
            
            try:
                paginator = self.identity_store_client.get_paginator('list_group_memberships_for_member')
                
                for page in paginator.paginate(
                    IdentityStoreId=self.identity_store_id,
                    MemberId={
                        'UserId': user_id
                    }
                ):
                    memberships.extend(page.get('GroupMemberships', []))
                    
            except ClientError as e:
                # 如果用户不存在或没有组成员关系，返回空列表
                if e.response.get('Error', {}).get('Code') in ['ResourceNotFoundException']:
                    return []
                raise
            
            return memberships
        
        return self._retry_api_call(_get_user_group_memberships)
    
    def check_user_in_group(self, user_id: str, group_id: str) -> Optional[str]:
        """
        检查用户是否在指定组中
        
        Args:
            user_id: 用户ID
            group_id: 组ID
            
        Returns:
            如果在组中返回成员关系ID，否则返回None
        """
        memberships = self.get_user_group_memberships(user_id)
        
        for membership in memberships:
            if membership.get('GroupId') == group_id:
                return membership.get('MembershipId')
        
        return None
    
    def test_connection(self) -> bool:
        """
        测试AWS连接
        
        Returns:
            连接是否成功
        """
        try:
            # 尝试列出实例来测试连接
            self.sso_admin_client.list_instances()
            self.logger.info("AWS连接测试成功")
            return True
            
        except Exception as e:
            self.logger.error(f"AWS连接测试失败: {e}")
            return False
    
    def delete_user(self, user_id: str) -> Dict:
        """
        删除用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            删除结果
        """
        def _delete_user():
            return self.identity_store_client.delete_user(
                IdentityStoreId=self.identity_store_id,
                UserId=user_id
            )
        
        return self._retry_api_call(_delete_user)
    
    def get_client_info(self) -> Dict:
        """
        获取客户端信息
        
        Returns:
            客户端信息
        """
        return {
            'profile': self.config.aws.profile,
            'region': self.config.aws.region,
            'identity_center_instance_id': self.config.aws.identity_center_instance_id,
            'identity_store_id': self.identity_store_id,
            'connection_status': self.test_connection()
        }