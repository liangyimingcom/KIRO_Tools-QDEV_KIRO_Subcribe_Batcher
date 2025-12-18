#!/usr/bin/env python3
"""
AWS IAM Identity Center 用户订阅管理系统主程序
"""
import argparse
import sys
import os
from datetime import datetime
from typing import List, Dict

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import ConfigManager
from src.logger import setup_logging, get_logger
from src.csv_parser import CSVParser
from src.data_validator import DataValidator
from src.aws_client import AWSClient, AWSClientError
from src.user_manager import UserManager
from src.group_manager import GroupManager
from src.verification_engine import VerificationEngine
from src.report_generator import ReportGenerator
from src.user_attribute_upgrader import UserAttributeUpgrader
from src.models import BatchResult, IAMUser


class SubscriptionManager:
    """订阅管理器主类"""
    
    def __init__(self, config_file: str = None):
        # 初始化配置
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.get_config()
        
        # 设置日志
        setup_logging(self.config.logging)
        self.logger = get_logger("subscription_manager")
        
        # 初始化组件
        self.csv_parser = CSVParser(self.config)
        self.data_validator = DataValidator(self.config)
        self.verification_engine = VerificationEngine()
        self.report_generator = ReportGenerator(self.config)
        
        # AWS相关组件（延迟初始化）
        self.aws_client = None
        self.user_manager = None
        self.group_manager = None
        self.user_attribute_upgrader = None
    
    def _initialize_aws_components(self):
        """初始化AWS组件"""
        if self.aws_client is None:
            try:
                self.aws_client = AWSClient(self.config)
                self.user_manager = UserManager(self.aws_client, self.config)
                self.group_manager = GroupManager(self.aws_client, self.config)
                self.user_attribute_upgrader = UserAttributeUpgrader(self.aws_client, self.config)
                
                self.logger.info("AWS组件初始化成功")
                
            except AWSClientError as e:
                self.logger.error(f"AWS组件初始化失败: {e}")
                raise
    
    def process_subscription_file(self, csv_file: str, dry_run: bool = False, remove_users: bool = False, 
                                 sync_users: bool = False, update_to_ver0928: bool = False,
                                 verbose: bool = False, quiet: bool = False, 
                                 max_workers: int = 5, show_progress: bool = True) -> bool:
        """
        处理用户订阅文件
        
        Args:
            csv_file: CSV文件路径
            dry_run: 是否为试运行模式
            remove_users: 是否删除用户模式
            sync_users: 是否同步用户模式
            update_to_ver0928: 是否为属性升级模式
            
        Returns:
            处理是否成功
        """
        try:
            # 应用日志级别设置
            if verbose:
                import logging
                logging.getLogger().setLevel(logging.DEBUG)
                self.logger.setLevel(logging.DEBUG)
                self.logger.info("启用详细日志模式")
            elif quiet:
                import logging
                logging.getLogger().setLevel(logging.WARNING)
                self.logger.setLevel(logging.WARNING)
            
            # 验证max_workers参数
            min_workers = self.config.performance.max_workers_min
            max_workers_limit = self.config.performance.max_workers_max
            default_workers = self.config.performance.max_workers
            
            if max_workers < min_workers or max_workers > max_workers_limit:
                self.logger.warning(
                    f"max_workers参数超出范围({min_workers}-{max_workers_limit})，"
                    f"使用默认值{default_workers}"
                )
                max_workers = default_workers
            
            self.logger.info(f"开始处理用户订阅文件: {csv_file}")
            self.logger.info(f"并发线程数: {max_workers}, 显示进度: {show_progress}")
            
            # 1. 解析CSV文件
            self.logger.info("步骤1: 解析CSV文件")
            users = self.csv_parser.parse_subscription_file(csv_file)
            self.logger.info(f"解析到{len(users)}个用户")
            
            # 2. 验证数据
            self.logger.info("步骤2: 验证用户数据")
            validation_result = self.data_validator.validate_batch_data(users)
            
            if not validation_result.is_valid:
                self.logger.error("数据验证失败")
                print(self.data_validator.get_validation_summary(validation_result))
                return False
            
            if validation_result.warnings:
                self.logger.warning(f"数据验证有{len(validation_result.warnings)}个警告")
                for warning in validation_result.warnings[:5]:
                    self.logger.warning(f"  - {warning}")
            
            # 修复常见问题
            users = self.data_validator.fix_common_issues(users)
            
            if dry_run:
                if remove_users:
                    self.logger.info("试运行模式，跳过实际删除操作")
                    print(f"试运行完成，将删除{len(users)}个用户:")
                    for user in users:
                        print(f"  - {user.get_username()} ({user.name})")
                elif sync_users:
                    self.logger.info("试运行模式，跳过实际同步操作")
                    # 初始化AWS组件进行同步分析
                    self._initialize_aws_components()
                    sync_plan = self.user_manager.sync_users(users)
                    
                    print(f"试运行完成，同步计划:")
                    print(f"  新增用户: {len(sync_plan['users_to_create'])}个")
                    for user in sync_plan['users_to_create'][:5]:
                        print(f"    + {user.get_username()} ({user.name})")
                    if len(sync_plan['users_to_create']) > 5:
                        print(f"    + ... 还有{len(sync_plan['users_to_create']) - 5}个")
                    
                    print(f"  删除用户: {len(sync_plan['users_to_delete'])}个")
                    for user in sync_plan['users_to_delete'][:5]:
                        print(f"    - {user.get_username()} ({user.name})")
                    if len(sync_plan['users_to_delete']) > 5:
                        print(f"    - ... 还有{len(sync_plan['users_to_delete']) - 5}个")
                    
                    print(f"  更新用户: {len(sync_plan['users_to_update'])}个")
                    for user in sync_plan['users_to_update'][:5]:
                        print(f"    ~ {user.get_username()} ({user.name})")
                    if len(sync_plan['users_to_update']) > 5:
                        print(f"    ~ ... 还有{len(sync_plan['users_to_update']) - 5}个")
                elif update_to_ver0928:
                    self.logger.info("试运行模式，跳过实际属性升级操作")
                    # 初始化AWS组件进行升级分析
                    self._initialize_aws_components()
                    iam_users = self._get_iam_users_list()
                    upgrade_result = self.user_attribute_upgrader.upgrade_user_attributes(iam_users, users, dry_run=True)
                    
                    print(f"试运行完成，属性升级计划:")
                    print(upgrade_result.upgrade_plan.get_preview())
                else:
                    self.logger.info("试运行模式，跳过实际操作")
                    print(f"试运行完成，将处理{len(users)}个用户")
                return True
            
            # 3. 初始化AWS组件
            self.logger.info("步骤3: 初始化AWS连接")
            self._initialize_aws_components()
            
            if update_to_ver0928:
                # 属性升级模式
                self.logger.info("步骤4: 执行用户属性升级")
                
                # 获取IAM用户列表
                iam_users = self._get_iam_users_list()
                
                # 生成升级计划并确认
                upgrade_result = self.user_attribute_upgrader.upgrade_user_attributes(iam_users, users, dry_run=True)
                
                print(f"\n📋 用户属性升级计划:")
                print(upgrade_result.upgrade_plan.get_preview())
                
                if upgrade_result.upgrade_plan.total_operations == 0:
                    print("✅ 所有用户属性已是最新格式，无需升级")
                    return True
                
                confirm = input(f"\n确认执行属性升级操作吗？(输入 'UPGRADE' 确认): ")
                if confirm != 'UPGRADE':
                    print("操作已取消")
                    return False
                
                # 执行实际升级
                upgrade_result = self.user_attribute_upgrader.upgrade_user_attributes(iam_users, users, dry_run=False)
                
                # 验证升级结果
                self.logger.info("步骤5: 验证升级结果")
                verification_stats = self.user_attribute_upgrader.batch_verify_upgrades(upgrade_result.upgrade_operations)
                
                print(f"\n📊 升级验证结果:")
                print(f"  验证总数: {verification_stats['total_verified']}")
                print(f"  验证通过: {verification_stats['passed_verification']}")
                print(f"  验证失败: {verification_stats['failed_verification']}")
                
                if verification_stats['verification_errors']:
                    print(f"\n⚠️  验证错误:")
                    for error in verification_stats['verification_errors'][:5]:
                        print(f"  - {error}")
                    if len(verification_stats['verification_errors']) > 5:
                        print(f"  - ... 还有{len(verification_stats['verification_errors']) - 5}个错误")
                
                # 构造批量结果
                user_batch_result = BatchResult(
                    total_operations=upgrade_result.total_users,
                    successful_operations=upgrade_result.successful_upgrades,
                    failed_operations=upgrade_result.failed_upgrades,
                    operation_results=upgrade_result.upgrade_operations
                )
                group_batch_result = BatchResult(0, 0, 0, [])  # 升级模式不涉及组操作
                
            elif remove_users:
                # 删除用户模式
                self.logger.info("步骤4: 删除用户")
                
                # 确认删除操作
                print(f"\n⚠️  警告：即将删除{len(users)}个用户:")
                for user in users[:5]:  # 只显示前5个
                    print(f"  - {user.get_username()} ({user.name})")
                if len(users) > 5:
                    print(f"  - ... 还有{len(users) - 5}个用户")
                
                confirm = input("\n确认删除这些用户吗？(输入 'DELETE' 确认): ")
                if confirm != 'DELETE':
                    print("操作已取消")
                    return False
                
                user_batch_result = self.user_manager.batch_delete_users(users)
                group_batch_result = BatchResult(0, 0, 0, [])  # 删除模式不需要组操作
            elif sync_users:
                # 同步用户模式
                self.logger.info("步骤4: 分析用户同步计划")
                sync_plan = self.user_manager.sync_users(users)
                
                # 显示同步计划并确认
                print(f"\n📋 用户同步计划:")
                print(f"  新增用户: {len(sync_plan['users_to_create'])}个")
                print(f"  删除用户: {len(sync_plan['users_to_delete'])}个")
                print(f"  更新用户: {len(sync_plan['users_to_update'])}个")
                print(f"  总操作数: {sync_plan['total_operations']}个")
                
                if sync_plan['total_operations'] == 0:
                    print("✅ 用户已同步，无需任何操作")
                    return True
                
                confirm = input(f"\n确认执行同步操作吗？(输入 'SYNC' 确认): ")
                if confirm != 'SYNC':
                    print("操作已取消")
                    return False
                
                self.logger.info("步骤5: 执行用户同步")
                # 创建性能指标收集器
                from src.performance_metrics import PerformanceMetrics
                from src.data_cache import DataCache
                
                performance_metrics = PerformanceMetrics()
                performance_metrics.start_phase("总体同步")
                
                # 创建共享的DataCache实例
                self.logger.info("创建共享数据缓存...")
                shared_cache = DataCache()
                performance_metrics.start_phase("数据缓存初始化")
                shared_cache.initialize(self.aws_client)
                performance_metrics.end_phase("数据缓存初始化")
                
                sync_results = self.user_manager.execute_sync_plan(
                    sync_plan,
                    shared_cache=shared_cache,  # 传递共享缓存
                    max_workers=max_workers,
                    show_progress=show_progress,
                    performance_metrics=performance_metrics
                )
                
                performance_metrics.end_phase("总体同步")
                
                # 处理组订阅（仅对新增和更新的用户）
                self.logger.info("步骤6: 处理组订阅关系")
                subscription_users = sync_plan['users_to_create'] + sync_plan['users_to_update']
                if subscription_users:
                    group_batch_result = self.group_manager.batch_update_subscriptions(
                        subscription_users,
                        data_cache=shared_cache  # 传递共享缓存
                    )
                else:
                    group_batch_result = BatchResult(0, 0, 0, [])
                
                # 清理缓存
                shared_cache.clear()
                
                # 构造用户批量结果（合并同步结果）
                all_operations = (sync_results['create_results'] + 
                                sync_results['update_results'] + 
                                sync_results['delete_results'])
                user_batch_result = BatchResult(
                    total_operations=len(all_operations),
                    successful_operations=sync_results['total_successful'],
                    failed_operations=sync_results['total_failed'],
                    operation_results=all_operations
                )
            else:
                # 正常处理模式
                # 4. 处理用户信息
                self.logger.info("步骤4: 处理用户信息")
                user_batch_result = self.user_manager.batch_process_users(users)
                
                # 5. 处理组订阅
                self.logger.info("步骤5: 处理组订阅关系")
                group_batch_result = self.group_manager.batch_update_subscriptions(users)
            
            # 6. 生成更新报告
            self.logger.info("步骤6: 生成更新报告")
            if update_to_ver0928:
                # 生成属性升级报告
                update_report = self.report_generator.generate_upgrade_report(upgrade_result)
            else:
                # 生成常规更新报告
                all_operations = user_batch_result.operation_results + group_batch_result.operation_results
                # 如果有性能数据，集成到报告中
                performance_data = None
                if sync_users and 'performance_metrics' in locals():
                    performance_metrics.set_end_time()  # 设置结束时间
                    performance_data = performance_metrics.generate_report()
                    self.logger.info("性能指标已生成")
                    # 输出性能摘要到日志
                    self.logger.info(performance_metrics.get_summary_text())
                
                # 使用带超时保护的报告生成
                update_report = self.report_generator.generate_update_report_with_timeout(
                    all_operations, 
                    performance_data,
                    timeout=self.config.timeouts.report_generation
                )
            
            # 保存更新报告
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if remove_users:
                report_prefix = "delete_report"
            elif sync_users:
                report_prefix = "sync_report"
            elif update_to_ver0928:
                report_prefix = "upgrade_report"
            else:
                report_prefix = "update_report"
            update_report_file = f"reports/{report_prefix}_{timestamp}.md"
            self.report_generator.save_report_to_file(update_report, update_report_file)
            
            # 生成执行记录
            if sync_users and 'performance_metrics' in locals():
                self.logger.info("生成执行记录文件")
                all_operations = user_batch_result.operation_results + group_batch_result.operation_results
                performance_data = performance_metrics.generate_report()
                execution_record = self.report_generator.generate_execution_record(
                    all_operations,
                    performance_data
                )
                execution_record_file = f"reports/execution_record_{timestamp}.md"
                self.report_generator.save_report_to_file(execution_record, execution_record_file)
                
                # 生成失败用户列表文件
                failed_users = self.user_manager.get_failed_users()
                if failed_users:
                    self.logger.info(f"生成失败用户列表文件，共 {len(failed_users)} 个失败用户")
                    failed_users_file = f"reports/failed_users_{timestamp}.csv"
                    self.report_generator.generate_failed_users_csv(failed_users, failed_users_file)
            
            # 7. 校验对比
            if not remove_users and not sync_users and not update_to_ver0928:
                self.logger.info("步骤7: 执行校验对比")
                verification_result = self._perform_verification(users)
            else:
                # 删除模式、同步模式和升级模式不需要校验
                from src.models import VerificationResult
                verification_result = VerificationResult(
                    total_users=0,
                    matched_users=0,
                    mismatched_users=[],
                    group_verification={},
                    consistency_rate=1.0
                )
            
            # 生成校验报告
            if not remove_users and not sync_users and not update_to_ver0928:
                verification_report = self.report_generator.generate_verification_report(verification_result)
                verification_report_file = f"reports/verification_report_{timestamp}.md"
                self.report_generator.save_report_to_file(verification_report, verification_report_file)
            
            # 输出结果摘要
            self._print_summary(user_batch_result, group_batch_result, verification_result)
            
            self.logger.info("用户订阅处理完成")
            return True
            
        except Exception as e:
            self.logger.error(f"处理用户订阅文件失败: {e}")
            return False
    
    def _perform_verification(self, csv_users):
        """执行校验对比"""
        try:
            # 获取当前IAM用户
            iam_users = self.user_manager.get_existing_users()
            
            # 对比用户信息
            comparison_result = self.verification_engine.compare_users(csv_users, iam_users)
            
            # 构建预期和实际的组成员关系
            expected_groups = {}
            actual_groups = {}
            
            # 预期的组成员关系
            for user in csv_users:
                target_groups = user.get_target_groups()
                for group_name in target_groups:
                    if group_name not in expected_groups:
                        expected_groups[group_name] = []
                    expected_groups[group_name].append(user.get_username())
            
            # 实际的组成员关系
            for group_name in [self.config.groups.kiro, self.config.groups.qdev]:
                actual_groups[group_name] = self.group_manager.get_group_members(group_name)
            
            # 验证组成员关系
            verification_result = self.verification_engine.verify_group_memberships(
                expected_groups, actual_groups
            )
            
            return verification_result
            
        except Exception as e:
            self.logger.error(f"校验对比失败: {e}")
            # 返回空的验证结果
            from src.models import VerificationResult
            return VerificationResult(
                total_users=0,
                matched_users=0,
                mismatched_users=[],
                group_verification={},
                consistency_rate=0.0
            )
    
    def _get_iam_users_list(self) -> List[IAMUser]:
        """获取IAM用户列表"""
        try:
            raw_users = self.aws_client.list_users()
            iam_users = []
            
            for user_data in raw_users:
                # 获取用户的组成员关系
                user_groups = []
                try:
                    memberships = self.aws_client.get_user_group_memberships(user_data['UserId'])
                    for membership in memberships:
                        group_id = membership.get('GroupId')
                        if group_id:
                            # 获取组名
                            groups = self.aws_client.list_groups()
                            for group in groups:
                                if group['GroupId'] == group_id:
                                    user_groups.append(group['DisplayName'])
                                    break
                except Exception as e:
                    self.logger.warning(f"获取用户 {user_data['UserId']} 的组信息失败: {e}")
                
                # 提取用户信息
                iam_user = IAMUser(
                    user_id=user_data['UserId'],
                    username=user_data.get('UserName', ''),
                    email=self._extract_primary_email(user_data.get('Emails', [])),
                    first_name=user_data.get('Name', {}).get('GivenName', ''),
                    last_name=user_data.get('Name', {}).get('FamilyName', ''),
                    display_name=user_data.get('DisplayName', ''),
                    groups=user_groups
                )
                iam_users.append(iam_user)
            
            return iam_users
            
        except Exception as e:
            self.logger.error(f"获取IAM用户列表失败: {e}")
            return []
    
    def _extract_primary_email(self, emails: List[Dict]) -> str:
        """从邮箱列表中提取主邮箱"""
        if not emails:
            return ""
        
        # 查找主邮箱
        for email in emails:
            if email.get('Primary', False):
                return email.get('Value', '')
        
        # 如果没有主邮箱，返回第一个邮箱
        return emails[0].get('Value', '') if emails else ""
    
    def _print_summary(self, user_result, group_result, verification_result):
        """打印结果摘要"""
        print("\n" + "="*60)
        print("处理结果摘要")
        print("="*60)
        
        print(f"\n用户操作:")
        print(f"  总数: {user_result.total_operations}")
        print(f"  成功: {user_result.successful_operations}")
        print(f"  失败: {user_result.failed_operations}")
        print(f"  成功率: {user_result.success_rate:.1%}")
        
        print(f"\n组操作:")
        print(f"  总数: {group_result.total_operations}")
        print(f"  成功: {group_result.successful_operations}")
        print(f"  失败: {group_result.failed_operations}")
        print(f"  成功率: {group_result.success_rate:.1%}")
        
        print(f"\n校验结果:")
        print(f"  一致性率: {verification_result.consistency_rate:.1%}")
        print(f"  总用户数: {verification_result.total_users}")
        
        if verification_result.group_verification:
            for group_name, group_verify in verification_result.group_verification.items():
                status = "✅" if group_verify.is_consistent else "❌"
                print(f"  {status} {group_name}: {len(group_verify.expected_members)}预期 / {len(group_verify.actual_members)}实际")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AWS IAM Identity Center 用户订阅管理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py process user_list.csv
  python main.py process user_list.csv --dry-run
  python main.py process user_list.csv --config custom_config.yaml
  python main.py process user_list.csv --update2ver0928
  python main.py process user_list.csv --update2ver0928 --dry-run
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # process命令
    process_parser = subparsers.add_parser('process', help='处理用户订阅文件')
    process_parser.add_argument('csv_file', help='用户清单订阅表CSV文件路径')
    process_parser.add_argument('--config', '-c', help='配置文件路径')
    process_parser.add_argument('--dry-run', action='store_true', help='试运行模式，不执行实际操作')
    process_parser.add_argument('--removeusers', action='store_true', help='删除用户模式，删除CSV文件中列出的用户')
    process_parser.add_argument('--syncusers', action='store_true', help='同步用户模式，同步CSV文件与IAM Identity Center中的用户')
    process_parser.add_argument('--update2ver0928', action='store_true', help='属性升级模式，将用户属性升级到配置的新用户名格式（如 工号@domain）')
    
    # 性能和日志控制参数
    log_group = process_parser.add_mutually_exclusive_group()
    log_group.add_argument('--verbose', action='store_true', help='详细日志模式，记录每个API调用和操作详情')
    log_group.add_argument('--quiet', action='store_true', help='简化日志模式，仅显示关键信息和错误')
    process_parser.add_argument('--max-workers', type=int, default=5, metavar='N',
                               help='并发线程数（默认5，范围1-10）')
    process_parser.add_argument('--no-progress', action='store_true', help='不显示进度信息')
    
    # test命令
    test_parser = subparsers.add_parser('test', help='测试AWS连接')
    test_parser.add_argument('--config', '-c', help='配置文件路径')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        manager = SubscriptionManager(args.config)
        
        if args.command == 'process':
            if not os.path.exists(args.csv_file):
                print(f"错误: CSV文件不存在: {args.csv_file}")
                return 1
            
            # 检查互斥参数
            exclusive_params = [args.removeusers, args.syncusers, args.update2ver0928]
            if sum(exclusive_params) > 1:
                print("错误: --removeusers, --syncusers 和 --update2ver0928 不能同时使用")
                return 1
            
            # 获取日志和性能参数
            verbose = getattr(args, 'verbose', False)
            quiet = getattr(args, 'quiet', False)
            max_workers = getattr(args, 'max_workers', 5)
            show_progress = not getattr(args, 'no_progress', False)
            
            success = manager.process_subscription_file(
                args.csv_file, 
                args.dry_run, 
                args.removeusers, 
                args.syncusers, 
                args.update2ver0928,
                verbose=verbose,
                quiet=quiet,
                max_workers=max_workers,
                show_progress=show_progress
            )
            return 0 if success else 1
            
        elif args.command == 'test':
            manager._initialize_aws_components()
            if manager.aws_client.test_connection():
                print("✅ AWS连接测试成功")
                client_info = manager.aws_client.get_client_info()
                print(f"Profile: {client_info['profile']}")
                print(f"Region: {client_info['region']}")
                print(f"Identity Store ID: {client_info['identity_store_id']}")
                return 0
            else:
                print("❌ AWS连接测试失败")
                return 1
    
    except KeyboardInterrupt:
        print("\n操作被用户中断")
        return 1
    except Exception as e:
        print(f"程序执行失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())