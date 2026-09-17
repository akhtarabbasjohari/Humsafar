"""
Document Processing & Distillation Service for Humsafar.
Handles document uploads (PDF, plain text, PNG, JPEG, WEBP), magic byte validation,
server-side text extraction, image OCR, Ollama distillation, and session-scoped storage.
"""

import io
import os
import re
import uuid
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from pypdf import PdfReader
from PIL import Image

from services.ollama_service import ollama_service

logger = logging.getLogger(__name__)

# Enforce 10 MB maximum upload size limit
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/webp",
}

# Distinct confidence label for user-uploaded documents
CONFIDENCE_LABEL_DOCUMENT = "from your uploaded document"

# In-memory ephemeral storage for guest sessions (strictly ephemeral, never persisted to DB)
_EPHEMERAL_DOCUMENTS: Dict[str, List[Dict[str, Any]]] = {}


class DocumentValidationError(Exception):
    """Raised when an uploaded file violates format, content-type, or size constraints."""
    pass


class DocumentExtractionError(Exception):
    """Raised when text cannot be extracted from a validated document."""
    pass


def detect_file_type_from_bytes(file_bytes: bytes, original_filename: str = "") -> str:
    """
    Validate actual file content type by inspecting magic bytes, not just the file extension.
    Returns canonical MIME type or raises DocumentValidationError.
    """
    if not file_bytes or len(file_bytes) == 0:
        raise DocumentValidationError("Uploaded file is empty.")

    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise DocumentValidationError(f"File size ({len(file_bytes)} bytes) exceeds the 10 MB limit.")

    # 1. PDF: starts with '%PDF-'
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"

    # 2. PNG: 8-byte magic header \x89PNG\r\n\x1a\n
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # 3. JPEG: starts with \xff\xd8\xff
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # 4. WEBP: starts with 'RIFF' and has 'WEBP' at offset 8..12
    if len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"

    # 5. Plain text check: reject if contains null bytes or unprintable binaries
    if b"\x00" not in file_bytes[:4096]:
        try:
            file_bytes.decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            try:
                file_bytes.decode("latin-1")
                # Ensure it looks like plain text, not binary garbage
                sample = file_bytes[:512]
                non_printable = sum(1 for b in sample if b < 9 or (13 < b < 32))
                if non_printable / len(sample) < 0.10:
                    return "text/plain"
            except Exception:
                pass

    raise DocumentValidationError(
        "Unsupported or invalid file content. Allowed formats: PDF, plain text (.txt), and common images (PNG, JPEG, WEBP)."
    )


def extract_text_from_document(file_bytes: bytes, mime_type: str, filename: str = "") -> str:
    """
    Extract raw text from a document based on its validated MIME type.
    - Plain text: direct decode.
    - PDF: pypdf.PdfReader.
    - Image: OCR (Windows Media OCR / pytesseract / PIL fallback).
    """
    if mime_type == "text/plain":
        try:
            return file_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="ignore").strip()

    elif mime_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for idx, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(f"--- Page {idx + 1} ---\n{txt.strip()}")
            full_text = "\n\n".join(pages_text).strip()
            if not full_text:
                raise DocumentExtractionError("PDF document does not contain readable text or is an image-only scan.")
            return full_text
        except DocumentExtractionError:
            raise
        except Exception as exc:
            logger.exception("Error extracting PDF text: %s", exc)
            raise DocumentExtractionError(f"Failed to read PDF text: {str(exc)}")

    elif mime_type in ("image/png", "image/jpeg", "image/webp"):
        return _extract_text_from_image(file_bytes, filename)

    raise DocumentExtractionError(f"Extraction not supported for MIME type {mime_type}")


def _extract_text_from_image(file_bytes: bytes, filename: str = "") -> str:
    """
    Extract text from an image using OCR.
    Supports Windows Media OCR engine natively, with pytesseract or PIL verification fallback.
    """
    # Verify image integrity via PIL first
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image.verify()
    except Exception as exc:
        raise DocumentExtractionError(f"Corrupt or invalid image file: {str(exc)}")

    # 1. Try pytesseract if available
    try:
        import pytesseract
        reopened = Image.open(io.BytesIO(file_bytes))
        ocr_text = pytesseract.image_to_string(reopened).strip()
        if ocr_text:
            return ocr_text
    except Exception:
        pass

    # 2. Try Windows 10/11 built-in Windows.Media.Ocr via PowerShell
    if os.name == "nt":
        try:
            temp_path = os.path.join(os.environ.get("TEMP", "."), f"humsafar_ocr_{uuid.uuid4().hex[:8]}.png")
            # Save normalized PNG for Windows OCR
            norm_img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            norm_img.save(temp_path, format="PNG")

            ps_script = f"""
            [Windows.Globalization.Language, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
            [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
            [Windows.Media.Ocr.OcrEngine, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
            [Windows.Storage.StorageFile, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null

            $filePath = "{temp_path}"
            $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($filePath).GetAwaiter().GetResult()
            $stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read).GetAwaiter().GetResult()
            $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
            $softwareBitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
            if (-not $engine) {{
                $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
            }}
            $result = $engine.RecognizeAsync($softwareBitmap).GetAwaiter().GetResult()
            Write-Output $result.Text
            """
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=12.0,
            )
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

            ocr_text = (proc.stdout or "").strip()
            if ocr_text:
                return ocr_text
        except Exception as ocr_err:
            logger.info("Windows Media OCR execution error: %s", ocr_err)

    # 3. Fallback: Image is valid, but no text could be recognized
    return f"[Image Document: {filename or 'screenshot/ticket'}. Image validated successfully; text could not be resolved from image visual contents.]"


def process_and_distill_document(
    file_bytes: bytes,
    original_filename: str,
    session_id: str = "default",
) -> Dict[str, Any]:
    """
    Validate, extract text from, and distill an uploaded document using Ollama.
    Returns structured document record with distinct confidence labeling.
    """
    # 1. Magic byte & size validation
    mime_type = detect_file_type_from_bytes(file_bytes, original_filename)

    # 2. Server-side text extraction
    raw_text = extract_text_from_document(file_bytes, mime_type, original_filename)

    # 3. Distillation through Ollama (conserves Groq tokens and filters boilerplate)
    distill_result = ollama_service.distill_uploaded_document_content(
        raw_text=raw_text,
        filename=original_filename,
        session_id=session_id,
    )
    distilled_content = distill_result.get("distilled_content", "") or raw_text[:500]

    document_record = {
        "id": str(uuid.uuid4()),
        "filename": original_filename,
        "mime_type": mime_type,
        "size_bytes": len(file_bytes),
        "distilled_content": distilled_content,
        "confidence_label": CONFIDENCE_LABEL_DOCUMENT,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    return document_record


def store_session_document(session_id: str, document_record: Dict[str, Any], user=None) -> None:
    """
    Store the distilled document content scoped to the current session:
    - Guest sessions: ephemeral in-memory storage (never written to DB).
    - Logged-in sessions: persisted in ChatSession.metadata["uploaded_documents"] following Phase 9 auth rules.
    """
    if not session_id:
        return

    # Check if session belongs to an authenticated user
    from apps.chat.models import ChatSession
    try:
        import uuid as _uuid
        from django.core.exceptions import ValidationError
        valid_uuid = _uuid.UUID(str(session_id))
        session = ChatSession.objects.get(id=valid_uuid)
        if session.user or (user and user.is_authenticated):
            if not isinstance(session.metadata, dict):
                session.metadata = {}
            docs = session.metadata.setdefault("uploaded_documents", [])
            docs.append(document_record)
            session.save(update_fields=["metadata"])
            return
    except (ValueError, TypeError, ValidationError, ChatSession.DoesNotExist, Exception):
        pass

    # Ephemeral store for guest sessions
    if session_id not in _EPHEMERAL_DOCUMENTS:
        _EPHEMERAL_DOCUMENTS[session_id] = []
    _EPHEMERAL_DOCUMENTS[session_id].append(document_record)


def get_session_documents(session_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all distilled documents for the given session.
    Checks DB metadata for authenticated sessions, and ephemeral store for guest sessions.
    """
    if not session_id:
        return []

    from apps.chat.models import ChatSession
    try:
        import uuid as _uuid
        from django.core.exceptions import ValidationError
        valid_uuid = _uuid.UUID(str(session_id))
        session = ChatSession.objects.get(id=valid_uuid)
        if session.user and isinstance(session.metadata, dict):
            return session.metadata.get("uploaded_documents", [])
    except (ValueError, TypeError, ValidationError, ChatSession.DoesNotExist, Exception):
        pass

    return _EPHEMERAL_DOCUMENTS.get(session_id, [])


def format_documents_for_prompt(documents: List[Dict[str, Any]]) -> str:
    """
    Format stored distilled documents for injection into Groq reasoning prompts.
    Attaches explicit provenance instruction and confidence label.
    """
    if not documents:
        return ""

    blocks = []
    for doc in documents:
        blocks.append(
            f"--- UPLOADED DOCUMENT: {doc.get('filename', 'document')} ---\n"
            f"Provenance: Traveler-Uploaded Document ({doc.get('confidence_label', CONFIDENCE_LABEL_DOCUMENT)})\n"
            f"Distilled Travel Facts:\n{doc.get('distilled_content', '')}"
        )

    return (
        "[TRAVELER-UPLOADED DOCUMENT CONTEXT]\n"
        "The traveler provided the following travel details via uploaded documents (tickets, screenshots, or existing bookings).\n"
        "CRITICAL INSTRUCTION: This information was provided directly by the traveler, not scraped from askoliadventure.com. "
        "Any claims, bookings, or flight dates from this document MUST be labeled distinctly as 'from your uploaded document' "
        "and must NEVER carry official company package confidence labels.\n\n"
        + "\n\n".join(blocks)
    )
