"""
性能指标收集模块
用于收集和统计用户同步操作的性能指标
"""
import threading
import time
from typing import Dict, List
from datetime import datetime
from src.logger import get_logger


class PerformanceMetrics:
    """
    性能指标收集类
    
    职责：
    1. 记录各阶段的耗时
    2. 统计API调用次数和成功率
    3. 统计用户操作（创建/更新/删除）的数量和成功率
    4. 生成性能报告
    
    线程安全：使用Lock保护所有共享数据
    """
    
    def __init__(self):
        """初始化性能指标收集器"""
        self._phases: Dict[str, Dict] = {}
        self._api_calls: Dict[str, int] = {
            'total': 0,
            'success': 0,
            'failed': 0
        }
        self._api_response_times: List[float] = []
        self._operations: Dict[str, Dict[str, int]] = {
            'create': {'total': 0, 'success': 0, 'failed': 0},
            'update': {'total': 0, 'success': 0, 'failed': 0},
            'delete': {'total': 0, 'success': 0, 'failed': 0}
        }
        # 新增：缓存命中率统计
        self._cache_stats: Dict[str, int] = {
            'hits': 0,
            'misses': 0,
            'total': 0
        }
        # 新增：API调用详细统计（按API类型分类）
        self._api_call_details: Dict[str, Dict[str, int]] = {}
        self._lock = threading.Lock()
        self._start_time = None
        self._end_time = None
        self.logger = get_logger("performance_metrics")
    
    def start_phase(self, phase_name: str):
        """
        开始一个阶段
        
        Args:
            phase_name: 阶段名称（如"数据获取"、"用户处理"、"组处理"）
        """
        with self._lock:
            if phase_name not in self._phases:
                self._phases[phase_name] = {}
            self._phases[phase_name]['start'] = time.time()
            self.logger.info(f"阶段开始: {phase_name}")
    
    def end_phase(self, phase_name: str):
        """
        结束一个阶段
        
        Args:
            phase_name: 阶段名称
        """
        with self._lock:
            if phase_name not in self._phases:
                self.logger.warning(f"阶段{phase_name}未开始，无法结束")
                return
            
            if 'start' not in self._phases[phase_name]:
                self.logger.warning(f"阶段{phase_name}没有开始时间")
                return
            
            self._phases[phase_name]['end'] = time.time()
            self._phases[phase_name]['duration'] = (
                self._phases[phase_name]['end'] - 
                self._phases[phase_name]['start']
            )
            self.logger.info(f"阶段完成: {phase_name}, "
                           f"耗时: {self._phases[phase_name]['duration']:.2f}秒")
    
    def record_api_call(self, success: bool, response_time: float = None, api_type: str = None):
        """
        记录API调用
        
        Args:
            success: 是否成功
            response_time: 响应时间（秒）
            api_type: API类型（如'list_users', 'get_user', 'update_user'等）
        """
        with self._lock:
            self._api_calls['total'] += 1
            if success:
                self._api_calls['success'] += 1
            else:
                self._api_calls['failed'] += 1
            
            if response_time is not None:
                self._api_response_times.append(response_time)
            
            # 记录API调用详细统计
            if api_type:
                if api_type not in self._api_call_details:
                    self._api_call_details[api_type] = {
                        'total': 0,
                        'success': 0,
                        'failed': 0
                    }
                self._api_call_details[api_type]['total'] += 1
                if success:
                    self._api_call_details[api_type]['success'] += 1
                else:
                    self._api_call_details[api_type]['failed'] += 1
    
    def record_cache_hit(self):
        """记录缓存命中"""
        with self._lock:
            self._cache_stats['hits'] += 1
            self._cache_stats['total'] += 1
    
    def record_cache_miss(self):
        """记录缓存未命中"""
        with self._lock:
            self._cache_stats['misses'] += 1
            self._cache_stats['total'] += 1
    
    def get_cache_hit_rate(self) -> float:
        """
        获取缓存命中率
        
        Returns:
            缓存命中率（0-100），如果没有缓存访问则返回0
        """
        with self._lock:
            total = self._cache_stats['total']
            if total == 0:
                return 0.0
            return (self._cache_stats['hits'] / total) * 100
    
    def get_users_per_second(self) -> float:
        """
        计算每秒处理用户数
        
        Returns:
            每秒处理用户数，如果总耗时为0则返回0
        """
        with self._lock:
            # 直接计算总耗时，避免调用get_total_duration导致死锁
            if self._start_time is None or self._end_time is None:
                total_duration = 0.0
            else:
                total_duration = self._end_time - self._start_time
            
            if total_duration == 0:
                return 0.0
            total_users = sum(stats['total'] for stats in self._operations.values())
            return total_users / total_duration
    
    def record_operation(self, op_type: str, success: bool):
        """
        记录用户操作结果
        
        Args:
            op_type: 操作类型（'create', 'update', 'delete'）
            success: 是否成功
        """
        with self._lock:
            if op_type not in self._operations:
                self.logger.warning(f"未知的操作类型: {op_type}")
                return
            
            self._operations[op_type]['total'] += 1
            if success:
                self._operations[op_type]['success'] += 1
            else:
                self._operations[op_type]['failed'] += 1
    
    def set_start_time(self):
        """设置整体开始时间"""
        with self._lock:
            self._start_time = time.time()
    
    def set_end_time(self):
        """设置整体结束时间"""
        with self._lock:
            self._end_time = time.time()
    
    def get_total_duration(self) -> float:
        """
        获取总耗时
        
        Returns:
            总耗时（秒），如果未设置结束时间则返回0
        """
        with self._lock:
            if self._start_time is None or self._end_time is None:
                return 0.0
            return self._end_time - self._start_time
    
    def get_average_api_response_time(self) -> float:
        """
        获取平均API响应时间
        
        Returns:
            平均响应时间（秒），如果没有记录则返回0
        """
        with self._lock:
            if not self._api_response_times:
                return 0.0
            return sum(self._api_response_times) / len(self._api_response_times)
    
    def generate_report(self) -> Dict:
        """
        生成性能报告
        
        Returns:
            包含所有性能指标的字典
        """
        with self._lock:
            # 直接计算，避免调用其他方法导致死锁
            if self._start_time is None or self._end_time is None:
                total_duration = 0.0
            else:
                total_duration = self._end_time - self._start_time
            
            if not self._api_response_times:
                avg_api_time = 0.0
            else:
                avg_api_time = sum(self._api_response_times) / len(self._api_response_times)
            
            # 计算各操作的成功率
            operation_stats = {}
            for op_type, stats in self._operations.items():
                total = stats['total']
                success = stats['success']
                success_rate = (success / total * 100) if total > 0 else 0.0
                operation_stats[op_type] = {
                    'total': total,
                    'success': success,
                    'failed': stats['failed'],
                    'success_rate': success_rate
                }
            
            # 计算API调用成功率
            api_total = self._api_calls['total']
            api_success = self._api_calls['success']
            api_success_rate = (api_success / api_total * 100) if api_total > 0 else 0.0
            
            # 计算各阶段耗时
            phase_durations = {}
            for phase_name, phase_data in self._phases.items():
                if 'duration' in phase_data:
                    phase_durations[phase_name] = phase_data['duration']
            
            # 估算优化前的耗时（用于对比）
            # 假设优化前每个用户需要0.5s获取组信息，加上2次list_groups调用
            estimated_old_time = 0
            total_users = sum(stats['total'] for stats in self._operations.values())
            if total_users > 0:
                # 优化前：1次list_users + N次get_user_group_memberships + 2N次list_groups
                # 假设每次API调用0.5秒
                estimated_old_time = (1 + total_users + 2 * total_users) * 0.5
            
            improvement_percentage = 0
            if estimated_old_time > 0 and total_duration > 0:
                improvement_percentage = ((estimated_old_time - total_duration) / 
                                        estimated_old_time * 100)
            
            # 直接计算缓存命中率和每秒处理用户数，避免死锁
            cache_total = self._cache_stats['total']
            if cache_total == 0:
                cache_hit_rate = 0.0
            else:
                cache_hit_rate = (self._cache_stats['hits'] / cache_total) * 100
            
            if total_duration == 0:
                users_per_second = 0.0
            else:
                users_per_second = total_users / total_duration
            
            # 构建API调用详细统计
            api_details = {}
            for api_type, stats in self._api_call_details.items():
                total = stats['total']
                success = stats['success']
                success_rate = (success / total * 100) if total > 0 else 0.0
                api_details[api_type] = {
                    'total': total,
                    'success': success,
                    'failed': stats['failed'],
                    'success_rate': success_rate
                }
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'total_duration': total_duration,
                'phases': phase_durations,
                'api_calls': {
                    'total': self._api_calls['total'],
                    'success': self._api_calls['success'],
                    'failed': self._api_calls['failed'],
                    'success_rate': api_success_rate,
                    'average_response_time': avg_api_time,
                    'details': api_details  # 新增：API调用详细统计
                },
                'cache_stats': {  # 新增：缓存统计
                    'hits': self._cache_stats['hits'],
                    'misses': self._cache_stats['misses'],
                    'total': self._cache_stats['total'],
                    'hit_rate': cache_hit_rate
                },
                'operations': operation_stats,
                'users_per_second': users_per_second,  # 新增：每秒处理用户数
                'performance_comparison': {
                    'estimated_old_time': estimated_old_time,
                    'actual_time': total_duration,
                    'improvement_percentage': improvement_percentage,
                    'speedup_factor': (estimated_old_time / total_duration) 
                                     if total_duration > 0 else 0
                }
            }
            
            return report
    
    def get_summary_text(self) -> str:
        """
        生成性能摘要文本
        
        Returns:
            格式化的性能摘要字符串
        """
        report = self.generate_report()
        
        lines = []
        lines.append("=" * 60)
        lines.append("性能统计报告")
        lines.append("=" * 60)
        
        # 总耗时
        lines.append(f"\n总耗时: {report['total_duration']:.2f}秒")
        
        # 各阶段耗时
        if report['phases']:
            lines.append("\n各阶段耗时:")
            for phase, duration in report['phases'].items():
                lines.append(f"  {phase}: {duration:.2f}秒")
        
        # API调用统计
        api = report['api_calls']
        lines.append(f"\nAPI调用统计:")
        lines.append(f"  总次数: {api['total']}")
        lines.append(f"  成功: {api['success']}")
        lines.append(f"  失败: {api['failed']}")
        lines.append(f"  成功率: {api['success_rate']:.1f}%")
        if api['average_response_time'] > 0:
            lines.append(f"  平均响应时间: {api['average_response_time']:.2f}秒")
        
        # API调用详细统计
        if api.get('details'):
            lines.append(f"\nAPI调用详细统计:")
            for api_type, stats in api['details'].items():
                lines.append(f"  {api_type}: {stats['success']}/{stats['total']} "
                           f"(成功率: {stats['success_rate']:.1f}%)")
        
        # 缓存统计
        cache = report.get('cache_stats', {})
        if cache.get('total', 0) > 0:
            lines.append(f"\n缓存统计:")
            lines.append(f"  命中: {cache['hits']}")
            lines.append(f"  未命中: {cache['misses']}")
            lines.append(f"  总访问: {cache['total']}")
            lines.append(f"  命中率: {cache['hit_rate']:.1f}%")
        
        # 处理速度
        users_per_sec = report.get('users_per_second', 0)
        if users_per_sec > 0:
            lines.append(f"\n处理速度:")
            lines.append(f"  每秒处理用户数: {users_per_sec:.2f}")
        
        # 用户操作统计
        lines.append(f"\n用户操作统计:")
        for op_type, stats in report['operations'].items():
            if stats['total'] > 0:
                lines.append(f"  {op_type}: {stats['success']}/{stats['total']} "
                           f"(成功率: {stats['success_rate']:.1f}%)")
        
        # 性能对比
        comp = report['performance_comparison']
        if comp['estimated_old_time'] > 0:
            lines.append(f"\n性能对比:")
            lines.append(f"  优化前预估耗时: {comp['estimated_old_time']:.2f}秒")
            lines.append(f"  优化后实际耗时: {comp['actual_time']:.2f}秒")
            lines.append(f"  性能提升: {comp['improvement_percentage']:.1f}%")
            lines.append(f"  加速倍数: {comp['speedup_factor']:.1f}x")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
