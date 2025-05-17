
import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

DEFAULT_MAGNIFICENT_7 = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA']

@st.cache_data
def get_weekly_fridays(n=10):
    today = datetime.today()
    return [(today + timedelta(days=(4 - today.weekday() + 7*i) % 7 + 7*i)).strftime('%Y-%m-%d') for i in range(n)]

def get_put_option_data(ticker, target_expiration, moneyness_pct):
    try:
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")['Close'].iloc[-1]
        if target_expiration not in stock.options:
            return None
        puts = stock.option_chain(target_expiration).puts
        max_strike = price * (1 - moneyness_pct / 100)
        puts = puts[puts['strike'] <= max_strike]
        if puts.empty:
            return None
        best_put = puts.loc[puts['bid'].idxmax()]
        days_to_exp = (pd.to_datetime(target_expiration) - datetime.today()).days
        return {
            'Ticker': ticker,
            'Current Price': round(price, 2),
            'Strike': round(best_put['strike'], 2),
            'Bid': round(best_put['bid'], 2),
            'Ask': round(best_put['ask'], 2),
            'Open Interest': int(best_put['openInterest']),
            'Premium': round(best_put['bid'] * 100, 2),
            'Cash Required': round(best_put['strike'] * 100, 2),
            'Abs ROI (%)': round((best_put['bid'] / best_put['strike']) * 100, 2),
            'Annualized ROI (%)': round((best_put['bid'] / best_put['strike']) * 100 * 365 / days_to_exp, 2),
            'Expiration': target_expiration,
            'IV': round(best_put['impliedVolatility'] * 100, 2)
        }
    except:
        return None

def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        earnings_date = stock.calendar.loc['Earnings Date'][0] if 'Earnings Date' in stock.calendar.index else None
        eps_data = stock.quarterly_earnings if hasattr(stock, 'quarterly_earnings') else pd.DataFrame()
        eps_list = eps_data['Earnings'].tail(4).tolist() if not eps_data.empty else []
        beats = [int(e >= m) for e, m in zip(eps_data['Earnings'], eps_data['Estimate'])] if not eps_data.empty else []
        score = 0
        if info.get('recommendationKey') == 'buy': score += 1
        if info.get('targetMeanPrice') and info.get('targetMeanPrice') > info.get('currentPrice'): score += 1
        if info.get('dividendYield'): score += 1
        return {
            'Dividend Yield (%)': round(info.get('dividendYield', 0) * 100, 2) if info.get('dividendYield') else 0.00,
            'Earnings Date': earnings_date.strftime('%Y-%m-%d') if earnings_date else "N/A",
            'Price Target': round(info.get('targetMeanPrice', 0), 2),
            'Recommendation': info.get('recommendationKey', 'N/A').capitalize(),
            'EPS (Last 4)': ', '.join([f"{x:.2f}" for x in eps_list]) if eps_list else "N/A",
            'EPS Beats (4Q)': f"{sum(beats)}/{len(beats)}" if beats else "N/A",
            'Overall Score': score
        }
    except:
        return {
            'Dividend Yield (%)': 0.00,
            'Earnings Date': "N/A",
            'Price Target': 0.00,
            'Recommendation': "N/A",
            'EPS (Last 4)': "N/A",
            'EPS Beats (4Q)': "N/A",
            'Overall Score': 0
        }

# Streamlit GUI
st.set_page_config(layout="wide")
st.title("💼 Magnificent 7 + Custom Tickers Cash-Secured Puts ROI Screener")

user_input = st.text_input("Add more tickers (comma separated)", "")
custom_tickers = [x.strip().upper() for x in user_input.split(",") if x.strip()]
all_tickers = ['ALL'] + sorted(set(DEFAULT_MAGNIFICENT_7 + custom_tickers))

selected_stock = st.selectbox("Select Stock", all_tickers)
min_price = st.number_input("Minimum Current Price", min_value=0.0, value=50.0)
max_price = st.number_input("Maximum Current Price", min_value=0.0, value=1000.0)
moneyness = st.selectbox("Moneyness % Below Current Price", [1, 2, 3, 4, 5, 10, 15, 20, 30], index=4)

if selected_stock == 'ALL':
    expiration = st.selectbox("Weekly Expiration Date", get_weekly_fridays())
    if st.button("Run Screener for ALL"):
        results = []
        for ticker in all_tickers[1:]:
            option_data = get_put_option_data(ticker, expiration, moneyness)
            if option_data and min_price <= option_data['Current Price'] <= max_price:
                fundamentals = get_fundamentals(ticker)
                option_data.update(fundamentals)
                results.append(option_data)
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="Bid", ascending=False).reset_index(drop=True)
            st.success(f"Showing cash-secured puts for expiration: {expiration}")
            st.dataframe(df)
            st.download_button("Download CSV", df.to_csv(index=False), "cash_secured_puts_all.csv", "text/csv")
        else:
            st.warning("No results found for given filters.")
else:
    if st.button("Run Screener for Selected Stock"):
        results = []
        weekly_dates = get_weekly_fridays(n=4)
        for exp in weekly_dates:
            option_data = get_put_option_data(selected_stock, exp, moneyness)
            if option_data and min_price <= option_data['Current Price'] <= max_price:
                fundamentals = get_fundamentals(selected_stock)
                option_data.update(fundamentals)
                results.append(option_data)
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="Abs ROI (%)", ascending=False).reset_index(drop=True)
            st.success(f"Showing next 4 weekly expirations for {selected_stock}")
            st.dataframe(df)
            st.download_button("Download CSV", df.to_csv(index=False), f"{selected_stock}_puts_analysis.csv", "text/csv")
        else:
            st.warning("No results found for selected stock.")
