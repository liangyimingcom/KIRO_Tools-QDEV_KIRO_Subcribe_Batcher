"""
错误处理模块
"""
import time
from typing import Any, Callable, Optional
from botocore.exceptions import ClientError
from src.logger import get_logger


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.logger = get_logger("error_handler")
    
    def handle_csv_error(self, error: Exception) -> None:
        """处理CSV错误"""
        self.logger.error(f"CSV处理错误: {error}")
        raise error
    
    def handle_aws_api_error(self, error: Exception) -> bool:
        """
        处理AWS API错误
        
        Returns:
            是否应该继续处理
        """
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            
            # 不可重试的错误
            non_retryable_errors = [
                'ValidationException',
                'ResourceNotFoundException', 
                'ConflictException',
                'AccessDeniedException'
            ]
            
            if error_code in non_retryable_errors:
                self.logger.error(f"不可重试的AWS API错误: {error_code}")
                return False
            
            self.logger.warning(f"可重试的AWS API错误: {error_code}")
            return True
        
        self.logger.error(f"AWS API异常: {error}")
        return True
    
    def handle_business_error(self, error: Exception) -> None:
        """处理业务逻辑错误"""
        self.logger.warning(f"业务逻辑错误: {error}")
        # 业务错误不中断整个流程，继续处理其他项目