"""
进度跟踪模块
用于跟踪和显示用户同步操作的实时进度
"""
import threading
import time
import sys
from src.logger import get_logger


class ProgressTracker:
    """
    进度跟踪类
    
    职责：
    1. 跟踪当前处理进度
    2. 计算预计剩余时间
    3. 在控制台显示进度信息
    
    线程安全：使用Lock保护所有共享数据
    """
    
    def __init__(self, total: int, phase: str, show_progress: bool = True):
        """
        初始化进度跟踪器
        
        Args:
            total: 总任务数
            phase: 当前阶段名称
            show_progress: 是否显示进度（可用于简化日志模式）
        """
        self._total = total
        self._processed = 0
        self._phase = phase
        self._start_time = time.time()
        self._lock = threading.Lock()
        self._show_progress = show_progress
        self._last_update_time = 0
        self._update_interval = 0.5  # 最小更新间隔（秒），避免过于频繁的输出
        self.logger = get_logger("progress_tracker")
    
    def update(self, increment: int = 1):
        """
        更新进度
        
        Args:
            increment: 增加的处理数量（默认1）
        """
        with self._lock:
            self._processed += increment
            
            # 检查是否需要更新显示（避免过于频繁）
            current_time = time.time()
            if (self._show_progress and 
                (current_time - self._last_update_time >= self._update_interval or 
                 self._processed >= self._total)):
                self._display_progress()
                self._last_update_time = current_time
    
    def _display_progress(self):
        """显示进度信息（内部方法，需要在锁内调用）"""
        if not self._show_progress:
            return
        
        elapsed = time.time() - self._start_time
        percentage = (self._processed / self._total * 100) if self._total > 0 else 0
        
        # 计算预计剩余时间
        if self._processed > 0:
            avg_time = elapsed / self._processed
            remaining = avg_time * (self._total - self._processed)
            remaining_str = self._format_time(remaining)
        else:
            remaining_str = "计算中..."
        
        # 格式化输出
        # 使用\r实现同行更新
        progress_text = (
            f"\r[{self._phase}] 进度: {self._processed}/{self._total} "
            f"({percentage:.1f}%) | "
            f"已用时: {self._format_time(elapsed)} | "
            f"预计剩余: {remaining_str}"
        )
        
        # 输出到控制台
        sys.stdout.write(progress_text)
        sys.stdout.flush()
        
        # 如果完成，换行
        if self._processed >= self._total:
            sys.stdout.write("\n")
            sys.stdout.flush()
    
    def _format_time(self, seconds: float) -> str:
        """
        格式化时间显示
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串（如"2m15s"、"1h30m"）
        """
        if seconds < 0:
            return "0s"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h{minutes}m{secs}s"
        elif minutes > 0:
            return f"{minutes}m{secs}s"
        else:
            return f"{secs}s"
    
    def get_progress(self) -> dict:
        """
        获取当前进度信息
        
        Returns:
            包含进度信息的字典
        """
        with self._lock:
            elapsed = time.time() - self._start_time
            percentage = (self._processed / self._total * 100) if self._total > 0 else 0
            
            if self._processed > 0:
                avg_time = elapsed / self._processed
                remaining = avg_time * (self._total - self._processed)
            else:
                remaining = 0
            
            return {
                'phase': self._phase,
                'total': self._total,
                'processed': self._processed,
                'percentage': percentage,
                'elapsed_time': elapsed,
                'remaining_time': remaining,
                'avg_time_per_item': elapsed / self._processed if self._processed > 0 else 0
            }
    
    def finish(self):
        """完成进度跟踪，确保显示100%"""
        with self._lock:
            self._processed = self._total
            self._display_progress()
    
    def reset(self, total: int = None, phase: str = None):
        """
        重置进度跟踪器
        
        Args:
            total: 新的总任务数（如果为None则保持不变）
            phase: 新的阶段名称（如果为None则保持不变）
        """
        with self._lock:
            if total is not None:
                self._total = total
            if phase is not None:
                self._phase = phase
            self._processed = 0
            self._start_time = time.time()
            self._last_update_time = 0
