"""
FIXED Background Extraction Service - Supports Homework AND Tests
===================================================================
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ExtractionStatus:
    """Extraction status constants"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


class ExtractionStage:
    """Extraction stage constants"""
    UPLOADED = 'UPLOADED'
    PROCESSING = 'PROCESSING'
    EXTRACTING_QUESTIONS = 'EXTRACTING_QUESTIONS'
    EXTRACTING_SOLUTIONS = 'EXTRACTING_SOLUTIONS'
    SAVING_TO_S3 = 'SAVING_TO_S3'
    VERIFYING_S3 = 'VERIFYING_S3'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


async def update_extraction_status(
    db,
    item_id: str,
    status: str,
    stage: str,
    progress: int,
    content_type: str = 'homework',
    stage_message: str = None,
    error: str = None,
    questions_count: int = None,
    solutions_count: int = None,
    questions_s3_key: str = None,
    answers_s3_key: str = None
):
    """Update extraction status in DB for homework OR test OR pyq"""
    from app.models.database import Homework, Test, PreviousYearPaper
    from sqlalchemy import select
    
    try:
        Model = Test if content_type == 'test' else (PreviousYearPaper if content_type == 'pyq' else Homework)
        result = await db.execute(select(Model).where(Model.id == item_id))
        item = result.scalars().first()
        
        if not item:
            logger.error(f"[DB_UPDATE][{item_id}] {content_type} not found!")
            return False
        
        item.extraction_status = status
        item.extraction_stage = stage
        item.extraction_progress = progress
        
        if stage_message:
            item.extraction_stage_message = stage_message
        if error:
            item.extraction_error = error
        if questions_count is not None:
            item.questions_extracted_count = questions_count
            item.questions_extracted = True if questions_count > 0 else False
        if solutions_count is not None and hasattr(item, 'solutions_extracted_count'):
            item.solutions_extracted_count = solutions_count
        
        # Save S3 keys to database
        if questions_s3_key and hasattr(item, 'questions_s3_key'):
            item.questions_s3_key = questions_s3_key
            logger.info(f"[DB_UPDATE][{item_id}] Saved questions_s3_key: {questions_s3_key}")
        if answers_s3_key and hasattr(item, 'answers_s3_key'):
            item.answers_s3_key = answers_s3_key
            logger.info(f"[DB_UPDATE][{item_id}] Saved answers_s3_key: {answers_s3_key}")
        
        # Only set timing fields if the model defines them (Homework/Test)
        if status == ExtractionStatus.PROCESSING and hasattr(item, "extraction_started_at") and not item.extraction_started_at:
            item.extraction_started_at = datetime.now(timezone.utc)
        if status in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED] and hasattr(item, "extraction_completed_at"):
            item.extraction_completed_at = datetime.now(timezone.utc)
        
        # CRITICAL: Set test/homework status to 'active' when extraction completes successfully
        if status == ExtractionStatus.COMPLETED and hasattr(item, 'status'):
            item.status = 'active'
            logger.info(f"[DB_UPDATE][{item_id}] ✅ Status set to 'active' - now visible to students!")
        
        await db.commit()
        await db.refresh(item)
        
        logger.info(f"[DB_UPDATE][{item_id}] ✅ {content_type}: {status}/{stage} {progress}%")
        return True
        
    except Exception as e:
        logger.error(f"[DB_UPDATE][{item_id}] ❌ {e}")
        await db.rollback()
        return False


async def verify_s3_file(s3_client, bucket, key):
    """Verify file exists in S3"""
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        return len(obj['Body'].read()) > 0
    except:
        return False


async def background_extract_homework(
    homework_id: str,
    homework_pdf_bytes: bytes,
    model_answers_bytes: Optional[bytes],
    standard: int,
    subject_name: str,
    db_session_factory,
    s3_upload_questions_func,
    s3_upload_solutions_func=None,
    content_type: str = 'homework'
):
    """Extract questions/solutions and update DB"""
    from app.services.gpt4o_extraction import extract_with_gemini, validate_extracted_data, convert_to_legacy_format
    from app.services.storage_service import s3_client, S3_BUCKET
    
    logger.info(f"[EXTRACT][{homework_id}] ========== STARTING {content_type.upper()} EXTRACTION ==========")
    logger.info(f"[EXTRACT][{homework_id}] PDF size: {len(homework_pdf_bytes)} bytes")
    logger.info(f"[EXTRACT][{homework_id}] Has solutions: {bool(model_answers_bytes)}")
    
    async with db_session_factory() as db:
        try:
            logger.info(f"[EXTRACT][{homework_id}] DB session created")
            
            await update_extraction_status(db, homework_id, ExtractionStatus.PROCESSING, ExtractionStage.UPLOADED, 5, content_type)
            logger.info(f"[EXTRACT][{homework_id}] Initial status updated")
            
            # Extract questions
            logger.info(f"[EXTRACT][{homework_id}] Starting AI extraction...")
            q_data = await extract_with_gemini(homework_id, homework_pdf_bytes)
            logger.info(f"[EXTRACT][{homework_id}] AI extraction complete, validating...")
            
            validate_extracted_data(q_data)
            questions = convert_to_legacy_format(q_data)
            q_count = len(questions)
            logger.info(f"[EXTRACT][{homework_id}] Extracted {q_count} questions")
            
            if q_count == 0:
                raise Exception("No questions extracted from PDF")
            
            await update_extraction_status(db, homework_id, ExtractionStatus.PROCESSING, ExtractionStage.SAVING_TO_S3, 50, content_type)
            logger.info(f"[EXTRACT][{homework_id}] Uploading questions to S3...")
            
            # Upload to S3
            q_key = await s3_upload_questions_func(questions)
            logger.info(f"[EXTRACT][{homework_id}] Questions uploaded to S3: {q_key}")
            
            logger.info(f"[EXTRACT][{homework_id}] Verifying S3 upload...")
            q_verified = await verify_s3_file(s3_client, S3_BUCKET, q_key)
            logger.info(f"[EXTRACT][{homework_id}] S3 verification: {q_verified}")
            
            if not q_verified:
                raise Exception("S3 verification failed - file not found or empty")
            
            # Extract solutions if provided
            s_count = 0
            s_key = None  # Initialize solutions key
            if model_answers_bytes and s3_upload_solutions_func:
                logger.info(f"[EXTRACT][{homework_id}] Extracting solutions...")
                try:
                    s_data = await extract_with_gemini(f"{homework_id}-sol", model_answers_bytes)
                    validate_extracted_data(s_data)
                    solutions = convert_to_legacy_format(s_data)
                    s_count = len(solutions)
                    logger.info(f"[EXTRACT][{homework_id}] Extracted {s_count} solutions")
                    
                    s_key = await s3_upload_solutions_func(solutions)
                    await verify_s3_file(s3_client, S3_BUCKET, s_key)
                    logger.info(f"[EXTRACT][{homework_id}] Solutions uploaded and verified")
                except Exception as e:
                    logger.warning(f"[EXTRACT][{homework_id}] Solutions extraction failed: {e}")
            
            # Success!
            logger.info(f"[EXTRACT][{homework_id}] Updating final status to COMPLETED...")
            await update_extraction_status(
                db, homework_id, ExtractionStatus.COMPLETED, ExtractionStage.COMPLETED, 100,
                content_type, 
                questions_count=q_count, 
                solutions_count=s_count,
                questions_s3_key=q_key,
                answers_s3_key=s_key
            )
            logger.info(f"[EXTRACT][{homework_id}] ========== SUCCESS: {q_count} questions, {s_count} solutions ==========")
            
            # Auto-generate solutions for PYQs
            if content_type == 'pyq':
                logger.info(f"[EXTRACT][{homework_id}] Starting PYQ solution generation...")
                try:
                    from app.services.ai_service import generate_pyq_solution_from_questions
                    from app.models.database import PreviousYearPaper
                    from sqlalchemy import select
                    import json
                    
                    # Get PYQ record for exam name and year
                    pyq_result = await db.execute(select(PreviousYearPaper).where(PreviousYearPaper.id == homework_id))
                    pyq = pyq_result.scalars().first()
                    
                    if pyq:
                        # Generate solutions with actual exam info
                        solutions = await generate_pyq_solution_from_questions(
                            questions=questions,
                            exam_name=pyq.exam_name or "Previous Year Paper",
                            year=pyq.year or "2024",
                            standard=standard
                        )
                        
                        # Save as exam_solution.json
                        solutions_key = f"{pyq.s3_folder_key}/exam_solution.json"
                        solutions_bytes = json.dumps(solutions, indent=2, ensure_ascii=False).encode('utf-8')
                        s3_client.put_object(Bucket=S3_BUCKET, Key=solutions_key, Body=solutions_bytes)
                        
                        # Update DB
                        pyq.solution_generated = True
                        pyq.solution_s3_key = solutions_key
                        pyq.solution_generated_at = datetime.now(timezone.utc)
                        await db.commit()
                        
                        logger.info(f"[EXTRACT][{homework_id}] ✅ PYQ solutions saved to S3: exam_solution.json")
                    
                except Exception as e:
                    logger.error(f"[EXTRACT][{homework_id}] ⚠️ Solution generation failed: {e}")

            
        except Exception as e:
            logger.error(f"[EXTRACT][{homework_id}] ========== FAILED: {e} ==========")
            logger.exception(f"[EXTRACT][{homework_id}] Full traceback:")
            await update_extraction_status(
                db, homework_id, ExtractionStatus.FAILED, ExtractionStage.FAILED, 100,
                content_type, error=str(e)
            )


_active_tasks = {}

async def start_extraction_task(
    test_id: str,
    test_pdf_bytes: bytes,
    model_answers_bytes: Optional[bytes],
    standard: int,
    subject_name: str,
    db_session_factory,
    s3_upload_func,
    s3_solutions_upload_func=None,
    content_type: str = 'homework'
):
    """Start background extraction"""
    task = asyncio.create_task(
        background_extract_homework(
            test_id, test_pdf_bytes, model_answers_bytes,
            standard, subject_name, db_session_factory,
            s3_upload_func, s3_solutions_upload_func, content_type
        )
    )
    _active_tasks[test_id] = task
    task.add_done_callback(lambda t: _active_tasks.pop(test_id, None))
    return task
