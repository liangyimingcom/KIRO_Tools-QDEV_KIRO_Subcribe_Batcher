"""
CSV解析器模块
"""
import csv
import os
from typing import List, Optional
from src.models import UserSubscription, ValidationResult
from src.logger import get_logger


class CSVParser:
    """CSV解析器"""
    
    def __init__(self, config=None):
        self.logger = get_logger("csv_parser")
        self.config = config
    
    def parse_subscription_file(self, file_path: str) -> List[UserSubscription]:
        """
        解析用户清单订阅表CSV文件
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            用户订阅信息列表
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV文件不存在: {file_path}")
        
        if not self.validate_csv_format(file_path):
            raise ValueError(f"CSV文件格式错误: {file_path}")
        
        users = []
        
        try:
            # 尝试不同的编码格式（优先使用utf-8-sig处理BOM）
            encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    self.logger.info(f"成功使用编码 {encoding} 读取文件")
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise ValueError("无法使用任何编码格式读取CSV文件")
            
            # 解析CSV内容
            lines = content.strip().split('\n')
            if len(lines) < 2:
                raise ValueError("CSV文件内容不足，至少需要标题行和一行数据")
            
            # 检查标题行
            header = lines[0].strip()
            expected_headers = ['工号', '姓名', '邮箱', '订阅项目']
            
            # 处理可能的分隔符
            if ',' in header:
                delimiter = ','
            elif '\t' in header:
                delimiter = '\t'
            elif ';' in header:
                delimiter = ';'
            else:
                delimiter = ','
            
            # 解析标题
            headers = [h.strip() for h in header.split(delimiter)]
            
            # 移除BOM字符（如果存在）
            if headers and headers[0].startswith('\ufeff'):
                headers[0] = headers[0][1:]
            
            # 验证标题
            missing_headers = []
            for expected in expected_headers:
                if expected not in headers:
                    missing_headers.append(expected)
            
            if missing_headers:
                raise ValueError(f"CSV文件缺少必要的列: {missing_headers}")
            
            # 获取列索引
            try:
                employee_id_idx = headers.index('工号')
                name_idx = headers.index('姓名')
                email_idx = headers.index('邮箱')
                subscription_idx = headers.index('订阅项目')
            except ValueError as e:
                raise ValueError(f"无法找到必要的列: {e}")
            
            # 解析数据行
            for line_num, line in enumerate(lines[1:], start=2):
                line = line.strip()
                if not line:  # 跳过空行
                    continue
                
                try:
                    fields = [f.strip() for f in line.split(delimiter)]
                    
                    if len(fields) < len(expected_headers):
                        self.logger.warning(f"第{line_num}行字段数量不足，跳过: {line}")
                        continue
                    
                    # 提取字段值
                    employee_id = fields[employee_id_idx]
                    name = fields[name_idx]
                    email = fields[email_idx]
                    subscription_type = fields[subscription_idx]
                    
                    # 基本验证
                    if not employee_id or not name or not email or not subscription_type:
                        self.logger.warning(f"第{line_num}行存在空字段，跳过: {line}")
                        continue
                    
                    # 创建用户订阅对象
                    user = UserSubscription(
                        employee_id=employee_id,
                        name=name,
                        email=email,
                        subscription_type=subscription_type
                    )
                    
                    # 注入配置（如果可用）
                    if self.config:
                        user.set_config(self.config)
                    
                    users.append(user)
                    
                except Exception as e:
                    self.logger.error(f"解析第{line_num}行时出错: {e}, 行内容: {line}")
                    continue
            
            self.logger.info(f"成功解析CSV文件，共{len(users)}个用户")
            return users
            
        except Exception as e:
            self.logger.error(f"解析CSV文件失败: {e}")
            raise
    
    def validate_csv_format(self, file_path: str) -> bool:
        """
        验证CSV文件格式
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            是否格式正确
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            # 检查文件扩展名
            if not file_path.lower().endswith('.csv'):
                self.logger.warning(f"文件扩展名不是.csv: {file_path}")
            
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                self.logger.error("CSV文件为空")
                return False
            
            if file_size > 10 * 1024 * 1024:  # 10MB限制
                self.logger.warning(f"CSV文件过大: {file_size / 1024 / 1024:.2f}MB")
            
            # 尝试读取前几行进行基本验证
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        first_line = f.readline().strip()
                        if first_line:
                            # 检查是否包含必要的标题
                            required_keywords = ['工号', '姓名', '邮箱', '订阅']
                            found_keywords = sum(1 for keyword in required_keywords if keyword in first_line)
                            
                            if found_keywords >= 3:  # 至少包含3个关键词
                                return True
                    
                except UnicodeDecodeError:
                    continue
            
            self.logger.error("CSV文件格式验证失败：无法找到必要的标题列")
            return False
            
        except Exception as e:
            self.logger.error(f"验证CSV文件格式时出错: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> dict:
        """
        获取CSV文件信息
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            文件信息字典
        """
        info = {
            'exists': False,
            'size': 0,
            'encoding': None,
            'line_count': 0,
            'has_header': False
        }
        
        try:
            if not os.path.exists(file_path):
                return info
            
            info['exists'] = True
            info['size'] = os.path.getsize(file_path)
            
            # 检测编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        lines = f.readlines()
                        info['encoding'] = encoding
                        info['line_count'] = len(lines)
                        
                        if lines:
                            first_line = lines[0].strip()
                            info['has_header'] = any(keyword in first_line for keyword in ['工号', '姓名', '邮箱'])
                        
                        break
                        
                except UnicodeDecodeError:
                    continue
            
        except Exception as e:
            self.logger.error(f"获取文件信息时出错: {e}")
        
        return info
    
    def preview_csv_content(self, file_path: str, max_lines: int = 5) -> List[str]:
        """
        预览CSV文件内容
        
        Args:
            file_path: CSV文件路径
            max_lines: 最大预览行数
            
        Returns:
            预览内容列表
        """
        preview = []
        
        try:
            if not os.path.exists(file_path):
                return ["文件不存在"]
            
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        for i, line in enumerate(f):
                            if i >= max_lines:
                                break
                            preview.append(line.strip())
                    break
                    
                except UnicodeDecodeError:
                    continue
            
            if not preview:
                preview = ["无法读取文件内容"]
                
        except Exception as e:
            preview = [f"读取文件时出错: {e}"]
        
        return preview