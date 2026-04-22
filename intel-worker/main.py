import os
import json
import time
import requests
import feedparser
import zmq
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import Literal
from dotenv import load_dotenv

# Load env variables for Gemini API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "YOUR_API_KEY"))

# The Data Bridge will bind a PULL socket to this port to ingest Intel
ZMQ_INTEL_ADDR = "tcp://127.0.0.1:5557"
POLL_INTERVAL_SEC = 300 # 5 minutes

class AISentimentAnalysis(BaseModel):
    overall_sentiment: Literal["Bullish", "Bearish", "Neutral"] = Field(description="The macro sentiment towards Gold (XAUUSD)")
    conviction_score: int = Field(description="Confidence score from 0 to 100")
    one_sentence_summary: str = Field(description="A concise synthesis of the news and social sentiment")

class IntelWorker:
    def __init__(self):
        self.ctx = zmq.Context()
        self.publisher = self.ctx.socket(zmq.PUSH)
        # Connect to the Data Bridge's designated intel ingestion port
        self.publisher.connect(ZMQ_INTEL_ADDR)
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    def fetch_rss_news(self):
        print("[INTEL] Fetching RSS News...")
        # Using Yahoo Finance commodities/gold feed as a reliable placeholder
        feed_url = "https://finance.yahoo.com/news/rssindex"
        feed = feedparser.parse(feed_url)
        news = []
        
        # Grab top 10 recent headlines
        for i, entry in enumerate(feed.entries[:10]):
            title_lower = entry.title.lower()
            # Basic impact heuristic
            impact = "HIGH" if any(kw in title_lower for kw in ["fed", "rate", "gold", "war", "inflation"]) else "MED"
            
            news.append({
                "id": f"news_{i}",
                "title": entry.title,
                "source": "Yahoo Finance",
                "time": "Just now", # In prod, parse entry.published to relative time
                "impact": impact
            })
        return news

    def fetch_reddit_social(self):
        print("[INTEL] Fetching Reddit Social Chatter...")
        # Reddit requires a custom User-Agent to prevent 429 blocking
        headers = {'User-Agent': 'BullionHunterIntelBot/1.0'}
        subreddits = ['Daytrading', 'Forex']
        social = []
        
        idx = 0
        for sub in subreddits:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=3"
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    for post in data['data']['children']:
                        # Ignore sticky/announcement posts
                        if not post['data']['stickied']:
                            social.append({
                                "id": f"soc_{idx}",
                                "text": post['data']['title'],
                                "source": f"Reddit / r/{sub}",
                                "time": "Recent"
                            })
                            idx += 1
            except Exception as e:
                print(f"[INTEL] Failed to fetch Reddit {sub}: {e}")
                
        return social

    def analyze_sentiment(self, news, social):
        print("[INTEL] Analyzing aggregated data with Gemini Vertex AI...")
        prompt = f"""
You are the macroeconomic intelligence AI for the BullionHunter XAUUSD trading system.
Analyze the following recent news headlines and social chatter.
Determine the overall macroeconomic sentiment towards Gold (XAUUSD).

Recent News:
{json.dumps(news, indent=2)}

Recent Social Chatter:
{json.dumps(social, indent=2)}

Provide your strict JSON response evaluating the impact on XAUUSD.
"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=AISentimentAnalysis
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"[INTEL] AI Analysis failed: {e}")
            return {
                "overall_sentiment": "Neutral",
                "conviction_score": 0,
                "one_sentence_summary": "Intel analysis temporarily unavailable due to API timeout."
            }

    def run(self):
        print("Starting BullionHunter Intel Worker (Poller)...")
        while True:
            try:
                news_data = self.fetch_rss_news()
                social_data = self.fetch_reddit_social()
                
                # If we have no data, skip analysis
                if not news_data and not social_data:
                    print("[INTEL] No data fetched. Skipping analysis.")
                else:
                    ai_analysis = self.analyze_sentiment(news_data, social_data)
                    
                    # Package the final telemetry payload
                    payload = {
                        "type": "INTEL_FEED_UPDATE",
                        "timestamp": time.time(),
                        "data": {
                            "news": news_data,
                            "social": social_data,
                            "ai_sentiment": ai_analysis
                        }
                    }
                    
                    print(f"[INTEL] Broadcast Payload: {ai_analysis['overall_sentiment']} ({ai_analysis['conviction_score']}%)")
                    print(f"[INTEL] Summary: {ai_analysis['one_sentence_summary']}")
                    
                    # Fire-and-forget push to Node.js bridge
                    self.publisher.send_json(payload)
                
            except Exception as e:
                print(f"[INTEL] Critical error in worker loop: {e}")
                
            print(f"[INTEL] Sleeping for {POLL_INTERVAL_SEC} seconds...\n")
            time.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    worker = IntelWorker()
    worker.run()
