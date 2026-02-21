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
        Extract common resume sections
        
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
        
        # Common section headers (case-insensitive)
        education_keywords = ['education', 'academic background', 'qualifications']
        experience_keywords = ['experience', 'work history', 'employment', 'professional experience']
        skills_keywords = ['skills', 'technical skills', 'competencies']
        summary_keywords = ['summary', 'objective', 'profile', 'about']
        
        # Simple section detection (can be enhanced)
        text_lower = text.lower()
        
        # Find education section
        for keyword in education_keywords:
            if keyword in text_lower:
                sections['education'] = text  # Simplified: return full text
                break
        
        # Find experience section
        for keyword in experience_keywords:
            if keyword in text_lower:
                sections['experience'] = text  # Simplified: return full text
                break
        
        # Find skills section
        for keyword in skills_keywords:
            if keyword in text_lower:
                sections['skills'] = text  # Simplified: return full text
                break
        
        # If no sections found, put everything in 'other'
        if not any(sections.values()):
            sections['other'] = text
        
        return sections
