import datetime
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from nselib import capital_market
from market_data.providers.base_provider import BaseProvider
from market_data.exceptions import DownloadError, ProviderError

# Setup logger matching Falcon style
logger = logging.getLogger("Falcon.MarketData.NSEProvider")

class NSEProvider(BaseProvider):
    """
    Production-grade Historical Data Provider for NSE India using nselib.
    Implements the same interface as YahooProvider and satisfies BaseProvider.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initializes the NSE Provider.
        
        Args:
            config (Optional[Dict[str, Any]]): Provider configuration dictionary.
        """
        # Fixed: Invoke parent class initialization without forwarding config arguments
        super().__init__()
        self.config = config or {}
        self._name = "NSE"

    # region Abstract Properties Implementation

    @property
    def name(self) -> str:
        """
        Returns the unique identifier string for this provider.
        """
        return self._name

    @property
    def capabilities(self) -> List[str]:
        """
        Returns the list of supported operational capabilities for this provider.
        """
        return ["history"]

    # endregion

    # region Core Interface Methods

    def get_history(
        self, 
        symbol: str, 
        start_date: datetime.date, 
        end_date: datetime.date
    ) -> pd.DataFrame:
        """
        Fetches historical daily OHLCV and delivery data from NSE India via nselib.
        
        Args:
            symbol (str): Ticker symbol with .NS suffix (e.g., 'MARKSANS.NS').
            start_date (datetime.date): Requested window start boundary.
            end_date (datetime.date): Requested window end boundary.
            
        Returns:
            pd.DataFrame: Structured OHLCV DataFrame matching Falcon standards.
            
        Raises:
            DownloadError: When data cannot be downloaded or lookbacks fail.
            ProviderError: When structural execution errors or boundary conditions fail.
        """
        if not symbol:
            raise ProviderError("Symbol parameter cannot be empty or None.")

        # Clean symbol to strip exchange suffixes
        clean_symbol = symbol.upper()
        if clean_symbol.endswith(".NS"):
            clean_symbol = clean_symbol[:-3]

        # Handle nselib small-window bug by padding the query range
        requested_days = (end_date - start_date).days
        actual_start = start_date
        
        if requested_days < 30:
            actual_start = end_date - datetime.timedelta(days=30)
            logger.info(
                f"[{self.name}] Target lookback window for {symbol} is small ({requested_days} days). "
                f"Expanding request boundary to 30 days. Query range: {actual_start} to {end_date}"
            )

        # Initialize tracking state
        df_raw = pd.DataFrame()
        attempts = [
            {"start": actual_start, "end": end_date, "label": "Initial Adjusted 30-Day Window"},
            {"start": end_date - datetime.timedelta(days=365), "end": end_date, "label": "Secondary 365-Day Extended Lookback"}
        ]

        for i, attempt in enumerate(attempts):
            str_start = attempt["start"].strftime("%d-%m-%Y")
            str_end = attempt["end"].strftime("%d-%m-%Y")
            
            logger.info(
                f"[{self.name}] Downloading data for {clean_symbol} via nselib. "
                f"Attempt {i+1}: {attempt['label']} ({str_start} to {str_end})"
            )
            
            try:
                df_raw = capital_market.price_volume_and_deliverable_position_data(
                    symbol=clean_symbol,
                    from_date=str_start,
                    to_date=str_end
                )
            except Exception as e:
                logger.error(f"[{self.name}] Underlying connection error during fetch for {clean_symbol}: {str(e)}")
                df_raw = pd.DataFrame()

            if df_raw is not None and not df_raw.empty:
                logger.info(f"[{self.name}] Successfully fetched {len(df_raw)} raw rows for {clean_symbol} on attempt {i+1}.")
                break
            else:
                logger.warning(f"[{self.name}] Attempt {i+1} returned empty dataset for {clean_symbol}.")

        if df_raw is None or df_raw.empty:
            msg = f"Failed to retrieve data for {symbol} after secondary 365-day macro lookup strategy."
            logger.error(f"[{self.name}] {msg}")
            raise DownloadError(msg)

        # Process and structure raw payload
        try:
            # 1. Clean UTF-8 BOM characters from column index if present
            df_raw.columns = [c.encode("utf-8").decode("utf-8-sig").strip() for c in df_raw.columns]

            # 2. Dynamic Column Mapping Engine
            actual_cols = list(df_raw.columns)
            norm_map = {c.lower().replace(" ", "").replace("_", ""): c for c in actual_cols}

            target_keys = {
                "Date": ["date"],
                "Open": ["open", "openprice"],
                "High": ["high", "highprice"],
                "Low": ["low", "lowprice"],
                "Close": ["close", "closeprice", "lastprice"],
                "Volume": ["volume", "totaltradedquantity", "ttltrdqty", "tradedqty"],
                # Optional -- degrade gracefully if absent rather than failing.
                # Not wired into any decision logic yet; just made available
                # on the dataframe for whatever consumes it later.
                "Deliverable_Qty": ["deliverableqty"],
                "Delivery_Pct": ["%dlyqttotradedqty", "dlyqttotradedqty"],
            }

            mapped_columns = {}
            for clean_name, fallback_keys in target_keys.items():
                for key in fallback_keys:
                    if key in norm_map:
                        mapped_columns[clean_name] = norm_map[key]
                        break

            # Only Date/OHLCV are required -- a future payload shape change to
            # the delivery columns specifically can't break basic ingestion.
            required_keys = ["Date", "Open", "High", "Low", "Close", "Volume"]
            missing_keys = [k for k in required_keys if k not in mapped_columns]
            if missing_keys:
                raise ProviderError(f"Required structural columns missing from payload index: {missing_keys}")

            # 3. Build output with whatever was successfully mapped -- core
            # columns guaranteed, delivery columns included only if present.
            available_cols = [c for c in target_keys.keys() if c in mapped_columns]
            df = df_raw[[mapped_columns[c] for c in available_cols]].copy()
            df.columns = available_cols

            # 4. Data Cleaning Pipeline
            # Format text strings to numeric objects, removing thousand separators
            for col in ["Open", "High", "Low", "Close"]:
                df[col] = df[col].astype(str).str.replace(",", "")
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

            df["Volume"] = df["Volume"].astype(str).str.replace(",", "")
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").astype("int64")

            if "Deliverable_Qty" in df.columns:
                df["Deliverable_Qty"] = df["Deliverable_Qty"].astype(str).str.replace(",", "")
                df["Deliverable_Qty"] = pd.to_numeric(df["Deliverable_Qty"], errors="coerce")

            if "Delivery_Pct" in df.columns:
                df["Delivery_Pct"] = df["Delivery_Pct"].astype(str).str.replace(",", "")
                df["Delivery_Pct"] = pd.to_numeric(df["Delivery_Pct"], errors="coerce")

            # Parse strings into true timezone-naive pandas Timestamps
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            
            # Drop entries that failed schema parsers or dates that are invalid
            df = df.dropna(subset=["Date"])
            
            # Sort chronologically, deduplicate, and flush structural indexes
            df = df.sort_values(by="Date", ascending=True)
            df = df.drop_duplicates(subset=["Date"], keep="last")
            df = df.reset_index(drop=True)

            logger.info(f"[{self.name}] Data formatting engine pipeline finished cleanly. Rows returned: {len(df)}")
            return df

        except ProviderError:
            raise
        except Exception as e:
            msg = f"Fatal data pipeline processing corruption for symbol {symbol}: {str(e)}"
            logger.error(f"[{self.name}] {msg}")
            raise ProviderError(msg)

    # endregion

    # region Unsupported Abstract Methods Placeholder Implementations

    def get_intraday(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Intraday data functionality is not implemented for the NSE Provider environment.")

    def get_dividends(self, symbol: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Dividends functionality is not implemented for the NSE Provider environment.")

    def get_splits(self, symbol: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Splits functionality is not implemented for the NSE Provider environment.")

    def get_corporate_actions(self, symbol: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Corporate actions functionality is not implemented for the NSE Provider environment.")

    def get_actions(self, symbol: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Actions functionality is not implemented for the NSE Provider environment.")

    def get_financials(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Financials data functionality is not implemented for the NSE Provider environment.")

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Balance sheet data functionality is not implemented for the NSE Provider environment.")

    def get_cashflow(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Cashflow data functionality is not implemented for the NSE Provider environment.")

    def get_earnings(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Earnings data functionality is not implemented for the NSE Provider environment.")

    def get_company_info(self, symbol: str) -> Dict[str, Any]:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Company information data functionality is not implemented for the NSE Provider environment.")

    def get_news(self, symbol: str) -> List[Dict[str, Any]]:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("News feed functionality is not implemented for the NSE Provider environment.")

    def get_recommendations(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Recommendations functionality is not implemented for the NSE Provider environment.")

    def get_major_holders(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Major holders data functionality is not implemented for the NSE Provider environment.")

    def get_institutional_holders(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Institutional holders data functionality is not implemented for the NSE Provider environment.")

    def get_mutualfund_holders(self, symbol: str) -> pd.DataFrame:
        """Not implemented for the NSE data provider layer."""
        raise NotImplementedError("Mutual fund holders data functionality is not implemented for the NSE Provider environment.")

    # endregion