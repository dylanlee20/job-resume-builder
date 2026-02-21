"""Resume assessment service using LLM"""
import logging
import json
from datetime import datetime, timedelta
from config import Config
from models.database import db
from models.resume_assessment import ResumeAssessment

logger = logging.getLogger(__name__)


class ResumeAssessmentService:
    """Service for AI-powered resume assessment"""
    
    @staticmethod
    def check_rate_limit(user_id):
        """
        Check if user has exceeded daily assessment limit
        
        Args:
            user_id: User ID
        
        Returns:
            Tuple (is_allowed: bool, remaining: int)
        """
        from models.user import User
        
        user = User.query.get(user_id)
        if not user:
            return (False, 0)
        
        # Premium users have unlimited assessments
        if user.tier == 'premium':
            return (True, -1)  # -1 means unlimited
        
        # Free users: check daily limit
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_count = ResumeAssessment.query.filter(
            ResumeAssessment.user_id == user_id,
            ResumeAssessment.created_at >= today_start,
            ResumeAssessment.assessment_type == 'free'
        ).count()
        
        limit = Config.FREE_TIER_DAILY_ASSESSMENTS
        remaining = max(0, limit - today_count)
        
        return (remaining > 0, remaining)
    
    @staticmethod
    def assess_resume(extracted_text, target_industries=None):
        """
        Assess resume using LLM
        
        Args:
            extracted_text: Resume text
            target_industries: List of target industries (optional)
        
        Returns:
            Dict with assessment results or None if failed
        """
        if not extracted_text or len(extracted_text) < 50:
            return {
                'overall_score': 0,
                'strengths': ['Unable to parse resume text'],
                'weaknesses': ['Please ensure the resume is readable'],
                'industry_compatibility': {},
                'detailed_feedback': 'Could not analyze resume due to insufficient text.'
            }
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=Config.OPENAI_API_KEY)
            
            # Prepare system prompt
            system_prompt = """You are an expert finance career advisor specializing in AI-proof industries:
Investment Banking, Sales & Trading, Portfolio Management, Risk Management, and M&A Advisory.

Analyze the following resume and provide a JSON response with these exact fields:
1. overall_score (integer 0-100): How competitive is this resume for top-tier finance roles?
2. strengths (array of 3-5 strings): Specific strengths
3. weaknesses (array of 3-5 strings): Specific areas for improvement
4. industry_compatibility (object): Score 0-100 for each AI-proof industry:
   - "Investment Banking"
   - "Sales & Trading"
   - "Portfolio Management"
   - "Risk Management"
   - "M&A Advisory"
5. key_recommendations (array of 3 strings): Actionable next steps

Respond with ONLY valid JSON, no other text."""
            
            # Prepare user prompt
            user_prompt = f"""Resume Text:
{extracted_text[:3000]}

{f'Target Industries: {", ".join(target_industries)}' if target_industries else ''}

Provide the assessment in JSON format."""
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response (in case there's extra text)
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                content = content[json_start:json_end]
            
            result = json.loads(content)
            
            # Validate and normalize
            assessment = {
                'overall_score': min(100, max(0, int(result.get('overall_score', 0)))),
                'strengths': result.get('strengths', [])[:5],
                'weaknesses': result.get('weaknesses', [])[:5],
                'industry_compatibility': result.get('industry_compatibility', {}),
                'detailed_feedback': json.dumps(result, indent=2),
                'model_used': 'gpt-4o-mini',
                'tokens_used': response.usage.total_tokens
            }
            
            logger.info(f"Resume assessed successfully. Score: {assessment['overall_score']}")
            return assessment
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return ResumeAssessmentService._get_fallback_assessment()
        except Exception as e:
            logger.error(f"Error assessing resume: {e}")
            return ResumeAssessmentService._get_fallback_assessment()
    
    @staticmethod
    def _get_fallback_assessment():
        """Fallback assessment when LLM fails"""
        return {
            'overall_score': 50,
            'strengths': [
                'Resume uploaded successfully',
                'Readable format'
            ],
            'weaknesses': [
                'Unable to perform AI analysis at this time',
                'Please try again later'
            ],
            'industry_compatibility': {
                'Investment Banking': 50,
                'Sales & Trading': 50,
                'Portfolio Management': 50,
                'Risk Management': 50,
                'M&A Advisory': 50
            },
            'detailed_feedback': 'Fallback assessment due to API unavailability.',
            'model_used': 'fallback',
            'tokens_used': 0
        }
