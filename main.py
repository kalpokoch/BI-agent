
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import validate_env
from agent import build_agent, run_query, format_tool_traces
from tools import get_deals_data, get_work_orders_data
import logging
import sys
import re
from datetime import datetime

# ─────────────────────────────────────────────
# LOGGING CONFIGURATION
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)
logger.info("[APP] Streamlit app starting...")

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Monday.com BI Agent",
    layout="wide"
)

# ─────────────────────────────────────────────
# STARTUP VALIDATION
# ─────────────────────────────────────────────

@st.cache_resource
def init_agent():
    """
    Initialize agent once at startup.
    Cached so it doesn't rebuild on every rerun.
    """
    validate_env()
    tools = [get_deals_data, get_work_orders_data]
    return build_agent(tools)

try:
    agent_executor = init_agent()
except EnvironmentError as e:
    st.error(f"Configuration Error: {str(e)}")
    st.stop()
except Exception as e:
    st.error(f"Failed to initialize agent: {str(e)}")
    st.stop()


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "traces" not in st.session_state:
    st.session_state.traces = []


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("### BI Agent")
    st.caption("Powered by Monday.com + Groq AI")
    st.divider()

    st.markdown("### Sample Questions")
    st.markdown("**Deals Questions**")
    deals_questions = [
        "How is our pipeline looking this quarter?",
        "What is the total revenue from Mining sector?", 
        "Which deals are still open and high priority?",
        "What is our win rate this year?",
        "Show me all deals in the Renewables sector",
    ]
    for q in deals_questions:
        if st.button(q, use_container_width=True, key=q):
            st.session_state.prefill = q
    
    st.markdown("**Work Orders Questions**")
    wo_questions = [
        "How many work orders are completed vs ongoing?",
        "What is our total amount receivable?",
        "Which work orders include Spectra software?",
        "Show me execution status breakdown",
        "What are our top priority AR accounts?",
    ]
    for q in wo_questions:
        if st.button(q, use_container_width=True, key=q):
            st.session_state.prefill = q
    
    st.markdown("**Cross-Board Questions (Full dashboards):**")
    cross_questions = [
        "Give me a business health summary",
        "Show me complete operational overview",
    ]
    for q in cross_questions:
        if st.button(q, use_container_width=True, key=q):
            st.session_state.prefill = q

    st.divider()
    if st.button("Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.traces = []
        st.rerun()

    st.divider()
    st.markdown("### Auto-Generated Visualizations")
    st.caption("• **Deals**: Metrics, Status Charts, Sector Analysis, Funnel, Top Deals")
    st.caption("• **Work Orders**: Metrics, Execution Status, Invoice Analysis, AR Priority")
    st.caption("• **Cross-Board**: Complete analytics dashboard")
    
    st.divider()
    st.caption("Data source: Live Monday.com API")
    st.caption("No data is cached or pre-loaded")


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

st.markdown("# Monday.com Business Intelligence Agent")
st.caption(
    "Ask founder-level business questions. "
    "Every response fetches live data from Monday.com. "
    "Visualizations are automatically generated based on your query type."
)
st.divider()

# ─────────────────────────────────────────────
# VISUALIZATION HELPER FUNCTIONS
# ─────────────────────────────────────────────

def detect_question_type(query: str) -> str:
    """Detect if question is about deals, work orders, or both."""
    query_lower = query.lower()
    
    deals_keywords = ['deal', 'pipeline', 'revenue', 'win rate', 'sales', 'sector', 'closure', 'won', 'lost']
    wo_keywords = ['work order', 'execution', 'survey', 'billing', 'collection', 'receivable', 'invoice', 'quantity']
    
    has_deals = any(keyword in query_lower for keyword in deals_keywords)
    has_wo = any(keyword in query_lower for keyword in wo_keywords) or 'wo' in query_lower
    
    if has_deals and has_wo:
        return 'both'
    elif has_deals:
        return 'deals'
    elif has_wo:
        return 'work_orders'
    else:
        return 'general'

def create_deals_visualizations(data_dict):
    """Create all deals-related visualizations from tools data."""
    if not data_dict or 'summary' not in data_dict:
        st.warning("No deals data available for visualization.")
        return
    
    summary = data_dict['summary']
    deals_list = data_dict.get('sample_deals', [])
    
    # Metric Cards using summary data
    col1, col2, col3, col4 = st.columns(4)
    
    total_deals = summary.get('total_deals', 0)
    status_counts = summary.get('by_status', {})
    open_deals = status_counts.get('Open', 0)
    won_deals = status_counts.get('Won', 0)
    win_rate = (won_deals / total_deals * 100) if total_deals > 0 else 0
    
    with col1:
        st.metric("Total Deals", total_deals)
    with col2:
        st.metric("Open Deals", open_deals)
    with col3:
        st.metric("Won Deals", won_deals)
    with col4:
        st.metric("Win Rate", f"{win_rate:.1f}%")
    
    st.divider()
    
    # Row 1: Deal Status Donut + Deals by Sector
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Deal Status Distribution")
        if status_counts:
            fig = px.pie(values=list(status_counts.values()), names=list(status_counts.keys()),
                        hole=0.4, title="Deal Status")
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Status data not available")
    
    with col2:
        st.markdown("#### Deals by Sector")
        sector_data = summary.get('by_sector', {})
        if sector_data:
            sectors = list(sector_data.keys())
            counts = [sector_data[s]['count'] for s in sectors]
            fig = px.bar(y=sectors, x=counts, orientation='h', title="Deals by Sector")
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sector data not available")
    
    # Row 2: Deal Stage Funnel + Top Deals Sample
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Deal Stage Funnel")
        stage_data = summary.get('by_stage', {})
        if stage_data:
            stages = list(stage_data.keys())
            counts = list(stage_data.values())
            fig = go.Figure(go.Funnel(
                y=stages,
                x=counts,
                textinfo="value+percent initial"
            ))
            fig.update_layout(title="Deal Stage Funnel")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Stage data not available")
    
    with col2:
        st.markdown("#### Sample Deals")
        if deals_list:
            # Create DataFrame from sample deals
            deals_df = pd.DataFrame(deals_list)
            # Show relevant columns if they exist
            display_cols = ['deal_name', 'deal_value', 'deal_sector', 'deal_status']
            available_cols = [col for col in display_cols if col in deals_df.columns]
            if available_cols:
                st.dataframe(deals_df[available_cols].head(10), use_container_width=True, hide_index=True)
            else:
                st.dataframe(deals_df.head(10), use_container_width=True, hide_index=True)
        else:
            st.info("No sample deals available")

def create_work_orders_visualizations(data_dict):
    """Create all work orders-related visualizations from tools data."""
    if not data_dict or 'summary' not in data_dict:
        st.warning("No work orders data available for visualization.")
        return
    
    summary = data_dict['summary']
    wo_list = data_dict.get('sample_work_orders', [])
    
    # Metric Cards using summary data
    col1, col2, col3, col4 = st.columns(4)
    
    total_wos = summary.get('total_work_orders', 0)
    financials = summary.get('financials', {})
    
    # Extract numeric values from formatted strings (remove currency symbols and convert)
    def extract_amount(formatted_str):
        if not formatted_str:
            return 0
        # Remove currency symbols and extract numeric value
        import re
        numeric = re.findall(r'[\d.]+', str(formatted_str))
        if numeric:
            base_val = float(numeric[0])
            if 'Cr' in str(formatted_str):
                return base_val * 10000000  # Convert Crores to actual amount
            elif 'L' in str(formatted_str):
                return base_val * 100000   # Convert Lakhs to actual amount
            return base_val
        return 0
    
    contract_value = extract_amount(financials.get('total_contract_value_incl_gst', '₹0'))
    collected = extract_amount(financials.get('total_collected_incl_gst', '₹0'))
    receivable = extract_amount(financials.get('total_amount_receivable', '₹0'))
    
    with col1:
        st.metric("Total Work Orders", total_wos)
    with col2:
        st.metric("Contract Value", financials.get('total_contract_value_incl_gst', '₹0'))
    with col3:
        st.metric("Collected", financials.get('total_collected_incl_gst', '₹0'))
    with col4:
        st.metric("Receivable", financials.get('total_amount_receivable', '₹0'))
    
    st.divider()
    
    # Row 1: Execution Status + Invoice Status
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Execution Status")
        exec_status = summary.get('by_execution_status', {})
        if exec_status:
            fig = px.pie(values=list(exec_status.values()), names=list(exec_status.keys()),
                        hole=0.4, title="Execution Status")
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Execution status data not available")
    
    with col2:
        st.markdown("#### Invoice Status")
        invoice_status = summary.get('by_invoice_status', {})
        if invoice_status:
            fig = px.bar(x=list(invoice_status.keys()), y=list(invoice_status.values()),
                        title="Invoice Status")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Invoice status data not available")
    
    # Row 2: WO by Sector + Sample Work Orders
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Work Orders by Sector")
        sector_data = summary.get('by_sector', {})
        if sector_data:
            sectors = list(sector_data.keys())
            counts = [sector_data[s]['count'] for s in sectors]
            fig = px.bar(x=sectors, y=counts, title="Work Orders by Sector (Count)")
            fig.update_traces(texttemplate='%{y}', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sector data not available")
    
    with col2:
        st.markdown("#### Sample Work Orders")
        if wo_list:
            wo_df = pd.DataFrame(wo_list)
            # Show relevant columns if they exist
            display_cols = ['work_order_name', 'execution_status', 'invoice_status', 'work_order_sector']
            available_cols = [col for col in display_cols if col in wo_df.columns]
            if available_cols:
                st.dataframe(wo_df[available_cols].head(10), use_container_width=True, hide_index=True)
            else:
                st.dataframe(wo_df.head(10), use_container_width=True, hide_index=True)
        else:
            st.info("No sample work orders available")
    
    # AR Priority Accounts from summary
    st.markdown("#### AR Priority Accounts")
    ar_accounts = summary.get('ar_priority_accounts', [])
    if ar_accounts:
        ar_df = pd.DataFrame(ar_accounts)
        st.dataframe(ar_df, use_container_width=True, hide_index=True)
    else:
        st.info("No AR priority accounts data available")


# ─────────────────────────────────────────────
# CHAT HISTORY DISPLAY
# ─────────────────────────────────────────────

for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show tool traces for assistant messages
        if msg["role"] == "assistant" and i // 2 < len(st.session_state.traces):
            traces = st.session_state.traces[i // 2]
            if traces:
                with st.expander(f"Agent Actions ({len(traces)} API call(s))", expanded=False):
                    for j, trace in enumerate(traces):
                        st.markdown(f"**Step {j+1} — Tool called:** `{trace['tool_name']}`")
                        st.markdown(f"**Input:** {trace['tool_input']}")
                        st.code(trace["tool_output_preview"], language="json")
                        if j < len(traces) - 1:
                            st.divider()


# ─────────────────────────────────────────────
# CHAT INPUT
# ─────────────────────────────────────────────

# Handle sidebar button prefill
prefill_value = st.session_state.pop("prefill", "")

user_input = st.chat_input(
    "Ask a business question — e.g. How is our Renewables pipeline looking?",
)

# Use prefill if sidebar button was clicked
if prefill_value and not user_input:
    user_input = prefill_value


# ─────────────────────────────────────────────
# QUERY PROCESSING
# ─────────────────────────────────────────────

if user_input:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Fetching live data from Monday.com..."):
            result = run_query(
                agent_executor=agent_executor,
                user_input=user_input,
                chat_history=st.session_state.messages[:-1]  # exclude current message
            )

        response = result["output"]
        traces = format_tool_traces(result["intermediate_steps"])

        # Display response
        st.markdown(response)
        
        # Generate visualizations based on question type and available data
        # REUSE tool results from agent execution instead of calling tools again!
        question_type = detect_question_type(user_input)
        tool_results = result.get('tool_results', {})
        
        if question_type in ['deals', 'both']:
            st.markdown("## Deals Analytics Dashboard")
            try:
                # Reuse data from agent execution instead of calling tool again
                deals_data = tool_results.get('get_deals_data')
                if deals_data and isinstance(deals_data, str):
                    import json
                    deals_dict = json.loads(deals_data)
                    if deals_dict.get('sample_deals') or deals_dict.get('summary'):
                        create_deals_visualizations(deals_dict)
                    else:
                        st.info("No deals data available for visualization")
                elif question_type == 'deals':
                    st.info("Deals data not available - agent may not have called the deals tool")
            except Exception as e:
                st.error(f"Error creating deals visualizations: {str(e)}")
        
        if question_type in ['work_orders', 'both']:
            st.markdown("## Work Orders Analytics Dashboard")
            try:
                # Reuse data from agent execution instead of calling tool again
                wo_data = tool_results.get('get_work_orders_data')
                if wo_data and isinstance(wo_data, str):
                    import json
                    wo_dict = json.loads(wo_data)
                    if wo_dict.get('sample_work_orders') or wo_dict.get('summary'):
                        create_work_orders_visualizations(wo_dict)
                    else:
                        st.info("No work orders data available for visualization")
                elif question_type == 'work_orders':
                    st.info("Work orders data not available - agent may not have called the work orders tool")
            except Exception as e:
                st.error(f"Error creating work orders visualizations: {str(e)}")

        # Display tool call traces
        if traces:
            with st.expander(f"Agent Actions ({len(traces)} API call(s))", expanded=False):
                for j, trace in enumerate(traces):
                    st.markdown(f"**Step {j+1} — Tool called:** `{trace['tool_name']}`")
                    st.markdown(f"**Input:** {trace['tool_input']}")
                    st.code(trace["tool_output_preview"], language="json")
                    if j < len(traces) - 1:
                        st.divider()

        # Show error banner if agent hit an error
        if result["error"]:
            st.warning(f"Warning: {result['error']}")

    # Save to session state
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.traces.append(traces)