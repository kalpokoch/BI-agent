# Monday.com BI Agent

A Business Intelligence assistant that provides real-time insights from Monday.com data for drone survey company operations.

## Live Demo

**Access the application:** https://bi-agent.streamlit.app/

## Architecture

### Dual LLM Setup
- **Primary LLM:** Llama 3.3 70B Versatile (via Groq API)
- **Fallback LLM:** Llama 3.1 8B Instant (via Groq API)

The application uses a two-LLM architecture to handle rate limiting scenarios. When the primary model hits rate limits, queries automatically fall back to the faster 8B model to ensure continuous service availability.

### Tech Stack
- **Framework:** LangChain + LangGraph for agent orchestration
- **Frontend:** Streamlit for web interface
- **Data Source:** Monday.com API v2
- **Visualization:** Plotly for interactive charts
- **Data Processing:** Pandas for analysis

## Features

- Real-time data fetching from Monday.com boards
- Natural language query interface
- Automated data cleaning and quality validation
- Interactive visualizations with Plotly
- Financial reporting with Indian currency formatting
- Chat-based interaction with conversation history

## Data Sources

The agent connects to two Monday.com boards:
1. **Deals Board** - Pipeline data, revenue tracking, deal stages, closure probabilities
2. **Work Orders Board** - Operational data, project status, billing information

## Setup

### Prerequisites
- Python 3.8+
- Groq API key
- Monday.com API key and board IDs

### Environment Variables
```
GROQ_API_KEY=your_groq_api_key
MONDAY_API_KEY=your_monday_api_key
DEALS_BOARD_ID=your_deals_board_id
WORK_ORDERS_BOARD_ID=your_work_orders_board_id
```

### Installation
```bash
pip install -r requirements.txt
```

### Local Development
```bash
streamlit run main.py
```

## Usage

Ask business intelligence questions in natural language:
- "What are our open deals this quarter?"
- "Show me revenue breakdown by sector"
- "What's the status of work orders?"
- "Generate a pipeline report for this month"

The agent automatically fetches relevant data, performs analysis, and provides insights with visualizations.

## Key Capabilities

- Automated tool selection based on query context
- Data quality assessment and caveats reporting  
- Financial metrics in Indian number system (Lakhs/Crores)
- Context-aware date handling for financial year queries
- Export capabilities for reports and visualizations

## License

This project is proprietary software for internal business intelligence use.