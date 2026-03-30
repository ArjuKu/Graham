# GRAHAM

**G**lobal **R**ecursive **A**nalyst for **M**arket **A**ssessment and **H**eadlines

## About

Named after **Benjamin Graham** — the father of financial analysis and value investing — GRAHAM is a Python + Streamlit web application that performs fundamental analysis of publicly traded companies.

As a beginner in programming and an aspiring professional, I noticed that high-quality financial valuation tools are often locked behind expensive paywalls. Building a proper Discounted Cash Flow (DCF) model, performing comparative analysis, and collating analyst sentiment manually takes hours. GRAHAM automates that "ballpark" valuation so anyone can do in seconds what takes professionals hours.

If you're a finance professional or a programmer with suggestions on model corrections, code optimizations, or fine-tuning — I'd love to hear from you.

## Features

- **DCF Valuation** — 2-stage WACC-based Discounted Cash Flow model with configurable assumptions
- **P/E Ratio Analysis** — Company P/E vs S&P 500 benchmark with valuation scoring
- **Sensitivity Matrix** — 3x3 grid showing how IV changes across WACC and Growth variations
- **Reverse DCF** — Solves for the implied FCF growth rate the market is pricing in
- **News Sentiment** — AI-powered sentiment analysis using Gemini 2.5 Flash Lite
- **Analyst Price Targets** — Real-time analyst targets via Google Search Grounding
- **Historical Financials** — 5-year income statement, balance sheet, and cash flow data
- **Ownership Data** — Institutional holders and insider transaction details
- **Weighted Verdict** — Buy/Hold/Sell recommendation combining DCF, P/E, sentiment, and analyst targets

## Tech Stack

| Component | Tool |
|-----------|------|
| Language | Python 3.11+ |
| Frontend | Streamlit |
| Financial Data | yfinance |
| AI | Google Gemini 2.5 Flash Lite |
| Charts | Plotly |
| Validation | Pydantic v2 |
| Config | PyYAML |

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/ArjuKu/Graham.git
cd Graham
```

### 2. Create and activate virtual environment

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your API key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Click **Get API key** in the sidebar
3. Create a new key (or use an existing project)
4. Copy `config.example.yaml` to `config.yaml`:

```bash
copy config.example.yaml config.yaml      # Windows
# cp config.example.yaml config.yaml      # Mac/Linux
```

5. Open `config.yaml` and paste your key into the `api_key` field:

```yaml
llm:
  api_key: "YOUR_ACTUAL_KEY_HERE"
```

### 5. Run the app

```bash
streamlit run main.py
```

The app will open in your browser at `http://localhost:8501`.

## How to use

1. Type a company name or ticker (e.g., "Apple" or "AAPL") in the search bar
2. Press **Enter** or click **Analyze**
3. Review the valuation gauge, metrics, and DCF results
4. Explore tabs for Research & Sentiment, Historical Data, and Sources
5. Adjust DCF assumptions in the sidebar and re-analyze

## Project Structure

```
graham/
├── config.example.yaml       # Template config (safe to share)
├── main.py                   # Streamlit app entry point
├── requirements.txt          # Python dependencies
│
├── data/
│   ├── fetcher.py            # yfinance data fetching + search
│   └── parser.py             # Data normalization
│
├── models/
│   ├── dcf.py                # WACC + DCF calculation engine
│   ├── schemas.py            # Pydantic response models
│   ├── sensitivity.py        # Sensitivity matrix
│   ├── reverse_dcf.py        # Implied growth solver
│   ├── valuation.py          # P/E scoring
│   └── verdict.py            # Buy/Hold/Sell verdict
│
└── llm/
    ├── analyst.py            # Gemini news sentiment
    ├── rate_limiter.py       # API rate limiting
    └── research.py           # Analyst price targets
```

## Disclaimer

GRAHAM does not provide financial advice. All analysis is for educational and research purposes only. Always do your own research before making investment decisions.
