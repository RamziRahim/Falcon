import datetime
import pandas as pd
from growwapi import GrowwAPI

# =====================================================================
# 🛠️ DIRECT ACCESS TOKEN (From your first screenshot modal)
# =====================================================================
# Paste the long "Access Token" string from the modal named "new" here.
# Note: This token will handle data queries cleanly until 6:00 AM tomorrow.
GROWW_ACCESS_TOKEN = "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NzEwMzg0MTAsImlhdCI6MTc4MjYzODQxMCwibmJmIjoxNzgyNjM4NDEwLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCI2NmQzMDk4Zi00ZDRlLTRiM2ItYTlhYS0yNGQxMjE1YTNiMDlcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiZTQ3ZDNmYTktYTZlMS00ZGY4LTllODItZTBhNWQ1ZmIzYjBiXCIsXCJkZXZpY2VJZFwiOlwiM2ExNjgyMzAtZjYyZS01NzhlLWIyODctNTZjYjI4NjhkZjZjXCIsXCJzZXNzaW9uSWRcIjpcIjQyYmI0MjNmLTVmMTItNGUwNS05MTRiLWMwMTY0MmM5MWI1MlwiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYk1aV1ZEb3c3a0ZjNnMvcDRESmFkaWRSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDA1OjIwMTpkMDAwOmIwZTM6NzRkNjpkNTRjOmZiNjE6MTRlZSwxNzIuNzAuMjE4LjEzNSwzNS4yNDEuMjMuMTIzXCIsXCJ0d29GYUV4cGlyeVRzXCI6MjU3MTAzODQxMDQ0NCxcInZlbmRvck5hbWVcIjpcImdyb3d3QXBpXCJ9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.uGLlP_6fE2UVdC8PJVdoVMijoj08LhMsZZ3BwMZOmqEchop-2Fw3QHw8GKEaru4bt08B8M7AkQTWxkNc6Zxkhw"

SYMBOL = "MARKSANS"
GROWW_SYMBOL = f"NSE-{SYMBOL}"  
OUTPUT_FILE = "marksans_groww_history.xlsx"

def fetch_historical_data():
    print("[*] Connecting to Groww data node using active Access Token...")
    
    try:
        # Initialize the API engine directly with your temporary session token
        groww = GrowwAPI(GROWW_ACCESS_TOKEN)
        print("[+] Session verified successfully.")
        
    except Exception as auth_err:
        print(f"[!] Initialization failed: {auth_err}")
        return

    # Calculate 180 days market limit window
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=180)
    
    start_time_str = start_date.strftime("%Y-%m-%d 09:15:00")
    end_time_str = end_date.strftime("%Y-%m-%d 15:30:00")
    
    print(f"[*] Querying {GROWW_SYMBOL} from {start_time_str} to {end_time_str}")
    
    try:
        response = groww.get_historical_candles(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            groww_symbol=GROWW_SYMBOL,
            start_time=start_time_str,
            end_time=end_time_str,
            candle_interval=groww.CANDLE_INTERVAL_DAY  
        )
        
        if response.get("status") != "SUCCESS":
            print(f"[!] Server Data Exception: {response.get('remark')}")
            return
            
        raw_candles = response.get("payload", {}).get("candles", [])
        if not raw_candles:
            print("[!] Warning: Zero active candles returned.")
            return
            
        print(f"[+] Downloaded {len(raw_candles)} trading days.")
        
        # Structure columns
        columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI']
        df = pd.DataFrame(raw_candles, columns=columns)
        
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df = df.drop(columns=['OI'])
        
        for price_col in ['Open', 'High', 'Low', 'Close']:
            df[price_col] = df[price_col].astype(float).round(2)
            
        df['Volume'] = df['Volume'].astype(int)
        df = df.sort_values(by='Date', ascending=True)

        with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Marksans Daily')
            
        print(f"[+] Operational Process Complete! Spreadsheet saved: {OUTPUT_FILE}")
        
    except Exception as data_err:
        print(f"[!] Processing Loop Failed: {data_err}")

if __name__ == "__main__":
    fetch_historical_data()