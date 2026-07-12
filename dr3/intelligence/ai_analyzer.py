"""
DR3 OSINT — AI Analyzer (Gemini Integration)
Uses Google Gemini API to provide intelligent analysis of discovered profiles.
Falls back to rule-based analysis when API key is not available.
"""

import json
import logging
from typing import List, Optional

from ..core.models import Evidence, IdentityReport, ProfileData

logger = logging.getLogger("dr3.ai_analyzer")


class AIAnalyzer:
    """
    AI-powered identity analysis engine.
    Uses Gemini API when available, falls back to rule-based analysis.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._model = None

    @property
    def is_ai_available(self) -> bool:
        return bool(self.api_key)

    async def analyze_report(self, report: IdentityReport) -> IdentityReport:
        """Analyze the complete investigation report with AI."""
        if self.is_ai_available:
            try:
                report = await self._ai_analyze(report)
            except Exception as e:
                logger.warning(f"AI analysis failed, using rule-based: {e}")
                report = self._rule_based_analyze(report)
        else:
            report = self._rule_based_analyze(report)

        return report

    async def _ai_analyze(self, report: IdentityReport) -> IdentityReport:
        """Use Gemini API for intelligent analysis."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            # Build context for AI
            profiles_summary = []
            for p in report.profiles[:20]:  # Limit to top 20
                profiles_summary.append({
                    "site": p.site_name,
                    "url": p.url,
                    "display_name": p.display_name,
                    "bio": p.bio[:200] if p.bio else "",
                    "avatar": bool(p.avatar_url),
                    "confidence": p.confidence_score,
                    "tags": p.tags[:5],
                })

            prompt = f"""You are a professional OSINT analyst. Analyze the following investigation results for the username "{report.target_username}".

Profiles found ({len(report.profiles)} total):
{json.dumps(profiles_summary, indent=2)}

Provide a concise analysis in JSON format with these fields:
1. "cross_platform_analysis": A paragraph analyzing patterns across platforms (shared names, bios, images, activity patterns). Be specific about what matches.
2. "risk_assessment": Assess the digital footprint risk level (Low/Medium/High) with explanation.
3. "ai_analysis": Your expert assessment of whether these accounts likely belong to the same person, and why.
4. "suggested_steps": A list of 3-5 specific next investigation steps.

Be professional, evidence-based, and concise. Do not speculate without evidence. If data is limited, say so.
Respond ONLY with valid JSON, no markdown."""

            response = model.generate_content(prompt)
            text = response.text.strip()

            # Clean potential markdown wrapping
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]

            analysis = json.loads(text)

            report.cross_platform_analysis = analysis.get("cross_platform_analysis", "")
            report.risk_assessment = analysis.get("risk_assessment", "")
            report.ai_analysis = analysis.get("ai_analysis", "")

            ai_steps = analysis.get("suggested_steps", [])
            if ai_steps:
                report.suggested_next_steps = ai_steps

            logger.info("AI analysis completed successfully")

        except ImportError:
            logger.warning("google-generativeai not installed, using rule-based analysis")
            report = self._rule_based_analyze(report)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response: {e}")
            report = self._rule_based_analyze(report)
        except Exception as e:
            logger.warning(f"AI analysis error: {e}")
            report = self._rule_based_analyze(report)

        return report

    def _rule_based_analyze(self, report: IdentityReport) -> IdentityReport:
        """Rule-based analysis when AI is not available."""
        profiles = report.profiles

        if not profiles:
            report.cross_platform_analysis = "No accounts were found for this username."
            report.risk_assessment = "No digital footprint detected."
            report.ai_analysis = "Insufficient data for analysis."
            return report

        # Cross-platform analysis
        analysis_parts = []
        high_conf = [p for p in profiles if p.confidence_score >= 70]
        med_conf = [p for p in profiles if 50 <= p.confidence_score < 70]
        low_conf = [p for p in profiles if p.confidence_score < 50]

        analysis_parts.append(
            f"The investigation identified {len(profiles)} potential accounts for "
            f"'{report.target_username}' across multiple platforms."
        )

        if high_conf:
            sites = ", ".join(p.site_name for p in high_conf[:5])
            analysis_parts.append(
                f"{len(high_conf)} high-confidence matches were found on: {sites}."
            )

        # Check for shared display names
        display_names = [p.display_name for p in profiles if p.display_name]
        if len(display_names) >= 2:
            unique_names = set(n.lower().strip() for n in display_names)
            if len(unique_names) == 1:
                analysis_parts.append(
                    f"All profiles share the same display name: '{display_names[0]}', "
                    "strongly suggesting they belong to the same individual."
                )
            elif len(unique_names) < len(display_names):
                analysis_parts.append(
                    "Some profiles share similar display names, supporting identity correlation."
                )

        # Check for shared bios
        bios = [p.bio for p in profiles if p.bio and len(p.bio) > 20]
        if len(bios) >= 2:
            import difflib
            for i in range(min(len(bios), 5)):
                for j in range(i + 1, min(len(bios), 5)):
                    ratio = difflib.SequenceMatcher(None, bios[i].lower(), bios[j].lower()).ratio()
                    if ratio > 0.6:
                        analysis_parts.append(
                            "Similar biographical descriptions were found across multiple platforms, "
                            "indicating consistent self-representation."
                        )
                        break

        # Tag analysis
        all_tags = []
        for p in profiles:
            all_tags.extend(p.tags)
        if all_tags:
            from collections import Counter
            tag_counts = Counter(all_tags).most_common(5)
            top_tags = ", ".join(f"{tag} ({count})" for tag, count in tag_counts)
            analysis_parts.append(f"Most common platform categories: {top_tags}.")

        report.cross_platform_analysis = " ".join(analysis_parts)

        # Risk assessment
        if len(high_conf) >= 5:
            report.risk_assessment = (
                "HIGH — Significant digital footprint detected. "
                f"The username '{report.target_username}' has a strong presence "
                f"across {len(high_conf)} major platforms, making the individual "
                "highly identifiable through open-source intelligence."
            )
        elif len(high_conf) >= 2:
            report.risk_assessment = (
                "MEDIUM — Moderate digital footprint detected. "
                f"Several confirmed accounts exist for this username, "
                "providing a reasonable basis for identity correlation."
            )
        else:
            report.risk_assessment = (
                "LOW — Limited digital footprint detected. "
                "Few confirmed accounts were found, limiting the scope of "
                "open-source intelligence available."
            )

        # AI analysis summary
        if high_conf:
            confidence_desc = (
                f"Based on {len(report.evidence_summary)} pieces of evidence, "
                f"there is {'strong' if len(high_conf) > 3 else 'moderate'} indication "
                f"that the discovered accounts belong to the same individual. "
                f"Key evidence includes exact username matches across "
                f"{len(high_conf)} platforms"
            )
            if display_names:
                confidence_desc += f" and consistent use of the display name '{display_names[0]}'"
            confidence_desc += "."
            report.ai_analysis = confidence_desc
        else:
            report.ai_analysis = (
                "Insufficient high-confidence matches to make a definitive "
                "identity correlation. Results should be manually verified."
            )

        return report
