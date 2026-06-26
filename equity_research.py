"""
Equity Research
Dark-theme PNG dashboard — single-image, information-dense output.
Matches the visual style of Option Watch, Option Yield Compare, and Monte Carlo.
"""
import json
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd

# matplotlib is only needed for the (unused) PNG dashboard generator. Keep it
# optional so the web app doesn't require it as a dependency.
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    _HAS_MPL = True
except Exception:
    plt = None
    gridspec = None
    _HAS_MPL = False


# (runtime auto-install removed — dependencies come from requirements.txt)

import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# --- Dark theme palette (matching all other tools) ---
C = {
    'bg':     '#0D1117',
    'panel':  '#161B22',
    'border': '#30363D',
    'green':  '#3FB950',
    'red':    '#F85149',
    'yellow': '#D29922',
    'blue':   '#58A6FF',
    'purple': '#BC8CFF',
    'orange': '#FF7B72',
    'teal':   '#39D353',
    'pink':   '#FF79C6',
    'white':  '#E6EDF3',
    'sub':    '#8B949E',
}

SCRIPT_DIR   = Path(__file__).parent
SNAPSHOT_DIR = SCRIPT_DIR / 'snapshots'  # created lazily only if PNG export is used

if _HAS_MPL:
    plt.rcParams.update({
        'font.family':      'monospace',
        'figure.facecolor': C['bg'],
        'axes.facecolor':   C['panel'],
        'axes.edgecolor':   C['border'],
        'axes.labelcolor':  C['sub'],
        'xtick.color':      C['sub'],
        'ytick.color':      C['sub'],
        'grid.color':       C['border'],
        'grid.linewidth':   0.5,
        'grid.linestyle':   '--',
        'legend.facecolor': C['panel'],
        'legend.edgecolor': C['border'],
        'text.color':       C['white'],
    })


def _style_ax(ax, title=''):
    """Apply standard dark-theme styling to an axis."""
    ax.set_facecolor(C['panel'])
    for sp in ax.spines.values():
        sp.set_edgecolor(C['border'])
        sp.set_linewidth(0.8)
    ax.tick_params(colors=C['sub'], labelsize=8.5)
    ax.xaxis.label.set_color(C['sub'])
    ax.yaxis.label.set_color(C['sub'])
    ax.grid(True, color=C['border'], lw=0.5, linestyle='--', alpha=0.5)
    if title:
        ax.set_title(title, color=C['white'], fontsize=10, fontweight='bold', pad=6)


# =============================================================================
#  DATA CLASS
# =============================================================================

class EquityResearchReport:
    def __init__(self, ticker):
        self.ticker = ticker.upper()
        self.stock = None
        self.info = {}
        self.company_name = ""
        self.sector = ""
        self.industry = ""
        self.gics_sector = ""
        self.gics_industry = ""
        self.market_cap = 0
        self.earnings_data = {}
        self.yearly_eps = {}
        self.quarterly_eps = {}
        self.current_year = datetime.now().year

        self.sp500_constituents = self.load_comprehensive_sp500_database()
        self.initialize_stock_data()
        self.extract_accurate_financial_data()
        self.extract_quarterly_eps_data()

    # -------------------------------------------------------------------------
    # S&P 500 database
    # -------------------------------------------------------------------------

    def load_comprehensive_sp500_database(self):
        try:
            print("Attempting to load S&P 500 data from Wikipedia...")
            sp500_data = self.load_sp500_from_wikipedia()
            if sp500_data:
                print(f"✓ Successfully loaded {len(sp500_data)} S&P 500 companies from Wikipedia")
                return sp500_data
        except Exception as e:
            print(f"Could not load from Wikipedia: {e}")
        print("Using built-in S&P 500 database...")
        return self.load_extended_sp500_database()

    def load_sp500_from_wikipedia(self):
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            tables = pd.read_html(url)
            if len(tables) > 0:
                sp500_table = tables[0]
                sp500_data = {}
                for _, row in sp500_table.iterrows():
                    ticker = str(row['Symbol']).replace('.', '-')
                    name = str(row['Security'])
                    sector = str(row['GICS Sector'])
                    sub_industry = str(row['GICS Sub-Industry'])
                    if pd.isna(ticker) or pd.isna(sector):
                        continue
                    sp500_data[ticker] = {
                        'name': name,
                        'sector': sector,
                        'industry': sub_industry,
                        'gics_sector': sector,
                        'gics_industry': sub_industry
                    }
                return sp500_data
        except Exception as e:
            print(f"Error loading from Wikipedia: {e}")
        return None

    def load_extended_sp500_database(self):
        sp500_data = {
            # Information Technology
            'AAPL': {'name': 'Apple Inc.', 'sector': 'Information Technology', 'industry': 'Technology Hardware, Storage & Peripherals'},
            'MSFT': {'name': 'Microsoft Corporation', 'sector': 'Information Technology', 'industry': 'Systems Software'},
            'NVDA': {'name': 'NVIDIA Corporation', 'sector': 'Information Technology', 'industry': 'Semiconductors'},
            'AVGO': {'name': 'Broadcom Inc.', 'sector': 'Information Technology', 'industry': 'Semiconductors'},
            'ADBE': {'name': 'Adobe Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'CRM': {'name': 'Salesforce Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'CSCO': {'name': 'Cisco Systems Inc.', 'sector': 'Information Technology', 'industry': 'Communications Equipment'},
            'ACN': {'name': 'Accenture plc', 'sector': 'Information Technology', 'industry': 'IT Consulting & Other Services'},
            'ORCL': {'name': 'Oracle Corporation', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'IBM': {'name': 'International Business Machines', 'sector': 'Information Technology', 'industry': 'IT Consulting & Other Services'},
            'INTC': {'name': 'Intel Corporation', 'sector': 'Information Technology', 'industry': 'Semiconductors'},
            'AMD': {'name': 'Advanced Micro Devices Inc.', 'sector': 'Information Technology', 'industry': 'Semiconductors'},
            'QCOM': {'name': 'QUALCOMM Incorporated', 'sector': 'Information Technology', 'industry': 'Semiconductors'},
            'TXN': {'name': 'Texas Instruments Incorporated', 'sector': 'Information Technology', 'industry': 'Semiconductors'},
            'AMAT': {'name': 'Applied Materials Inc.', 'sector': 'Information Technology', 'industry': 'Semiconductor Equipment'},
            'LRCX': {'name': 'Lam Research Corporation', 'sector': 'Information Technology', 'industry': 'Semiconductor Equipment'},
            'MU': {'name': 'Micron Technology Inc.', 'sector': 'Information Technology', 'industry': 'Semiconductors'},
            'KLAC': {'name': 'KLA Corporation', 'sector': 'Information Technology', 'industry': 'Semiconductor Equipment'},
            'INTU': {'name': 'Intuit Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'NOW': {'name': 'ServiceNow Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'ADP': {'name': 'Automatic Data Processing Inc.', 'sector': 'Information Technology', 'industry': 'Data Processing & Outsourced Services'},
            'CDNS': {'name': 'Cadence Design Systems Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'SNPS': {'name': 'Synopsys Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'ANET': {'name': 'Arista Networks Inc.', 'sector': 'Information Technology', 'industry': 'Communications Equipment'},
            'FTNT': {'name': 'Fortinet Inc.', 'sector': 'Information Technology', 'industry': 'Systems Software'},
            'CRWD': {'name': 'CrowdStrike Holdings Inc.', 'sector': 'Information Technology', 'industry': 'Systems Software'},
            'PANW': {'name': 'Palo Alto Networks Inc.', 'sector': 'Information Technology', 'industry': 'Systems Software'},
            'ZS': {'name': 'Zscaler Inc.', 'sector': 'Information Technology', 'industry': 'Systems Software'},
            'NET': {'name': 'Cloudflare Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'MDB': {'name': 'MongoDB Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'SNOW': {'name': 'Snowflake Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'DDOG': {'name': 'Datadog Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'TEAM': {'name': 'Atlassian Corporation', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'PLTR': {'name': 'Palantir Technologies Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'UBER': {'name': 'Uber Technologies Inc.', 'sector': 'Information Technology', 'industry': 'Application Software'},
            'MRVL': {'name': 'Marvell Technology Inc.', 'sector': 'Information Technology', 'industry': 'Semiconductors'},

            # Communication Services
            'GOOGL': {'name': 'Alphabet Inc.', 'sector': 'Communication Services', 'industry': 'Interactive Media & Services'},
            'GOOG': {'name': 'Alphabet Inc.', 'sector': 'Communication Services', 'industry': 'Interactive Media & Services'},
            'META': {'name': 'Meta Platforms Inc.', 'sector': 'Communication Services', 'industry': 'Interactive Media & Services'},
            'NFLX': {'name': 'Netflix Inc.', 'sector': 'Communication Services', 'industry': 'Movies & Entertainment'},
            'DIS': {'name': 'Walt Disney Company', 'sector': 'Communication Services', 'industry': 'Movies & Entertainment'},
            'CMCSA': {'name': 'Comcast Corporation', 'sector': 'Communication Services', 'industry': 'Cable & Satellite'},
            'T': {'name': 'AT&T Inc.', 'sector': 'Communication Services', 'industry': 'Integrated Telecommunication Services'},
            'VZ': {'name': 'Verizon Communications Inc.', 'sector': 'Communication Services', 'industry': 'Integrated Telecommunication Services'},
            'TMUS': {'name': 'T-Mobile US Inc.', 'sector': 'Communication Services', 'industry': 'Wireless Telecommunication Services'},
            'CHTR': {'name': 'Charter Communications Inc.', 'sector': 'Communication Services', 'industry': 'Cable & Satellite'},
            'EA': {'name': 'Electronic Arts Inc.', 'sector': 'Communication Services', 'industry': 'Interactive Home Entertainment'},
            'TTWO': {'name': 'Take-Two Interactive Software Inc.', 'sector': 'Communication Services', 'industry': 'Interactive Home Entertainment'},
            'LYV': {'name': 'Live Nation Entertainment Inc.', 'sector': 'Communication Services', 'industry': 'Movies & Entertainment'},
            'FOXA': {'name': 'Fox Corporation', 'sector': 'Communication Services', 'industry': 'Movies & Entertainment'},
            'OMC': {'name': 'Omnicom Group Inc.', 'sector': 'Communication Services', 'industry': 'Advertising'},

            # Consumer Discretionary
            'AMZN': {'name': 'Amazon.com Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Broadline Retail'},
            'TSLA': {'name': 'Tesla Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Automobile Manufacturers'},
            'HD': {'name': 'Home Depot Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Home Improvement Retail'},
            'MCD': {'name': "McDonald's Corporation", 'sector': 'Consumer Discretionary', 'industry': 'Restaurants'},
            'NKE': {'name': 'Nike Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Apparel, Accessories & Luxury Goods'},
            'LOW': {'name': "Lowe's Companies Inc.", 'sector': 'Consumer Discretionary', 'industry': 'Home Improvement Retail'},
            'SBUX': {'name': 'Starbucks Corporation', 'sector': 'Consumer Discretionary', 'industry': 'Restaurants'},
            'TJX': {'name': 'TJX Companies Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Apparel Retail'},
            'BKNG': {'name': 'Booking Holdings Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Hotels, Resorts & Cruise Lines'},
            'MAR': {'name': 'Marriott International Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Hotels, Resorts & Cruise Lines'},
            'ORLY': {'name': "O'Reilly Automotive Inc.", 'sector': 'Consumer Discretionary', 'industry': 'Specialty Stores'},
            'AZO': {'name': 'AutoZone Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Specialty Stores'},
            'CMG': {'name': 'Chipotle Mexican Grill Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Restaurants'},
            'LULU': {'name': 'Lululemon Athletica Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Apparel, Accessories & Luxury Goods'},
            'DHI': {'name': 'D.R. Horton Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Homebuilding'},
            'LEN': {'name': 'Lennar Corporation', 'sector': 'Consumer Discretionary', 'industry': 'Homebuilding'},
            'CCL': {'name': 'Carnival Corporation & plc', 'sector': 'Consumer Discretionary', 'industry': 'Hotels, Resorts & Cruise Lines'},
            'RCL': {'name': 'Royal Caribbean Group', 'sector': 'Consumer Discretionary', 'industry': 'Hotels, Resorts & Cruise Lines'},
            'ABNB': {'name': 'Airbnb Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Hotels, Resorts & Cruise Lines'},
            'YUM': {'name': 'Yum! Brands Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Restaurants'},
            'DPZ': {"name": "Domino's Pizza Inc.", 'sector': 'Consumer Discretionary', 'industry': 'Restaurants'},

            # Consumer Staples
            'WMT': {'name': 'Walmart Inc.', 'sector': 'Consumer Staples', 'industry': 'Consumer Staples Merchandise Retail'},
            'PG': {'name': 'Procter & Gamble Company', 'sector': 'Consumer Staples', 'industry': 'Personal Care Products'},
            'KO': {'name': 'Coca-Cola Company', 'sector': 'Consumer Staples', 'industry': 'Soft Drinks & Non-alcoholic Beverages'},
            'PEP': {'name': 'PepsiCo Inc.', 'sector': 'Consumer Staples', 'industry': 'Soft Drinks & Non-alcoholic Beverages'},
            'COST': {'name': 'Costco Wholesale Corporation', 'sector': 'Consumer Staples', 'industry': 'Consumer Staples Merchandise Retail'},
            'PM': {'name': 'Philip Morris International Inc.', 'sector': 'Consumer Staples', 'industry': 'Tobacco'},
            'MO': {'name': 'Altria Group Inc.', 'sector': 'Consumer Staples', 'industry': 'Tobacco'},
            'MDLZ': {'name': 'Mondelez International Inc.', 'sector': 'Consumer Staples', 'industry': 'Packaged Foods & Meats'},
            'KHC': {'name': 'Kraft Heinz Company', 'sector': 'Consumer Staples', 'industry': 'Packaged Foods & Meats'},
            'CL': {'name': 'Colgate-Palmolive Company', 'sector': 'Consumer Staples', 'industry': 'Personal Care Products'},
            'EL': {'name': 'Estee Lauder Companies Inc.', 'sector': 'Consumer Staples', 'industry': 'Personal Care Products'},
            'STZ': {'name': 'Constellation Brands Inc.', 'sector': 'Consumer Staples', 'industry': 'Distillers & Vintners'},
            'KR': {'name': 'Kroger Company', 'sector': 'Consumer Staples', 'industry': 'Consumer Staples Merchandise Retail'},
            'SYY': {'name': 'Sysco Corporation', 'sector': 'Consumer Staples', 'industry': 'Food Distributors'},

            # Healthcare
            'UNH': {'name': 'UnitedHealth Group Inc.', 'sector': 'Health Care', 'industry': 'Managed Health Care'},
            'JNJ': {'name': 'Johnson & Johnson', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},
            'LLY': {'name': 'Eli Lilly and Company', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},
            'MRK': {'name': 'Merck & Co. Inc.', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},
            'ABBV': {'name': 'AbbVie Inc.', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},
            'PFE': {'name': 'Pfizer Inc.', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},
            'TMO': {'name': 'Thermo Fisher Scientific Inc.', 'sector': 'Health Care', 'industry': 'Life Sciences Tools & Services'},
            'DHR': {'name': 'Danaher Corporation', 'sector': 'Health Care', 'industry': 'Life Sciences Tools & Services'},
            'ABT': {'name': 'Abbott Laboratories', 'sector': 'Health Care', 'industry': 'Health Care Equipment'},
            'BMY': {'name': 'Bristol-Myers Squibb Company', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},
            'AMGN': {'name': 'Amgen Inc.', 'sector': 'Health Care', 'industry': 'Biotechnology'},
            'CVS': {'name': 'CVS Health Corporation', 'sector': 'Health Care', 'industry': 'Health Care Services'},
            'ISRG': {'name': 'Intuitive Surgical Inc.', 'sector': 'Health Care', 'industry': 'Health Care Equipment'},
            'GILD': {'name': 'Gilead Sciences Inc.', 'sector': 'Health Care', 'industry': 'Biotechnology'},
            'VRTX': {'name': 'Vertex Pharmaceuticals Incorporated', 'sector': 'Health Care', 'industry': 'Biotechnology'},
            'REGN': {'name': 'Regeneron Pharmaceuticals Inc.', 'sector': 'Health Care', 'industry': 'Biotechnology'},
            'CI': {'name': 'Cigna Corporation', 'sector': 'Health Care', 'industry': 'Managed Health Care'},
            'HUM': {'name': 'Humana Inc.', 'sector': 'Health Care', 'industry': 'Managed Health Care'},
            'BDX': {'name': 'Becton, Dickinson and Company', 'sector': 'Health Care', 'industry': 'Health Care Equipment'},
            'SYK': {'name': 'Stryker Corporation', 'sector': 'Health Care', 'industry': 'Health Care Equipment'},
            'BSX': {'name': 'Boston Scientific Corporation', 'sector': 'Health Care', 'industry': 'Health Care Equipment'},
            'ZTS': {'name': 'Zoetis Inc.', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},
            'MRNA': {'name': 'Moderna Inc.', 'sector': 'Health Care', 'industry': 'Biotechnology'},
            'BIIB': {'name': 'Biogen Inc.', 'sector': 'Health Care', 'industry': 'Biotechnology'},
            'NVO': {'name': 'Novo Nordisk A/S', 'sector': 'Health Care', 'industry': 'Pharmaceuticals'},

            # Financials
            'JPM': {'name': 'JPMorgan Chase & Co.', 'sector': 'Financials', 'industry': 'Diversified Banks'},
            'V': {'name': 'Visa Inc.', 'sector': 'Financials', 'industry': 'Transaction & Payment Processing Services'},
            'MA': {'name': 'Mastercard Incorporated', 'sector': 'Financials', 'industry': 'Transaction & Payment Processing Services'},
            'BAC': {'name': 'Bank of America Corporation', 'sector': 'Financials', 'industry': 'Diversified Banks'},
            'WFC': {'name': 'Wells Fargo & Company', 'sector': 'Financials', 'industry': 'Diversified Banks'},
            'GS': {'name': 'Goldman Sachs Group Inc.', 'sector': 'Financials', 'industry': 'Investment Banking & Brokerage'},
            'MS': {'name': 'Morgan Stanley', 'sector': 'Financials', 'industry': 'Investment Banking & Brokerage'},
            'BLK': {'name': 'BlackRock Inc.', 'sector': 'Financials', 'industry': 'Asset Management & Custody Banks'},
            'SCHW': {'name': 'Charles Schwab Corporation', 'sector': 'Financials', 'industry': 'Investment Banking & Brokerage'},
            'AXP': {'name': 'American Express Company', 'sector': 'Financials', 'industry': 'Consumer Finance'},
            'C': {'name': 'Citigroup Inc.', 'sector': 'Financials', 'industry': 'Diversified Banks'},
            'BRK-B': {'name': 'Berkshire Hathaway Inc.', 'sector': 'Financials', 'industry': 'Multi-Sector Holdings'},
            'PYPL': {'name': 'PayPal Holdings Inc.', 'sector': 'Financials', 'industry': 'Transaction & Payment Processing Services'},
            'COF': {'name': 'Capital One Financial Corporation', 'sector': 'Financials', 'industry': 'Consumer Finance'},
            'USB': {'name': 'U.S. Bancorp', 'sector': 'Financials', 'industry': 'Regional Banks'},
            'PNC': {'name': 'PNC Financial Services Group Inc.', 'sector': 'Financials', 'industry': 'Regional Banks'},
            'CB': {'name': 'Chubb Limited', 'sector': 'Financials', 'industry': 'Property & Casualty Insurance'},
            'SPGI': {'name': 'S&P Global Inc.', 'sector': 'Financials', 'industry': 'Financial Exchanges & Data'},
            'MMC': {'name': 'Marsh & McLennan Companies Inc.', 'sector': 'Financials', 'industry': 'Insurance Brokers'},
            'ICE': {'name': 'Intercontinental Exchange Inc.', 'sector': 'Financials', 'industry': 'Financial Exchanges & Data'},
            'CME': {'name': 'CME Group Inc.', 'sector': 'Financials', 'industry': 'Financial Exchanges & Data'},
            'MCO': {'name': "Moody's Corporation", 'sector': 'Financials', 'industry': 'Financial Exchanges & Data'},
            'SOFI': {'name': 'SoFi Technologies Inc.', 'sector': 'Financials', 'industry': 'Consumer Finance'},

            # Industrials
            'BA': {'name': 'Boeing Company', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
            'CAT': {'name': 'Caterpillar Inc.', 'sector': 'Industrials', 'industry': 'Construction Machinery & Heavy Trucks'},
            'UNP': {'name': 'Union Pacific Corporation', 'sector': 'Industrials', 'industry': 'Rail Transportation'},
            'UPS': {'name': 'United Parcel Service Inc.', 'sector': 'Industrials', 'industry': 'Air Freight & Logistics'},
            'HON': {'name': 'Honeywell International Inc.', 'sector': 'Industrials', 'industry': 'Industrial Conglomerates'},
            'RTX': {'name': 'Raytheon Technologies Corporation', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
            'LMT': {'name': 'Lockheed Martin Corporation', 'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
            'GE': {'name': 'General Electric Company', 'sector': 'Industrials', 'industry': 'Industrial Conglomerates'},
            'DE': {'name': 'Deere & Company', 'sector': 'Industrials', 'industry': 'Agricultural & Farm Machinery'},
            'CSX': {'name': 'CSX Corporation', 'sector': 'Industrials', 'industry': 'Rail Transportation'},
            'FDX': {'name': 'FedEx Corporation', 'sector': 'Industrials', 'industry': 'Air Freight & Logistics'},
            'EMR': {'name': 'Emerson Electric Co.', 'sector': 'Industrials', 'industry': 'Electrical Components & Equipment'},
            'ITW': {'name': 'Illinois Tool Works Inc.', 'sector': 'Industrials', 'industry': 'Industrial Machinery'},
            'ETN': {'name': 'Eaton Corporation plc', 'sector': 'Industrials', 'industry': 'Electrical Components & Equipment'},
            'WM': {'name': 'Waste Management Inc.', 'sector': 'Industrials', 'industry': 'Environmental & Facilities Services'},
            'VRT': {'name': 'Vertiv Holdings Co', 'sector': 'Industrials', 'industry': 'Electrical Components & Equipment'},

            # Energy
            'XOM': {'name': 'Exxon Mobil Corporation', 'sector': 'Energy', 'industry': 'Integrated Oil & Gas'},
            'CVX': {'name': 'Chevron Corporation', 'sector': 'Energy', 'industry': 'Integrated Oil & Gas'},
            'COP': {'name': 'ConocoPhillips', 'sector': 'Energy', 'industry': 'Oil & Gas Exploration & Production'},
            'SLB': {'name': 'Schlumberger Limited', 'sector': 'Energy', 'industry': 'Oil & Gas Equipment & Services'},
            'EOG': {'name': 'EOG Resources Inc.', 'sector': 'Energy', 'industry': 'Oil & Gas Exploration & Production'},
            'MPC': {'name': 'Marathon Petroleum Corporation', 'sector': 'Energy', 'industry': 'Oil & Gas Refining & Marketing'},
            'OXY': {'name': 'Occidental Petroleum Corporation', 'sector': 'Energy', 'industry': 'Oil & Gas Exploration & Production'},

            # Materials
            'LIN': {'name': 'Linde plc', 'sector': 'Materials', 'industry': 'Industrial Gases'},
            'APD': {'name': 'Air Products and Chemicals Inc.', 'sector': 'Materials', 'industry': 'Industrial Gases'},
            'FCX': {'name': 'Freeport-McMoRan Inc.', 'sector': 'Materials', 'industry': 'Copper'},
            'NEM': {'name': 'Newmont Corporation', 'sector': 'Materials', 'industry': 'Gold'},
            'SHW': {'name': 'Sherwin-Williams Company', 'sector': 'Materials', 'industry': 'Specialty Chemicals'},

            # Real Estate
            'PLD': {'name': 'Prologis Inc.', 'sector': 'Real Estate', 'industry': 'Industrial REITs'},
            'AMT': {'name': 'American Tower Corporation', 'sector': 'Real Estate', 'industry': 'Specialized REITs'},
            'EQIX': {'name': 'Equinix Inc.', 'sector': 'Real Estate', 'industry': 'Specialized REITs'},
            'PSA': {'name': 'Public Storage', 'sector': 'Real Estate', 'industry': 'Self-Storage REITs'},

            # Utilities
            'NEE': {'name': 'NextEra Energy Inc.', 'sector': 'Utilities', 'industry': 'Electric Utilities'},
            'DUK': {'name': 'Duke Energy Corporation', 'sector': 'Utilities', 'industry': 'Electric Utilities'},
            'SO': {'name': 'Southern Company', 'sector': 'Utilities', 'industry': 'Electric Utilities'},
        }
        return sp500_data

    # -------------------------------------------------------------------------
    # Stock data initialisation
    # -------------------------------------------------------------------------

    def initialize_stock_data(self):
        try:
            self.stock = yf.Ticker(self.ticker)
            self.info = self.stock.info

            if not self.info or ('regularMarketPrice' not in self.info and 'currentPrice' not in self.info):
                hist = self.stock.history(period='5d')
                if hist.empty:
                    print(f"No data found for {self.ticker} on Yahoo Finance")
                    return
                if not self.info:
                    self.info = {}
                if not hist.empty:
                    self.info.setdefault('currentPrice', float(hist['Close'].iloc[-1]))

            self.company_name = self.info.get('longName', self.ticker)
            self.sector       = self.info.get('sector', 'N/A')
            self.industry     = self.info.get('industry', 'N/A')
            self.market_cap   = self.info.get('marketCap', 0)
            self.gics_sector  = self.map_to_gics_sector(self.sector)
            self.gics_industry = self.industry

            print(f"✓ Loaded data for {self.company_name}")
            print(f"  Sector: {self.sector} -> GICS: {self.gics_sector}")
        except Exception as e:
            print(f"Error initializing stock data: {e}")

    # -------------------------------------------------------------------------
    # EPS extraction
    # -------------------------------------------------------------------------

    def extract_accurate_financial_data(self):
        print(f"\nExtracting financial data for {self.ticker}...")
        self.yearly_eps = {}
        self.extract_eps_from_financials_accurate()
        self.extract_eps_from_earnings_dates_accurate()
        self.get_analyst_estimates()
        self.add_accurate_eps_fallbacks()

        if self.yearly_eps:
            print("✓ EPS data:")
            for year in sorted(self.yearly_eps.keys()):
                print(f"  {year}: ${self.yearly_eps[year]:.2f}")
        else:
            print("⚠ No EPS data extracted")

    def extract_eps_from_financials_accurate(self):
        try:
            financials = self.stock.financials
            if financials is None or financials.empty:
                return
            eps_patterns = ['Basic EPS', 'Diluted EPS', 'Earnings Per Share', 'EPS', 'Net Income Per Share']
            for pattern in eps_patterns:
                for idx in financials.index:
                    if isinstance(idx, str) and pattern.lower() in idx.lower():
                        eps_data = financials.loc[idx]
                        for date, eps_value in eps_data.items():
                            if pd.notna(eps_value) and abs(eps_value) > 0.001:
                                year = date.year
                                self.yearly_eps[year] = float(eps_value)
                                print(f"    Found {year} annual EPS: ${float(eps_value):.2f}")
                        return
            print("  Calculating EPS from net income and shares...")
            self.calculate_eps_from_components(financials)
        except Exception as e:
            print(f"  Error extracting EPS from financials: {e}")

    def calculate_eps_from_components(self, financials):
        try:
            net_income_row = None
            for pattern in ['Net Income', 'Net Profit', 'Net Earnings']:
                for idx in financials.index:
                    if isinstance(idx, str) and pattern.lower() in idx.lower():
                        net_income_row = idx
                        break
                if net_income_row:
                    break

            if net_income_row:
                net_income_data = financials.loc[net_income_row]
                shares = (self.info.get('impliedSharesOutstanding')
                          or self.info.get('sharesOutstanding'))
                if shares and shares > 0:
                    for date, net_income in net_income_data.items():
                        if pd.notna(net_income) and abs(net_income) > 1e4:
                            year = date.year
                            eps = net_income / shares
                            self.yearly_eps[year] = eps
                            print(f"    Calculated {year} EPS: ${eps:.2f}")
        except Exception as e:
            print(f"  Error calculating EPS from components: {e}")

    def extract_eps_from_earnings_dates_accurate(self):
        try:
            earnings = self.stock.earnings_dates
            if earnings is None or earnings.empty:
                return
            if 'Reported EPS' in earnings.columns:
                for date, row in earnings.iterrows():
                    eps = row['Reported EPS']
                    if pd.notna(eps) and abs(eps) > 0.001:
                        year    = date.year
                        quarter = f"Q{(date.month - 1) // 3 + 1}"
                        if year not in self.quarterly_eps:
                            self.quarterly_eps[year] = {}
                        self.quarterly_eps[year][quarter] = eps
                        print(f"    Found {year} {quarter} EPS: ${eps:.2f}")
        except Exception as e:
            print(f"  Error extracting EPS from earnings dates: {e}")

    def extract_quarterly_eps_data(self):
        try:
            earnings = self.stock.earnings_dates
            if earnings is None or earnings.empty:
                return
            if 'Reported EPS' in earnings.columns:
                self.quarterly_eps = {}
                for date, row in earnings.iterrows():
                    eps = row['Reported EPS']
                    if pd.notna(eps) and abs(eps) > 0.001:
                        year    = date.year
                        quarter = f"Q{(date.month - 1) // 3 + 1}"
                        if year not in self.quarterly_eps:
                            self.quarterly_eps[year] = {}
                        self.quarterly_eps[year][quarter] = eps
                print(f"  Quarterly EPS data extracted for {len(self.quarterly_eps)} years")
        except Exception as e:
            print(f"  Error extracting quarterly EPS data: {e}")

    def calculate_trailing_eps(self, year):
        try:
            current_year = datetime.now().year
            if year == current_year:
                total_eps    = 0
                quarter_count = 0
                check_year   = year
                quarters_left = 4
                while quarters_left > 0 and check_year >= year - 1:
                    if check_year in self.quarterly_eps:
                        for q in sorted(self.quarterly_eps[check_year].keys(), reverse=True):
                            if quarters_left > 0:
                                total_eps += self.quarterly_eps[check_year][q]
                                quarter_count += 1
                                quarters_left -= 1
                    check_year -= 1
                if quarter_count == 4:
                    return total_eps
                elif quarter_count > 0:
                    return total_eps * (4 / quarter_count)
            elif year > current_year:
                forward_eps = self.info.get('forwardEps')
                if forward_eps and forward_eps > 0:
                    return forward_eps
                current_ttm = self.get_current_ttm_eps()
                return current_ttm * (1.08 ** (year - current_year))
            else:
                if year in self.yearly_eps:
                    return self.yearly_eps[year]
                if year in self.quarterly_eps:
                    quarters = self.quarterly_eps[year]
                    if len(quarters) == 4:
                        return sum(quarters.values())
                    elif len(quarters) > 0:
                        return sum(quarters.values()) * (4 / len(quarters))
            return self.get_current_ttm_eps()
        except Exception as e:
            print(f"  Error calculating trailing EPS for {year}: {e}")
            return self.get_current_ttm_eps()

    def get_analyst_estimates(self):
        try:
            forward_eps = self.info.get('forwardEps')
            current_year = datetime.now().year
            if forward_eps and forward_eps > 0:
                next_year = current_year + 1
                if next_year not in self.yearly_eps:
                    self.yearly_eps[next_year] = forward_eps
                    print(f"    Using forward EPS for {next_year}: ${forward_eps:.2f}")
        except Exception as e:
            print(f"  Error getting analyst estimates: {e}")

    def add_accurate_eps_fallbacks(self):
        try:
            current_year = datetime.now().year
            if current_year not in self.yearly_eps:
                trailing_eps = self.info.get('trailingEps')
                if trailing_eps and trailing_eps > 0:
                    self.yearly_eps[current_year] = trailing_eps
                    print(f"    Using trailing EPS for {current_year}: ${trailing_eps:.2f}")

            next_year = current_year + 1
            if next_year not in self.yearly_eps:
                forward_eps = self.info.get('forwardEps')
                if forward_eps and forward_eps > 0:
                    self.yearly_eps[next_year] = forward_eps
                    print(f"    Using forward EPS for {next_year}: ${forward_eps:.2f}")
                elif current_year in self.yearly_eps:
                    estimated = self.yearly_eps[current_year] * 1.10
                    self.yearly_eps[next_year] = estimated
                    print(f"    Estimated {next_year} EPS: ${estimated:.2f} (10% growth)")

            year_2 = current_year + 2
            if year_2 not in self.yearly_eps and current_year in self.yearly_eps:
                estimated = self.yearly_eps[current_year] * (1.08 ** 2)
                self.yearly_eps[year_2] = estimated
                print(f"    Estimated {year_2} EPS: ${estimated:.2f} (8% annual growth)")

            prev_year = current_year - 1
            if prev_year not in self.yearly_eps and self.yearly_eps:
                earliest = min(self.yearly_eps.keys())
                if earliest < prev_year:
                    self.yearly_eps[prev_year] = self.yearly_eps[earliest] * 0.95
        except Exception as e:
            print(f"  Error adding EPS fallbacks: {e}")

    def get_current_ttm_eps(self):
        try:
            ttm = self.info.get('trailingEps')
            if ttm and ttm > 0:
                return ttm
            ttm_calc = self.calculate_trailing_eps(datetime.now().year)
            if ttm_calc and ttm_calc > 0:
                return ttm_calc
            financials = self.stock.financials
            if financials is not None and not financials.empty:
                for idx in financials.index:
                    if any(k in str(idx).lower() for k in ['eps', 'earnings per share', 'net income per share']):
                        for date, eps in financials.loc[idx].items():
                            if pd.notna(eps) and abs(eps) > 0.001:
                                return eps
            return 1.0
        except Exception:
            return 1.0

    def get_forward_eps_for_year(self, year):
        try:
            current_year = datetime.now().year
            if year == current_year + 1:
                forward_eps = self.info.get('forwardEps')
                if forward_eps and forward_eps > 0:
                    return forward_eps
            if current_year in self.yearly_eps:
                return self.yearly_eps[current_year] * (1.08 ** (year - current_year))
            return self.info.get('trailingEps', 1.0)
        except Exception:
            return self.info.get('trailingEps', 1.0)

    def get_historical_eps_for_year(self, year):
        try:
            if year in self.yearly_eps:
                return self.yearly_eps[year]
            if self.yearly_eps:
                closest = min(self.yearly_eps.keys(), key=lambda x: abs(x - year))
                return self.yearly_eps[closest]
            return self.info.get('trailingEps', 1.0)
        except Exception:
            return self.info.get('trailingEps', 1.0)

    def get_annual_eps_for_year(self, year):
        try:
            current_year = datetime.now().year
            if year <= current_year:
                trailing = self.calculate_trailing_eps(year)
                if trailing and trailing > 0:
                    return trailing
                if year == current_year:
                    return self.get_current_ttm_eps()
                return self.get_historical_eps_for_year(year)
            elif year == current_year + 1:
                if year in self.yearly_eps:
                    return self.yearly_eps[year]
                forward_eps = self.info.get('forwardEps')
                if forward_eps and forward_eps > 0:
                    return forward_eps
                return self.get_current_ttm_eps() * 1.08
            else:
                return self.get_current_ttm_eps() * (1.08 ** (year - current_year))
        except Exception as e:
            print(f"Error in get_annual_eps_for_year for {year}: {e}")
            return self.get_current_ttm_eps()

    # -------------------------------------------------------------------------
    # Sector / peers
    # -------------------------------------------------------------------------

    def map_to_gics_sector(self, yahoo_sector):
        mapping = {
            'Technology': 'Information Technology',
            'Consumer Cyclical': 'Consumer Discretionary',
            'Healthcare': 'Health Care',
            'Financial Services': 'Financials',
            'Communication Services': 'Communication Services',
            'Energy': 'Energy',
            'Industrials': 'Industrials',
            'Consumer Defensive': 'Consumer Staples',
            'Utilities': 'Utilities',
            'Real Estate': 'Real Estate',
            'Basic Materials': 'Materials',
        }
        return mapping.get(yahoo_sector, yahoo_sector)

    def get_industry_peers(self) -> List[str]:
        print(f"\nSearching for peers in {self.gics_sector} - {self.industry}...")
        peers = list(set(
            self.get_sp500_peers_from_database() + self.get_yahoo_recommendations()
        ))
        if len(peers) < 4:
            peers += self.get_broader_sector_peers()
        peers = list(set(peers))
        if self.ticker in peers:
            peers.remove(self.ticker)
        valid = []
        for p in peers[:12]:
            if self.validate_ticker(p):
                valid.append(p)
        print(f"✓ Found {len(valid)} valid peers: {valid}")
        return valid

    def get_sp500_peers_from_database(self) -> List[str]:
        try:
            industry_peers = []
            sector_peers   = []
            for ticker, data in self.sp500_constituents.items():
                if ticker == self.ticker:
                    continue
                db_ind = str(data.get('industry', '')).lower()
                my_ind = str(self.industry).lower() if self.industry else ''
                if my_ind and db_ind and (my_ind == db_ind or my_ind in db_ind or db_ind in my_ind):
                    industry_peers.append(ticker)
                elif data.get('sector', '').lower() == self.gics_sector.lower():
                    sector_peers.append(ticker)
            return industry_peers[:8] if industry_peers else sector_peers[:8]
        except Exception as e:
            print(f"Error with S&P 500 database: {e}")
            return []

    def get_yahoo_recommendations(self) -> List[str]:
        try:
            rec_data = self.stock.recommendations
            if rec_data is not None and not rec_data.empty:
                return []
            return []
        except Exception:
            return []

    def get_broader_sector_peers(self) -> List[str]:
        try:
            return [t for t, d in self.sp500_constituents.items()
                    if t != self.ticker and d['sector'].lower() == self.gics_sector.lower()][:6]
        except Exception:
            return []

    def validate_ticker(self, ticker: str) -> bool:
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info
            return info is not None and 'currentPrice' in info
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Financial helpers
    # -------------------------------------------------------------------------

    def get_comprehensive_earnings_data(self) -> dict:
        try:
            earnings_dates = self.stock.earnings_dates
            if earnings_dates is None or earnings_dates.empty:
                return {}

            now = datetime.now()
            if earnings_dates.index.tz is not None:
                earnings_dates.index = earnings_dates.index.tz_localize(None)

            cols_needed = ['EPS Estimate', 'Reported EPS']
            if not all(c in earnings_dates.columns for c in cols_needed):
                return {}

            recent = earnings_dates[
                (earnings_dates.index < now) &
                pd.notna(earnings_dates['EPS Estimate']) &
                pd.notna(earnings_dates['Reported EPS'])
            ].sort_index(ascending=False).head(8)

            earnings_info = {}
            for date, row in recent.iterrows():
                est  = row['EPS Estimate']
                act  = row['Reported EPS']
                diff = act - est
                pct  = (diff / abs(est) * 100) if abs(est) > 0.001 else 0
                surprise = 'Beat' if diff > 0.001 else ('Miss' if diff < -0.001 else 'Meet')
                earnings_info[date.strftime('%Y-%m-%d')] = {
                    'date':            date.strftime('%Y-%m-%d'),
                    'quarter':         f"Q{(date.month-1)//3+1} {date.year}",
                    'eps_estimate':    est,
                    'eps_actual':      act,
                    'eps_beat_miss':   diff,
                    'eps_percent_diff': pct,
                    'eps_surprise':    surprise,
                }
            return dict(sorted(earnings_info.items()))
        except Exception as e:
            print(f"Error getting earnings data: {e}")
            return {}

    def calculate_dividend_yield(self) -> float:
        try:
            rate  = self.info.get('dividendRate')
            price = self.info.get('currentPrice')
            if rate and price:
                return (rate / price) * 100
            div_yield = self.info.get('dividendYield')
            return div_yield * 100 if div_yield else 0.0
        except Exception:
            return 0.0

    def calculate_peg_ratio(self):
        try:
            peg = self.info.get('pegRatio')
            if peg:
                return peg
            pe = self.info.get('trailingPE')
            if not pe:
                return None
            eg = self.info.get('earningsGrowth', self.info.get('revenueGrowth'))
            if eg and eg > 0:
                return max(0.1, min(pe / (eg * 100), 10))
            return None
        except Exception:
            return None

    def get_peer_data_with_forward_pe(self) -> List[dict]:
        peers_data   = []
        peer_tickers = self.get_industry_peers()
        for ticker in peer_tickers:
            try:
                peer_info = yf.Ticker(ticker).info
                if not peer_info or 'currentPrice' not in peer_info:
                    continue
                price  = peer_info.get('currentPrice', 0)
                w_lo   = peer_info.get('fiftyTwoWeekLow', 0)
                w_hi   = peer_info.get('fiftyTwoWeekHigh', 0)
                pos    = ((price - w_lo) / (w_hi - w_lo) * 100) if w_hi > w_lo else 50
                div_r  = peer_info.get('dividendRate', 0)
                div_y  = (div_r / price * 100) if (div_r and price) else (peer_info.get('dividendYield', 0) * 100)
                peers_data.append({
                    'ticker':            ticker,
                    'name':              peer_info.get('longName', ticker),
                    'forward_pe':        peer_info.get('forwardPE'),
                    'trailing_pe':       peer_info.get('trailingPE'),
                    'dividend_yield':    div_y,
                    'market_cap':        peer_info.get('marketCap', 0),
                    'price_position_pct': pos,
                    'current_price':     price,
                })
            except Exception:
                continue
        return peers_data

    def get_target_company_data(self) -> Optional[dict]:
        try:
            price = self.info.get('currentPrice', 0)
            w_lo  = self.info.get('fiftyTwoWeekLow', 0)
            w_hi  = self.info.get('fiftyTwoWeekHigh', 0)
            pos   = ((price - w_lo) / (w_hi - w_lo) * 100) if w_hi > w_lo else 50
            return {
                'ticker':            self.ticker,
                'name':              self.company_name,
                'forward_pe':        self.info.get('forwardPE'),
                'trailing_pe':       self.info.get('trailingPE'),
                'dividend_yield':    self.calculate_dividend_yield(),
                'market_cap':        self.market_cap,
                'price_position_pct': pos,
                'current_price':     price,
            }
        except Exception:
            return None

    def _find_financial_row(self, df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
        if df is None or df.empty:
            return None
        for kw in keywords:
            for idx in df.index:
                if kw in str(idx).lower():
                    return idx
        return None

    # =========================================================================
    #  VISUALISATION — dark-theme PNG dashboard
    # =========================================================================

    def generate_image_report(self) -> str:
        """Render a single dark-theme PNG dashboard and return the file path."""
        self.earnings_data = self.get_comprehensive_earnings_data()

        fig = plt.figure(figsize=(22, 26), dpi=100)
        fig.patch.set_facecolor(C['bg'])

        # 4-row layout: compact combined banner, price+metrics, financials, peers
        gs = gridspec.GridSpec(
            4, 3, figure=fig,
            height_ratios=[1.6, 10, 10, 5.5],
            hspace=0.34, wspace=0.32,
            left=0.03, right=0.97, top=0.975, bottom=0.025,
        )

        ax_banner = fig.add_subplot(gs[0, :])
        ax_price  = fig.add_subplot(gs[1, :2])
        ax_mets   = fig.add_subplot(gs[1,  2])
        ax_ann    = fig.add_subplot(gs[2,  0])
        ax_qtr    = fig.add_subplot(gs[2,  1])
        ax_earn   = fig.add_subplot(gs[2,  2])
        ax_peers  = fig.add_subplot(gs[3, :])

        self._draw_banner(ax_banner)
        self._draw_price_chart(ax_price)
        self._draw_metrics_and_risk(ax_mets)
        self._draw_annual_financials(ax_ann)
        self._draw_quarterly_financials(ax_qtr)
        self._draw_earnings_chart(ax_earn)
        self._draw_peer_table(ax_peers)

        fig.text(
            0.5, 0.004,
            f'Data: Yahoo Finance  |  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}  '
            f'|  For informational purposes only. Not investment advice.',
            ha='center', va='bottom', fontsize=8, color=C['sub'],
        )

        ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = SNAPSHOT_DIR / f'{self.ticker}_research_{ts}.png'
        fig.savefig(out, dpi=100, bbox_inches='tight', facecolor=C['bg'])
        plt.close(fig)
        print(f'✓ Dashboard saved: {out}')
        return str(out)

    # -------------------------------------------------------------------------
    # Combined banner: identity left | price centre-left | metric chips right
    # -------------------------------------------------------------------------

    def _draw_banner(self, ax):
        """Single compact banner row that replaces the old separate header + chips rows.
        Left panel  (0–0.22): Ticker, company name, sector/industry tag
        Price panel (0.22–0.42): Current price, day change, 52-week range bar
        Chips panel (0.42–1.0): 2-row × 5-col key metric grid
        """
        ax.set_facecolor(C['panel'])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        for sp in ax.spines.values():
            sp.set_edgecolor(C['border'])
            sp.set_linewidth(1.2)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

        # ── data ──────────────────────────────────────────────────────────────
        price   = float(self.info.get('currentPrice') or self.info.get('regularMarketPrice') or 0)
        prev    = float(self.info.get('previousClose') or price)
        chg     = price - prev
        chg_pct = (chg / prev * 100) if prev else 0
        chg_col = C['green'] if chg >= 0 else C['red']
        sign    = '+' if chg >= 0 else ''

        mktcap  = self.market_cap or 0
        pe      = self.info.get('trailingPE') or 0
        fpe     = self.info.get('forwardPE')  or 0
        peg     = self.calculate_peg_ratio()
        ev_eb   = self.info.get('enterpriseToEbitda')
        beta    = self.info.get('beta')
        div     = self.calculate_dividend_yield()
        rev_g   = self.info.get('revenueGrowth')
        margin  = self.info.get('profitMargins')
        w_lo    = self.info.get('fiftyTwoWeekLow', 0)
        w_hi    = self.info.get('fiftyTwoWeekHigh', 0)
        pos52   = ((price - w_lo) / (w_hi - w_lo) * 100) if w_hi > w_lo else 50
        country = self.info.get('country', '')

        def _mc(v):
            if v >= 1e12: return f'${v/1e12:.2f}T'
            if v >= 1e9:  return f'${v/1e9:.2f}B'
            if v >= 1e6:  return f'${v/1e6:.0f}M'
            return 'N/A'

        # ── LEFT PANEL (0 → 0.22): identity ──────────────────────────────────
        ax.axvline(0.22, color=C['border'], lw=0.8, alpha=0.8)
        ax.text(0.01, 0.80, self.ticker, fontsize=28, fontweight='bold',
                color=C['white'], va='center', ha='left', transform=ax.transAxes)
        name_short = (self.company_name[:28] + '…') if len(self.company_name) > 30 else self.company_name
        ax.text(0.01, 0.52, name_short, fontsize=10, color=C['sub'],
                va='center', ha='left', transform=ax.transAxes)
        sector_short = (self.gics_sector[:28] + '…') if len(self.gics_sector) > 30 else self.gics_sector
        ax.text(0.01, 0.26, sector_short, fontsize=9, color=C['blue'],
                va='center', ha='left', fontweight='bold', transform=ax.transAxes)
        if country:
            ax.text(0.01, 0.09, country, fontsize=8, color=C['sub'],
                    va='center', ha='left', transform=ax.transAxes)

        # ── PRICE PANEL (0.22 → 0.42) ─────────────────────────────────────────
        ax.axvline(0.42, color=C['border'], lw=0.8, alpha=0.8)
        ax.text(0.32, 0.78, f'${price:,.2f}', fontsize=24, fontweight='bold',
                color=C['white'], va='center', ha='center', transform=ax.transAxes)
        ax.text(0.32, 0.56, f'{sign}{chg:.2f}  ({sign}{chg_pct:.2f}%)',
                fontsize=11, color=chg_col, va='center', ha='center',
                fontweight='bold', transform=ax.transAxes)

        # 52-week range bar
        bar_x0, bar_x1 = 0.235, 0.408
        bar_y = 0.28
        bar_h = 0.07
        # track background
        ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
            (bar_x0, bar_y - bar_h / 2), bar_x1 - bar_x0, bar_h,
            boxstyle='round,pad=0.002', transform=ax.transAxes,
            facecolor=C['bg'], edgecolor=C['border'], lw=0.6, clip_on=True))
        # filled portion
        filled_w = (bar_x1 - bar_x0) * max(0, min(pos52 / 100, 1))
        fill_col = C['green'] if pos52 >= 60 else (C['yellow'] if pos52 >= 35 else C['red'])
        if filled_w > 0.002:
            ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
                (bar_x0, bar_y - bar_h / 2 + 0.008), filled_w, bar_h - 0.016,
                boxstyle='round,pad=0.001', transform=ax.transAxes,
                facecolor=fill_col, edgecolor='none', alpha=0.75, clip_on=True))
        ax.text(bar_x0, bar_y - bar_h, f'${w_lo:.0f}', fontsize=7.5, color=C['red'],
                ha='left', va='top', transform=ax.transAxes)
        ax.text(bar_x1, bar_y - bar_h, f'${w_hi:.0f}', fontsize=7.5, color=C['green'],
                ha='right', va='top', transform=ax.transAxes)
        ax.text((bar_x0 + bar_x1) / 2, bar_y - bar_h,
                f'52W  {pos52:.0f}%', fontsize=7.5, color=C['sub'],
                ha='center', va='top', transform=ax.transAxes)

        # ── CHIP GRID (0.42 → 1.0): 2 rows × 5 cols ─────────────────────────
        chips = [
            ('Mkt Cap',    _mc(mktcap),                                            C['blue']),
            ('P/E TTM',    f'{pe:.1f}×'  if pe  else 'N/A',                       C['yellow']),
            ('Fwd P/E',    f'{fpe:.1f}×' if fpe else 'N/A',                       C['yellow']),
            ('PEG',        f'{peg:.2f}'  if peg else 'N/A',                       C['purple']),
            ('EV/EBITDA',  f'{ev_eb:.1f}×' if (ev_eb and ev_eb > 0) else 'N/A',  C['purple']),
            ('Beta',       f'{beta:.2f}' if beta else 'N/A',                      C['orange']),
            ('Div Yield',  f'{div:.2f}%',                                          C['teal']),
            ('Rev Growth', f'{rev_g*100:+.1f}%' if rev_g else 'N/A',
             C['green'] if (rev_g or 0) > 0 else C['red']),
            ('Net Margin', f'{margin*100:.1f}%' if margin else 'N/A',
             C['green'] if (margin or 0) > 0.10 else C['sub']),
            (datetime.now().strftime('%Y-%m-%d %H:%M'),
             'Yahoo Finance', C['sub']),
        ]
        n_cols   = 5
        grid_x0  = 0.43
        grid_x1  = 0.99
        col_w    = (grid_x1 - grid_x0) / n_cols
        row_ys   = [0.72, 0.26]   # label y, value y for row 0; same offsets for row 1
        label_ys = [0.80, 0.34]
        val_ys   = [0.55, 0.09]

        for i, (label, val, col) in enumerate(chips):
            row   = i // n_cols
            col_i = i %  n_cols
            cx    = grid_x0 + (col_i + 0.5) * col_w
            if col_i > 0:
                ax.axvline(grid_x0 + col_i * col_w, color=C['border'], lw=0.4,
                           alpha=0.5, ymin=0.04, ymax=0.96)
            if row == 1 and col_i == 0:
                ax.axhline(0.445, color=C['border'], lw=0.5, alpha=0.6,
                           xmin=grid_x0, xmax=1.0)
            ax.text(cx, label_ys[row], label, ha='center', va='center',
                    fontsize=8, color=C['sub'], transform=ax.transAxes)
            ax.text(cx, val_ys[row], val, ha='center', va='center',
                    fontsize=11.5, color=col, fontweight='bold', transform=ax.transAxes)

    # -------------------------------------------------------------------------
    # 1-year price chart vs S&P 500
    # -------------------------------------------------------------------------

    def _draw_price_chart(self, ax):
        _style_ax(ax, f'{self.ticker} vs S&P 500  —  1-Year Relative Performance (Base = 100)')
        try:
            end   = datetime.now()
            start = end - timedelta(days=365)
            hist  = self.stock.history(start=start, end=end)
            spy   = yf.Ticker('SPY').history(start=start, end=end)

            if hist.empty or spy.empty:
                ax.text(0.5, 0.5, 'No price data available', ha='center', va='center',
                        color=C['sub'], fontsize=12)
                return

            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)
            if spy.index.tz is not None:
                spy.index = spy.index.tz_localize(None)

            stock_norm = hist['Close'] / hist['Close'].iloc[0] * 100
            spy_norm   = spy['Close']  / spy['Close'].iloc[0]  * 100

            ax.plot(stock_norm.index, stock_norm.values,
                    color=C['blue'], lw=2.2, label=self.ticker, zorder=3)
            ax.plot(spy_norm.index,   spy_norm.values,
                    color=C['sub'],  lw=1.5, label='S&P 500', linestyle='--', zorder=2)
            ax.axhline(100, color=C['border'], lw=0.8, linestyle=':', zorder=1)
            ax.fill_between(stock_norm.index, 100, stock_norm.values,
                            alpha=0.10, color=C['blue'])

            sr   = stock_norm.iloc[-1] - 100
            spr  = spy_norm.iloc[-1]   - 100
            alph = sr - spr
            ac   = C['green'] if alph >= 0 else C['red']
            s1   = '+' if sr   >= 0 else ''
            s2   = '+' if spr  >= 0 else ''
            sa   = '+' if alph >= 0 else ''
            txt  = (f'{self.ticker}: {s1}{sr:.1f}%\n'
                    f'S&P 500: {s2}{spr:.1f}%\n'
                    f'Alpha:   {sa}{alph:.1f}%')
            ax.text(0.02, 0.97, txt, transform=ax.transAxes,
                    fontsize=10, fontweight='bold', color=ac, va='top', ha='left',
                    bbox=dict(boxstyle='round,pad=0.45', facecolor=C['panel'],
                              edgecolor=ac, alpha=0.95))

            ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%b %Y'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right', fontsize=8)
            ax.set_ylabel('Normalized Return (%)', fontsize=9)
            ax.legend(loc='lower left', fontsize=9)

        except Exception as e:
            ax.text(0.5, 0.5, f'Chart error: {e}', ha='center', va='center',
                    color=C['sub'], fontsize=9)

    # -------------------------------------------------------------------------
    # Valuation + risk metrics panel
    # -------------------------------------------------------------------------

    def _draw_metrics_and_risk(self, ax):
        ax.set_facecolor(C['panel'])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        for sp in ax.spines.values():
            sp.set_edgecolor(C['border'])
            sp.set_linewidth(0.8)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

        def _row(y, label, val, val_col=C['white']):
            ax.text(0.04, y, label, va='center', ha='left', fontsize=9,
                    color=C['sub'], transform=ax.transAxes)
            ax.text(0.96, y, val, va='center', ha='right', fontsize=9,
                    color=val_col, fontweight='bold', transform=ax.transAxes)

        def _div(y, title, col):
            ax.axhline(y, color=C['border'], lw=0.8, xmin=0, xmax=1)
            ax.text(0.5, y + 0.025, f'── {title} ──', va='bottom', ha='center',
                    fontsize=9, fontweight='bold', color=col, transform=ax.transAxes)

        price   = float(self.info.get('currentPrice') or 0)
        mktcap  = self.market_cap or 0
        pe      = self.info.get('trailingPE') or 0
        fpe     = self.info.get('forwardPE')  or 0
        peg     = self.calculate_peg_ratio()
        ev_eb   = self.info.get('enterpriseToEbitda')
        rev_g   = self.info.get('revenueGrowth')
        margin  = self.info.get('profitMargins')
        div     = self.calculate_dividend_yield()
        eps_ttm = self.get_current_ttm_eps()
        eps_fwd = self.info.get('forwardEps')

        def _mc(v):
            if v >= 1e12: return f'${v/1e12:.2f}T'
            if v >= 1e9:  return f'${v/1e9:.2f}B'
            return 'N/A'

        _div(0.96, 'VALUATION', C['blue'])
        _row(0.90, 'Current Price',  f'${price:,.2f}')
        _row(0.83, 'Market Cap',     _mc(mktcap))
        _row(0.76, 'P/E Ratio TTM', f'{pe:.1f}×'  if pe  else 'N/A',
             C['yellow'])
        _row(0.69, 'Forward P/E',   f'{fpe:.1f}×' if fpe else 'N/A',
             C['yellow'])
        _row(0.62, 'PEG Ratio',     f'{peg:.2f}'  if peg else 'N/A',
             C['green'] if peg and peg < 1.5 else (C['red'] if peg and peg > 3 else C['white']))
        _row(0.55, 'EV / EBITDA',   f'{ev_eb:.1f}×' if (ev_eb and ev_eb > 0) else 'N/A',
             C['purple'])
        _row(0.48, 'EPS (TTM)',      f'${eps_ttm:.2f}' if eps_ttm else 'N/A', C['white'])
        _row(0.41, 'EPS (Fwd)',      f'${eps_fwd:.2f}' if eps_fwd else 'N/A', C['teal'])
        _row(0.34, 'Revenue Growth', f'{rev_g*100:+.1f}%' if rev_g else 'N/A',
             C['green'] if (rev_g or 0) > 0 else C['red'])
        _row(0.27, 'Net Margin',     f'{margin*100:.1f}%' if margin else 'N/A',
             C['green'] if (margin or 0) > 0.10 else C['sub'])
        _row(0.20, 'Dividend Yield', f'{div:.2f}%',
             C['teal'] if div > 1 else C['white'])

        # Risk section — occupies y in [0, 0.13]
        try:
            hist = self.stock.history(period='1y')
            if not hist.empty:
                ret_1y = (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100
                rets   = hist['Close'].pct_change().dropna()
                vol    = rets.std() * np.sqrt(252) * 100
                rf_d   = 0.045 / 252
                sharpe = ((rets - rf_d).mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0
                cumr   = (1 + rets).cumprod()
                max_dd = ((cumr - cumr.cummax()) / cumr.cummax()).min() * 100
                w52_hi = self.info.get('fiftyTwoWeekHigh', hist['Close'].max())
                w52_lo = self.info.get('fiftyTwoWeekLow',  hist['Close'].min())
                curr   = hist['Close'].iloc[-1]
                pos52  = ((curr - w52_lo) / (w52_hi - w52_lo) * 100) if w52_hi > w52_lo else 50
                beta   = self.info.get('beta')

                # Clear and redraw risk rows in [0.01 .. 0.11]
                risk_rows = [
                    ('1-Yr Return',     f'{ret_1y:+.1f}%',   C['green'] if ret_1y >= 0 else C['red']),
                    ('Ann. Volatility', f'{vol:.1f}%',        C['yellow']),
                    ('Sharpe Ratio',    f'{sharpe:.2f}',
                     C['green'] if sharpe >= 1 else (C['sub'] if sharpe >= 0 else C['red'])),
                    ('Max Drawdown',    f'{max_dd:.1f}%',     C['red'] if max_dd < -20 else C['white']),
                    ('52W High / Low',  f'${w52_hi:.2f} / ${w52_lo:.2f}', C['sub']),
                    ('52W Position',    f'{pos52:.0f}%',      C['blue']),
                    ('Beta',            f'{beta:.2f}' if beta else 'N/A', C['orange']),
                ]
                # Position section header at y=0.125
                ax.axhline(0.125, color=C['border'], lw=0.8)
                ax.text(0.5, 0.148, '── RISK & RANGE ──', va='bottom', ha='center',
                        fontsize=9, fontweight='bold', color=C['orange'], transform=ax.transAxes)

                n_risk  = len(risk_rows)
                y_start = 0.115
                step    = 0.115 / (n_risk + 0.5)
                for i, (lbl, val, col) in enumerate(risk_rows):
                    y = y_start - step * (i + 0.5)
                    ax.text(0.04, y, lbl, va='center', ha='left', fontsize=8.5,
                            color=C['sub'], transform=ax.transAxes)
                    ax.text(0.96, y, val, va='center', ha='right', fontsize=8.5,
                            color=col, fontweight='bold', transform=ax.transAxes)

                # Adjust valuation section to sit above 0.125
                # (already drawn above — this block just adds risk correctly)
        except Exception:
            ax.text(0.5, 0.06, 'Risk data unavailable', ha='center', va='center',
                    fontsize=8, color=C['sub'], transform=ax.transAxes)

    # -------------------------------------------------------------------------
    # Annual financials bar chart
    # -------------------------------------------------------------------------

    def _draw_annual_financials(self, ax):
        _style_ax(ax, 'Annual Revenue & Net Income + EPS')
        try:
            fin     = self.stock.financials
            rev_row = self._find_financial_row(fin, ['total revenue', 'revenue', 'sales'])
            inc_row = self._find_financial_row(fin, ['net income', 'netprofit', 'net profit'])

            if not rev_row or not inc_row:
                ax.text(0.5, 0.5, 'Annual financial data not found',
                        ha='center', va='center', color=C['sub'])
                return

            rev = pd.Series(fin.loc[rev_row].dropna().head(4)).sort_index() / 1e9
            inc = pd.Series(fin.loc[inc_row].dropna().head(4)).sort_index() / 1e9

            common = set(rev.index) & set(inc.index)
            if not common:
                ax.text(0.5, 0.5, 'No common dates', ha='center', color=C['sub'])
                return

            rev = rev[rev.index.isin(common)]
            inc = inc[inc.index.isin(common)]
            years = [d.year for d in rev.index]
            x = np.arange(len(years))
            w = 0.34

            b1 = ax.bar(x - w/2, rev.values, w, color=C['blue'],  alpha=0.85, label='Revenue ($B)')
            b2 = ax.bar(x + w/2, inc.values, w, color=C['green'], alpha=0.85, label='Net Income ($B)')

            ax.set_xticks(x)
            ax.set_xticklabels([str(y) for y in years], color=C['sub'], fontsize=9)
            ax.set_ylabel('$B', fontsize=9)

            # Value labels on bars
            for bar in list(b1) + list(b2):
                h = bar.get_height()
                if abs(h) > 0.01:
                    ax.text(bar.get_x() + bar.get_width() / 2, h,
                            f'{h:.0f}', ha='center',
                            va='bottom' if h >= 0 else 'top',
                            fontsize=7, color=C['white'])

            # EPS line on twin axis
            eps_vals = [self.get_annual_eps_for_year(y) for y in years]
            if any(e and e > 0 for e in eps_vals):
                ax2 = ax.twinx()
                ax2.set_facecolor('none')
                for sp in ax2.spines.values():
                    sp.set_edgecolor(C['border'])
                    sp.set_linewidth(0.5)
                ax2.plot(x, eps_vals, color=C['yellow'], marker='o', lw=2,
                         markersize=5, label='EPS ($)', zorder=4)
                for xi, ep in zip(x, eps_vals):
                    if ep:
                        ax2.text(xi, ep, f'${ep:.2f}', ha='center', va='bottom',
                                 fontsize=7, color=C['yellow'])
                ax2.set_ylabel('EPS ($)', color=C['yellow'], fontsize=9)
                ax2.tick_params(colors=C['yellow'], labelsize=8)
                ax2.grid(False)

            ax.legend(loc='upper left', fontsize=8)

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', ha='center', va='center',
                    color=C['sub'], fontsize=8)

    # -------------------------------------------------------------------------
    # Quarterly financials bar chart
    # -------------------------------------------------------------------------

    def _draw_quarterly_financials(self, ax):
        _style_ax(ax, 'Quarterly Revenue & Net Income')
        try:
            fin     = self.stock.quarterly_financials
            rev_row = self._find_financial_row(fin, ['total revenue', 'revenue', 'sales'])
            inc_row = self._find_financial_row(fin, ['net income', 'netprofit', 'net profit'])

            if not rev_row or not inc_row:
                ax.text(0.5, 0.5, 'Quarterly data not found',
                        ha='center', va='center', color=C['sub'])
                return

            rev = pd.Series(fin.loc[rev_row].dropna().head(4)).sort_index() / 1e6
            inc = pd.Series(fin.loc[inc_row].dropna().head(4)).sort_index() / 1e6

            common = set(rev.index) & set(inc.index)
            if not common:
                ax.text(0.5, 0.5, 'No common quarters', ha='center', color=C['sub'])
                return

            rev = rev[rev.index.isin(common)]
            inc = inc[inc.index.isin(common)]
            labels = [f"Q{(d.month-1)//3+1}\n{d.year}" for d in rev.index]
            x = np.arange(len(labels))
            w = 0.34

            margins = [(inc.iloc[i] / rev.iloc[i] * 100) if rev.iloc[i] != 0 else 0
                       for i in range(len(rev))]

            b1 = ax.bar(x - w/2, rev.values, w, color=C['blue'],  alpha=0.85, label='Revenue ($M)')
            b2 = ax.bar(x + w/2, inc.values, w, color=C['green'], alpha=0.85, label='Net Income ($M)')

            ax.set_xticks(x)
            ax.set_xticklabels(labels, color=C['sub'], fontsize=9)
            ax.set_ylabel('$M', fontsize=9)

            for bar in list(b1) + list(b2):
                h = bar.get_height()
                if abs(h) > 0.01:
                    ax.text(bar.get_x() + bar.get_width() / 2, h,
                            f'{h:.0f}', ha='center',
                            va='bottom' if h >= 0 else 'top',
                            fontsize=7, color=C['white'])

            # Net margin line
            ax2 = ax.twinx()
            ax2.set_facecolor('none')
            for sp in ax2.spines.values():
                sp.set_edgecolor(C['border'])
                sp.set_linewidth(0.5)
            ax2.plot(x, margins, color=C['orange'], marker='D', lw=1.8,
                     markersize=5, label='Net Margin %', zorder=4)
            for xi, m in zip(x, margins):
                ax2.text(xi, m, f'{m:.1f}%', ha='center', va='bottom',
                         fontsize=7, color=C['orange'])
            ax2.set_ylabel('Net Margin %', color=C['orange'], fontsize=9)
            ax2.tick_params(colors=C['orange'], labelsize=8)
            ax2.grid(False)

            ax.legend(loc='upper left', fontsize=8)

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', ha='center', va='center',
                    color=C['sub'], fontsize=8)

    # -------------------------------------------------------------------------
    # Earnings beat / miss chart
    # -------------------------------------------------------------------------

    def _draw_earnings_chart(self, ax):
        _style_ax(ax, 'EPS: Estimate vs Actual  (last 8 quarters)')
        if not self.earnings_data:
            ax.text(0.5, 0.5, 'Earnings data not available',
                    ha='center', va='center', color=C['sub'], fontsize=10)
            return
        try:
            items    = sorted(self.earnings_data.items())[-8:]
            quarters = [v['quarter']       for _, v in items]
            ests     = [v['eps_estimate']   for _, v in items]
            acts     = [v['eps_actual']     for _, v in items]
            surprises = [v['eps_surprise']  for _, v in items]

            x = np.arange(len(quarters))
            w = 0.35

            ax.bar(x - w/2, ests, w, color=C['sub'],  alpha=0.7, label='Estimate')

            act_colors = [C['green'] if s == 'Beat' else (C['red'] if s == 'Miss' else C['yellow'])
                          for s in surprises]
            for i, (xi, a, col) in enumerate(zip(x, acts, act_colors)):
                ax.bar(xi + w/2, a, w, color=col, alpha=0.85)

            # Labels on actual bars
            for xi, a, col in zip(x, acts, act_colors):
                va = 'bottom' if a >= 0 else 'top'
                ax.text(xi + w/2, a, f'${a:.2f}', ha='center', va=va,
                        fontsize=7.5, fontweight='bold', color=C['white'])

            ax.set_xticks(x)
            ax.set_xticklabels(quarters, rotation=30, ha='right', fontsize=8, color=C['sub'])
            ax.set_ylabel('EPS ($)', fontsize=9)
            ax.axhline(0, color=C['border'], lw=0.8)

            # Beat rate annotation
            beats = sum(1 for s in surprises if s == 'Beat')
            total = len(surprises)
            rate  = beats / total * 100 if total else 0
            beat_col = C['green'] if rate >= 70 else (C['red'] if rate < 50 else C['yellow'])
            ax.text(0.98, 0.97,
                    f'Beat rate: {rate:.0f}%  ({beats}/{total})',
                    transform=ax.transAxes, ha='right', va='top',
                    fontsize=9, fontweight='bold', color=beat_col,
                    bbox=dict(boxstyle='round,pad=0.35', facecolor=C['panel'],
                              edgecolor=beat_col, alpha=0.95))

            # Legend patch for Actual
            from matplotlib.patches import Patch
            legend_patches = [
                Patch(color=C['sub'],    label='Estimate'),
                Patch(color=C['green'],  label='Beat'),
                Patch(color=C['red'],    label='Miss'),
                Patch(color=C['yellow'], label='Meet'),
            ]
            ax.legend(handles=legend_patches, loc='lower left', fontsize=8)

        except Exception as e:
            ax.text(0.5, 0.5, f'Error: {e}', ha='center', va='center',
                    color=C['sub'], fontsize=8)

    # -------------------------------------------------------------------------
    # Peer comparison table
    # -------------------------------------------------------------------------

    def _draw_peer_table(self, ax):
        ax.set_facecolor(C['panel'])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        for sp in ax.spines.values():
            sp.set_edgecolor(C['border'])
            sp.set_linewidth(0.8)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.set_title('Peer Comparison', color=C['white'], fontsize=10, fontweight='bold', pad=6)

        peers_data  = self.get_peer_data_with_forward_pe()
        target_data = self.get_target_company_data()
        if target_data:
            peers_data.insert(0, target_data)

        if not peers_data:
            ax.text(0.5, 0.5, 'No peer data available', ha='center', va='center',
                    color=C['sub'], fontsize=11)
            return

        cols   = ['Ticker', 'Company', 'Price', 'Fwd P/E', 'P/E TTM', 'Div %', '52W Pos', 'Mkt Cap']
        # left edges and widths must sum to ≤ 1
        col_x  = [0.01, 0.09, 0.33, 0.43, 0.53, 0.63, 0.73, 0.82]
        col_w  = [0.08, 0.24, 0.10, 0.10, 0.10, 0.10, 0.09, 0.17]

        max_rows   = min(len(peers_data), 9)
        total_rows = max_rows + 1      # +1 header
        y_top      = 0.92
        row_h      = 0.90 / total_rows

        # Header
        hdr_y = y_top - row_h * 0.5
        for j, col in enumerate(cols):
            ax.text(col_x[j] + col_w[j] / 2, hdr_y, col,
                    ha='center', va='center', fontsize=8.5, color=C['blue'],
                    fontweight='bold', transform=ax.transAxes)
        ax.axhline(y_top - row_h, color=C['border'], lw=1.0)

        def _mc(v):
            if not v: return 'N/A'
            if v >= 1e12: return f'${v/1e12:.1f}T'
            if v >= 1e9:  return f'${v/1e9:.1f}B'
            if v >= 1e6:  return f'${v/1e6:.0f}M'
            return 'N/A'

        for i, p in enumerate(peers_data[:max_rows]):
            is_target  = p['ticker'] == self.ticker
            row_y_top  = y_top - row_h * (i + 1)
            row_y_bot  = row_y_top - row_h
            row_y_mid  = (row_y_top + row_y_bot) / 2

            # Row background
            bg = '#1C3A2A' if is_target else (C['bg'] if i % 2 == 0 else C['panel'])
            ax.add_patch(plt.Rectangle(
                (0, row_y_bot), 1, row_h,
                facecolor=bg, edgecolor='none',
                transform=ax.transAxes, zorder=0,
            ))

            fpe  = p.get('forward_pe')  or 0
            tpe  = p.get('trailing_pe') or 0
            div  = p.get('dividend_yield', 0) or 0
            pos  = p.get('price_position_pct', 50) or 50
            px   = p.get('current_price', 0) or 0
            name = p.get('name', '') or ''
            if len(name) > 26:
                name = name[:24] + '…'

            fpe_col = (C['green'] if fpe and fpe < 20
                       else (C['red'] if fpe and fpe > 40 else C['yellow']))
            txt_col = C['green'] if is_target else C['white']

            row_vals = [
                (p['ticker'],                txt_col if not is_target else C['green'],  True),
                (name,                       C['teal'] if is_target else C['sub'],      False),
                (f'${px:.2f}',               txt_col,                                   False),
                (f'{fpe:.1f}×' if fpe else 'N/A', fpe_col,                             True),
                (f'{tpe:.1f}×' if tpe else 'N/A', C['sub'],                            False),
                (f'{div:.2f}%',              C['teal'] if div > 2 else txt_col,         False),
                (f'{pos:.0f}%',              txt_col,                                   False),
                (_mc(p.get('market_cap')),   txt_col,                                   False),
            ]

            for j, (val, col, bold) in enumerate(row_vals):
                ax.text(col_x[j] + col_w[j] / 2, row_y_mid, val,
                        ha='center', va='center', fontsize=8.5,
                        color=col, fontweight='bold' if (bold or is_target) else 'normal',
                        transform=ax.transAxes)

            ax.axhline(row_y_bot, color=C['border'], lw=0.4, alpha=0.5)

        # Legend note
        ax.text(0.5, 0.01,
                f'★ Target highlighted in green  ·  Fwd P/E: green < 20×, yellow 20-40×, red > 40×',
                ha='center', va='bottom', fontsize=7.5, color=C['sub'],
                transform=ax.transAxes)


# =============================================================================
#  MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  EQUITY RESEARCH DASHBOARD")
    print("=" * 60)

    while True:
        print("\n" + "─" * 40)
        ticker = input("Enter ticker (e.g. AAPL) or 'quit': ").strip().upper()

        if ticker.lower() in ('quit', 'q', 'exit'):
            print("Goodbye!")
            break

        if not ticker:
            print("No ticker entered.")
            continue

        # Quick pre-flight check before the heavy data pull
        print(f"Validating ticker '{ticker}'...")
        _quick = yf.Ticker(ticker).info
        _price = _quick.get('currentPrice') or _quick.get('regularMarketPrice')
        if not _price or not _quick.get('quoteType'):
            print(f"❌  '{ticker}' is not a recognised ticker. "
                  f"Please check the symbol and try again.")
            continue

        print(f"Generating dashboard for {ticker}...")
        try:
            report = EquityResearchReport(ticker)
            path   = report.generate_image_report()
            if path:
                print(f"\n✅  Dashboard: {path}")
            else:
                print(f"\n❌  Failed to generate dashboard for {ticker}")
        except Exception as e:
            print(f"\n❌  Error: {e}")

        again = input("\nAnother ticker? (y/n): ").strip().lower()
        if again not in ('y', 'yes'):
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()
