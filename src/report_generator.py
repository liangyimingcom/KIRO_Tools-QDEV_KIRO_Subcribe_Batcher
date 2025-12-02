"""
报告生成器模块
"""
import os
from datetime import datetime
from typing import List
from src.models import OperationResult, VerificationResult, BatchResult, UpgradeResult
from src.logger import get_logger


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        self.logger = get_logger("report_generator")
    
    def generate_update_report_with_timeout(self, operations: List[OperationResult],
                                           performance_data: dict = None,
                                           timeout: int = 120) -> str:
        """
        带超时保护的报告生成
        
        Args:
            operations: 操作结果列表
            performance_data: 性能数据（可选）
            timeout: 超时时间（秒），默认120秒
            
        Returns:
            报告内容
            
        优化点：
        1. 设置超时限制，防止报告生成卡住
        2. 超时时自动生成简化报告
        3. 记录超时警告日志
        """
        import signal
        import threading
        
        # 用于存储报告结果
        result = {'report': None, 'error': None}
        
        def generate_report_thread():
            """在线程中生成报告"""
            try:
                result['report'] = self.generate_update_report(operations, performance_data)
            except Exception as e:
                result['error'] = str(e)
                self.logger.error(f"报告生成异常: {e}")
        
        # 创建并启动线程
        thread = threading.Thread(target=generate_report_thread)
        thread.daemon = True
        thread.start()
        
        # 等待线程完成或超时
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            # 超时了，生成简化报告
            self.logger.warning(f"报告生成超时({timeout}秒)，生成简化报告")
            return self.generate_simplified_report(operations, performance_data)
        
        if result['error']:
            # 发生错误，生成简化报告
            self.logger.error(f"报告生成失败: {result['error']}，生成简化报告")
            return self.generate_simplified_report(operations, performance_data)
        
        return result['report']
    
    def generate_simplified_report(self, operations: List[OperationResult],
                                   performance_data: dict = None) -> str:
        """
        生成简化报告（用于超时或错误情况）
        
        Args:
            operations: 操作结果列表
            performance_data: 性能数据（可选）
            
        Returns:
            简化报告内容
        """
        self.logger.info("生成简化报告")
        
        report = []
        report.append("# AWS IAM Identity Center 用户订阅更新报告（简化版）")
        report.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n**注意**: 由于报告生成超时或异常，此为简化版本报告")
        
        # 基本统计
        total = len(operations)
        successful = sum(1 for op in operations if op.success)
        failed = total - successful
        
        report.append(f"\n## 操作统计")
        report.append(f"- 总操作数: {total}")
        report.append(f"- 成功操作: {successful}")
        report.append(f"- 失败操作: {failed}")
        report.append(f"- 成功率: {successful/total*100:.1f}%" if total > 0 else "- 成功率: 0%")
        
        # 性能摘要
        if performance_data:
            total_duration = performance_data.get('total_duration', 0)
            report.append(f"\n## 性能摘要")
            report.append(f"- 总耗时: {total_duration:.2f}秒")
            
            users_per_second = performance_data.get('users_per_second', 0)
            if users_per_second > 0:
                report.append(f"- 处理速度: {users_per_second:.2f} 用户/秒")
        
        # 只显示失败的操作
        failed_ops = [op for op in operations if not op.success]
        if failed_ops:
            report.append(f"\n## 失败操作列表")
            for op in failed_ops:
                report.append(f"- ❌ {op.target} ({op.operation_type}): {op.message}")
        else:
            report.append(f"\n## 操作结果")
            report.append(f"✅ 所有操作均成功完成！")
        
        return "\n".join(report)
    
    def generate_update_report(self, operations: List[OperationResult], 
                              performance_data: dict = None,
                              simplified: bool = False) -> str:
        """
        生成更新说明报告（优化版本）
        
        Args:
            operations: 操作结果列表
            performance_data: 性能数据（可选）
            simplified: 是否生成简化报告（默认False）
        
        优化点：
        1. 限制详细日志数量，只保留失败用户的详细信息
        2. 省略API调用详情和中间步骤（在简化模式下）
        3. 使用生成器逐段生成，避免大量字符串拼接
        """
        self.logger.info(f"开始生成报告，操作数: {len(operations)}, 简化模式: {simplified}")
        
        report = []
        report.append("# AWS IAM Identity Center 用户订阅更新报告")
        report.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 统计信息
        total = len(operations)
        successful = sum(1 for op in operations if op.success)
        failed = total - successful
        
        report.append(f"\n## 操作统计")
        report.append(f"- 总操作数: {total}")
        report.append(f"- 成功操作: {successful}")
        report.append(f"- 失败操作: {failed}")
        report.append(f"- 成功率: {successful/total*100:.1f}%" if total > 0 else "- 成功率: 0%")
        
        self.logger.info("报告统计信息已生成")
        
        # 性能数据
        if performance_data:
            report.append(f"\n## 性能指标")
            
            # 总耗时
            total_duration = performance_data.get('total_duration', 0)
            report.append(f"\n### 总体性能")
            report.append(f"- 总耗时: {total_duration:.2f}秒")
            
            # 每秒处理用户数
            users_per_second = performance_data.get('users_per_second', 0)
            if users_per_second > 0:
                report.append(f"- 处理速度: {users_per_second:.2f} 用户/秒")
            
            # 各阶段耗时
            if 'phases' in performance_data and performance_data['phases']:
                report.append(f"\n### 各阶段耗时")
                for phase_name, duration in performance_data['phases'].items():
                    percentage = (duration / total_duration * 100) if total_duration > 0 else 0
                    report.append(f"- {phase_name}: {duration:.2f}秒 ({percentage:.1f}%)")
            
            # API调用统计（简化模式下省略详细信息）
            if 'api_calls' in performance_data:
                api_data = performance_data['api_calls']
                report.append(f"\n### API调用统计")
                report.append(f"- 总调用次数: {api_data.get('total', 0)}")
                report.append(f"- 成功调用: {api_data.get('success', 0)}")
                report.append(f"- 失败调用: {api_data.get('failed', 0)}")
                report.append(f"- 成功率: {api_data.get('success_rate', 0):.1f}%")
                
                # 非简化模式下显示详细API调用统计
                if not simplified and 'details' in api_data and api_data['details']:
                    report.append(f"\n#### API调用详细统计")
                    for api_type, stats in api_data['details'].items():
                        report.append(f"- {api_type}: {stats['success']}/{stats['total']} "
                                    f"(成功率: {stats['success_rate']:.1f}%)")
            
            # 缓存统计
            if 'cache_stats' in performance_data:
                cache = performance_data['cache_stats']
                if cache.get('total', 0) > 0:
                    report.append(f"\n### 缓存统计")
                    report.append(f"- 命中率: {cache['hit_rate']:.1f}%")
                    report.append(f"- 命中次数: {cache['hits']}")
                    report.append(f"- 未命中次数: {cache['misses']}")
            
            # 性能对比
            if 'performance_comparison' in performance_data:
                comp = performance_data['performance_comparison']
                if comp.get('estimated_old_time', 0) > 0:
                    report.append(f"\n### 性能对比（优化前 vs 优化后）")
                    report.append(f"- 优化前预估耗时: {comp['estimated_old_time']:.2f}秒")
                    report.append(f"- 优化后实际耗时: {comp['actual_time']:.2f}秒")
                    report.append(f"- 性能提升: {comp['improvement_percentage']:.1f}%")
                    report.append(f"- 加速倍数: {comp['speedup_factor']:.1f}x")
            
            # 用户操作统计
            if 'operations' in performance_data:
                report.append(f"\n### 用户操作统计")
                for op_type, stats in performance_data['operations'].items():
                    if stats['total'] > 0:
                        report.append(f"- {op_type}: {stats['success']}/{stats['total']} "
                                    f"(成功率: {stats['success_rate']:.1f}%)")
        
        self.logger.info("报告性能指标已生成")
        
        # 按操作类型分组（添加进度日志）
        op_types = {}
        failed_operations = []  # 只收集失败的操作
        
        self.logger.info(f"开始处理操作结果，共 {len(operations)} 个操作")
        
        for idx, op in enumerate(operations):
            # 每处理100个操作输出一次进度
            if idx > 0 and idx % 100 == 0:
                self.logger.info(f"报告生成进度: 已处理 {idx}/{len(operations)} 个操作")
            
            op_type = op.operation_type
            if op_type not in op_types:
                op_types[op_type] = {'success': 0, 'failed': 0}
            
            if op.success:
                op_types[op_type]['success'] += 1
            else:
                op_types[op_type]['failed'] += 1
                failed_operations.append(op)  # 收集失败操作
        
        self.logger.info(f"操作结果处理完成，失败操作数: {len(failed_operations)}")
        
        # 详细操作结果（只显示失败的操作）
        if failed_operations:
            report.append(f"\n## 失败操作详情")
            report.append(f"\n共 {len(failed_operations)} 个失败操作：")
            
            for op in failed_operations:
                status = "❌"
                report.append(f"- {status} {op.target} ({op.operation_type}): {op.message}")
                
                # 显示详细错误信息
                if op.details:
                    for key, value in op.details.items():
                        report.append(f"  - {key}: {value}")
        else:
            report.append(f"\n## 操作结果")
            report.append(f"\n✅ 所有操作均成功完成！")
        
        # 操作类型统计摘要
        if op_types:
            report.append(f"\n## 按操作类型统计")
            for op_type, data in op_types.items():
                total_type = data['success'] + data['failed']
                success_rate = data['success'] / total_type * 100 if total_type > 0 else 0
                report.append(f"- {op_type}: {data['success']}/{total_type} "
                            f"(成功率: {success_rate:.1f}%)")
        
        self.logger.info("报告生成完成")
        
        return "\n".join(report)
    
    def generate_verification_report(self, verification: VerificationResult) -> str:
        """生成校验对比报告"""
        report = []
        report.append("# AWS IAM Identity Center 校验对比报告")
        report.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 总体一致性
        report.append(f"\n## 总体一致性")
        report.append(f"- 一致性率: {verification.consistency_rate*100:.1f}%")
        report.append(f"- 总用户数: {verification.total_users}")
        report.append(f"- 匹配用户数: {verification.matched_users}")
        
        if verification.mismatched_users:
            report.append(f"- 不匹配用户: {len(verification.mismatched_users)}")
        
        # 组验证详情
        if verification.group_verification:
            report.append(f"\n## 组成员关系验证")
            
            for group_name, group_verify in verification.group_verification.items():
                status = "✅" if group_verify.is_consistent else "❌"
                report.append(f"\n### {status} {group_name}")
                report.append(f"- 预期成员数: {len(group_verify.expected_members)}")
                report.append(f"- 实际成员数: {len(group_verify.actual_members)}")
                
                if group_verify.missing_members:
                    report.append(f"- 缺失成员: {', '.join(group_verify.missing_members)}")
                
                if group_verify.extra_members:
                    report.append(f"- 多余成员: {', '.join(group_verify.extra_members)}")
        
        return "\n".join(report)
    
    def generate_upgrade_report(self, upgrade_result: UpgradeResult) -> str:
        """生成属性升级报告"""
        report = []
        report.append("# AWS IAM Identity Center 用户属性升级报告")
        report.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 升级统计
        report.append(f"\n## 升级统计")
        report.append(f"- 总用户数: {upgrade_result.total_users}")
        report.append(f"- 成功升级: {upgrade_result.successful_upgrades}")
        report.append(f"- 失败升级: {upgrade_result.failed_upgrades}")
        report.append(f"- 成功率: {upgrade_result.success_rate*100:.1f}%")
        
        if upgrade_result.upgrade_plan:
            report.append(f"- 总操作数: {upgrade_result.upgrade_plan.total_operations}")
            report.append(f"- 预估时间: {upgrade_result.upgrade_plan.estimated_time}秒")
        
        # 升级详情
        if upgrade_result.upgrade_operations:
            report.append(f"\n## 升级操作详情")
            
            # 成功的升级
            successful_ops = [op for op in upgrade_result.upgrade_operations if op.success]
            if successful_ops:
                report.append(f"\n### ✅ 成功升级的用户 ({len(successful_ops)}个)")
                for op in successful_ops[:20]:  # 显示前20个
                    report.append(f"- {op.target}: {op.message}")
                    
                    # 显示属性变更详情
                    if op.details and 'old_attributes' in op.details and 'new_attributes' in op.details:
                        old_attrs = op.details['old_attributes']
                        new_attrs = op.details['new_attributes']
                        
                        report.append(f"  - 用户名: {old_attrs.get('username', 'N/A')} → {new_attrs.get('username', 'N/A')}")
                        report.append(f"  - 显示名: {old_attrs.get('display_name', 'N/A')} → {new_attrs.get('display_name', 'N/A')}")
                        report.append(f"  - 姓名: {old_attrs.get('first_name', 'N/A')} {old_attrs.get('last_name', 'N/A')} → {new_attrs.get('first_name', 'N/A')} {new_attrs.get('last_name', 'N/A')}")
                        
                        if old_attrs.get('email') != new_attrs.get('email'):
                            report.append(f"  - 邮箱: {old_attrs.get('email', 'N/A')} → {new_attrs.get('email', 'N/A')}")
                
                if len(successful_ops) > 20:
                    report.append(f"- ... 还有{len(successful_ops) - 20}个成功升级的用户")
            
            # 失败的升级
            failed_ops = [op for op in upgrade_result.upgrade_operations if not op.success]
            if failed_ops:
                report.append(f"\n### ❌ 升级失败的用户 ({len(failed_ops)}个)")
                for op in failed_ops:
                    report.append(f"- {op.target}: {op.message}")
                    
                    # 显示错误详情
                    if op.details and 'error' in op.details:
                        report.append(f"  - 错误: {op.details['error']}")
        
        # 升级前后格式对比说明
        report.append(f"\n## 属性格式说明")
        report.append(f"\n### 新格式标准")
        report.append(f"- **Username**: 工号@haier-saml.com")
        report.append(f"- **First name**: 工号")
        report.append(f"- **Last name**: 中文姓名")
        report.append(f"- **Display name**: 工号_中文姓名")
        report.append(f"- **Email**: 保持原有邮箱地址不变")
        
        report.append(f"\n### 升级示例")
        report.append(f"```")
        report.append(f"升级前:")
        report.append(f"  Username: 20117703")
        report.append(f"  Display name: 王晓莲")
        report.append(f"  First name: 王")
        report.append(f"  Last name: 晓莲")
        report.append(f"")
        report.append(f"升级后:")
        report.append(f"  Username: 20117703@haier-saml.com")
        report.append(f"  Display name: 20117703_王晓莲")
        report.append(f"  First name: 20117703")
        report.append(f"  Last name: 王晓莲")
        report.append(f"```")
        
        return "\n".join(report)
    
    def generate_execution_record(self, operations: List[OperationResult], 
                                 performance_data: dict = None) -> str:
        """
        生成执行记录文件
        
        Args:
            operations: 操作结果列表
            performance_data: 性能数据（可选）
            
        Returns:
            执行记录的Markdown格式文本
        """
        report = []
        report.append("# 用户同步执行记录")
        report.append(f"\n**执行时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 统计信息
        total = len(operations)
        successful = sum(1 for op in operations if op.success)
        failed = total - successful
        
        report.append(f"\n## 执行摘要")
        report.append(f"- 总操作数: {total}")
        report.append(f"- 成功操作: {successful}")
        report.append(f"- 失败操作: {failed}")
        report.append(f"- 成功率: {successful/total*100:.1f}%" if total > 0 else "- 成功率: 0%")
        
        # 性能数据
        if performance_data:
            report.append(f"\n## 性能指标")
            if 'phases' in performance_data:
                report.append(f"\n### 各阶段耗时")
                for phase_name, duration in performance_data['phases'].items():
                    # duration 直接是 float 类型，不是字典
                    report.append(f"- {phase_name}: {duration:.2f}秒")
            
            if 'api_calls' in performance_data:
                api_data = performance_data['api_calls']
                report.append(f"\n### API调用统计")
                report.append(f"- 总调用次数: {api_data.get('total', 0)}")
                report.append(f"- 成功调用: {api_data.get('success', 0)}")
                report.append(f"- 失败调用: {api_data.get('failed', 0)}")
        
        # 成功处理的用户列表 - 完整记录所有成功操作
        successful_ops = [op for op in operations if op.success]
        if successful_ops:
            report.append(f"\n## 成功处理的用户 ({len(successful_ops)}个)")
            report.append(f"\n| 用户名 | 操作类型 | 消息 | 时间 |")
            report.append(f"|--------|---------|------|------|")
            
            # 记录所有成功操作，不再限制数量
            for op in successful_ops:
                timestamp = op.timestamp.strftime('%H:%M:%S') if op.timestamp else 'N/A'
                # 截断过长的消息，但保留完整的用户信息
                message = op.message[:100] if len(op.message) > 100 else op.message
                report.append(f"| {op.target} | {op.operation_type} | {message} | {timestamp} |")
        
        # 失败处理的用户列表
        failed_ops = [op for op in operations if not op.success]
        if failed_ops:
            report.append(f"\n## 失败处理的用户 ({len(failed_ops)}个)")
            report.append(f"\n| 用户名 | 操作类型 | 失败原因 | 时间 |")
            report.append(f"|--------|---------|---------|------|")
            for op in failed_ops:
                timestamp = op.timestamp.strftime('%H:%M:%S') if op.timestamp else 'N/A'
                report.append(f"| {op.target} | {op.operation_type} | {op.message} | {timestamp} |")
        
        # 按操作类型分组统计
        op_types = {}
        for op in operations:
            op_type = op.operation_type
            if op_type not in op_types:
                op_types[op_type] = {'success': 0, 'failed': 0}
            
            if op.success:
                op_types[op_type]['success'] += 1
            else:
                op_types[op_type]['failed'] += 1
        
        if op_types:
            report.append(f"\n## 按操作类型统计")
            report.append(f"\n| 操作类型 | 成功 | 失败 | 总计 | 成功率 |")
            report.append(f"|---------|------|------|------|--------|")
            for op_type, data in op_types.items():
                total_type = data['success'] + data['failed']
                success_rate = data['success'] / total_type * 100 if total_type > 0 else 0
                report.append(f"| {op_type} | {data['success']} | {data['failed']} | {total_type} | {success_rate:.1f}% |")
        
        return "\n".join(report)
    
    def generate_failed_users_csv(self, failed_users: List, filename: str) -> bool:
        """
        生成失败用户列表CSV文件
        
        Args:
            failed_users: 失败用户记录列表（FailedUserRecord对象）
            filename: CSV文件路径
            
        Returns:
            是否成功生成
        """
        try:
            import csv
            
            # 确保目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                
                # 写入表头
                writer.writerow([
                    '用户名',
                    '操作类型',
                    '错误代码',
                    '错误信息',
                    '重试次数',
                    '时间戳',
                    '修复建议'
                ])
                
                # 写入失败用户数据
                for failed_user in failed_users:
                    writer.writerow([
                        failed_user.username,
                        failed_user.operation_type,
                        failed_user.error_code,
                        failed_user.error_message,
                        failed_user.retry_count,
                        failed_user.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        failed_user.suggested_fix
                    ])
            
            self.logger.info(f"失败用户列表已保存到: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"生成失败用户列表失败: {e}")
            return False
    
    def save_report_to_file(self, report: str, filename: str) -> bool:
        """保存报告到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            self.logger.info(f"报告已保存到: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存报告失败: {e}")
            return False