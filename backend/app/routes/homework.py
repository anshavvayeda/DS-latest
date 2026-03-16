"""Homework routes: CRUD, submission, evaluation."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, desc, text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import logging
import json
import uuid
import httpx
import os

from app.models.database import (
    get_db, User, Subject, Test, TestQuestion,
    StudentProfile, StudentHomeworkStatus, AsyncSessionLocal,
    Homework, HomeworkSolution, HomeworkSubmission
)
from app.deps import (
    get_current_user, require_teacher, get_user_school, OPENROUTER_API_KEY
)

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateHomeworkRequest(BaseModel):
    subject_id: str
    standard: int
    title: str

@router.post("/homework")
async def create_homework(
    subject_id: str = Form(...),
    standard: int = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    model_answers_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Teacher uploads homework PDF - uses unified extraction pipeline"""
    # WRAPPED IN TRY-EXCEPT BLOCK FOR DEBUGGING 520 ERRORS
    try:
        logger.info(f"POST /api/homework received. Subject: {subject_id}, Std: {standard}, Title: {title}")
        logger.info(f"Files received - Homework: {file.filename if file else 'None'}, Model Answers: {model_answers_file.filename if model_answers_file else 'None'}")

        from datetime import timedelta
        from sqlalchemy.exc import IntegrityError
        from app.services.storage_service import s3_client, S3_BUCKET, upload_homework_questions_to_s3, normalize_title, sanitize_component
        from app.services.background_extraction import start_extraction_task, ExtractionStatus
        from app.models.database import AsyncSessionLocal
        import uuid
        
        # Verify subject
        result = await db.execute(select(Subject).where(Subject.id == subject_id))
        subject = result.scalars().first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        # Get teacher's school
        teacher_school = await get_user_school(user, db)
        if not teacher_school:
            raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
        
        try:
            normalized_title = normalize_title(title)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid title: {e}")
        
        homework_id = str(uuid.uuid4())
        
        logger.info(f"Reading homework PDF bytes for ID: {homework_id}")
        file_content = await file.read()
        logger.info(f"Read {len(file_content)} bytes from homework PDF")
        
        # NEW: School-based S3 structure
        school_folder = sanitize_school_name(teacher_school)
        s3_folder_key = f"{school_folder}/homework/class{standard}/{sanitize_component(subject.name)}/{homework_id}"
        homework_s3_key = f"{s3_folder_key}/homework.pdf"
        
        logger.info(f"Uploading homework to S3: {homework_s3_key}")
        try:
            s3_client.put_object(Bucket=S3_BUCKET, Key=homework_s3_key, Body=file_content, ContentType='application/pdf')
        except Exception as e:
            logger.error(f"Homework upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload homework: {str(e)}")
        
        model_answers_key = None
        model_answers_filename = None
        model_answers_content = None
        
        if model_answers_file and model_answers_file.filename:
            logger.info(f"Reading model answers PDF bytes")
            model_answers_content = await model_answers_file.read()
            logger.info(f"Read {len(model_answers_content)} bytes from model answers PDF")
            
            model_answers_key = f"{s3_folder_key}/model_answers.pdf"
            try:
                logger.info(f"Uploading model answers to S3: {model_answers_key}")
                s3_client.put_object(Bucket=S3_BUCKET, Key=model_answers_key, Body=model_answers_content, ContentType='application/pdf')
                model_answers_filename = model_answers_file.filename
            except Exception as e:
                logger.error(f"Model answers upload failed: {e}")
                s3_client.delete_object(Bucket=S3_BUCKET, Key=homework_s3_key)
                raise HTTPException(status_code=500, detail="Failed to upload model answers")
        
        expiry_date = datetime.now(timezone.utc) + timedelta(days=10)
        
        logger.info("Creating DB record")
        homework = Homework(
            id=homework_id,
            subject_id=subject_id,
            standard=standard,
            title=title,
            normalized_title=normalized_title,
            file_name=file.filename,
            file_path=homework_s3_key,
            s3_folder_key=s3_folder_key,
            school_name=teacher_school,  # SET SCHOOL
            model_answers_file=model_answers_filename,
            model_answers_path=model_answers_key,
            expiry_date=expiry_date,
            created_by=user.id,
            extraction_status=ExtractionStatus.PENDING,
            extraction_progress=0,
            questions_extracted_count=0
        )
        
        try:
            db.add(homework)
            await db.commit()
            await db.refresh(homework)
            logger.info(f"DB record created: {homework.id}")
        except IntegrityError:
            await db.rollback()
            logger.warning("DB IntegrityError - duplicate title?")
            s3_client.delete_object(Bucket=S3_BUCKET, Key=homework_s3_key)
            if model_answers_key:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=model_answers_key)
            raise HTTPException(status_code=409, detail=f"Homework '{title}' already exists")
        except Exception as e:
            logger.error(f"DB Commit Error: {e}")
            raise
        
        async def s3_upload_wrapper(questions):
            # Get the homework to fetch s3_folder_key
            hw_result = await db.execute(select(Homework).where(Homework.id == homework_id))
            hw = hw_result.scalars().first()
            return await upload_homework_questions_to_s3(questions, homework_id, s3_folder_key=hw.s3_folder_key if hw else None)
        
        async def s3_solutions_upload_wrapper(solutions):
            from app.services.storage_service import upload_homework_solutions_to_s3
            # Get the homework to fetch s3_folder_key
            hw_result = await db.execute(select(Homework).where(Homework.id == homework_id))
            hw = hw_result.scalars().first()
            return await upload_homework_solutions_to_s3(solutions, homework_id, s3_folder_key=hw.s3_folder_key if hw else None)
        
        logger.info("Starting background extraction task")
        try:
            # We must use start_extraction_task which calls background_extract_test (which we renamed to extract_with_gemini logic inside)
            # Ensure imports are correct in background_extraction.py
            await start_extraction_task(
                test_id=homework_id,
                test_pdf_bytes=file_content,
                model_answers_bytes=model_answers_content,
                standard=standard,
                subject_name=subject.name,
                db_session_factory=AsyncSessionLocal,
                s3_upload_func=s3_upload_wrapper,
                s3_solutions_upload_func=s3_solutions_upload_wrapper if model_answers_content else None,
                content_type='homework'
            )
            logger.info("Background task queued successfully")
        except Exception as e:
            logger.error(f"Failed to start extraction: {e}")
            # Don't fail the request, just mark failed
            homework.extraction_status = 'failed'
            homework.extraction_error = str(e)
            await db.commit()
        
        response_data = {
            "message": "Homework uploaded. Extraction in progress.",
            "status": "processing",
            "homework_id": homework.id,
            "title": homework.title,
            "extraction_status": homework.extraction_status,
            "extraction_stage": homework.extraction_stage or 'UPLOADED',
            "extraction_progress": homework.extraction_progress,
            "poll_url": f"/api/homework/{homework_id}/extraction-status"
        }
        logger.info(f"Returning response: {response_data}")
        return response_data

    except Exception as e:
        logger.exception("HOMEWORK UPLOAD CRASHED")
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")



@router.get("/homework/{homework_id}/extraction-status")
async def get_homework_extraction_status(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Poll extraction status for homework"""
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    from datetime import datetime, timezone
    elapsed_seconds = 0
    if homework.extraction_started_at:
        started = homework.extraction_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed_seconds = int((datetime.now(timezone.utc) - started).total_seconds())
    
    should_poll = homework.extraction_status == 'processing'
    is_stuck = elapsed_seconds > 180 and homework.extraction_status == 'processing'
    
    return {
        "content_id": homework_id,
        "content_type": "homework",
        "homework_id": homework_id,
        "extraction_stage": homework.extraction_stage or 'UPLOADED',
        "extraction_status": homework.extraction_status,
        "extraction_progress": homework.extraction_progress or 0,
        "extraction_stage_message": homework.extraction_stage_message or "Processing...",
        "elapsed_seconds": elapsed_seconds,
        "can_retry": homework.extraction_status in ['failed', 'timeout'] or is_stuck,
        "should_poll": should_poll and not is_stuck,
        "is_stuck": is_stuck,
        "error": homework.extraction_error,
        "questions_extracted_count": homework.questions_extracted_count,
        "extraction_mismatch": False
    }


@router.post("/homework/{homework_id}/retry-extraction")
async def retry_homework_extraction(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Retry failed homework extraction"""
    from app.services.storage_service import s3_client, S3_BUCKET
    from app.services.background_extraction import start_extraction_task
    from app.models.database import AsyncSessionLocal
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    if homework.extraction_status == 'processing':
        raise HTTPException(status_code=409, detail="Extraction already in progress")
    
    # Fetch PDFs from S3
    try:
        homework_pdf_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=homework.file_path)
        homework_pdf_bytes = homework_pdf_obj['Body'].read()
        
        model_answers_bytes = None
        if homework.model_answers_path:
            model_answers_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=homework.model_answers_path)
            model_answers_bytes = model_answers_obj['Body'].read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PDFs from S3: {e}")
    
    # Get subject
    subject_result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Reset extraction status
    homework.extraction_status = 'pending'
    homework.extraction_stage = 'UPLOADED'
    homework.extraction_progress = 0
    homework.extraction_error = None
    homework.extraction_started_at = None
    homework.extraction_completed_at = None
    await db.commit()
    
    # Restart extraction
    async def s3_upload_wrapper(questions):
        from app.services.storage_service import upload_homework_questions_to_s3
        return await upload_homework_questions_to_s3(questions, homework_id, homework.standard, subject.name)
    
    async def s3_solutions_upload_wrapper(solutions):
        from app.services.storage_service import upload_homework_solutions_to_s3
        return await upload_homework_solutions_to_s3(solutions, homework_id, homework.standard, subject.name)
    
    await start_extraction_task(
        test_id=homework_id,
        test_pdf_bytes=homework_pdf_bytes,
        model_answers_bytes=model_answers_bytes,
        standard=homework.standard,
        subject_name=subject.name,
        db_session_factory=AsyncSessionLocal,
        s3_upload_func=s3_upload_wrapper,
        s3_solutions_upload_func=s3_solutions_upload_wrapper if model_answers_bytes else None,
        content_type='homework'
    )
    
    return {"message": "Extraction restarted", "status": "processing"}

@router.get("/homework")
async def list_homework(
    standard: Optional[int] = None,
    subject_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List homework with verified extraction counts from S3 (if completed).
    Ensures teacher dashboard matches reality.
    
    School-Based Multi-Tenancy:
    - Students only see homework from their school
    - Teachers see homework from their school
    - Admins see all homework
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    import json
    
    # Get the user's school for filtering
    user_school = await get_user_school(user, db)
    
    query = select(Homework).where(Homework.expiry_date > datetime.now(timezone.utc))
    
    # School-based filtering
    if user_school and user.role in ['student', 'teacher']:
        query = query.where(Homework.school_name == user_school)
    # Admin sees all homework (no additional filter)
    
    if standard:
        query = query.where(Homework.standard == standard)
    if subject_id:
        query = query.where(Homework.subject_id == subject_id)
    
    query = query.order_by(Homework.created_at.desc())
    
    result = await db.execute(query)
    homework_list = result.scalars().all()
    
    response_list = []
    
    for hw in homework_list:
        hw_data = {
            "id": str(hw.id),
            "subject_id": str(hw.subject_id),
            "standard": hw.standard,
            "title": hw.title,
            "file_name": hw.file_name,
            "file_path": hw.file_path,
            "upload_date": hw.upload_date.isoformat(),
            "expiry_date": hw.expiry_date.isoformat(),
            "extraction_status": hw.extraction_status,
            "extraction_stage": hw.extraction_stage,
            "extraction_error": hw.extraction_error,
            "questions_extracted_count": hw.questions_extracted_count or 0,
            "solutions_extracted_count": getattr(hw, 'solutions_extracted_count', 0) or 0,
            "has_model_answers": bool(hw.model_answers_path),
            "extraction_mismatch": False
        }
        
        # Verify completed items against S3 if user requested strict check
        if hw.extraction_status == 'completed':
            try:
                # Check Questions
                q_key = f"{hw.s3_folder_key}/questions.json"
                q_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=q_key)
                q_data = json.loads(q_obj['Body'].read())
                real_q_count = len(q_data)
                
                # Update if different
                if real_q_count != hw_data['questions_extracted_count']:
                    hw_data['extraction_mismatch'] = True
                    hw_data['questions_extracted_count'] = real_q_count
                
                # Check Solutions (if expected)
                if hw.model_answers_path:
                    s_key = f"{hw.s3_folder_key}/solutions.json"
                    try:
                        s_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=s_key)
                        s_data = json.loads(s_obj['Body'].read())
                        real_s_count = len(s_data)
                        
                        # Compare with safe integer (0 if None)
                        db_s_count = hw_data.get('solutions_extracted_count') or 0
                        
                        if real_s_count != db_s_count:
                            hw_data['extraction_mismatch'] = True
                            hw_data['solutions_extracted_count'] = real_s_count
                    except Exception:
                        # Missing solutions.json when model answers exist
                        hw_data['extraction_mismatch'] = True
                        hw_data['solutions_extracted_count'] = 0
                        
            except Exception as e:
                logger.warning(f"S3 verification failed for list_homework item {hw.id}: {e}")
                # If S3 read fails, rely on DB but maybe flag?
                # Keeping as-is for now (trust DB fallback)
                pass
        
        response_list.append(hw_data)
            
    return response_list


@router.post("/homework/{homework_id}/get-solution")
async def get_homework_solution(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get AI-generated solution for homework (cached for 10 days)"""
    from datetime import timedelta
    from app.services.ai_service import generate_homework_solution
    
    # Get homework
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Check if expired (handle both timezone-aware and naive datetimes)
    now = datetime.now(timezone.utc)
    expiry = homework.expiry_date
    if expiry.tzinfo is None:
        # If stored datetime is naive, make it aware
        expiry = expiry.replace(tzinfo=timezone.utc)
    
    if expiry < now:
        raise HTTPException(status_code=410, detail="Homework has expired")
    
    # Check if solution already cached
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(HomeworkSolution).where(HomeworkSolution.homework_id == homework_id)
    )
    cached_solution = result.scalars().first()
    
    # Check if cache is still valid
    if cached_solution:
        cache_expiry = cached_solution.cache_expiry
        if cache_expiry.tzinfo is None:
            cache_expiry = cache_expiry.replace(tzinfo=timezone.utc)
        
        if cache_expiry > now:
            # Cache is valid, return it
            cached_solution.access_count += 1
            await db.commit()
            
            return {
                "homework_id": homework_id,
                "title": homework.title,
                "solution": cached_solution.solution,
                "cached": True,
                "generated_at": cached_solution.created_at.isoformat()
            }
    
    # Generate new solution
    if not homework.ocr_text:
        raise HTTPException(status_code=400, detail="Homework text not extracted. Please try again later.")
    
    solution = await generate_homework_solution(
        homework_text=homework.ocr_text,
        title=homework.title,
        standard=homework.standard
    )
    
    if not solution:
        raise HTTPException(status_code=500, detail="Failed to generate solution")
    
    # Cache solution for 10 days
    cache_expiry = datetime.now(timezone.utc) + timedelta(days=10)
    hw_solution = HomeworkSolution(
        homework_id=homework_id,
        solution=solution,
        cache_expiry=cache_expiry,
        access_count=1
    )
    db.add(hw_solution)
    await db.commit()
    
    return {
        "homework_id": homework_id,
        "title": homework.title,
        "solution": solution,
        "cached": False,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.delete("/homework/{homework_id}")
async def delete_homework(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    Delete homework - FIXED VERSION
    Deletes entire S3 folder and DB record
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    logger.info(f"[DELETE_HOMEWORK] Deleting homework ID: {homework_id}")
    logger.info(f"[DELETE_HOMEWORK] S3 folder: {homework.s3_folder_key}")
    
    # Delete entire S3 folder
    if homework.s3_folder_key:
        try:
            # List all objects in the folder
            response = s3_client.list_objects_v2(
                Bucket=S3_BUCKET,
                Prefix=f"{homework.s3_folder_key}/"
            )
            
            if 'Contents' in response and len(response['Contents']) > 0:
                objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
                
                # Delete all objects
                s3_client.delete_objects(
                    Bucket=S3_BUCKET,
                    Delete={'Objects': objects_to_delete}
                )
                
                logger.info(f"[DELETE_HOMEWORK] ✅ Deleted {len(objects_to_delete)} S3 objects")
            else:
                logger.info(f"[DELETE_HOMEWORK] No S3 objects found")
                
        except Exception as e:
            logger.error(f"[DELETE_HOMEWORK] ❌ S3 deletion failed: {e}")
            # Continue to delete DB record even if S3 fails
    
    # Delete from database
    await db.delete(homework)
    await db.commit()
    
    logger.info(f"[DELETE_HOMEWORK] ✅ Homework deleted from DB")
    
    return {"message": "Homework deleted successfully"}


@router.get("/homework/{homework_id}/solutions")
async def get_homework_solutions(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get homework solutions JSON from S3.
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    if homework.s3_folder_key:
        s3_key = f"{homework.s3_folder_key}/solutions.json"
    else:
        result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
        subject = result.scalars().first()
        if not subject:
             raise HTTPException(status_code=404, detail="Subject not found")
        
        from app.services.storage_service import sanitize_component
        s3_key = f"homework/class{homework.standard}/{sanitize_component(subject.name)}/{homework.id}/solutions.json"
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        # Return in format expected by frontend
        return {
            "solutions": content if isinstance(content, list) else content.get("solutions", []),
            "homework_id": homework_id
        }
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Solutions not available")
    except Exception as e:
        logger.error(f"Error fetching solutions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch solutions")


@router.get("/homework/{homework_id}/questions-v2", response_model=None)
async def get_homework_questions_v2(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    FIXED VERSION - Get homework questions JSON from S3.
    Ensures student frontend can fetch questions using the correct S3 path structure.
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    logger.info(f"[QUESTIONS_API_V2] Fetching questions for homework: {homework_id}")
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Use deterministic path structure: homework/class{std}/{subject}/{id}/questions.json
    # Fallback to DB s3_folder_key if available, otherwise reconstruct
    if homework.s3_folder_key:
        s3_key = f"{homework.s3_folder_key}/questions.json"
    else:
        # Reconstruction logic (fallback)
        result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
        subject = result.scalars().first()
        if not subject:
             raise HTTPException(status_code=404, detail="Subject not found")
        
        from app.services.storage_service import sanitize_component
        s3_key = f"homework/class{homework.standard}/{sanitize_component(subject.name)}/{homework.id}/questions.json"
    
    logger.info(f"[QUESTIONS_API_V2] S3 Key: {s3_key}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        logger.info(f"[QUESTIONS_API_V2] Retrieved {len(content) if isinstance(content, list) else 'N/A'} questions from S3")
        
        # Return in format expected by frontend
        result_data = {
            "questions_extracted": True,
            "questions": content if isinstance(content, list) else content.get("questions", []),
            "homework_id": homework_id
        }
        logger.info(f"[QUESTIONS_API_V2] Returning object with {len(result_data['questions'])} questions")
        return result_data
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Questions not found in S3: {s3_key}")
        raise HTTPException(status_code=404, detail="Questions not available")
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch questions")


@router.get("/homework/{homework_id}/questions", response_model=None)
async def get_homework_questions(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    FIXED VERSION - Get homework questions JSON from S3.
    Ensures student frontend can fetch questions using the correct S3 path structure.
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    logger.info(f"[QUESTIONS_API_V2] Fetching questions for homework: {homework_id}")
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Use deterministic path structure: homework/class{std}/{subject}/{id}/questions.json
    # Fallback to DB s3_folder_key if available, otherwise reconstruct
    if homework.s3_folder_key:
        s3_key = f"{homework.s3_folder_key}/questions.json"
    else:
        # Reconstruction logic (fallback)
        result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
        subject = result.scalars().first()
        if not subject:
             raise HTTPException(status_code=404, detail="Subject not found")
        
        from app.services.storage_service import sanitize_component
        s3_key = f"homework/class{homework.standard}/{sanitize_component(subject.name)}/{homework.id}/questions.json"
    
    logger.info(f"[QUESTIONS_API_V2] S3 Key: {s3_key}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        logger.info(f"[QUESTIONS_API_V2] Retrieved {len(content) if isinstance(content, list) else 'N/A'} questions from S3")
        
        # Return in format expected by frontend
        result_data = {
            "questions_extracted": True,
            "questions": content if isinstance(content, list) else content.get("questions", []),
            "homework_id": homework_id
        }
        logger.info(f"[QUESTIONS_API_V2] Returning object with {len(result_data['questions'])} questions")
        return result_data
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Questions not found in S3: {s3_key}")
        raise HTTPException(status_code=404, detail="Questions not available")
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch questions")


@router.post("/homework/{homework_id}/evaluate-answer")
async def evaluate_homework_answer(
    homework_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Evaluate student's answer using free LLM"""
    from app.services.ai_service import evaluate_student_answer
    
    question_number = request.get('question_number', 1)
    question_text = request.get('question_text')
    student_answer = request.get('student_answer')
    model_answer = request.get('model_answer')
    
    if not question_text or not student_answer:
        raise HTTPException(status_code=400, detail="question_text and student_answer required")
    
    # Validate word count (max 25 words)
    word_count = len(student_answer.split())
    if word_count > 25:
        return {
            "error": True,
            "message": f"Answer too long! Please keep it under 25 words. (Current: {word_count} words)"
        }
    
    # Evaluate answer
    evaluation = await evaluate_student_answer(
        question=question_text,
        student_answer=student_answer,
        model_answer=model_answer,
        question_number=question_number
    )
    
    return {
        "evaluation": evaluation,
        "question_number": question_number
    }


@router.post("/homework/{homework_id}/help")
async def get_homework_help(
    homework_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get AI help for a homework question"""
    from app.services.ai_service import help_with_question
    
    question_text = request.get('question_text')
    model_answer = request.get('model_answer')
    
    if not question_text:
        raise HTTPException(status_code=400, detail="question_text is required")
    
    # Get homework to know the standard (class level)
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    standard = homework.standard if homework else 5  # Default to class 5
    
    help_text = await help_with_question(
        question=question_text,
        model_answer=model_answer,
        standard=standard
    )
    
    return {
        "help_text": help_text
    }


@router.post("/homework/{homework_id}/submit")
async def submit_homework(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Submit homework (mark as submitted) - Submission record is PERMANENT for reports"""
    # Get student profile
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get homework details for permanent record
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Get subject name
    result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
    subject = result.scalars().first()
    
    # Check if already submitted
    result = await db.execute(
        select(HomeworkSubmission).where(
            HomeworkSubmission.homework_id == homework_id,
            HomeworkSubmission.student_id == str(user.id)
        )
    )
    submission = result.scalars().first()
    
    if submission:
        if submission.submitted:
            return {"message": "Already submitted", "submitted_at": submission.submitted_at.isoformat()}
        else:
            # Update to submitted
            submission.submitted = True
            submission.submitted_at = datetime.now(timezone.utc)
    else:
        # Create new submission with permanent metadata
        submission = HomeworkSubmission(
            homework_id=homework_id,
            homework_title=homework.title,
            subject_name=subject.name if subject else "Unknown",
            standard=homework.standard,
            student_id=str(user.id),
            roll_no=profile.roll_no,
            submitted=True,
            submitted_at=datetime.now(timezone.utc),
            homework_upload_date=homework.upload_date
        )
        db.add(submission)
    
    await db.commit()
    
    return {
        "message": "Homework submitted successfully",
        "submitted_at": submission.submitted_at.isoformat()
    }


@router.get("/homework/{homework_id}/submissions")
async def get_homework_submissions(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Get submission status for homework (teacher only)"""
    # Get homework
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Get all students in this standard
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.standard == homework.standard)
    )
    all_students = result.scalars().all()
    
    # Get submissions
    result = await db.execute(
        select(HomeworkSubmission).where(HomeworkSubmission.homework_id == homework_id)
    )
    submissions = result.scalars().all()
    
    # Create submission map
    submission_map = {sub.roll_no: sub for sub in submissions}
    
    # Build response
    submitted_students = []
    not_submitted_students = []
    
    for student in all_students:
        student_data = {
            "roll_no": student.roll_no,
            "name": student.name,
            "submitted_at": None
        }
        
        if student.roll_no in submission_map and submission_map[student.roll_no].submitted:
            student_data["submitted_at"] = submission_map[student.roll_no].submitted_at.isoformat()
            submitted_students.append(student_data)
        else:
            not_submitted_students.append(student_data)
    
    return {
        "homework_id": homework_id,
        "title": homework.title,
        "total_students": len(all_students),
        "submitted_count": len(submitted_students),
        "not_submitted_count": len(not_submitted_students),
        "submitted_students": submitted_students,
        "not_submitted_students": not_submitted_students
    }


@router.get("/teacher/students/count")
async def get_students_count(
    standard: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Get total number of students enrolled for a standard"""
    from sqlalchemy import func
    
    result = await db.execute(
        select(func.count(StudentProfile.id)).where(StudentProfile.standard == standard)
    )
    count = result.scalar()
    
    return {
        "standard": standard,
        "total_students": count or 0
    }


@router.get("/student/homework-history")
async def get_student_homework_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get student's homework submission history - PERMANENT RECORD for reports"""
    # Get student profile
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get all submissions for this student
    result = await db.execute(
        select(HomeworkSubmission)
        .where(HomeworkSubmission.student_id == str(user.id))
        .order_by(HomeworkSubmission.homework_upload_date.desc())
    )
    submissions = result.scalars().all()
    
    # Build response
    history = []
    for sub in submissions:
        history.append({
            "homework_id": sub.homework_id,
            "homework_title": sub.homework_title,
            "subject_name": sub.subject_name,
            "standard": sub.standard,
            "submitted": sub.submitted,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "upload_date": sub.homework_upload_date.isoformat()
        })
    
    # Calculate stats
    total_homework = len(submissions)
    submitted_count = sum(1 for sub in submissions if sub.submitted)
    completion_rate = (submitted_count / total_homework * 100) if total_homework > 0 else 0
    
    return {
        "student_name": profile.name,
        "roll_no": profile.roll_no,
        "total_homework_assigned": total_homework,
        "submitted_count": submitted_count,
        "not_submitted_count": total_homework - submitted_count,
        "completion_rate": round(completion_rate, 2),
        "history": history
    }


@router.get("/parent/student-homework-report/{roll_no}")
async def get_student_homework_report_for_parent(
    roll_no: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get student homework report for parents - Shows PERMANENT submission history"""
    # In future, add parent authentication check here
    
    # Get student profile
    result = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == roll_no))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get all submissions for this student
    result = await db.execute(
        select(HomeworkSubmission)
        .where(HomeworkSubmission.roll_no == roll_no)
        .order_by(HomeworkSubmission.homework_upload_date.desc())
    )
    submissions = result.scalars().all()
    
    # Build response with detailed history
    history = []
    for sub in submissions:
        history.append({
            "homework_title": sub.homework_title,
            "subject_name": sub.subject_name,
            "standard": sub.standard,
            "submitted": sub.submitted,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "upload_date": sub.homework_upload_date.isoformat(),
            "days_to_submit": (sub.submitted_at - sub.homework_upload_date).days if sub.submitted_at else None
        })
    
    # Calculate comprehensive stats
    total_homework = len(submissions)
    submitted_count = sum(1 for sub in submissions if sub.submitted)
    on_time_count = sum(1 for sub in submissions if sub.submitted and (sub.submitted_at - sub.homework_upload_date).days <= 10)
    
    return {
        "student_name": profile.name,
        "roll_no": profile.roll_no,
        "standard": profile.standard,
        "school_name": profile.school_name,
        "total_homework_assigned": total_homework,
        "submitted_count": submitted_count,
        "not_submitted_count": total_homework - submitted_count,
        "completion_rate": round((submitted_count / total_homework * 100) if total_homework > 0 else 0, 2),
        "on_time_submission_rate": round((on_time_count / total_homework * 100) if total_homework > 0 else 0, 2),
        "history": history
    }


