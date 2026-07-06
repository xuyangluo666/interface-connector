import sys
import os
from datetime import datetime, timedelta
from loguru import logger
from sync.config import settings


def setup_logging():
    """配置日志输出到控制台和文件"""
    logger.remove()  # 移除默认 handler

    # 控制台输出（带颜色）
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # 文件输出（滚动，保留配置的天数）
    logger.add(
        "logs/sync_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention=f"{settings.log_retention_days} days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        encoding="utf-8"
    )

    logger.info(f"日志配置完成，保留天数: {settings.log_retention_days} 天")


def cleanup_old_logs(log_dir: str = "logs", retention_days: int = None):
    """
    清理旧日志文件
    
    :param log_dir: 日志目录
    :param retention_days: 保留天数，默认为配置文件中的值
    """
    if retention_days is None:
        retention_days = settings.log_retention_days
    
    if not os.path.exists(log_dir):
        logger.debug(f"日志目录 {log_dir} 不存在，跳过清理")
        return

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0

    for filename in os.listdir(log_dir):
        file_path = os.path.join(log_dir, filename)
        
        if os.path.isfile(file_path) and filename.startswith("sync_") and filename.endswith(".log"):
            try:
                # 提取日期部分 sync_YYYY-MM-DD.log
                date_str = filename.split("_")[1].replace(".log", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if file_date < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.debug(f"已删除过期日志: {filename}")
            except Exception as e:
                logger.warning(f"处理日志文件 {filename} 时出错: {e}")
    
    if deleted_count > 0:
        logger.info(f"日志清理完成，共删除 {deleted_count} 个过期日志文件")
    else:
        logger.debug("没有需要清理的过期日志")