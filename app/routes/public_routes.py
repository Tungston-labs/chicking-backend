from smtplib import SMTPException

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import EmailStr

from app.schemas.blog_schema import PublicCommentCreateSchema
from app.services.blog_service import (
    create_public_comment,
    get_public_blog,
    list_public_blogs,
    list_public_comments,
)
from app.utils.email import send_franchise_enquiry_email

router = APIRouter(tags=["Public Blogs"])
MAX_FRANCHISE_DOCUMENT_BYTES = 10 * 1024 * 1024


async def _read_franchise_document(uploaded: UploadFile | None) -> tuple[str, bytes, str] | None:
    if uploaded is None:
        return None

    content = await uploaded.read()
    if len(content) > MAX_FRANCHISE_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded document must be 10 MB or smaller",
        )
    if not content:
        return None

    return (
        uploaded.filename or "franchise-document",
        content,
        uploaded.content_type or "application/octet-stream",
    )


async def _first_uploaded_document(
    document: UploadFile | None,
    document_upload: UploadFile | None,
    file: UploadFile | None,
    attachment: UploadFile | None,
) -> tuple[str, bytes, str] | None:
    for uploaded in (document, document_upload, file, attachment):
        document_payload = await _read_franchise_document(uploaded)
        if document_payload is not None:
            return document_payload
    return None


@router.get("/blogs")
async def public_blogs(category: str | None = Query(default=None)):
    return await list_public_blogs(category)


@router.get("/blogs/{blog_id}")
async def public_blog_detail(blog_id: str):
    return await get_public_blog(blog_id)


@router.post("/blogs/{blog_id}/comments")
async def add_blog_comment(blog_id: str, payload: PublicCommentCreateSchema):
    return await create_public_comment(blog_id, payload)


@router.get("/blogs/{blog_id}/comments")
async def get_public_blog_comments(blog_id: str):
    return await list_public_comments(blog_id)


@router.post("/franchise-enquiries")
async def submit_franchise_enquiry(
    full_name: str = Form(..., alias="fullName"),
    email: EmailStr = Form(...),
    phone: str = Form(..., alias="phoneNumber"),
    country: str = Form(...),
    level_of_interest: str = Form(..., alias="levelOfInterest"),
    investment_capacity: str = Form(..., alias="investmentCapacity"),
    additional_info: str = Form(default="", alias="additionalInfo"),
    document: UploadFile | None = File(default=None),
    document_upload: UploadFile | None = File(default=None, alias="documentUpload"),
    file: UploadFile | None = File(default=None),
    attachment: UploadFile | None = File(default=None),
):
    enquiry = {
        "full_name": full_name.strip(),
        "email": str(email).lower(),
        "phone": phone.strip(),
        "country": country.strip(),
        "level_of_interest": level_of_interest.strip(),
        "investment_capacity": investment_capacity.strip(),
        "additional_info": additional_info.strip(),
    }
    document_payload = await _first_uploaded_document(document, document_upload, file, attachment)

    try:
        await send_franchise_enquiry_email(enquiry, document_payload)
    except (RuntimeError, SMTPException, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to send franchise enquiry email at the moment. Please try again later.",
        ) from exc

    return {
        "message": "Franchise enquiry submitted successfully"
    }
