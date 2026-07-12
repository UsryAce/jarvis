"""Trading & Financial Analysis Skill for Jarvis."""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from src.skills.registry import Skill
from src.config import config


class TradingSkill(Skill):
    """Trading, market analysis, backtesting, and prop firm skill."""

    name = "trading"
    description = "Trading analysis, backtesting, prop firm management, market data"
    triggers = ["trade", "trading", "market", "stock", "crypto", "forex", "futures", "options", 
                "backtest", "prop firm", "analysis", "technical", "indicator", "bloomberg"]

    def __init__(self, jarvis=None):
        super().__init__(jarvis)
        self.alpha_vantage_key = config.get("external_apis.alpha_vantage") or config.get("ALPHA_VANTAGE_API_KEY")
        self.polygon_key = config.get("external_apis.polygon") or config.get("POLYGON_API_KEY")
        self.twelve_data_key = config.get("external_apis.twelve_data") or config.get("TWELVE_DATA_API_KEY")
        self.finnhub_key = config.get("external_apis.finnhub") or config.get("FINNHUB_API_KEY")
        
        # Prop firm tracking
        self.prop_firms = {
            "ftmo": {"name": "FTMO", "max_drawdown": 10, "profit_target": 10, "phases": 2},
            "funded_trader": {"name": "The Funded Trader", "max_drawdown": 10, "profit_target": 8, "phases": 2},
            "my_forex_funds": {"name": "My Forex Funds", "max_drawdown": 12, "profit_target": 8, "phases": 2},
            "surge_trader": {"name": "SurgeTrader", "max_drawdown": 5, "profit_target": 10, "phases": 1},
            "topstep": {"name": "TopStep", "max_drawdown": 3, "profit_target": 6, "phases": 2},
            "earn2trade": {"name": "Earn2Trade", "max_drawdown": 10, "profit_target": 8, "phases": 2},
        }

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        
        if "prop firm" in text or "propfirm" in text:
            return await self._prop_firm_info(params.get("firm", ""))
        elif "backtest" in text:
            return await self._backtest_strategy(params)
        elif "market" in text or "price" in text or "quote" in text:
            return await self._get_market_data(params.get("symbol", "SPY"))
        elif "technical" in text or "indicator" in text:
            return await self._technical_analysis(params)
        elif "bloomberg" in text or "terminal" in text:
            return self._bloomberg_terminal_info()
        elif "risk" in text or "position size" in text:
            return await self._risk_management(params)
        elif "journal" in text or "track" in text:
            return self._trading_journal_help()
        else:
            return self._trading_help()

    async def _prop_firm_info(self, firm: str) -> str:
        """Get prop firm information."""
        if not firm:
            firms_list = "\n".join([f"• {v['name']}: {v['profit_target']}% target, {v['max_drawdown']}% max DD, {v['phases']} phases" 
                                   for k, v in self.prop_firms.items()])
            return f"**Prop Firms Available:**\n{firms_list}\n\nSpecify a firm for details: FTMO, Funded Trader, My Forex Funds, SurgeTrader, TopStep, Earn2Trade"
        
        firm_key = firm.lower().replace(" ", "_")
        if firm_key in self.prop_firms:
            f = self.prop_firms[firm_key]
            return f"""**{f['name']} Prop Firm Details:**
- Profit Target: {f['profit_target']}%
- Max Drawdown: {f['max_drawdown']}%
- Phases: {f['phases']}
- Daily Loss Limit: Typically 5%
- Trading Hours: 24/5 (Forex), Market hours (Futures/Stocks)
- Allowed: EA/Bots, Scalping, Hedging (varies)
- Payout Split: Usually 80/20 or 90/10 after passing"""
        return f"Firm '{firm}' not found. Available: {', '.join([v['name'] for v in self.prop_firms.values()])}"

    async def _get_market_data(self, symbol: str) -> str:
        """Get real-time market data."""
        if not any([self.alpha_vantage_key, self.polygon_key, self.twelve_data_key, self.finnhub_key]):
            return "No market data API keys configured. Add ALPHA_VANTAGE_API_KEY, POLYGON_API_KEY, TWELVE_DATA_API_KEY, or FINNHUB_API_KEY to .env"
        
        # Try Finnhub first (free tier available)
        if self.finnhub_key:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"https://finnhub.io/api/v1/quote"
                    params = {"symbol": symbol.upper(), "token": self.finnhub_key}
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if "c" in data:
                            return f"""**{symbol.upper()} Quote (Finnhub):**
- Current: ${data['c']:.2f}
- Change: ${data['d']:.2f} ({data['dp']:.2f}%)
- High: ${data['h']:.2f}
- Low: ${data['l']:.2f}
- Open: ${data['o']:.2f}
- Prev Close: ${data['pc']:.2f}"""
            except Exception as e:
                pass
        
        # Try Twelve Data
        if self.twelve_data_key:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.twelvedata.com/quote"
                    params = {"symbol": symbol.upper(), "apikey": self.twelve_data_key}
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if "close" in data:
                            return f"""**{symbol.upper()} Quote (Twelve Data):**
- Current: ${float(data['close']):.2f}
- Change: ${float(data['change']):.2f} ({float(data['percent_change']):.2f}%)
- High: ${float(data['high']):.2f}
- Low: ${float(data['low']):.2f}
- Open: ${float(data['open']):.2f}
- Volume: {data.get('volume', 'N/A')}"""
            except Exception as e:
                pass
        
        return f"Could not fetch data for {symbol}. Check API keys."

    async def _technical_analysis(self, params: Dict) -> str:
        """Technical analysis with indicators."""
        symbol = params.get("symbol", "SPY")
        indicators = params.get("indicators", ["rsi", "macd", "sma_20", "sma_50", "bb", "atr"])
        
        return f"""**Technical Analysis Setup for {symbol.upper()}**

**Requested Indicators:** {', '.join(indicators).upper()}

**Available Indicators:**
- RSI (14) - Momentum oscillator
- MACD (12,26,9) - Trend/momentum
- SMA/EMA (20, 50, 200) - Moving averages
- Bollinger Bands (20,2) - Volatility
- ATR (14) - Volatility/position sizing
- VWAP - Volume weighted price
- Stochastic (14,3,3) - Momentum
- ADX (14) - Trend strength
- OBV - Volume flow
- Ichimoku Cloud - Full system

**To implement backtest:** Use the backtest command with strategy parameters.

**Example Strategy:**
```
Entry: RSI < 30 + Price > SMA200 + MACD bullish cross
Exit: RSI > 70 or MACD bearish cross or 2:1 R:R
Risk: 1% per trade, max 3 concurrent
```"""

    async def _backtest_strategy(self, params: Dict) -> str:
        """Run backtest on strategy."""
        strategy = params.get("strategy", "rsi_mean_reversion")
        symbol = params.get("symbol", "SPY")
        timeframe = params.get("timeframe", "1h")
        start_date = params.get("start", "2023-01-01")
        end_date = params.get("end", "2024-12-31")
        initial_capital = params.get("capital", 100000)
        risk_per_trade = params.get("risk", 0.01)
        
        # This would connect to a backtesting engine
        return f"""**Backtest Configuration:**
- Strategy: {strategy}
- Symbol: {symbol.upper()}
- Timeframe: {timeframe}
- Period: {start_date} to {end_date}
- Initial Capital: ${initial_capital:,}
- Risk per Trade: {risk_per_trade*100}%

**To Run Full Backtest:**
1. Install backtesting.py or vectorbt: `pip install backtesting vectorbt`
2. Use Jarvis code execution skill to run Python backtest
3. Or connect to TradeStation/NT8/MetaTrader via API

**Example Python Backtest (run via code skill):**
```python
import vectorbt as vbt
import yfinance as yf

# Get data
data = yf.download('{symbol}', start='{start_date}', end='{end_date}', interval='{timeframe}')

# RSI Strategy
rsi = vbt.RSI.run(data['Close'], window=14)
entries = rsi.rsi_crossed_below(30)
exits = rsi.rsi_crossed_above(70)

# Run backtest
pf = vbt.Portfolio.from_signals(data['Close'], entries, exits, 
                                 init_cash={initial_capital}, 
                                 fees=0.001, slippage=0.001)
print(pf.stats())
pf.plot().show()
```"""

    def _bloomberg_terminal_info(self) -> str:
        """Bloomberg terminal recreation info."""
        return """**Bloomberg Terminal Alternative - OpenBB Terminal**

**Best Free/Open Source Alternative:**
- **OpenBB Terminal** (formerly Gamestonk Terminal)
  - `pip install openbb-terminal`
  - 100+ commands for equity, crypto, forex, options, futures
  - Bloomberg-style UI with widgets
  - Python SDK for custom analysis

**Key Features to Replicate:**
| Bloomberg Function | OpenBB Equivalent | Python Library |
|-------------------|-------------------|----------------|
| DES (Description) | `stocks.dd` | yfinance, SEC EDGAR |
| FA (Financial Analysis) | `stocks.fa` | yfinance, FundamentalAnalysis |
| GP (Price Chart) | `stocks.candle` | mplfinance, plotly |
| WEI (World Equity) | `stocks.screener` | pandas, yfinance |
| ECON (Economics) | `economy` | FRED, World Bank |
| CRNC (Currencies) | `forex` | Twelve Data, Alpha Vantage |
| CMOD (Commodities) | `futures` | yfinance, Quandl |
| OVML (Options) | `options.chains` | yfinance, polygon |

**Custom Bloomberg-Style Dashboard:**
```python
# Run via Jarvis code skill
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

# Real-time dashboard with:
# - Multi-asset watchlist
# - Options flow
# - News sentiment
# - Economic calendar
# - Correlation matrix
# - Risk metrics (VaR, CVaR)
```

**Data Sources (Free/Cheap):**
- **Yahoo Finance** (yfinance) - Free, comprehensive
- **Alpha Vantage** - Free tier 5 req/min
- **Twelve Data** - Free tier 800/day
- **Polygon.io** - Free tier 5/min
- **Finnhub** - Free tier 60/min
- **FRED** - Free economic data
- **Quandl/Nasdaq Data Link** - Some free
- **IEX Cloud** - Free tier available

**For Institutional Grade:**
- **Polygon.io** (paid) - Tick data, low latency
- **Databento** - Historical tick data
- **Refinitiv/Thomson Reuters** - Enterprise
- **Bloomberg B-PIPE** - Direct feed"""

    async def _risk_management(self, params: Dict) -> str:
        """Position sizing and risk management."""
        account_size = params.get("account", 100000)
        risk_pct = params.get("risk", 0.01)
        entry = params.get("entry", 0)
        stop = params.get("stop", 0)
        
        if entry and stop:
            risk_per_share = abs(entry - stop)
            if risk_per_share > 0:
                position_size = (account_size * risk_pct) / risk_per_share
                return f"""**Position Size Calculator:**
- Account: ${account_size:,.2f}
- Risk: {risk_pct*100}% (${account_size*risk_pct:,.2f})
- Entry: ${entry:.2f}
- Stop: ${stop:.2f}
- Risk/Share: ${risk_per_share:.2f}
- **Position: {position_size:,.0f} shares (${position_size*entry:,.2f})**
- **Max Loss if Stop Hit: ${account_size*risk_pct:,.2f}**"""
        
        return f"""**Risk Management Rules:**
- Max Risk per Trade: 1-2% of account
- Max Daily Loss: 3-5% of account
- Max Drawdown: 10-20% (prop firm limits)
- Max Correlated Positions: 3-5
- Risk:Reward Minimum: 1:2 (prefer 1:3)
- Position Size Formula: (Account × Risk%) ÷ (Entry - Stop)

**Prop Firm Specific:**
- FTMO: 1% risk, 10% target, 5% daily, 10% max DD
- Scale in/out: 25%/25%/25%/25% or 50%/50%
- Never average down on losers
- Move stop to breakeven at 1:1"""

    def _trading_journal_help(self) -> str:
        """Trading journal template."""
        return """**Trading Journal Template (Markdown/CSV/Notion):**

**Per Trade:**
```
Date | Symbol | Side | Entry | Stop | Target | Size | Risk$ | R:R | Result | P/L | Notes
```

**Daily Review:**
- Trades taken: X
- Wins: X | Losses: X | Win Rate: X%
- Gross P/L: $X | Net P/L: $X
- Max Drawdown: $X
- Best Trade: $X | Worst Trade: $X
- Mistakes: [List]
- Lessons: [List]

**Weekly/Monthly:**
- Expectancy: (Win% × Avg Win) - (Loss% × Avg Loss)
- Sharpe Ratio
- Max Consecutive Losses
- Largest Winner/Loser
- Time in Market %
- Strategy Breakdown

**Tools:** Edgewonk, Tradervue, Trademetria, Notion, Excel, Google Sheets"""

    def _trading_help(self) -> str:
        return """**Trading Commands:**
- "market data for SPY" - Get real-time quote
- "technical analysis for AAPL with RSI MACD" - Indicators
- "backtest RSI strategy on SPY 1h 2023-2024" - Run backtest
- "prop firm FTMO rules" - Prop firm details
- "position size account 100k risk 1% entry 450 stop 445" - Calc size
- "bloomberg terminal alternative" - OpenBB setup
- "risk management rules" - Risk guidelines
- "trading journal template" - Journal format

**API Keys Needed (add to .env):**
- ALPHA_VANTAGE_API_KEY
- POLYGON_API_KEY
- TWELVE_DATA_API_KEY
- FINNHUB_API_KEY

**Install for Full Features:**
```bash
pip install yfinance vectorbt backtesting mplfinance plotly openbb
```"""