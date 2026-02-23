"""Resume builder service - AI-powered resume generation and formatting"""
import logging
import json
from config import Config

logger = logging.getLogger(__name__)


class ResumeBuilderService:
    """Service for building and formatting resumes using LLM"""

    @staticmethod
    def build_from_scratch(data):
        """
        Generate a professional resume from structured user input.

        Args:
            data: Dict with user's personal info, education, experience, skills

        Returns:
            Dict with 'success', 'resume_text' or 'message'
        """
        # Build context from form data
        sections = []

        # Personal info
        name = data.get('full_name', '').strip()
        if not name:
            return {'success': False, 'message': 'Full name is required'}

        contact_parts = [name]
        if data.get('contact_email'):
            contact_parts.append(data['contact_email'])
        if data.get('phone'):
            contact_parts.append(data['phone'])
        if data.get('location'):
            contact_parts.append(data['location'])
        if data.get('linkedin'):
            contact_parts.append(data['linkedin'])

        sections.append('CONTACT INFO: ' + ' | '.join(contact_parts))

        if data.get('summary'):
            sections.append('SUMMARY: ' + data['summary'])

        if data.get('target_industry'):
            sections.append('TARGET INDUSTRY: ' + data['target_industry'])

        # Education
        edu_schools = data.get('edu_school', [])
        edu_degrees = data.get('edu_degree', [])
        edu_starts = data.get('edu_start', [])
        edu_ends = data.get('edu_end', [])
        edu_gpas = data.get('edu_gpa', [])
        edu_details = data.get('edu_details', [])

        edu_entries = []
        for i in range(len(edu_schools)):
            if i < len(edu_schools) and edu_schools[i].strip():
                entry = edu_schools[i]
                if i < len(edu_degrees) and edu_degrees[i]:
                    entry += ' - ' + edu_degrees[i]
                dates = []
                if i < len(edu_starts) and edu_starts[i]:
                    dates.append(edu_starts[i])
                if i < len(edu_ends) and edu_ends[i]:
                    dates.append(edu_ends[i])
                if dates:
                    entry += ' (' + ' - '.join(dates) + ')'
                if i < len(edu_gpas) and edu_gpas[i]:
                    entry += ', GPA: ' + edu_gpas[i]
                if i < len(edu_details) and edu_details[i]:
                    entry += '. ' + edu_details[i]
                edu_entries.append(entry)

        if edu_entries:
            sections.append('EDUCATION:\n' + '\n'.join(edu_entries))

        # Experience
        exp_companies = data.get('exp_company', [])
        exp_titles = data.get('exp_title', [])
        exp_starts = data.get('exp_start', [])
        exp_ends = data.get('exp_end', [])
        exp_locations = data.get('exp_location', [])
        exp_details_list = data.get('exp_details', [])

        exp_entries = []
        for i in range(len(exp_companies)):
            if i < len(exp_companies) and exp_companies[i].strip():
                entry = exp_companies[i]
                if i < len(exp_titles) and exp_titles[i]:
                    entry += ' - ' + exp_titles[i]
                dates = []
                if i < len(exp_starts) and exp_starts[i]:
                    dates.append(exp_starts[i])
                if i < len(exp_ends) and exp_ends[i]:
                    dates.append(exp_ends[i])
                if dates:
                    entry += ' (' + ' - '.join(dates) + ')'
                if i < len(exp_locations) and exp_locations[i]:
                    entry += ', ' + exp_locations[i]
                if i < len(exp_details_list) and exp_details_list[i]:
                    entry += '\n' + exp_details_list[i]
                exp_entries.append(entry)

        if exp_entries:
            sections.append('EXPERIENCE:\n' + '\n\n'.join(exp_entries))

        # Skills
        skills_parts = []
        if data.get('technical_skills'):
            skills_parts.append('Technical: ' + data['technical_skills'])
        if data.get('soft_skills'):
            skills_parts.append('Soft Skills: ' + data['soft_skills'])
        if data.get('certifications'):
            skills_parts.append('Certifications: ' + data['certifications'])
        if data.get('languages'):
            skills_parts.append('Languages: ' + data['languages'])
        if skills_parts:
            sections.append('SKILLS:\n' + '\n'.join(skills_parts))

        if data.get('additional'):
            sections.append('ADDITIONAL: ' + data['additional'])

        user_input = '\n\n'.join(sections)

        if len(user_input) < 30:
            return {'success': False, 'message': 'Please fill in more information to generate a resume'}

        # Call LLM
        prompt = f"""You are an expert resume writer specializing in finance and professional services.
Given the following information about a candidate, create a polished, professional resume.

Rules:
- Use a clean, standard resume format with clear section headings
- Write impactful bullet points using action verbs and quantified achievements
- If the summary is empty, write a compelling 2-3 sentence professional summary
- Optimize for the target industry if specified
- Keep it to 1 page equivalent (concise but comprehensive)
- Use professional language appropriate for top-tier firms
- Format dates consistently
- List experience in reverse chronological order

Candidate Information:
{user_input}

Generate the complete resume text now. Output ONLY the resume content, no commentary."""

        result = ResumeBuilderService._call_llm(prompt)
        if result:
            return {'success': True, 'resume_text': result}
        return {'success': False, 'message': 'AI generation failed. Please try again.'}

    @staticmethod
    def format_draft(draft_text, target_industry=''):
        """
        Reformat unstructured resume text into professional format.

        Args:
            draft_text: Raw/unformatted resume text
            target_industry: Optional target industry for optimization

        Returns:
            Dict with 'success', 'formatted_text' or 'message'
        """
        if not draft_text or len(draft_text.strip()) < 20:
            return {'success': False, 'message': 'Please provide more resume text (at least 20 characters)'}

        industry_note = f"\nOptimize the formatting for the {target_industry} industry." if target_industry else ""

        prompt = f"""You are an expert resume formatter specializing in professional services and finance.

Take the following unformatted/rough resume text and transform it into a clean, professional resume format.

Rules:
- Identify and organize into standard sections: Contact Info, Summary, Education, Experience, Skills, etc.
- Write proper bullet points with action verbs for experience descriptions
- Format dates consistently (Month Year or Year format)
- Clean up grammar and spelling
- Make bullet points impactful with quantified achievements where possible
- Keep the content accurate - don't invent information, but polish what's there
- Use a standard professional resume format{industry_note}

Raw Resume Text:
{draft_text[:4000]}

Output ONLY the formatted resume, no commentary or explanations."""

        result = ResumeBuilderService._call_llm(prompt)
        if result:
            return {'success': True, 'formatted_text': result}
        return {'success': False, 'message': 'AI formatting failed. Please try again.'}

    @staticmethod
    def revise_resume(original_text, assessment_data=None, target_industry=''):
        """
        Revise an existing resume with before/after improvements (Premium).

        Args:
            original_text: Original resume text
            assessment_data: Optional assessment results dict
            target_industry: Target industry for optimization

        Returns:
            Dict with 'success', 'revised_text', 'changes' or 'message'
        """
        if not original_text or len(original_text.strip()) < 50:
            return {'success': False, 'message': 'Resume text is too short for revision'}

        assessment_context = ""
        if assessment_data:
            weaknesses = assessment_data.get('weaknesses', [])
            if weaknesses:
                assessment_context = f"\nKey areas to improve based on assessment:\n" + "\n".join(f"- {w}" for w in weaknesses)

        industry_note = f"\nTarget industry: {target_industry}" if target_industry else ""

        prompt = f"""You are an expert resume revision specialist for top-tier finance and professional services.

Revise the following resume to be significantly stronger and more competitive.{industry_note}{assessment_context}

Rules:
- Improve bullet points with stronger action verbs and quantified achievements
- Enhance the professional summary to be more compelling
- Optimize formatting and section organization
- Fix any grammar, spelling, or consistency issues
- Make the language more impactful and results-oriented
- Keep all factual information accurate - enhance presentation, don't fabricate

After the revised resume, provide a section called "CHANGES MADE:" with a bulleted list of the key improvements you made.

Original Resume:
{original_text[:4000]}

Output the REVISED RESUME first, then the CHANGES MADE section."""

        result = ResumeBuilderService._call_llm(prompt, max_tokens=2000)
        if result:
            # Split result into revised text and changes
            parts = result.split('CHANGES MADE:')
            revised_text = parts[0].strip()
            changes = parts[1].strip() if len(parts) > 1 else 'Resume has been improved with stronger language and formatting.'

            return {
                'success': True,
                'revised_text': revised_text,
                'changes': changes
            }
        return {'success': False, 'message': 'AI revision failed. Please try again.'}

    @staticmethod
    def _call_llm(prompt, max_tokens=1500):
        """Call the LLM API and return the text response"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=Config.OPENAI_API_KEY)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert professional resume writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"LLM resume generation successful, tokens: {response.usage.total_tokens}")
            return content

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
