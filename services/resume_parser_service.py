"""Resume parsing service for PDF and DOCX files"""
import logging
import re

logger = logging.getLogger(__name__)


class ResumeParserService:
    """Service for parsing resume files"""
    
    @staticmethod
    def parse_pdf(file_path):
        """
        Extract text from PDF file
        
        Args:
            file_path: Absolute path to PDF file
        
        Returns:
            str: Extracted text or empty string if failed
        """
        try:
            from pdfminer.high_level import extract_text as pdf_extract_text
            text = pdf_extract_text(file_path)
            return text.strip() if text else ""
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            return ""
    
    @staticmethod
    def parse_docx(file_path):
        """
        Extract text from DOCX file
        
        Args:
            file_path: Absolute path to DOCX file
        
        Returns:
            str: Extracted text or empty string if failed
        """
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs]
            text = '\n'.join(paragraphs)
            return text.strip() if text else ""
        except Exception as e:
            logger.error(f"Error parsing DOCX {file_path}: {e}")
            return ""
    
    @staticmethod
    def parse_resume(file_path, file_type):
        """
        Parse resume file based on type
        
        Args:
            file_path: Absolute path to file
            file_type: 'pdf' or 'docx'
        
        Returns:
            str: Extracted text or empty string if failed
        """
        if file_type == 'pdf':
            return ResumeParserService.parse_pdf(file_path)
        elif file_type == 'docx':
            return ResumeParserService.parse_docx(file_path)
        else:
            logger.error(f"Unsupported file type: {file_type}")
            return ""
    
    @staticmethod
    def extract_sections(text):
        """
        Extract common resume sections by splitting on header lines.

        Args:
            text: Resume text

        Returns:
            dict: Sections dict {section_name: content}
        """
        sections = {
            'education': '',
            'experience': '',
            'skills': '',
            'summary': '',
            'other': ''
        }

        if not text:
            return sections

        # Map keywords → section keys (order matters: longer phrases first)
        header_map = [
            ('professional experience', 'experience'),
            ('work experience', 'experience'),
            ('work history', 'experience'),
            ('employment', 'experience'),
            ('experience', 'experience'),
            ('academic background', 'education'),
            ('qualifications', 'education'),
            ('education', 'education'),
            ('technical skills', 'skills'),
            ('competencies', 'skills'),
            ('skills', 'skills'),
            ('professional summary', 'summary'),
            ('objective', 'summary'),
            ('profile', 'summary'),
            ('summary', 'summary'),
            ('about', 'summary'),
        ]

        # Build a regex that matches any header keyword on its own line
        # e.g. "EDUCATION", "Education:", "== Experience ==", "SKILLS & TOOLS"
        keywords_pattern = '|'.join(re.escape(kw) for kw, _ in header_map)
        header_re = re.compile(
            rf'^[=\-\s]*({keywords_pattern})[:\s=\-]*$',
            re.IGNORECASE | re.MULTILINE,
        )

        # Find all header positions
        matches = list(header_re.finditer(text))

        if not matches:
            # No recognisable headers — put everything in 'other'
            sections['other'] = text.strip()
            return sections

        # Content before the first header → 'summary' or 'other'
        preamble = text[:matches[0].start()].strip()
        if preamble:
            sections['summary'] = preamble

        # Extract content between consecutive headers
        for i, match in enumerate(matches):
            matched_keyword = match.group(1).lower().strip()
            section_key = 'other'
            for kw, key in header_map:
                if kw == matched_keyword:
                    section_key = key
                    break

            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            # Append if the section already has content (e.g., two "Skills" headers)
            if sections[section_key]:
                sections[section_key] += '\n\n' + content
            else:
                sections[section_key] = content

        return sections
