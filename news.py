import requests
import xml.etree.ElementTree as ET
import time

# Curated list of high-impact news feeds
NEWS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]

# Sentiment Lexicon (Professional/Institutional keywords)
BULLISH_KEYWORDS = ["adoption", "bullish", "etf approval", "partnership", "growth", "surpasses", "ath", "pump", "support", "buying"]
BEARISH_KEYWORDS = ["hack", "exploit", "sec lawsuit", "lawsuit", "regulation", "scam", "bearish", "crash", "dump", "inflation", "liquidated"]

def fetch_rss_headlines():
    """
    Fetches latest headlines from top crypto news feeds.
    """
    headlines = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in NEWS_FEEDS:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for item in root.findall('.//item'):
                    title = item.find('title').text
                    headlines.append(title.lower())
        except Exception as e:
            print(f"Error fetching RSS from {url}: {e}")
            
    return headlines

def get_market_sentiment(symbol: str = None):
    """
    Analyzes current news headlines for sentiment.
    Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    headlines = fetch_rss_headlines()
    if not headlines:
        return "NEUTRAL"

    bull_count = 0
    bear_count = 0

    # Filter keywords based on symbol if provided (e.g. BTC)
    relevant_headlines = headlines
    if symbol:
        coin_name = symbol.split('/')[0].lower()
        relevant_headlines = [h for h in headlines if coin_name in h]

    # If no specific headlines for the coin, use global sentiment
    if not relevant_headlines:
        relevant_headlines = headlines[:20] # Take latest 20 global headlines

    for title in relevant_headlines:
        for word in BULLISH_KEYWORDS:
            if word in title:
                bull_count += 1
        for word in BEARISH_KEYWORDS:
            if word in title:
                bear_count += 1

    if bull_count > bear_count:
        return "BULLISH"
    elif bear_count > bull_count:
        return "BEARISH"
    else:
        return "NEUTRAL"

if __name__ == "__main__":
    print("Testing News Sentiment Engine...")
    print(f"Global Sentiment: {get_market_sentiment()}")
    print(f"BTC Sentiment: {get_market_sentiment('BTC/USDT:USDT')}")
