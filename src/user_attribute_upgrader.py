"""
用户属性升级器 - 处理用户属性格式升级到新标准
"""
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .models import (
    IAMUser, UserSubscription, OperationResult, UpgradeResult, 
    UpgradePlan, UserUpdateData, OperationType
)
from .logger import get_logger


class UserAttributeUpgrader:
    """用户属性升级器"""
    
    def __init__(self, aws_client):
        self.aws_client = aws_client
        self.logger = get_logger("user_attribute_upgrader")
    
    def upgrade_user_attributes(self, users: List[IAMUser], csv_users: List[UserSubscription], 
                              dry_run: bool = False) -> UpgradeResult:
        """
        升级用户属性到新格式
        
        Args:
            users: IAM用户列表
            csv_users: CSV用户数据列表
            dry_run: 是否为试运行模式
            
        Returns:
            升级结果
        """
        self.logger.info(f"开始用户属性升级，用户数量: {len(users)}, 试运行: {dry_run}")
        
        # 生成升级计划
        upgrade_plan = self.generate_upgrade_plan(users, csv_users)
        
        if dry_run:
            self.logger.info("试运行模式，跳过实际升级操作")
            return UpgradeResult(
                total_users=len(upgrade_plan.users_to_upgrade),
                successful_upgrades=0,
                failed_upgrades=0,
                upgrade_operations=[],
                upgrade_plan=upgrade_plan
            )
        
        # 执行升级
        upgrade_operations = []
        successful_count = 0
        failed_count = 0
        
        for iam_user, csv_user in upgrade_plan.users_to_upgrade:
            try:
                self.logger.info(f"升级用户: {iam_user.username}")
                
                # 转换为新格式
                update_data = self.convert_to_new_format(iam_user, csv_user)
                
                # 执行更新
                result = self._execute_user_update(update_data)
                upgrade_operations.append(result)
                
                if result.success:
                    successful_count += 1
                    self.logger.info(f"用户 {iam_user.username} 升级成功")
                else:
                    failed_count += 1
                    self.logger.error(f"用户 {iam_user.username} 升级失败: {result.message}")
                    
            except Exception as e:
                failed_count += 1
                error_msg = f"升级用户 {iam_user.username} 时发生异常: {str(e)}"
                self.logger.error(error_msg)
                
                upgrade_operations.append(OperationResult(
                    operation_type=OperationType.UPDATE.value,
                    target=iam_user.username,
                    success=False,
                    message=error_msg,
                    timestamp=datetime.now()
                ))
        
        result = UpgradeResult(
            total_users=len(upgrade_plan.users_to_upgrade),
            successful_upgrades=successful_count,
            failed_upgrades=failed_count,
            upgrade_operations=upgrade_operations,
            upgrade_plan=upgrade_plan
        )
        
        self.logger.info(f"用户属性升级完成，成功: {successful_count}, 失败: {failed_count}")
        return result
    
    def convert_to_new_format(self, iam_user: IAMUser, csv_user: UserSubscription) -> UserUpdateData:
        """
        将用户属性转换为新格式
        
        Args:
            iam_user: IAM用户信息
            csv_user: CSV用户数据
            
        Returns:
            用户更新数据
        """
        # 新格式属性
        new_username = csv_user.get_username()  # 工号@haier-saml.com
        new_first_name = csv_user.employee_id   # 工号
        new_last_name = csv_user.name           # 中文姓名
        new_display_name = f"{csv_user.employee_id}_{csv_user.name}"  # 工号_中文姓名
        
        # 构建更新操作
        operations = []
        
        # 单值属性更新
        if iam_user.first_name != new_first_name:
            operations.append({
                "AttributePath": "name.givenName",
                "AttributeValue": new_first_name
            })
        
        if iam_user.last_name != new_last_name:
            operations.append({
                "AttributePath": "name.familyName",
                "AttributeValue": new_last_name
            })
        
        if iam_user.display_name != new_display_name:
            operations.append({
                "AttributePath": "displayName",
                "AttributeValue": new_display_name
            })
        
        # 多值属性更新（邮箱）
        if iam_user.email != csv_user.email:
            operations.append({
                "AttributePath": "emails",
                "AttributeValue": [{
                    "Value": csv_user.email,
                    "Type": "work",
                    "Primary": True
                }]
            })
        
        # 记录旧属性和新属性
        old_attributes = {
            "username": iam_user.username,
            "first_name": iam_user.first_name,
            "last_name": iam_user.last_name,
            "display_name": iam_user.display_name,
            "email": iam_user.email
        }
        
        new_attributes = {
            "username": new_username,
            "first_name": new_first_name,
            "last_name": new_last_name,
            "display_name": new_display_name,
            "email": csv_user.email
        }
        
        return UserUpdateData(
            user_id=iam_user.user_id,
            username=iam_user.username,
            operations=operations,
            old_attributes=old_attributes,
            new_attributes=new_attributes
        )
    
    def generate_upgrade_plan(self, iam_users: List[IAMUser], csv_users: List[UserSubscription]) -> UpgradePlan:
        """
        生成用户属性升级计划
        
        Args:
            iam_users: IAM用户列表
            csv_users: CSV用户数据列表
            
        Returns:
            升级计划
        """
        self.logger.info("生成用户属性升级计划")
        
        # 创建CSV用户映射（按员工号）
        csv_user_map = {}
        for csv_user in csv_users:
            csv_user_map[csv_user.employee_id] = csv_user
        
        users_to_upgrade = []
        total_operations = 0
        
        for iam_user in iam_users:
            # 从用户名中提取员工号
            employee_id = self._extract_employee_id(iam_user.username)
            
            if employee_id and employee_id in csv_user_map:
                csv_user = csv_user_map[employee_id]
                
                # 检查是否需要升级
                if self._needs_upgrade(iam_user, csv_user):
                    users_to_upgrade.append((iam_user, csv_user))
                    
                    # 估算操作数量
                    update_data = self.convert_to_new_format(iam_user, csv_user)
                    total_operations += len(update_data.operations)
        
        # 估算执行时间（每个操作约2秒）
        estimated_time = total_operations * 2
        
        plan = UpgradePlan(
            users_to_upgrade=users_to_upgrade,
            total_operations=total_operations,
            estimated_time=estimated_time
        )
        
        self.logger.info(f"升级计划生成完成，待升级用户: {len(users_to_upgrade)}, 总操作数: {total_operations}")
        return plan
    
    def _extract_employee_id(self, username: str) -> Optional[str]:
        """
        从用户名中提取员工号
        
        Args:
            username: 用户名
            
        Returns:
            员工号或None
        """
        # 匹配 工号@haier-saml.com 格式
        match = re.match(r'^([A-Za-z0-9]+)@haier-saml\.com$', username)
        if match:
            return match.group(1)
        
        # 如果不是标准格式，尝试直接使用用户名作为员工号
        # 这适用于旧格式的用户名
        if username and not '@' in username:
            return username
        
        return None
    
    def _needs_upgrade(self, iam_user: IAMUser, csv_user: UserSubscription) -> bool:
        """
        检查用户是否需要升级
        
        Args:
            iam_user: IAM用户信息
            csv_user: CSV用户数据
            
        Returns:
            是否需要升级
        """
        # 检查用户名格式
        expected_username = csv_user.get_username()
        if iam_user.username != expected_username:
            return True
        
        # 检查显示名称格式
        expected_display_name = f"{csv_user.employee_id}_{csv_user.name}"
        if iam_user.display_name != expected_display_name:
            return True
        
        # 检查First name是否为员工号
        if iam_user.first_name != csv_user.employee_id:
            return True
        
        # 检查Last name是否为中文姓名
        if iam_user.last_name != csv_user.name:
            return True
        
        # 检查邮箱
        if iam_user.email != csv_user.email:
            return True
        
        return False
    
    def _execute_user_update(self, update_data: UserUpdateData) -> OperationResult:
        """
        执行用户更新
        
        Args:
            update_data: 用户更新数据
            
        Returns:
            操作结果
        """
        try:
            if not update_data.operations:
                return OperationResult(
                    operation_type=OperationType.UPDATE.value,
                    target=update_data.username,
                    success=True,
                    message="无需更新",
                    timestamp=datetime.now()
                )
            
            # 使用AWS客户端执行更新
            response = self.aws_client.update_user_with_operations(
                update_data.user_id, 
                update_data.operations
            )
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=update_data.username,
                success=True,
                message=f"成功更新{len(update_data.operations)}个属性",
                timestamp=datetime.now(),
                details={
                    "operations_count": len(update_data.operations),
                    "old_attributes": update_data.old_attributes,
                    "new_attributes": update_data.new_attributes
                }
            )
            
        except Exception as e:
            error_msg = f"更新用户属性失败: {str(e)}"
            self.logger.error(error_msg)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=update_data.username,
                success=False,
                message=error_msg,
                timestamp=datetime.now(),
                details={
                    "error": str(e),
                    "operations": update_data.operations
                }
            )
    
    def verify_upgrade_result(self, user_id: str, expected_attributes: Dict) -> bool:
        """
        验证升级后的用户属性是否正确
        
        Args:
            user_id: 用户ID
            expected_attributes: 期望的属性值
            
        Returns:
            验证是否通过
        """
        try:
            # 获取当前用户属性
            current_user = self.aws_client.describe_user(user_id)
            
            # 验证各个属性
            verifications = []
            
            # 验证显示名称
            current_display_name = current_user.get('DisplayName', '')
            expected_display_name = expected_attributes.get('display_name', '')
            verifications.append(current_display_name == expected_display_name)
            
            # 验证First name
            current_first_name = current_user.get('Name', {}).get('GivenName', '')
            expected_first_name = expected_attributes.get('first_name', '')
            verifications.append(current_first_name == expected_first_name)
            
            # 验证Last name
            current_last_name = current_user.get('Name', {}).get('FamilyName', '')
            expected_last_name = expected_attributes.get('last_name', '')
            verifications.append(current_last_name == expected_last_name)
            
            # 验证邮箱
            current_emails = current_user.get('Emails', [])
            expected_email = expected_attributes.get('email', '')
            if current_emails and expected_email:
                primary_email = next((email['Value'] for email in current_emails if email.get('Primary')), '')
                verifications.append(primary_email == expected_email)
            
            # 所有验证都通过才返回True
            result = all(verifications)
            
            if result:
                self.logger.info(f"用户 {user_id} 属性验证通过")
            else:
                self.logger.warning(f"用户 {user_id} 属性验证失败")
                self.logger.warning(f"当前属性: DisplayName={current_display_name}, FirstName={current_first_name}, LastName={current_last_name}")
                self.logger.warning(f"期望属性: DisplayName={expected_display_name}, FirstName={expected_first_name}, LastName={expected_last_name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"验证用户 {user_id} 属性时发生异常: {str(e)}")
            return False
    
    def batch_verify_upgrades(self, upgrade_operations: List[OperationResult]) -> Dict:
        """
        批量验证升级结果
        
        Args:
            upgrade_operations: 升级操作结果列表
            
        Returns:
            验证统计结果
        """
        verification_stats = {
            'total_verified': 0,
            'passed_verification': 0,
            'failed_verification': 0,
            'verification_errors': []
        }
        
        for operation in upgrade_operations:
            if not operation.success:
                continue  # 跳过失败的操作
            
            if not operation.details or 'new_attributes' not in operation.details:
                continue  # 跳过没有详细信息的操作
            
            try:
                # 从操作详情中提取用户ID和期望属性
                # 需要通过用户名获取用户ID
                username = operation.target
                user_info = self.aws_client.get_user_by_username(username)
                if not user_info:
                    verification_stats['verification_errors'].append(f"无法找到用户: {username}")
                    continue
                
                user_id = user_info['UserId']
                expected_attributes = operation.details['new_attributes']
                
                verification_stats['total_verified'] += 1
                
                if self.verify_upgrade_result(user_id, expected_attributes):
                    verification_stats['passed_verification'] += 1
                else:
                    verification_stats['failed_verification'] += 1
                    verification_stats['verification_errors'].append(f"用户 {username} 属性验证失败")
                    
            except Exception as e:
                verification_stats['failed_verification'] += 1
                error_msg = f"验证用户 {operation.target} 时发生异常: {str(e)}"
                verification_stats['verification_errors'].append(error_msg)
                self.logger.error(error_msg)
        
        self.logger.info(f"批量验证完成: 总数={verification_stats['total_verified']}, "
                        f"通过={verification_stats['passed_verification']}, "
                        f"失败={verification_stats['failed_verification']}")
        
        return verification_stats