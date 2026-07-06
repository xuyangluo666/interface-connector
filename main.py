"""
接口对接服务主入口
启动定时调度器，按配置间隔执行同步任务
"""
import sys
import time
from loguru import logger
from sync.scheduler import start_scheduler
from utils.logging_config import setup_logging, cleanup_old_logs

def main():
    # 配置日志
    setup_logging()
    logger.info("接口对接服务启动")
    
    # 启动时清理过期日志
    cleanup_old_logs()

    # 启动调度器（3分钟一次，由配置文件决定）
    scheduler = start_scheduler()
    logger.info("调度器已启动，按配置间隔执行同步任务")

    try:
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭调度器...")
        scheduler.shutdown()
        logger.info("服务已关闭")
        sys.exit(0)

if __name__ == "__main__":
    main()