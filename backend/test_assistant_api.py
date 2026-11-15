"""
Integration test for Financial Assistant API endpoints.

Run this after starting the FastAPI server:
    uvicorn app.main:app --reload

Then in another terminal:
    python test_assistant_api.py
"""

import requests
import json
from typing import Any

BASE_URL = "http://localhost:8000/api/v1/assistant"


class APITester:
    """Test the Financial Assistant API."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })

    def print_response(self, title: str, response: dict[str, Any]):
        """Pretty print a response."""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
        print(json.dumps(response, indent=2, default=str))

    def test_health(self):
        """Test health check endpoint."""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.print_response("✓ Health Check", data)
                return data
            else:
                print(f"✗ Health check failed: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"✗ Health check error: {e}")
            return None

    def test_ask_question(self):
        """Test asking a question."""
        try:
            payload = {
                "question": "What is the current state of the Indian stock market?",
                "include_history": False,
            }
            response = self.session.post(
                f"{self.base_url}/ask",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                self.print_response("✓ Ask Question", {
                    "answer": data["answer"][:200] + "...",
                    "sources": data["sources"],
                    "confidence": data["confidence"],
                    "related_companies": data["related_companies"],
                })
                return data
            else:
                print(f"✗ Ask question failed: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"✗ Ask question error: {e}")
            return None

    def test_ask_about_company(self):
        """Test asking about a specific company."""
        try:
            payload = {
                "question": "Tell me about TCS as an investment opportunity",
                "include_history": False,
            }
            response = self.session.post(
                f"{self.base_url}/ask",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                self.print_response("✓ Ask About Company", {
                    "answer": data["answer"][:200] + "...",
                    "sources": data["sources"],
                    "confidence": data["confidence"],
                })
                return data
            else:
                print(f"✗ Ask about company failed: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"✗ Ask about company error: {e}")
            return None

    def test_explain_fundamental_score(self):
        """Test explaining a fundamental score."""
        try:
            payload = {
                "ticker": "TCS",
                "type": "fundamental_score",
                "score_or_signal": 75.5,
                "factors": {
                    "pe_ratio": 18.5,
                    "pb_ratio": 3.2,
                    "roe": 16.5,
                    "debt_to_equity": 0.3,
                    "current_ratio": 1.8,
                }
            }
            response = self.session.post(
                f"{self.base_url}/explain/fundamental-score",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                self.print_response("✓ Explain Fundamental Score", {
                    "explanation": data["explanation"][:200] + "...",
                    "ticker": data["ticker"],
                })
                return data
            else:
                print(f"✗ Explain fundamental score failed: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"✗ Explain fundamental score error: {e}")
            return None

    def test_explain_technical_signal(self):
        """Test explaining a technical signal."""
        try:
            payload = {
                "ticker": "HDFC",
                "type": "technical_signal",
                "score_or_signal": "BUY",
                "factors": {
                    "rsi": 32,
                    "macd_signal": "bullish_crossover",
                    "sma_trend": "uptrend",
                    "volume": "high",
                    "support_level": 1850,
                }
            }
            response = self.session.post(
                f"{self.base_url}/explain/technical-signal",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                self.print_response("✓ Explain Technical Signal", {
                    "explanation": data["explanation"][:200] + "...",
                    "ticker": data["ticker"],
                    "type": data["type"],
                })
                return data
            else:
                print(f"✗ Explain technical signal failed: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"✗ Explain technical signal error: {e}")
            return None

    def test_compare_stocks(self):
        """Test comparing stocks."""
        try:
            payload = {
                "tickers": ["TCS", "INFY", "WIPRO"]
            }
            response = self.session.post(
                f"{self.base_url}/compare",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                self.print_response("✓ Compare Stocks", {
                    "comparison": data["comparison"][:200] + "...",
                    "tickers": data["tickers"],
                })
                return data
            else:
                print(f"✗ Compare stocks failed: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"✗ Compare stocks error: {e}")
            return None

    def test_invalid_request(self):
        """Test error handling with invalid request."""
        try:
            payload = {
                "question": "Hi",  # Too short
                "include_history": False,
            }
            response = self.session.post(
                f"{self.base_url}/ask",
                json=payload
            )
            if response.status_code != 200:
                self.print_response("✓ Error Handling (Expected 422)", {
                    "status_code": response.status_code,
                    "error": response.text[:200],
                })
                return True
            else:
                print("✗ Should have rejected short question")
                return False
        except Exception as e:
            print(f"✗ Invalid request test error: {e}")
            return False

    def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("  Financial Assistant API Integration Tests")
        print("="*60)
        
        # Test health first
        health = self.test_health()
        if not health or health.get("status") == "unhealthy":
            print("\n⚠ LLM service is not healthy. Some tests may be skipped.")
            if health and health.get("status") == "degraded":
                print("  → Running in degraded mode (backup provider active)")
        
        # Run tests
        print("\nRunning tests...\n")
        
        self.test_ask_question()
        self.test_ask_about_company()
        self.test_explain_fundamental_score()
        self.test_explain_technical_signal()
        self.test_compare_stocks()
        self.test_invalid_request()
        
        print("\n" + "="*60)
        print("  Tests Complete")
        print("="*60)


def main():
    """Run the API tests."""
    tester = APITester()
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n✗ Cannot connect to API server at", BASE_URL)
        print("\nStart the server with:")
        print("  cd backend")
        print("  uvicorn app.main:app --reload")
        return
    except Exception as e:
        print(f"\n✗ Connection error: {e}")
        return
    
    # Run tests
    tester.run_all_tests()


if __name__ == "__main__":
    main()
