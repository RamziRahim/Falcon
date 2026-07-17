import datetime
import pandas as pd
from nselib import capital_market

SYMBOL = "WABAG"
OUTPUT_FILE = "wabag_nse_1y_daily.xlsx"

def fetch_one_year_daily_data():
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    
    str_start = start_date.strftime("%d-%m-%Y")
    str_end = end_date.strftime("%d-%m-%Y")
    
    print(f"[*] Querying NSE India for {SYMBOL} ({str_start} to {str_end})...")
    
    try:
        raw_data = capital_market.price_volume_and_deliverable_position_data(
            symbol=SYMBOL, from_date=str_start, to_date=str_end
        )
        
        if raw_data.empty:
            print("[!] Error: No exchange rows returned.")
            return
            
        print(f"[+] Downloaded {len(raw_data)} trading sessions from the exchange.")
        
        # --- 🛠️ DYNAMIC COLUMN MAPPING ENGINE ---
        # Normalize columns to lowercase and remove spaces/underscores for match confirmation
        actual_cols = list(raw_data.columns)
        norm_map = {c.lower().replace(" ", "").replace("_", ""): c for c in actual_cols}
        
        # Target matching rules
        target_keys = {
            'Date': ['date'],
            'Open': ['open', 'openprice'],
            'High': ['high', 'highprice'],
            'Low': ['low', 'lowprice'],
            'Close': ['close', 'closeprice', 'lastprice'],
            'Volume': ['volume', 'totaltradedquantity', 'ttltrdqty', 'tradedqty']
        }
        
        mapped_columns = {}
        for clean_name, fallback_keys in target_keys.items():
            for key in fallback_keys:
                if key in norm_map:
                    mapped_columns[clean_name] = norm_map[key]
                    break
        
        # Verify if all essential OHLCV components were accurately located
        missing = [k for k in target_keys.keys() if k not in mapped_columns]
        if missing:
            print(f"[!] Target alignment failed. Missing keys: {missing}")
            print(f"[*] Available headers in your package: {actual_cols}")
            return
            
        # Extract the columns using their true underlying structural names
        df = raw_data[[mapped_columns['Date'], 
                        mapped_columns['Open'], 
                        mapped_columns['High'], 
                        mapped_columns['Low'], 
                        mapped_columns['Close'], 
                        mapped_columns['Volume']]].copy()
                        
        # Standardize columns for your target spreadsheet output layout
        df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        # --- 📊 Cleaning and Typing Format Pipelines ---
        # Parse text string timestamps into true date types
        try:
            df['Date'] = pd.to_datetime(df['Date'], format='mixed').dt.date
        except Exception:
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%b-%Y').dt.date
            
        df = df.sort_values(by='Date', ascending=True).reset_index(drop=True)
        
        # Format metrics explicitly to clean floating numbers
        for price_col in ['Open', 'High', 'Low', 'Close']:
            # Strip string commas if present in raw NSE numbers
            df[price_col] = df[price_col].astype(str).str.replace(',', '')
            df[price_col] = pd.to_numeric(df[price_col], errors='coerce').round(2)
            
        df['Volume'] = df['Volume'].astype(str).str.replace(',', '')
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').astype(int)
        
        # Save straight to disk
        print(f"[*] Writing clean tracking arrays to: {OUTPUT_FILE}...")
        df.to_excel(OUTPUT_FILE, index=False)
        print(f"[+] Complete! Excel generated successfully: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"[!] Pipeline processing failed: {e}")

if __name__ == "__main__":
    fetch_one_year_daily_data()