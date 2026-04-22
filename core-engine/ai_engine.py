import os
import json
import asyncio
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import Literal

# Configure the Gemini API key from environment
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "YOUR_API_KEY"))

class TradeDecision(BaseModel):
    action: Literal["BUY", "SELL", "HOLD", "CLOSE"] = Field(description="The trading action to take")
    conviction: int = Field(description="Confidence score from 0 to 100")
    regime: str = Field(description="Market state, e.g., 'Trending', 'Ranging', 'Volatility Breakout'")
    reasoning: str = Field(description="Markdown string explaining the trade logic for the UI stream")

class GeminiTradeEngine:
    def __init__(self):
        # We use gemini-1.5-pro for deep reasoning capabilities
        # It natively supports strict JSON output schema generation
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    async def analyze_market_state(self, market_data: dict, risk_params: dict) -> TradeDecision:
        """
        Asynchronously calls Gemini to analyze the market state.
        This function utilizes run_in_executor to ensure the HTTP request
        to Vertex AI/Gemini does not block the asyncio event loop.
        """
        prompt = self._build_prompt(market_data, risk_params)
        
        loop = asyncio.get_running_loop()
        
        try:
            # Execute the synchronous generate_content call in a background thread
            response = await loop.run_in_executor(
                None, 
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=TradeDecision
                    )
                )
            )
            
            # Parse the strict JSON response into our Pydantic model
            decision_dict = json.loads(response.text)
            return TradeDecision(**decision_dict)
            
        except Exception as e:
            print(f"[AI ENGINE] Error during analysis: {e}")
            return TradeDecision(
                action="HOLD",
                conviction=0,
                regime="System Error",
                reasoning=f"**Error:** AI Analysis failed or timed out: {str(e)}"
            )

    def _build_prompt(self, market_data: dict, risk_params: dict) -> str:
        return f"""
You are the BullionHunter XAUUSD core trading brain.
Analyze the following aggregated market data and active risk parameters.

Market Data (Aggregated OHLCV & Flow):
{json.dumps(market_data, indent=2)}

Active Risk Desk Parameters:
{json.dumps(risk_params, indent=2)}

Synthesize the data and determine the optimal trading action. 
You must strictly return the requested JSON schema. Provide a detailed markdown string for 'reasoning' detailing your logic, momentum shifts, and risk checks so the human operator can read it in the UI telemetry hub.
"""
