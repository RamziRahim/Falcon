"""
Run #4 fill-realism check (2026-10-20). Run from project root:
    python tests/run4_fill_realism_check.py

Run #4 recorded entry_price = the pattern's pivot level, but the signal is only
known at the signal-day close, and in 46 of the 59 taken trades the whole
signal-day range was ABOVE the pivot (a price that never traded that day).
Targets are set from the pivot, so 18 of 59 trades had a target already below
the signal-day close and booked a "TARGET_HIT" the next day for free.

This re-prices every EXECUTE signal at the next-day open (keeping the recorded
stop/target price levels; trades whose target was already passed are skipped),
optionally with a fresh-breakout filter, and re-runs the same portfolio
simulator. See docs/known_data_issues.md item 10.
"""
import sys, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,'.')
import pandas as pd, numpy as np
from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import simulate_portfolio, policy_hard_cap
raw=pd.read_csv('data/backtest_results_run4_calibrated_model.csv',low_memory=False)
for c in ['entry_date','exit_date']: raw[c]=pd.to_datetime(raw[c],format='mixed')
cache={}
def hist(t):
    if t not in cache:
        d=pd.read_parquet(f'data/technical/{t}.parquet',columns=['Date','Open','High','Low','Close']); d['Date']=pd.to_datetime(d.Date)
        cache[t]=d.sort_values('Date').reset_index(drop=True)
    return cache[t]
COST=0.3; MAXD=40
def honest(r, fresh_max=None):
    h=hist(r.ticker); idx=h.index[h.Date==r.entry_date]
    if len(idx)==0: return None
    i=idx[0]; sig_close=h.Close[i]
    if i+1>=len(h): return None
    pivot=r.entry_price; stop=pivot*(1-r.stop_pct/100); target=pivot*(1+r.target_pct/100)
    if fresh_max is not None and sig_close>pivot*(1+fresh_max/100): return 'SKIP_STALE'
    o=h.Open[i+1]
    if o>=target: return 'SKIP_PAST_TARGET'
    if o<=stop: return 'SKIP_BELOW_STOP'
    win=h.iloc[i+1:i+1+MAXD]
    for k,(_,b) in enumerate(win.iterrows(),start=1):
        if b.Low<=stop: ex,why=min(stop,b.Open),'STOP_HIT'; break     # gap-down fills at the open, not the stop
        if b.High>=target: ex,why=max(target,b.Open) if k>1 else target,'TARGET_HIT'; break
    else: ex,why,k=win.Close.iloc[-1],'TIME_EXIT',len(win)
    return dict(entry_price=o,exit_price=ex,exit_reason=why,days_held=k,return_pct=(ex/o-1)*100,
                stop_pct=(o-stop)/o*100,target_pct=(target-o)/o*100,exit_date=win.Date.iloc[k-1])
def run(label,fresh_max=None):
    R=raw.copy(); skips={}
    for j,r in R[R.category=='EXECUTE'].iterrows():
        x=honest(r,fresh_max)
        if x is None or isinstance(x,str):
            skips[x or 'NO_DATA']=skips.get(x or 'NO_DATA',0)+1; R.loc[j,'category']='AVOID'; continue
        for k,v in x.items(): R.loc[j,k]=v
    ep=build_episodes(R)
    founder=R[['ticker','entry_date','caps_applied']].rename(columns={'entry_date':'episode_start_date'})
    ep=ep.merge(founder,on=['ticker','episode_start_date'],how='left')
    res=simulate_portfolio(ep,policy_hard_cap,n_slots=5,base_risk_pct=1.0,starting_equity=100.0)
    tk_ep=ep[ep.category=='EXECUTE']
    print(f'{label:44s} return {res["final_equity"]-100:+6.1f}%  maxDD(exit-based) {res["max_drawdown_pct"]:5.1f}%  taken {res["n_taken"]:3d}  '
          f'EXECUTE episodes {len(tk_ep):3d}  mean net/episode {tk_ep.net_return_pct.mean():+.2f}%  win {(tk_ep.net_return_pct>0).mean()*100:.0f}%  skipped {skips}')
print('NIFTY buy-and-hold same window: -1.1%\n')
r=raw[raw.category=='EXECUTE']; ep0=build_episodes(raw)
print(f'{"As recorded (pivot fill)":44s} return  +82.7%  (reference)')
run('Honest fill: next-day open, all EXECUTE')
for fm in (1,2,3,5):
    run(f'Honest fill + fresh breakout only (close<=pivot+{fm}%)',fm)
