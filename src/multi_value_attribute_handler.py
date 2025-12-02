"""
多值属性更新处理器 - 处理AWS Identity Store的多值属性更新限制
"""
from typing import List, Dict, Optional, Any
from datetime import datetime

from .models import OperationResult, OperationType
from .logger import get_logger


class MultiValueAttributeHandler:
    """多值属性更新处理器"""
    
    def __init__(self, aws_client):
        self.aws_client = aws_client
        self.logger = get_logger("multi_value_attribute_handler")
    
    def handle_multi_value_attributes(self, user_id: str, email: str) -> OperationResult:
        """
        处理多值属性更新（主要是邮箱）
        
        Args:
            user_id: 用户ID
            email: 新邮箱地址
            
        Returns:
            操作结果
        """
        try:
            self.logger.info(f"更新用户 {user_id} 的邮箱属性")
            
            # 构建邮箱多值属性数组（完整替换）
            email_operations = [{
                "AttributePath": "emails",
                "AttributeValue": [{
                    "Value": email,
                    "Type": "work",
                    "Primary": True
                }]
            }]
            
            # 执行更新
            response = self.aws_client.update_user_with_operations(user_id, email_operations)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=user_id,
                success=True,
                message=f"成功更新邮箱属性: {email}",
                timestamp=datetime.now(),
                details={
                    "email": email,
                    "update_type": "multi_value_replacement"
                }
            )
            
        except Exception as e:
            error_msg = f"更新多值属性失败: {str(e)}"
            self.logger.error(error_msg)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=user_id,
                success=False,
                message=error_msg,
                timestamp=datetime.now(),
                details={
                    "error": str(e),
                    "email": email
                }
            )
    
    def mixed_attribute_update(self, user_id: str, single_attrs: Dict, multi_attrs: Dict) -> OperationResult:
        """
        混合更新策略：在一次API调用中更新单值和多值属性
        
        Args:
            user_id: 用户ID
            single_attrs: 单值属性字典 {attribute_path: value}
            multi_attrs: 多值属性字典 {attribute_path: value_array}
            
        Returns:
            操作结果
        """
        try:
            operations = []
            
            # 添加单值属性操作
            for attr_path, value in single_attrs.items():
                operations.append({
                    "AttributePath": attr_path,
                    "AttributeValue": value
                })
            
            # 添加多值属性操作
            for attr_path, value_array in multi_attrs.items():
                operations.append({
                    "AttributePath": attr_path,
                    "AttributeValue": value_array
                })
            
            if not operations:
                return OperationResult(
                    operation_type=OperationType.UPDATE.value,
                    target=user_id,
                    success=True,
                    message="无需更新",
                    timestamp=datetime.now()
                )
            
            # 执行混合更新
            response = self.aws_client.update_user_with_operations(user_id, operations)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=user_id,
                success=True,
                message=f"成功执行混合属性更新，操作数: {len(operations)}",
                timestamp=datetime.now(),
                details={
                    "operations_count": len(operations),
                    "single_attrs": single_attrs,
                    "multi_attrs": multi_attrs
                }
            )
            
        except Exception as e:
            error_msg = f"混合属性更新失败: {str(e)}"
            self.logger.error(error_msg)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=user_id,
                success=False,
                message=error_msg,
                timestamp=datetime.now(),
                details={
                    "error": str(e),
                    "single_attrs": single_attrs,
                    "multi_attrs": multi_attrs
                }
            )
    
    def get_current_user_attributes(self, user_id: str) -> Optional[Dict]:
        """
        获取用户现有属性
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户属性字典或None
        """
        try:
            response = self.aws_client.describe_user(user_id)
            return response
            
        except Exception as e:
            self.logger.error(f"获取用户属性失败: {str(e)}")
            return None
    
    def update_emails_with_preservation(self, user_id: str, new_email: str, 
                                      preserve_existing: bool = False) -> OperationResult:
        """
        更新邮箱属性，可选择保留现有邮箱
        
        Args:
            user_id: 用户ID
            new_email: 新邮箱地址
            preserve_existing: 是否保留现有邮箱
            
        Returns:
            操作结果
        """
        try:
            emails_to_set = []
            
            if preserve_existing:
                # 获取现有邮箱
                current_user = self.get_current_user_attributes(user_id)
                if current_user and 'Emails' in current_user:
                    existing_emails = current_user['Emails']
                    
                    # 保留现有邮箱，但将新邮箱设为主邮箱
                    for email_obj in existing_emails:
                        if email_obj['Value'] != new_email:
                            email_obj['Primary'] = False
                            emails_to_set.append(email_obj)
            
            # 添加新邮箱作为主邮箱
            emails_to_set.insert(0, {
                "Value": new_email,
                "Type": "work",
                "Primary": True
            })
            
            # 执行更新
            operations = [{
                "AttributePath": "emails",
                "AttributeValue": emails_to_set
            }]
            
            response = self.aws_client.update_user_with_operations(user_id, operations)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=user_id,
                success=True,
                message=f"成功更新邮箱属性，邮箱数量: {len(emails_to_set)}",
                timestamp=datetime.now(),
                details={
                    "new_email": new_email,
                    "total_emails": len(emails_to_set),
                    "preserve_existing": preserve_existing
                }
            )
            
        except Exception as e:
            error_msg = f"更新邮箱属性失败: {str(e)}"
            self.logger.error(error_msg)
            
            return OperationResult(
                operation_type=OperationType.UPDATE.value,
                target=user_id,
                success=False,
                message=error_msg,
                timestamp=datetime.now(),
                details={
                    "error": str(e),
                    "new_email": new_email
                }
            )
    
    def validate_multi_value_operations(self, operations: List[Dict]) -> List[str]:
        """
        验证多值属性操作的正确性
        
        Args:
            operations: 操作列表
            
        Returns:
            验证错误列表
        """
        errors = []
        multi_value_attributes = ["emails", "phoneNumbers", "addresses"]
        
        for operation in operations:
            attr_path = operation.get("AttributePath", "")
            attr_value = operation.get("AttributeValue")
            
            # 检查多值属性是否使用了正确的格式
            for mv_attr in multi_value_attributes:
                if mv_attr in attr_path:
                    # 多值属性不应该使用索引路径
                    if "[" in attr_path and "]" in attr_path:
                        errors.append(f"多值属性 {mv_attr} 不能使用索引路径: {attr_path}")
                    
                    # 多值属性的值应该是数组
                    if not isinstance(attr_value, list):
                        errors.append(f"多值属性 {mv_attr} 的值必须是数组: {attr_path}")
                    
                    # 验证邮箱格式
                    if mv_attr == "emails" and isinstance(attr_value, list):
                        for email_obj in attr_value:
                            if not isinstance(email_obj, dict):
                                errors.append(f"邮箱对象格式错误: {email_obj}")
                            elif "Value" not in email_obj:
                                errors.append(f"邮箱对象缺少Value字段: {email_obj}")
        
        return errors