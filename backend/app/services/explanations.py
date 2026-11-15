"""
AI Explanations Service - Interpret All Model Outputs

Provides clear, human-interpretable explanations for:
- ML predictions
- Technical signals
- Fundamental scores
- News sentiment
- Includes uncertainty & limitations communication
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class ExplanationService:
    """Generate AI-interpretable explanations."""

    def __init__(self):
        self.llm_service = get_llm_service()

    def explain_ml_prediction(
        self,
        ticker: str,
        prediction: Dict[str, Any],
        model_name: str = "gradient_boost",
        historical_accuracy: float = 0.68,
    ) -> str:
        """Explain an ML prediction in human terms."""
        try:
            direction = prediction.get("direction", "UNKNOWN")  # UP/DOWN
            confidence = prediction.get("confidence", 0.5)
            current_price = prediction.get("current_price", 0)
            prediction_price = prediction.get("prediction_price", 0)

            # Calculate expected move
            expected_move_pct = 0
            if current_price:
                expected_move_pct = ((prediction_price - current_price) / current_price) * 100

            context = {
                "ticker": ticker,
                "direction": direction,
                "confidence": confidence,
                "confidence_pct": f"{confidence*100:.0f}%",
                "expected_move": f"{expected_move_pct:.1f}%",
                "current_price": current_price,
                "prediction_price": prediction_price,
                "model": model_name,
                "historical_accuracy": f"{historical_accuracy*100:.0f}%",
            }

            prompt = f"""
Explain this ML stock prediction in clear, non-technical terms.

Prediction Details:
- Stock: {ticker}
- Direction: {direction}
- Confidence: {confidence*100:.0f}%
- Expected Move: {expected_move_pct:.1f}%
- Model Accuracy (historical): {historical_accuracy*100:.0f}%

Create explanation with these sections:

## Prediction Summary
- What the model predicts
- Confidence level interpretation
- Expected price movement

## What This Means
- In simple language, what this prediction suggests
- How confident we should be (not overconfident)

## Key Factors
- Main reasons for this prediction
- What the model is seeing in the data

## Important Limitations
- What could go wrong
- What the model can't predict
- Market risks not captured

## Proper Usage
- How to use this prediction (as ONE input)
- What NOT to do with it
- Recommendation: combine with other analysis

Guidelines:
- Use markdown formatting
- Be honest about limitations
- Avoid guarantees or certainty language
- Use phrase "the model suggests" not "the stock will"
- Include clear disclaimers
- Keep accessible to non-technical readers
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are an AI/ML expert. Explain predictions clearly and honestly, with emphasis on limitations.",
                temperature=0.5,
                max_tokens=1500,
            )

            # Add uncertainty section
            explanation = response.content + self._add_uncertainty_footer(
                confidence=confidence,
                model_type=model_name,
            )

            return explanation

        except Exception as e:
            logger.error(f"Error explaining ML prediction: {e}")
            return f"Error generating explanation: {str(e)}"

    def explain_technical_signal(
        self,
        ticker: str,
        signal: str,
        indicators: Dict[str, Any],
    ) -> str:
        """Explain a technical trading signal."""
        try:
            context = {
                "ticker": ticker,
                "signal": signal,
                "indicators": indicators,
            }

            prompt = f"""
Explain this technical trading signal in clear terms.

Stock: {ticker}
Signal: {signal}

Indicators:
{json.dumps(indicators, indent=2, default=str)}

Create explanation with sections:

## Signal Interpretation
- What does a {signal} signal mean?
- How strong is it?

## Supporting Indicators
- Which indicators support this signal?
- How do they reinforce each other?

## What to Watch
- Key price levels
- Confirmation signals
- When this could reverse

## Risks
- What could invalidate this signal?
- Market conditions that could change outlook
- Stop loss considerations

Guidelines:
- Use markdown formatting
- Explain what each indicator means
- Be specific with numbers and levels
- Avoid guarantees
- Include disclaimer about market risk
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a technical analyst. Explain signals clearly with practical guidance.",
                temperature=0.5,
                max_tokens=1200,
            )

            explanation = response.content + self._add_uncertainty_footer(
                confidence=0.6,
                model_type="technical_analysis",
            )

            return explanation

        except Exception as e:
            logger.error(f"Error explaining technical signal: {e}")
            return f"Error: {str(e)}"

    def explain_fundamental_score(
        self,
        ticker: str,
        score: float,
        factors: Dict[str, Any],
    ) -> str:
        """Explain why a company received a fundamental score."""
        try:
            score_quality = "Excellent" if score >= 80 else "Good" if score >= 70 else "Fair" if score >= 60 else "Poor"

            context = {
                "ticker": ticker,
                "score": score,
                "score_quality": score_quality,
                "factors": factors,
            }

            prompt = f"""
Explain this fundamental score in clear terms.

Stock: {ticker}
Score: {score}/100 ({score_quality})

Contributing Factors:
{json.dumps(factors, indent=2, default=str)}

Create explanation with sections:

## What This Score Means
- Is {score} good or bad?
- How does it compare to industry averages?
- What it suggests about the company

## Key Factors
- Which factors most influenced the score?
- What are the strongest areas?
- What areas are weaker?

## Investment Implications
- What this score means for different investor types
- Growth vs value investor implications
- Risk considerations

## What Could Change This Score
- Factors that could improve the score
- Red flags that could lower it

Guidelines:
- Use markdown formatting
- Be clear about what's good vs bad
- Avoid overstating score significance
- Include caveats about AI analysis
- Recommend verification with fundamentals
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a financial analyst. Explain fundamental scores clearly.",
                temperature=0.5,
                max_tokens=1200,
            )

            explanation = response.content + self._add_uncertainty_footer(
                confidence=0.65,
                model_type="fundamental_analysis",
            )

            return explanation

        except Exception as e:
            logger.error(f"Error explaining fundamental score: {e}")
            return f"Error: {str(e)}"

    def explain_news_sentiment(
        self,
        ticker: str,
        sentiment_score: float,
        sentiment_category: str,
        key_themes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Explain news sentiment and implications."""
        try:
            context = {
                "ticker": ticker,
                "sentiment_score": sentiment_score,
                "sentiment_category": sentiment_category,
                "themes": key_themes or {},
            }

            # Sentiment interpretation
            if sentiment_score > 0.6:
                sentiment_strength = "strongly positive"
            elif sentiment_score > 0.5:
                sentiment_strength = "moderately positive"
            elif sentiment_score < 0.4:
                sentiment_strength = "strongly negative"
            elif sentiment_score < 0.5:
                sentiment_strength = "moderately negative"
            else:
                sentiment_strength = "neutral"

            prompt = f"""
Explain this news sentiment analysis.

Stock: {ticker}
Sentiment Score: {sentiment_score:.2f}/1.0 ({sentiment_strength})

Key Themes:
{json.dumps(key_themes, indent=2, default=str) if key_themes else 'No specific themes'}

Create explanation with sections:

## What The Sentiment Tells Us
- Overall sentiment interpretation
- Is it positive, negative, or neutral?
- Relative to historical patterns

## Key Themes
- What are the main topics in recent news?
- Are they positive or negative?
- What do investors seem to care about?

## Possible Market Impact
- How might this sentiment affect the stock?
- Short-term vs long-term implications
- Historical patterns for similar sentiment

## Important Context
- Don't confuse sentiment with fundamentals
- News is backward-looking, not predictive
- Market can surprise despite sentiment

## Proper Usage
- Use sentiment as ONE input
- Don't trade solely on sentiment
- Monitor for sentiment changes
- Verify with company fundamentals

Guidelines:
- Use markdown formatting
- Be specific with numbers
- Explain what drove sentiment
- Include strong disclaimers
- Remind: sentiment ≠ stock movement guarantee
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a market analyst. Explain sentiment analysis clearly with context.",
                temperature=0.5,
                max_tokens=1200,
            )

            explanation = response.content + self._add_uncertainty_footer(
                confidence=0.6,
                model_type="sentiment_analysis",
            )

            return explanation

        except Exception as e:
            logger.error(f"Error explaining news sentiment: {e}")
            return f"Error: {str(e)}"

    def _add_uncertainty_footer(
        self,
        confidence: float,
        model_type: str,
    ) -> str:
        """Add uncertainty and limitations section to any explanation."""

        confidence_level = "High" if confidence > 0.75 else "Moderate" if confidence > 0.6 else "Low"

        footer = f"""

---

## ⚠️ Uncertainty & Limitations

### Confidence Level
- **{confidence_level} Confidence** ({confidence*100:.0f}%)
- This is an AI-generated analysis, not financial advice
- Not a substitute for professional investment advice

### What This Analysis Cannot Predict
- Unexpected company announcements
- Market crashes or black swan events
- Geopolitical surprises
- Changes in market sentiment
- Regulatory changes

### How to Use This Properly
✅ **Do:**
- Use as one input among many
- Combine with fundamental analysis
- Verify important claims independently
- Consider your risk tolerance
- Set stop losses appropriately
- Review regularly as new data arrives

❌ **Don't:**
- Treat as investment recommendation
- Risk money you can't afford to lose
- Ignore the fundamentals
- Trade based solely on this analysis
- Assume past patterns continue
- Override your investment thesis

### Data Recency
- Analysis based on latest available data
- Market conditions change rapidly
- Always check for breaking news
- Monitor positions actively

### Disclaimer
*This analysis is for informational purposes only. Past performance does not guarantee future results. 
Always consult with a qualified financial advisor before making investment decisions. 
The author/AI system is not liable for any losses resulting from using this information.*
"""

        return footer


def get_explanation_service() -> ExplanationService:
    """Create explanation service instance."""
    return ExplanationService()
