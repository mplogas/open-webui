"""
title: Tool to interact with Alpha Vantage stock market data
author: Marc Plogas
funding_url: https://github.com/mplogas/open-webui
version: 1.0.0
license: MIT
"""

import json
import os
import requests
import unittest
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Callable, Any, Optional, Dict

load_dotenv()


class EventEmitter:
    def __init__(self, event_emitter: Optional[Callable[[dict], Any]] = None):
        self.event_emitter = event_emitter

    async def progress_update(self, description: str):
        await self.emit(description, "in_progress", False)

    async def error_update(self, description: str):
        await self.emit(description, "error", True)

    async def success_update(self, description: str):
        await self.emit(description, "success", True)

    async def emit(
        self,
        description: str = "Unknown State",
        status: str = "in_progress",
        done: bool = False,
    ):
        if self.event_emitter:
            await self.event_emitter(
                {
                    "type": "status",
                    "data": {
                        "status": status,
                        "description": description,
                        "done": done,
                    },
                }
            )


class Tools:
    class Valves(BaseModel):
        ALPHAVANTAGE_URL: str = Field(
            default="https://www.alphavantage.co/query",
            description="The base URL for Alpha Vantage API",
        )
        ALPHAVANTAGE_API_KEY: str = Field(
            default="", description="The API key to access Alpha Vantage"
        )

    def __init__(self):
        self.valves = self.Valves()

    async def get_daily_time_series(
        self,
        symbol: str,
        __event_emitter__: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """
        Retrieve the daily time series data for a stock symbol.

        :param symbol: The stock ticker symbol (e.g., 'AAPL').
        :return: All daily time series data as a JSON string or an error as a string.
        """
        emitter = EventEmitter(__event_emitter__)
        try:
            await emitter.progress_update(f"Fetching daily time series for {symbol}")
            params: Dict[str, str] = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "apikey": self.valves.ALPHAVANTAGE_API_KEY,
            }
            response = requests.get(self.valves.ALPHAVANTAGE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            encoded_data = json.dumps(data, ensure_ascii=False)
            await emitter.success_update(
                f"Received daily time series data for {symbol}"
            )
            return encoded_data
        except Exception as e:
            error_msg = f"Error fetching daily time series data: {str(e)}"
            await emitter.error_update(error_msg)
            return error_msg

    async def get_intraday_series(
        self,
        symbol: str,
        interval: str = "5min",
        __event_emitter__: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """
        Retrieve intraday time series data for a stock symbol.

        :param symbol: The stock ticker symbol (e.g., 'AAPL').
        :param interval: The interval of the data (e.g., '1min', '5min', '15min', '30min', '60min').
        :return: Intraday data as a JSON string or an error as a string.
        """
        emitter = EventEmitter(__event_emitter__)
        try:
            await emitter.progress_update(
                f"Fetching intraday time series for {symbol} with interval {interval}"
            )
            params: Dict[str, str] = {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": interval,
                "apikey": self.valves.ALPHAVANTAGE_API_KEY,
            }
            response = requests.get(self.valves.ALPHAVANTAGE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            encoded_data = json.dumps(data, ensure_ascii=False)
            await emitter.success_update(
                f"Received intraday time series data for {symbol}"
            )
            return encoded_data
        except Exception as e:
            error_msg = f"Error fetching intraday data: {str(e)}"
            await emitter.error_update(error_msg)
            return error_msg

    async def get_global_quote(
        self,
        symbol: str,
        __event_emitter__: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """
        Retrieve the current global quote for a stock symbol.

        :param symbol: The stock ticker symbol (e.g., 'AAPL').
        :return: Global quote data as a JSON string or an error as a string.
        """
        emitter = EventEmitter(__event_emitter__)
        try:
            await emitter.progress_update(f"Fetching global quote for {symbol}")
            params: Dict[str, str] = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.valves.ALPHAVANTAGE_API_KEY,
            }
            response = requests.get(self.valves.ALPHAVANTAGE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            encoded_data = json.dumps(data, ensure_ascii=False)
            await emitter.success_update(f"Received global quote for {symbol}")
            return encoded_data
        except Exception as e:
            error_msg = f"Error fetching global quote: {str(e)}"
            await emitter.error_update(error_msg)
            return error_msg

    async def search_symbol(
        self,
        keywords: str,
        __event_emitter__: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """
        Search for stock symbols based on keywords.

        :param keywords: The keyword or phrase to search for symbols.
        :return: Search results as a JSON string or an error as a string.
        """
        emitter = EventEmitter(__event_emitter__)
        try:
            await emitter.progress_update(f"Searching symbols for keyword '{keywords}'")
            params: Dict[str, str] = {
                "function": "SYMBOL_SEARCH",
                "keywords": keywords,
                "apikey": self.valves.ALPHAVANTAGE_API_KEY,
            }
            response = requests.get(self.valves.ALPHAVANTAGE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            encoded_data = json.dumps(data, ensure_ascii=False)
            await emitter.success_update(f"Search completed for keyword '{keywords}'")
            return encoded_data
        except Exception as e:
            error_msg = f"Error searching symbols: {str(e)}"
            await emitter.error_update(error_msg)
            return error_msg


# Example asynchronous test cases using unittest
class AlphaVantageToolTest(unittest.IsolatedAsyncioTestCase):
    async def test_get_daily_time_series(self):
        tool = Tools()
        result = await tool.get_daily_time_series("AAPL")
        data = json.loads(result)
        # Alpha Vantage returns a dictionary with "Time Series (Daily)"
        self.assertTrue("Time Series (Daily)" in data or "Error" in result)

    async def test_get_intraday_series(self):
        tool = Tools()
        result = await tool.get_intraday_series("AAPL", interval="15min")
        data = json.loads(result)
        # Check that we received intraday data or an error message
        self.assertTrue("Time Series (15min)" in data or "Error" in result)

    async def test_get_global_quote(self):
        tool = Tools()
        result = await tool.get_global_quote("AAPL")
        data = json.loads(result)
        # Check that we received global quote data or an error message
        self.assertTrue("Global Quote" in data or "Error" in result)


if __name__ == "__main__":
    print("Running tests...")
    unittest.main()

