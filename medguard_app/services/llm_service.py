import json
import logging
from typing import Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class DeepSeekService:

    SYSTEM_PROMPT = """You are a medical risk analysis assistant for MedGuard AI.

Your role is to EXPLAIN drug safety findings to users in clear, concise language.

IMPORTANT RULES:
1. You are given structured findings (interactions, side effects) and a pre-calculated risk score
2. You MUST NOT change or contradict the risk score - it was calculated by a validated algorithm
3. You MUST NOT introduce new medical facts not present in the findings
4. You MUST NOT give medical advice - always recommend consulting healthcare professionals for serious concerns
5. Be BRIEF and DIRECT - users want quick, actionable information
6. Use simple language - avoid excessive medical jargon
7. Keep your entire response to 2-3 sentences maximum

Your explanation should be ONE concise paragraph that covers the key risk factors and recommended action."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or getattr(settings, "DEEPSEEK_API_KEY", "")
        self.base_url = base_url or getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")

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

        findings_text = self._format_findings(findings)

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
Provide a single, concise paragraph (2-3 sentences) that explains the key risk factors and what action the user should take. Be direct and actionable."""

        return prompt

    def _format_findings(self, findings: dict) -> str:
        """Format findings into readable text."""
        parts = []

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

        interaction_summary = findings.get("interaction_summary", {})
        interactions = findings.get("interactions", [])
        if interactions:
            parts.append(f"\n**Drug Interactions**: {len(interactions)} found")
            for interaction in interactions[:5]:
                drug = interaction.get("existing_drug", "unknown")
                severity = interaction.get("severity", "unknown")
                desc = interaction.get("description", "No description")[:200]
                parts.append(f"  - {drug}: {severity} severity - {desc}")

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
        for i, item in enumerate(context[:3], 1):
            text = item.get("text", "")[:300]
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

        if self.mock_mode:
            return self._generate_mock_explanation(findings, risk_score, risk_level)

        try:
            prompt = self.build_prompt(findings, context, risk_score, risk_level)

            response = self._call_api(prompt)
            return response

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
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
            "temperature": 0.3,
            "max_tokens": 150,
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

        risk_factors = []

        interactions = findings.get("interactions", [])
        if interactions:
            high_risk = [i for i in interactions if i.get("severity") in ["critical", "high"]]
            if high_risk:
                risk_factors.append(f"serious interactions with {len(high_risk)} medication(s)")
            else:
                risk_factors.append(f"{len(interactions)} potential drug interaction(s)")

        treatment = findings.get("treatment", {})
        if treatment and not treatment.get("overall_treats"):
            risk_factors.append("medication may not be appropriate for your symptoms")

        side_effects = findings.get("side_effects", {})
        if side_effects and side_effects.get("overlapping_count", 0) > 0:
            risk_factors.append("side effects may worsen current symptoms")

        if risk_factors:
            factors_text = ", ".join(risk_factors)
            if risk_level == "HIGH":
                return f"This medication received a {risk_level} risk rating due to {factors_text}. Consult a healthcare professional immediately before taking this medication."
            elif risk_level == "MEDIUM":
                return f"This medication received a {risk_level} risk rating due to {factors_text}. Consider discussing these concerns with a pharmacist or doctor."
            else:
                return f"This medication has a {risk_level} risk rating with minor concerns: {factors_text}. Follow recommended dosage and monitor for unusual reactions."
        else:
            return f"This medication received a {risk_level} risk rating with no major concerns identified. Follow recommended dosage and consult a healthcare provider if you have questions."

    def is_available(self) -> bool:
        """Check if the API is available and configured."""
        return not self.mock_mode


_llm_service: Optional[DeepSeekService] = None


def get_llm_service() -> DeepSeekService:
    """Get the global DeepSeekService instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = DeepSeekService()
    return _llm_service
