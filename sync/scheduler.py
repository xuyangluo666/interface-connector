"""
定时调度器配置
使用 APScheduler 实现每3分钟执行一次同步任务
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sync.config import settings
from sync.extractor import AExtractor
from sync.transformer import transform_companies
from sync.loader import BLoader

# 全局调度器实例
_scheduler = None


def run_sync():
    """执行一次完整同步流程"""
    logger.info("========== 开始执行同步任务 ==========")
    try:
        # 1. 初始化提取器并获取用户ID
        extractor = AExtractor()
        
        # 获取用户ID（用于后续接口调用）
        mobile = settings.a_system_default_mobile
        if mobile:
            open_user_id = extractor.get_user_id_by_mobile(mobile)
            logger.info(f"获取用户ID成功: ***")
        else:
            logger.warning("未配置默认手机号，请先设置 A_SYSTEM_DEFAULT_MOBILE")
            return

        # 2. 从 A 系统提取客户数据（纷享销客 CRM）
        # 获取客户数据并关联商机信息
        a_companies = extractor.get_companies_with_opportunities(limit=settings.sync_batch_size)
        logger.info(f"从 A 系统获取到 {len(a_companies)} 条公司数据（含商机信息）")

        if not a_companies:
            logger.info("无数据需要同步")
            return

        # 输出第一条数据示例
        if a_companies:
            import json
            logger.debug(f"数据格式示例:\n{json.dumps(a_companies[0], ensure_ascii=False, indent=2)}")

        # 3. 转换为 B 系统格式
        b_companies_raw = transform_companies(a_companies)

        # 4. 构造 company_id -> company_data 的映射
        # 使用纷享销客的 _id 作为 company_id
        companies_map = {}
        for idx, b_data in enumerate(b_companies_raw):
            company_id = a_companies[idx].get("_id")
            if not company_id:
                logger.warning(f"第 {idx} 条数据缺少 _id 字段，跳过")
                continue
            companies_map[str(company_id)] = b_data

        # 5. 创建到 B 系统
        loader = BLoader()
        result = loader.create_companies_batch(companies_map)
        logger.info(f"同步完成: 总数={result['total']}, 成功={result['success']}, 失败={len(result['failed'])}")
        
        # 记录创建成功的公司及其 B 系统 uId
        if result['created']:
            logger.info("创建成功的公司列表:")
            for item in result['created']:
                logger.info(f"  - {item['companyName']} (B系统 uId: {item['b_system_uId']})")
            
            # 6. 同步商机编号到 B 系统
            logger.info("========== 开始同步商机编号 ==========")
            for item in result['created']:
                company_uId = item['b_system_uId']
                company_name = item['companyName']
                company_id = item['company_id']
                
                # 从原始数据中查找该公司的商机信息
                opportunities = []
                for a_company in a_companies:
                    if str(a_company.get("_id")) == company_id:
                        opportunities = a_company.get("商机信息", [])
                        break
                
                if opportunities:
                    logger.info(f"同步商机编号: companyName={company_name}, company_uId={company_uId}, 商机数量={len(opportunities)}")
                    try:
                        bo_result = loader.create_business_opportunities(company_uId, opportunities)
                        logger.info(f"商机编号同步完成: {company_name} - 总数={bo_result['total']}, 新增={bo_result['created']}, 跳过={bo_result['skipped']}")
                    except Exception as e:
                        logger.error(f"商机编号同步失败 {company_name}: {e}")
                else:
                    logger.info(f"公司 {company_name} 没有商机信息，跳过")
            
            logger.info("========== 商机编号同步结束 ==========")
        
        if result['failed']:
            logger.warning(f"失败列表: {result['failed']}")

    except Exception as e:
        logger.exception(f"同步任务执行失败: {e}")
    finally:
        logger.info("========== 同步任务结束 ==========\n")


def start_scheduler(immediate: bool = True) -> BackgroundScheduler:
    """启动调度器
    
    Args:
        immediate: 是否在启动后立即执行一次同步任务（默认 True）
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        interval_minutes = settings.sync_interval_minutes
        _scheduler.add_job(
            run_sync,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='sync_job',
            max_instances=1,  # 防止任务堆积
            replace_existing=True
        )
        _scheduler.start()
        logger.info(f"调度器已启动，执行间隔: {interval_minutes} 分钟")
        
        # 启动后立即执行一次同步任务
        if immediate:
            logger.info("启动后立即执行首次同步任务...")
            run_sync()
    return _scheduler