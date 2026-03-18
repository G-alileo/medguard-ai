"""
DeepSeek LLM Service - Generate explanations for risk assessments.

IMPORTANT: The LLM only EXPLAINS decisions, it does NOT make them.
The risk score is calculated deterministically by RiskEngine.
"""

import json
import logging
from typing import Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class DeepSeekService:
    """
    Service for generating natural language explanations using DeepSeek API.

    The LLM's role is strictly limited to:
    1. Explaining the risk score (which it cannot change)
    2. Describing interactions and side effects in plain language
    3. Providing context from retrieved documents
    4. Generating user-friendly recommendations

    The LLM CANNOT:
    - Change the risk score
    - Override safety assessments
    - Introduce new medical facts not in the data
    """

    SYSTEM_PROMPT = """You are a medical risk analysis assistant for MedGuard AI.

Your role is to EXPLAIN drug safety findings to users in clear, helpful language.

IMPORTANT RULES:
1. You are given structured findings (interactions, side effects) and a pre-calculated risk score
2. You MUST NOT change or contradict the risk score - it was calculated by a validated algorithm
3. You MUST NOT introduce new medical facts not present in the findings
4. You MUST NOT give medical advice - always recommend consulting healthcare professionals for serious concerns
5. Be concise but thorough - users need to understand the risks
6. Use simple language - avoid excessive medical jargon
7. If the risk is HIGH, be clear about why without causing unnecessary alarm

Your explanation should:
- Summarize the key findings (interactions, treatment appropriateness, side effects)
- Explain WHY each finding contributes to the risk
- Reference the specific drugs and interactions found
- Provide practical guidance based on the risk level"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or getattr(settings, "DEEPSEEK_API_KEY", "")
        self.base_url = base_url or getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")

        # Use mock mode if no API key
        self.mock_mode = not bool(self.api_key)
        if self.mock_mode:
            logger.warning("DeepSeek API key not configured - using mock mode")

    def build_prompt(
        self,
        findings: dict,
        context: list[dict],
        risk_score: int,
        risk_level: str,
    ) -> str:
        """
        Build the prompt for the LLM with all relevant information.

        Args:
            findings: Structured findings from the analysis
            context: Retrieved context from vector store
            risk_score: The pre-calculated risk score (0-100+)
            risk_level: The risk level (LOW/MEDIUM/HIGH)

        Returns:
            Formatted prompt string
        """
        # Format findings
        findings_text = self._format_findings(findings)

        # Format retrieved context
        context_text = self._format_context(context)

        prompt = f"""## Drug Safety Analysis

### Pre-Calculated Risk Assessment
- **Risk Score**: {risk_score} points
- **Risk Level**: {risk_level}

### Structured Findings
{findings_text}

### Supporting Medical Context
{context_text}

### Your Task
Based on the above findings, provide a clear explanation for the user that:
1. Summarizes what we found (in 2-3 sentences)
2. Explains the main risk factors (interactions, treatment concerns, side effects)
3. Justifies why the risk is {risk_level} (reference the specific findings)
4. Gives practical guidance appropriate for the risk level

Remember: The risk score of {risk_score} ({risk_level}) was calculated by our validated algorithm and CANNOT be changed. Your job is to explain it clearly."""

        return prompt

    def _format_findings(self, findings: dict) -> str:
        """Format findings into readable text."""
        parts = []

        # Treatment assessment
        treatment = findings.get("treatment", {})
        if treatment:
            treats = "indicated" if treatment.get("overall_treats") else "NOT indicated"
            confidence = treatment.get("confidence", "unknown")
            parts.append(
                f"**Treatment Assessment**: Drug is {treats} for reported symptoms "
                f"(confidence: {confidence})"
            )
            if treatment.get("reason"):
                parts.append(f"  - {treatment['reason']}")

        # Interactions
        interaction_summary = findings.get("interaction_summary", {})
        interactions = findings.get("interactions", [])
        if interactions:
            parts.append(f"\n**Drug Interactions**: {len(interactions)} found")
            for interaction in interactions[:5]:  # Limit to top 5
                drug = interaction.get("existing_drug", "unknown")
                severity = interaction.get("severity", "unknown")
                desc = interaction.get("description", "No description")[:200]
                parts.append(f"  - {drug}: {severity} severity - {desc}")

        # Side effects
        side_effects = findings.get("side_effects", {})
        if side_effects:
            overlap_count = side_effects.get("overlapping_count", 0)
            if overlap_count > 0:
                parts.append(f"\n**Side Effect Concerns**: {overlap_count} overlaps with current symptoms")
                parts.append(f"  - {side_effects.get('explanation', '')}")

        return "\n".join(parts) if parts else "No significant findings."

    def _format_context(self, context: list[dict]) -> str:
        """Format retrieved context into readable text."""
        if not context:
            return "No additional context available."

        parts = []
        for i, item in enumerate(context[:3], 1):  # Limit to 3 items
            text = item.get("text", "")[:300]  # Limit text length
            source = item.get("metadata", {}).get("section", "Unknown source")
            parts.append(f"{i}. [{source}]: {text}...")

        return "\n".join(parts)

    def generate_explanation(
        self,
        findings: dict,
        context: list[dict],
        risk_score: int,
        risk_level: str,
    ) -> str:
        """
        Generate a natural language explanation of the risk assessment.

        Args:
            findings: Structured findings from the pipeline
            context: Retrieved context from vector store
            risk_score: Pre-calculated risk score
            risk_level: Risk level (LOW/MEDIUM/HIGH)

        Returns:
            Generated explanation text
        """
        if self.mock_mode:
            return self._generate_mock_explanation(findings, risk_score, risk_level)

        try:
            prompt = self.build_prompt(findings, context, risk_score, risk_level)

            response = self._call_api(prompt)
            return response

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            # Fallback to mock explanation
            return self._generate_mock_explanation(findings, risk_score, risk_level)

    def _call_api(self, prompt: str) -> str:
        """Call the DeepSeek API."""
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,  # Low temperature for more consistent outputs
            "max_tokens": 500,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _generate_mock_explanation(
        self,
        findings: dict,
        risk_score: int,
        risk_level: str,
    ) -> str:
        """
        Generate a mock explanation when API is not available.

        This provides a reasonable fallback that's still useful.
        """
        parts = []

        # Opening based on risk level
        if risk_level == "LOW":
            parts.append(
                "Based on our analysis, this medication appears to be relatively safe for your situation."
            )
        elif risk_level == "MEDIUM":
            parts.append(
                "Our analysis has identified some concerns that you should be aware of before taking this medication."
            )
        else:
            parts.append(
                "Our analysis has identified significant risks with this medication in your current situation."
            )

        # Add interaction details
        interactions = findings.get("interactions", [])
        if interactions:
            high_risk = [i for i in interactions if i.get("severity") in ["critical", "high"]]
            if high_risk:
                drugs = [i.get("existing_drug", "a medication") for i in high_risk]
                parts.append(
                    f"There are serious interactions with {', '.join(drugs)} that could cause adverse effects."
                )
            elif interactions:
                parts.append(
                    f"We found {len(interactions)} potential drug interaction(s) that may affect how these medications work together."
                )

        # Add treatment concern
        treatment = findings.get("treatment", {})
        if treatment and not treatment.get("overall_treats"):
            parts.append(
                "Additionally, this drug may not be the most appropriate choice for your reported symptoms."
            )

        # Add side effect concern
        side_effects = findings.get("side_effects", {})
        if side_effects and side_effects.get("overlapping_count", 0) > 0:
            parts.append(
                "Some of the drug's side effects overlap with symptoms you're already experiencing, "
                "which could make those symptoms worse."
            )

        # Add recommendation
        if risk_level == "HIGH":
            parts.append(
                "We strongly recommend consulting with a healthcare professional before taking this medication."
            )
        elif risk_level == "MEDIUM":
            parts.append(
                "Consider discussing these findings with a pharmacist or your doctor."
            )
        else:
            parts.append(
                "As always, follow the recommended dosage and watch for any unusual reactions."
            )

        return " ".join(parts)

    def is_available(self) -> bool:
        """Check if the API is available and configured."""
        return not self.mock_mode


# Singleton instance
_llm_service: Optional[DeepSeekService] = None


def get_llm_service() -> DeepSeekService:
    """Get the global DeepSeekService instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = DeepSeekService()
    return _llm_service
