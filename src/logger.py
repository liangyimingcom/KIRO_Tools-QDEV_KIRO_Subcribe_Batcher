"""
日志记录器模块
"""
import logging
import os
import sys
from typing import Optional
from src.config import LoggingConfig


class PrintLogger:
    """
    将print输出重定向到日志文件的类
    """
    def __init__(self, log_file, original_stdout):
        self.log_file = log_file
        self.original_stdout = original_stdout
        self.file_handle = None
    
    def write(self, message):
        """写入消息到控制台和日志文件"""
        # 写入到原始stdout（控制台）
        self.original_stdout.write(message)
        self.original_stdout.flush()
        
        # 写入到日志文件
        if self.file_handle is None:
            try:
                # 确保日志目录存在
                log_dir = os.path.dirname(self.log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                self.file_handle = open(self.log_file, 'a', encoding='utf-8')
            except Exception as e:
                self.original_stdout.write(f"无法打开日志文件: {e}\n")
                return
        
        try:
            self.file_handle.write(message)
            self.file_handle.flush()
        except Exception as e:
            self.original_stdout.write(f"写入日志文件失败: {e}\n")
    
    def flush(self):
        """刷新缓冲区"""
        self.original_stdout.flush()
        if self.file_handle:
            self.file_handle.flush()
    
    def close(self):
        """关闭文件句柄"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None


class Logger:
    """日志记录器"""
    
    def __init__(self, name: str, config: Optional[LoggingConfig] = None):
        self.name = name
        self.config = config or LoggingConfig()
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(self.name)
        logger.setLevel(getattr(logging, self.config.level.upper()))
        
        # 避免重复添加处理器
        if logger.handlers:
            return logger
        
        # 创建日志目录
        log_dir = os.path.dirname(self.config.file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 文件处理器
        file_handler = logging.FileHandler(self.config.file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, self.config.level.upper()))
        
        # 控制台处理器 - 同时输出到文件
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化器
        formatter = logging.Formatter(self.config.format)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def info(self, message: str, **kwargs):
        """记录信息日志"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """记录警告日志"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """记录错误日志"""
        self.logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """记录调试日志"""
        self.logger.debug(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """记录异常日志"""
        self.logger.exception(message, **kwargs)
    
    def log_operation_result(self, operation_type: str, target: str, success: bool, message: str):
        """记录操作结果"""
        status = "成功" if success else "失败"
        log_message = f"操作{status} - {operation_type}: {target} - {message}"
        
        if success:
            self.info(log_message)
        else:
            self.error(log_message)
    
    def log_user_operation(self, username: str, operation: str, success: bool, details: str = ""):
        """记录用户操作"""
        self.log_operation_result(f"用户{operation}", username, success, details)
    
    def log_group_operation(self, group_name: str, username: str, operation: str, success: bool, details: str = ""):
        """记录组操作"""
        target = f"{group_name}({username})"
        self.log_operation_result(f"组{operation}", target, success, details)
    
    def log_aws_api_call(self, api_name: str, success: bool, response_time: float = None, error: str = None):
        """记录AWS API调用"""
        if success:
            message = f"AWS API调用成功: {api_name}"
            if response_time:
                message += f" (耗时: {response_time:.2f}s)"
            self.info(message)
        else:
            message = f"AWS API调用失败: {api_name}"
            if error:
                message += f" - 错误: {error}"
            self.error(message)
    
    def log_validation_result(self, data_type: str, total_count: int, valid_count: int, errors: list):
        """记录验证结果"""
        message = f"{data_type}验证完成: 总数{total_count}, 有效{valid_count}, 错误{len(errors)}"
        
        if errors:
            self.warning(message)
            for error in errors[:5]:  # 只记录前5个错误
                self.warning(f"  验证错误: {error}")
            if len(errors) > 5:
                self.warning(f"  还有{len(errors) - 5}个错误未显示...")
        else:
            self.info(message)
    
    def log_performance_metrics(self, operation: str, duration: float, count: int):
        """记录性能指标"""
        avg_time = duration / count if count > 0 else 0
        message = f"性能指标 - {operation}: 总耗时{duration:.2f}s, 处理{count}项, 平均{avg_time:.3f}s/项"
        self.info(message)
    
    def setLevel(self, level):
        """设置日志级别"""
        self.logger.setLevel(level)


# 全局日志记录器实例
_loggers = {}


def get_logger(name: str, config: Optional[LoggingConfig] = None) -> Logger:
    """获取日志记录器实例"""
    if name not in _loggers:
        _loggers[name] = Logger(name, config)
    return _loggers[name]


def setup_logging(config: LoggingConfig):
    """设置全局日志配置"""
    # 清除现有的日志记录器
    _loggers.clear()
    
    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建日志目录
    log_dir = os.path.dirname(config.file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建文件处理器 - 记录所有日志
    file_handler = logging.FileHandler(config.file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(config.format)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到根日志记录器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 重定向print输出到日志文件
    # 保存原始stdout
    if not hasattr(sys.stdout, '_original_stdout'):
        sys.stdout._original_stdout = sys.stdout
    
    # 创建PrintLogger实例并替换sys.stdout
    print_logger = PrintLogger(config.file, sys.stdout._original_stdout)
    sys.stdout = print_logger
    
    # 创建新的全局日志记录器
    get_logger("subscription_manager", config)