import re, json, sys
OUT = sys.argv[1]
def parse(path):
    blocks, cur, lines = {}, None, open(path, encoding="utf-8").read().splitlines()
    for k, ln in enumerate(lines):
        m = re.match(r"^(\S.*?)\s+(W1|W2|H2018|Y2018) \d{4}-\d{2}-\d{2} -> ", ln)
        m2 = re.match(r"^(W1|W2) \d{4}-\d{2}-\d{2} -> \d{4}-\d{2}-\d{2}\s+(\S.*)$", ln)
        if m2 and k > 0 and lines[k-1].startswith("===="):
            cur = (m2.group(2).strip(), m2.group(1))
            blocks[cur] = {"passes": 0}
            continue
        if m and k > 0 and lines[k-1].startswith("===="):
            cur = (m.group(1).strip(), "2018" if m.group(2) in ("H2018", "Y2018") else m.group(2))
            blocks[cur] = {"passes": 0}
            continue
        if ln and not ln.startswith(" ") and not ln.startswith("===="):
            cur = None                                   # any unindented line ends the current block
        if cur is None: continue
        s = ln.strip()
        def num(v): return float(v.replace("%", "").replace("+", ""))
        for key, name in (("trades (closed)", "trades"), ("positions (closed)", "trades"), ("win rate after costs", "win"), ("mean net per trade", "net"),
                          ("n_closed_positions", "trades"), ("n_trades", "trades"), ("win_rate_pct (closed)", "win"),
                          ("win_rate_pct", "win"), ("mean_net_per_trade_pct", "net"),
                          ("cagr_pct", "cagr"), ("max_drawdown_pct", "dd"), ("total_return_pct", "total")):
            if key in ("n_closed_positions", "n_trades") and "trades" in blocks[cur]:
                continue                                 # keep the closed-trade count when the file has one
            if s.startswith(key + " ") and not s.startswith("nifty"):
                try: blocks[cur][name] = num(s[len(key):].strip().split()[0])
                except ValueError: pass
        if s.startswith("[PASS]"): blocks[cur]["passes"] += 1
    return blocks
D = "data/"
specs = [
 # id, name, family, entry, stop, target, filter, hold, file, header
 ("s3_orig","#3 original","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:3","None","4 weeks","swing_risk_1to3_result.txt","S entries + swing-low stop, 1:3"),
 ("s3_orig_r2","#3 original, 1:2","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:2","None","4 weeks","swing_risk_1to2_result.txt","S entries + swing-low stop, 1:2"),
 ("s3_nifty","#3 + Nifty filter","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:3","Nifty > 50-day avg","4 weeks","s_plus_result.txt","only market filter"),
 ("s3_splus","#3 + all three fixes","#3 Momentum breakout","Buy-stop at 20-day high","Swing low, max 3 ATR","1:3","Nifty > 50-day avg","8 weeks","s_plus_result.txt","S+ (all three)"),
 ("s3_hold40","#3 + 8-week hold only","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:3","None","8 weeks","s_plus_result.txt","only 40-session hold"),
 ("s3_atrcap","#3 + capped stop only","#3 Momentum breakout","Buy-stop at 20-day high","Swing low, max 3 ATR","1:3","None","4 weeks","s_plus_result.txt","only ATR-capped stop"),
 ("s3_sectbkt_r3","#3 + sector/size filter, 1:3","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:3","Sector, else mid/small index","4 weeks","s_sector_result.txt","R3 {'mode': 'swing', 'r_multiple': 3}"),
 ("s3_sectbkt_r2","#3 + sector/size filter, 1:2","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:2","Sector, else mid/small index","4 weeks","s_sector_result.txt","R2 {'mode': 'swing', 'r_multiple': 2}"),
 ("s3_sectbkt_f5","#3 + sector/size filter, ±5%","#3 Momentum breakout","Buy-stop at 20-day high","Fixed −5%","Fixed +5%","Sector, else mid/small index","4 weeks","s_sector_result.txt","F5 {'mode': 'fixed'}"),
 ("s3_sectbkt_r3h","#3 + sector/size filter, 1:3 + half at 5%","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:3, half at +5%","Sector, else mid/small index","4 weeks","s_sector_result.txt","R3H {'mode': 'swing', 'r_multiple': 3, 'half_at': 0.05}"),
 ("s3_sectbkt_r2h","#3 + sector/size filter, 1:2 + half at 5%","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:2, half at +5%","Sector, else mid/small index","4 weeks","s_sector_result.txt","R2H {'mode': 'swing', 'r_multiple': 2, 'half_at': 0.05}"),
 ("s3_sectnifty_r3","#3 + sector-else-Nifty filter, 1:3","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:3","Sector, else Nifty","4 weeks","s_sector_nifty_result.txt","R3 {'mode': 'swing', 'r_multiple': 3}"),
 ("s3_sectnifty_r2","#3 + sector-else-Nifty filter, 1:2","#3 Momentum breakout","Buy-stop at 20-day high","Swing low","1:2","Sector, else Nifty","4 weeks","s_sector_nifty_result.txt","R2 {'mode': 'swing', 'r_multiple': 2}"),
 ("s3_sectnifty_r3be","#3 + sector-else-Nifty, 1:3 + stop to cost","#3 Momentum breakout","Buy-stop at 20-day high","Swing low → cost at +5%","1:3","Sector, else Nifty","4 weeks","s_sector_nifty_result.txt","R3BE {'mode': 'swing', 'r_multiple': 3, 'be_at': 0.05}"),
 ("s3_sectnifty_r2be","#3 + sector-else-Nifty, 1:2 + stop to cost","#3 Momentum breakout","Buy-stop at 20-day high","Swing low → cost at +5%","1:2","Sector, else Nifty","4 weeks","s_sector_nifty_result.txt","R2BE {'mode': 'swing', 'r_multiple': 2, 'be_at': 0.05}"),
 ("s3_retest_rl3","#3 retest entry, 1:3","#3 Momentum breakout","Limit at breakout level (retest)","Swing low","1:3","Nifty > 50-day avg","4 weeks","s_retest_result.txt","RL3 {'mode': 'limit', 'r_multiple': 3}"),
 ("s3_retest_rl2","#3 retest entry, 1:2","#3 Momentum breakout","Limit at breakout level (retest)","Swing low","1:2","Nifty > 50-day avg","4 weeks","s_retest_result.txt","RL2 {'mode': 'limit', 'r_multiple': 2}"),
 ("s3_retest_rr3","#3 retest + reclaim, 1:3","#3 Momentum breakout","Retest, then close back above","Below retest low","1:3","Nifty > 50-day avg","4 weeks","s_retest_result.txt","RR3 {'mode': 'reclaim', 'r_multiple': 3}"),
 ("s3_retest_rr2","#3 retest + reclaim, 1:2","#3 Momentum breakout","Retest, then close back above","Below retest low","1:2","Nifty > 50-day avg","4 weeks","s_retest_result.txt","RR2 {'mode': 'reclaim', 'r_multiple': 2}"),
 ("s3_f515","#3 + Nifty filter, −5% / +15%","#3 Momentum breakout","Buy-stop at 20-day high","Fixed −5%","Fixed +15%","Nifty > 50-day avg","4 weeks","fixed_5_15_result.txt","S3-F515"),
 ("fm_r3","Falcon Momentum (original)","Falcon Momentum","Monday open after weekly rank","Swing low, max 3 ATR","1:3","Sector check + Nifty > 200-day avg","8 weeks","fm_variants_result.txt","FM R3 {'r_mult': 3.0}"),
 ("fm_r2","Falcon Momentum, 1:2","Falcon Momentum","Monday open after weekly rank","Swing low, max 3 ATR","1:2","Sector check + Nifty > 200-day avg","8 weeks","fm_variants_result.txt","FM R2 {'r_mult': 2.0}"),
 ("fm_r3be","Falcon Momentum, 1:3 + stop to cost","Falcon Momentum","Monday open after weekly rank","Swing low → cost at +5%","1:3","Sector check + Nifty > 200-day avg","8 weeks","fm_variants_result.txt","FM R3BE {'r_mult': 3.0, 'be_at': 0.05}"),
 ("fm_r2be","Falcon Momentum, 1:2 + stop to cost","Falcon Momentum","Monday open after weekly rank","Swing low → cost at +5%","1:2","Sector check + Nifty > 200-day avg","8 weeks","fm_variants_result.txt","FM R2BE {'r_mult': 2.0, 'be_at': 0.05}"),
 ("fm_t20","Falcon Momentum, 4-week hold","Falcon Momentum","Monday open after weekly rank","Swing low, max 3 ATR","1:3","Sector check + Nifty > 200-day avg","4 weeks","falcon_momentum_t20_result.txt","FM, time stop 20"),
 ("fm_review","Falcon Momentum + 4-week review","Falcon Momentum","Monday open after weekly rank","Swing low, max 3 ATR","1:3","Sector check + Nifty > 200-day avg","8 weeks, review at 4","fm_review_result.txt","FM, time stop 40"),
 ("fm_e_breakout","Falcon Momentum, range-breakout entry","Falcon Momentum","Range breakout (IA's definition)","Below range low","1:3","Sector check + Nifty > 200-day avg","8 weeks","fm_entries_breakout_result.txt","FM + breakout entry"),
 ("fm_e_sweep","Falcon Momentum, liquidity-sweep entry","Falcon Momentum","Liquidity sweep","Below sweep low","1:3","Sector check + Nifty > 200-day avg","8 weeks","fm_entries_sweep_result.txt","FM + sweep entry"),
 ("fm_e_fvg","Falcon Momentum, fair-value-gap entry","Falcon Momentum","Fair value gap retest","Below gap","1:3","Sector check + Nifty > 200-day avg","8 weeks","fm_entries_fvg_result.txt","FM + fvg entry"),
 ("fm_f510","Falcon Momentum, −5% / +10%","Falcon Momentum","Monday open after weekly rank","Fixed −5%","Fixed +10%","Sector check + Nifty > 200-day avg","8 weeks","fm_variants_F510_result.txt","FM F510 {'fixed_stop': 0.05, 'fixed_tgt': 0.1}"),
 ("fm_f515","Falcon Momentum, −5% / +15%","Falcon Momentum","Monday open after weekly rank","Fixed −5%","Fixed +15%","Sector check + Nifty > 200-day avg","8 weeks","fixed_5_15_result.txt","FM-F515"),
 ("fm_h3","Falcon Momentum, 20-day-high entry, 1:3","Falcon Momentum","Buy-stop at 20-day high (weekly list)","Swing low, max 3 ATR","1:3","Sector check + Nifty > 200-day avg","8 weeks","fm_high20_result.txt","H3 {'r_mult': 3.0}"),
 ("fm_h2","Falcon Momentum, 20-day-high entry, 1:2","Falcon Momentum","Buy-stop at 20-day high (weekly list)","Swing low, max 3 ATR","1:2","Sector check + Nifty > 200-day avg","8 weeks","fm_high20_result.txt","H2 {'r_mult': 2.0}"),
 ("fm_h5","Falcon Momentum, 20-day-high entry, ±5%","Falcon Momentum","Buy-stop at 20-day high (weekly list)","Fixed −5%","Fixed +5%","Sector check + Nifty > 200-day avg","8 weeks","fm_high20_result.txt","H5 {'fixed_stop': 0.05, 'fixed_tgt': 0.05}"),
 ("fm_h3be","Falcon Momentum, 20-day-high entry, 1:3 + stop to cost","Falcon Momentum","Buy-stop at 20-day high (weekly list)","Swing low → cost at +5%","1:3","Sector check + Nifty > 200-day avg","8 weeks","fm_high20_result.txt","H3BE {'r_mult': 3.0, 'be_at': 0.05}"),
 ("fm_h2be","Falcon Momentum, 20-day-high entry, 1:2 + stop to cost","Falcon Momentum","Buy-stop at 20-day high (weekly list)","Swing low → cost at +5%","1:2","Sector check + Nifty > 200-day avg","8 weeks","fm_high20_result.txt","H2BE {'r_mult': 2.0, 'be_at': 0.05}"),
 ("s3_q3","#3 quality breakout (base, tight range, volume, close), 1:3","#3 Momentum breakout","Close above 20-day-high base on 1.5× volume, next open","Swing low","1:3","Nifty > 50-day avg","4 weeks","s_quality_result.txt","Q3"),
 ("s3_q2","#3 quality breakout (base, tight range, volume, close), 1:2","#3 Momentum breakout","Close above 20-day-high base on 1.5× volume, next open","Swing low","1:2","Nifty > 50-day avg","4 weeks","s_quality_result.txt","Q2"),
 ("s3_rv3","#3 range + volume breakout, 1:3","#3 Momentum breakout","High above 20-day high, ≤10% range, 1.5× volume; next open","Swing low","1:3","Nifty > 50-day avg","4 weeks","range_volume_result.txt","S3_R3"),
 ("s3_rv2","#3 range + volume breakout, 1:2","#3 Momentum breakout","High above 20-day high, ≤10% range, 1.5× volume; next open","Swing low","1:2","Nifty > 50-day avg","4 weeks","range_volume_result.txt","S3_R2"),
 ("fm_rv3","Falcon Momentum, range + volume entry, 1:3","Falcon Momentum","Watch list; high above 20-day high, ≤10% range, 1.5× volume; next open","Swing low, max 3 ATR","1:3","Sector check + Nifty > 200-day avg","8 weeks","range_volume_result.txt","FM_R3"),
 ("fm_rv2","Falcon Momentum, range + volume entry, 1:2","Falcon Momentum","Watch list; high above 20-day high, ≤10% range, 1.5× volume; next open","Swing low, max 3 ATR","1:2","Sector check + Nifty > 200-day avg","8 weeks","range_volume_result.txt","FM_R2"),
 ('s3_ref2','#3 + Nifty filter, 1:2','#3 Momentum breakout','Buy-stop at 20-day high','Swing low','1:2','Nifty > 50-day avg','4 weeks',"volume_exit_result.txt",'S3_REF2'),
 ('s3_vx3','#3 + volume exit at close, 1:3','#3 Momentum breakout','Buy-stop at 20-day high; sell at close if volume < 1.5×','Swing low','1:3','Nifty > 50-day avg','4 weeks',"volume_exit_result.txt",'S3_VX3'),
 ('fm_vx3','Falcon Momentum 20-day-high + volume exit, 1:3','Falcon Momentum','Watch list; buy-stop at 20-day high; sell at close if volume < 1.5×','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks',"volume_exit_result.txt",'FM_VX3'),
 ('s3_vx2','#3 + volume exit at close, 1:2','#3 Momentum breakout','Buy-stop at 20-day high; sell at close if volume < 1.5×','Swing low','1:2','Nifty > 50-day avg','4 weeks',"volume_exit_result.txt",'S3_VX2'),
 ('fm_vx2','Falcon Momentum 20-day-high + volume exit, 1:2','Falcon Momentum','Watch list; buy-stop at 20-day high; sell at close if volume < 1.5×','Swing low, max 3 ATR','1:2','Sector check + Nifty > 200-day avg','8 weeks',"volume_exit_result.txt",'FM_VX2'),
 ('s3_rx3','#3 + volume exit at close + 10% range, 1:3','#3 Momentum breakout','Buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×','Swing low','1:3','Nifty > 50-day avg','4 weeks',"volume_exit_result.txt",'S3_RX3'),
 ('fm_rx3','Falcon Momentum 20-day-high + volume exit + 10% range, 1:3','Falcon Momentum','Watch list; buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks',"volume_exit_result.txt",'FM_RX3'),
 ('s3_rx2','#3 + volume exit at close + 10% range, 1:2','#3 Momentum breakout','Buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×','Swing low','1:2','Nifty > 50-day avg','4 weeks',"volume_exit_result.txt",'S3_RX2'),
 ('fm_rx2','Falcon Momentum 20-day-high + volume exit + 10% range, 1:2','Falcon Momentum','Watch list; buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×','Swing low, max 3 ATR','1:2','Sector check + Nifty > 200-day avg','8 weeks',"volume_exit_result.txt",'FM_RX2'),
 ('cs3_vx3','#3 + volume exit + 20-day cool-down, 1:3','#3 Momentum breakout','Buy-stop at 20-day high; sell at close if volume < 1.5×; no re-buy for 20 days','Swing low','1:3','Nifty > 50-day avg','4 weeks',"volume_cooldown_result.txt",'CS3_VX3'),
 ('cfm_vx3','Falcon Momentum 20-day-high + volume exit + cool-down, 1:3','Falcon Momentum','Watch list; buy-stop at 20-day high; sell at close if volume < 1.5×; no re-buy for 20 days','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks',"volume_cooldown_result.txt",'CFM_VX3'),
 ('cs3_vx2','#3 + volume exit + 20-day cool-down, 1:2','#3 Momentum breakout','Buy-stop at 20-day high; sell at close if volume < 1.5×; no re-buy for 20 days','Swing low','1:2','Nifty > 50-day avg','4 weeks',"volume_cooldown_result.txt",'CS3_VX2'),
 ('cfm_vx2','Falcon Momentum 20-day-high + volume exit + cool-down, 1:2','Falcon Momentum','Watch list; buy-stop at 20-day high; sell at close if volume < 1.5×; no re-buy for 20 days','Swing low, max 3 ATR','1:2','Sector check + Nifty > 200-day avg','8 weeks',"volume_cooldown_result.txt",'CFM_VX2'),
 ('cs3_rx3','#3 + volume exit + 20-day cool-down + 10% range, 1:3','#3 Momentum breakout','Buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×; no re-buy for 20 days','Swing low','1:3','Nifty > 50-day avg','4 weeks',"volume_cooldown_result.txt",'CS3_RX3'),
 ('cfm_rx3','Falcon Momentum 20-day-high + volume exit + cool-down + 10% range, 1:3','Falcon Momentum','Watch list; buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×; no re-buy for 20 days','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks',"volume_cooldown_result.txt",'CFM_RX3'),
 ('cs3_rx2','#3 + volume exit + 20-day cool-down + 10% range, 1:2','#3 Momentum breakout','Buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×; no re-buy for 20 days','Swing low','1:2','Nifty > 50-day avg','4 weeks',"volume_cooldown_result.txt",'CS3_RX2'),
 ('cfm_rx2','Falcon Momentum 20-day-high + volume exit + cool-down + 10% range, 1:2','Falcon Momentum','Watch list; buy-stop at 20-day high (skip unless ≤10% range); sell at close if volume < 1.5×; no re-buy for 20 days','Swing low, max 3 ATR','1:2','Sector check + Nifty > 200-day avg','8 weeks',"volume_cooldown_result.txt",'CFM_RX2'),
 ('p_asf_r','Combined: monthly momentum + #3 + Falcon (1/3 each, monthly rebalance)',"Portfolio combination","Each strategy's own entry","Each strategy's own stop","Mixed","Each strategy's own filter","Mixed","portfolio_combo_result.txt",'P_ASF_R'),
 ('p_asf_h','Combined: monthly momentum + #3 + Falcon (1/3 each, no rebalance)',"Portfolio combination","Each strategy's own entry","Each strategy's own stop","Mixed","Each strategy's own filter","Mixed","portfolio_combo_result.txt",'P_ASF_H'),
 ('p_as_r','Combined: monthly momentum + #3 (1/2 each)',"Portfolio combination","Each strategy's own entry","Each strategy's own stop","Mixed","Each strategy's own filter","Mixed","portfolio_combo_result.txt",'P_AS_R'),
 ('p_af_r','Combined: monthly momentum + Falcon (1/2 each)',"Portfolio combination","Each strategy's own entry","Each strategy's own stop","Mixed","Each strategy's own filter","Mixed","portfolio_combo_result.txt",'P_AF_R'),
 ('p_sf_r','Combined: #3 + Falcon (1/2 each)',"Portfolio combination","Each strategy's own entry","Each strategy's own stop","Mixed","Each strategy's own filter","Mixed","portfolio_combo_result.txt",'P_SF_R'),
 ('ha_s3_ref3','#3 + Nifty, 1:3 (half A)','#3 Momentum breakout','Buy-stop at 20-day high','Swing low','1:3','Nifty > 50-day avg','4 weeks','close_entry_result.txt','S3_REF3'),
 ('ha_s3_ref2','#3 + Nifty, 1:2 (half A)','#3 Momentum breakout','Buy-stop at 20-day high','Swing low','1:2','Nifty > 50-day avg','4 weeks','close_entry_result.txt','S3_REF2'),
 ('ha_s3_c3','#3, buy at close on clean candle, 1:3 (half A)','#3 Momentum breakout','Close, if green, above level, small wick','Swing low','1:3','Nifty > 50-day avg','4 weeks','close_entry_result.txt','S3_C3'),
 ('ha_s3_cv3','#3, clean close + 1.5× volume, 1:3 (half A)','#3 Momentum breakout','Close, clean candle + volume','Swing low','1:3','Nifty > 50-day avg','4 weeks','close_entry_result.txt','S3_CV3'),
 ('ha_fm_ref3','Falcon Momentum, Monday open, 1:3 (half A)','Falcon Momentum','Monday open after weekly rank','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','close_entry_result.txt','FM_REF3'),
 ('ha_fm_h3','Falcon Momentum, 20-day-high buy-stop, 1:3 (half A)','Falcon Momentum','Watch list; buy-stop at 20-day high','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','close_entry_result.txt','FM_H3'),
 ('ha_fm_c3','Falcon Momentum, buy at close on clean candle, 1:3 (half A)','Falcon Momentum','Watch list; close above 20-day high, green, small wick','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','close_entry_result.txt','FM_C3'),
 ('ha_fm_c2','Falcon Momentum, buy at close on clean candle, 1:2 (half A)','Falcon Momentum','Watch list; close above 20-day high, green, small wick','Swing low, max 3 ATR','1:2','Sector check + Nifty > 200-day avg','8 weeks','close_entry_result.txt','FM_C2'),
 ('ha_fm_cv3','Falcon Momentum, clean close + volume, 1:3 (half A)','Falcon Momentum','Watch list; clean candle + 1.5× volume, close','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','close_entry_result.txt','FM_CV3'),
 ('ha_rcl3','#3, dip to breakout candle low, 1:3 (half A)','#3 Momentum breakout','Limit at breakout candle low, 10 days','Swing low','1:3','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','RCL3'),
 ('ha_re3','#3, dip to 20 EMA, 1:3 (half A)','#3 Momentum breakout','Limit at 20 EMA, 10 days','Swing low','1:3','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','RE3'),
 ('ha_re2','#3, dip to 20 EMA, 1:2 (half A)','#3 Momentum breakout','Limit at 20 EMA, 10 days','Swing low','1:2','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','RE2'),
 ('ha_rs3','#3, dip to 20 SMA, 1:3 (half A)','#3 Momentum breakout','Limit at 20 SMA, 10 days','Swing low','1:3','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','RS3'),
 ('ha_kcl3','#3, clean breakout then dip to candle low, 1:3 (half A)','#3 Momentum breakout','Clean candle; limit at its low, 10 days','Swing low','1:3','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','KCL3'),
 ('ha_rb3','#3 range breakout, 1:3, 1% risk (half A)','#3 Momentum breakout','Close above 10+ day range (≤12%) on 1.5× volume, after swing-high break','Swing low','1:3','Nifty > 50-day avg','4 weeks','range_breakout_result.txt','RB3'),
 ('ha_rb3_r15','#3 range breakout, 1:3, 1.5% risk (half A)','#3 Momentum breakout','Range breakout at close','Swing low','1:3','Nifty > 50-day avg','4 weeks','rb_risk_combo_result.txt','RB3_R15'),
 ('ha_rb3_r20','#3 range breakout, 1:3, 2% risk (half A)','#3 Momentum breakout','Range breakout at close','Swing low','1:3','Nifty > 50-day avg','4 weeks','rb_risk_combo_result.txt','RB3_R20'),
 ('ha_a10','Monthly momentum + 10% stop (half A)','Monthly momentum','Month-end rank, next open','Fixed −10%','None','None','Until it leaves the top 20','rb_risk_combo_result.txt','A10'),
 ('ha_c_rb_a','Combined: range breakout + monthly momentum (half A)','Portfolio combination',"Each strategy's own","Each strategy's own",'Mixed',"Each strategy's own",'Mixed','rb_risk_combo_result.txt','C_RB_A'),
 ('ha_c_rb_f','Combined: range breakout + Falcon clean close (half A)','Portfolio combination',"Each strategy's own","Each strategy's own",'Mixed',"Each strategy's own",'Mixed','rb_risk_combo_result.txt','C_RB_F'),
 ('ha_pb10','Leader pullback (IA rules), 1% risk (half A)','Other','Close above prior-day high after 3–8 day quiet dip','Pullback low − 0.5 ATR','Half at 2R, trail 20 EMA','Nifty > 200-day, 50-day rising','4 weeks','pullback_result.txt','PB10'),
 ('ha_pbb10','Leader pullback + breadth filter, 1% risk (half A)','Other','Close above prior-day high after 3–8 day quiet dip','Pullback low − 0.5 ATR','Half at 2R, trail 20 EMA','Nifty filter + >50% above 200-day','4 weeks','pullback_result.txt','PBB10'),
 ('ha_rev_n','Momentum top 10% + buy 5-day dip, no filter (half A)','Monthly momentum','Every 2 weeks: 10 worst 5-day losers in top 10% by 6-1m return','−15% disaster stop','None (20-day hold)','None','20 days','mom_reversal_result.txt','REV_N'),
 ('ha_rev_f','Momentum top 10% + buy 5-day dip, Nifty 200-DMA filter (half A)','Monthly momentum','Every 2 weeks: 10 worst 5-day losers in top 10%','−15% disaster stop','None (20-day hold)','Nifty > 200-day avg','20 days','mom_reversal_result.txt','REV_F'),
 ('ha_mom10_n','Momentum top 10%, 20-day hold, no filter (half A)','Monthly momentum','Every 2 weeks: whole top 10% by 6-1m return','−15% disaster stop','None (20-day hold)','None','20 days','mom_reversal_result.txt','MOM10_N'),
 ('ha_mom10_f','Momentum top 10%, 20-day hold, Nifty 200-DMA filter (half A)','Monthly momentum','Every 2 weeks: whole top 10%','−15% disaster stop','None (20-day hold)','Nifty > 200-day avg','20 days','mom_reversal_result.txt','MOM10_F'),
 ('ha_f_ref','Falcon patterns, pivot buy-stop, Falcon stop/target (half A)','Other','Buy-stop at pattern pivot','Falcon two-low stop','Measured move','None','8 weeks','falcon_salvage_result.txt','F_REF'),
 ('ha_f_mom','Falcon patterns in top-20% momentum stocks (half A)','Other','Buy-stop at pattern pivot','Falcon two-low stop','Measured move','Top 20% 6-month momentum','8 weeks','falcon_salvage_result.txt','F_MOM'),
 ('ha_f_mom_cc_w','Falcon patterns + momentum + clean close + 3 ATR stop (half A)','Other','Clean close above pivot on 1.5× volume','3 ATR','1:3','Top 20% 6-month momentum','8 weeks','falcon_salvage_result.txt','F_MOM_CC_W'),
 ('ha_c_f_a','Combined: Falcon Momentum clean close + monthly momentum (half A)','Portfolio combination',"Each strategy's own","Each strategy's own",'Mixed',"Each strategy's own",'Mixed','wick_exit_result.txt','C_F_A'),
 ('ha_c_f_a_r','Combined: Falcon Momentum clean close + monthly momentum + range breakout 2% (half A)','Portfolio combination',"Each strategy's own","Each strategy's own",'Mixed',"Each strategy's own",'Mixed','wick_exit_result.txt','C_F_A_R'),
 ('ha_s3_wx','#3 + wick exit at close (half A)','#3 Momentum breakout','Buy-stop at 20-day high; sell at close if it closes back below','Swing low','1:3','Nifty > 50-day avg','4 weeks','wick_exit_result.txt','S3_WX'),
 ('ha_fm_wx','Falcon Momentum 20-day-high + wick exit (half A)','Falcon Momentum','Buy-stop at 20-day high; sell at close if it closes back below','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','wick_exit_result.txt','FM_WX'),
 ('hb_fm_c3','HALF B: Falcon Momentum, clean close, 1:3','Falcon Momentum','Watch list; close above 20-day high, green, small wick','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','halfB_confirmation_result.txt','FM_C3'),
 ('hb_c_f_a','HALF B: Falcon Momentum clean close + monthly momentum','Portfolio combination',"Each strategy's own","Each strategy's own",'Mixed',"Each strategy's own",'Mixed','halfB_confirmation_result.txt','C_F_A'),
 ('hb_a10','HALF B: Monthly momentum + 10% stop','Monthly momentum','Month-end rank, next open','Fixed −10%','None','None','Until it leaves the top 20','halfB_confirmation_result.txt','A10'),
 ('hb_fm_ref3','HALF B: Falcon Momentum, Monday open, 1:3','Falcon Momentum','Monday open after weekly rank','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','halfB_confirmation_result.txt','FM_REF3'),
 ('hb_s3_ref3','HALF B: #3 + Nifty filter, 1:3','#3 Momentum breakout','Buy-stop at 20-day high','Swing low','1:3','Nifty > 50-day avg','4 weeks','halfB_confirmation_result.txt','S3_REF3'),
 ('hb_rb3_r20','HALF B: #3 range breakout, 2% risk','#3 Momentum breakout','Range breakout at close','Swing low','1:3','Nifty > 50-day avg','4 weeks','halfB_confirmation_result.txt','RB3_R20'),
 ('all_a10_e50','Monthly momentum + 10% stop, half exposure when the stock list is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Equal-weight list > 200-day avg, else 50% exposure','Until it leaves the top 20','a_exposure_result.txt','A10_E50@ALL'),
 ('all_a10_e0','Monthly momentum + 10% stop, all cash when the stock list is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Equal-weight list > 200-day avg, else cash','Until it leaves the top 20','a_exposure_result.txt','A10_E0@ALL'),
 ('all_a10_n50','Monthly momentum + 10% stop, half exposure when the Nifty is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Nifty > 200-day avg, else 50% exposure','Until it leaves the top 20','a_exposure_result.txt','A10_N50@ALL'),
 ('ha_a10_e50','Monthly momentum + 10% stop, half exposure when the stock list is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Equal-weight list > 200-day avg, else 50% exposure','Until it leaves the top 20','a_exposure_result.txt','A10_E50@A'),
 ('ha_a10_e0','Monthly momentum + 10% stop, all cash when the stock list is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Equal-weight list > 200-day avg, else cash','Until it leaves the top 20','a_exposure_result.txt','A10_E0@A'),
 ('ha_a10_n50','Monthly momentum + 10% stop, half exposure when the Nifty is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Nifty > 200-day avg, else 50% exposure','Until it leaves the top 20','a_exposure_result.txt','A10_N50@A'),
 ('hb_a10_e50','Monthly momentum + 10% stop, half exposure when the stock list is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Equal-weight list > 200-day avg, else 50% exposure','Until it leaves the top 20','a_exposure_result.txt','A10_E50@B'),
 ('hb_a10_e0','Monthly momentum + 10% stop, all cash when the stock list is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Equal-weight list > 200-day avg, else cash','Until it leaves the top 20','a_exposure_result.txt','A10_E0@B'),
 ('hb_a10_n50','Monthly momentum + 10% stop, half exposure when the Nifty is below its 200-day avg','Monthly momentum','Month-end rank, next open','Fixed −10%','None (monthly rebalance)','Nifty > 200-day avg, else 50% exposure','Until it leaves the top 20','a_exposure_result.txt','A10_N50@B'),
 ('all_sw_a15','Monthly momentum + 15% stop','Monthly momentum','Month-end rank, next open','Fixed −15%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A15@ALL'),
 ('all_sw_a20','Monthly momentum + 20% stop','Monthly momentum','Month-end rank, next open','Fixed −20%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A20@ALL'),
 ('all_sw_a10c','Monthly momentum + 10% stop, no re-buy of a stopped stock at the next rebalance','Monthly momentum','Month-end rank, next open; a stopped stock is skipped for one rebalance','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A10C@ALL'),
 ('ha_sw_a15','Monthly momentum + 15% stop','Monthly momentum','Month-end rank, next open','Fixed −15%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A15@A'),
 ('ha_sw_a20','Monthly momentum + 20% stop','Monthly momentum','Month-end rank, next open','Fixed −20%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A20@A'),
 ('ha_sw_a10c','Monthly momentum + 10% stop, no re-buy of a stopped stock at the next rebalance','Monthly momentum','Month-end rank, next open; a stopped stock is skipped for one rebalance','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A10C@A'),
 ('ha_sw_a','Monthly momentum, top 20, no stop','Monthly momentum','Month-end rank, next open','None','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A@A'),
 ('hb_sw_a15','Monthly momentum + 15% stop','Monthly momentum','Month-end rank, next open','Fixed −15%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A15@B'),
 ('hb_sw_a20','Monthly momentum + 20% stop','Monthly momentum','Month-end rank, next open','Fixed −20%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A20@B'),
 ('hb_sw_a10c','Monthly momentum + 10% stop, no re-buy of a stopped stock at the next rebalance','Monthly momentum','Month-end rank, next open; a stopped stock is skipped for one rebalance','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A10C@B'),
 ('hb_sw_a','Monthly momentum, top 20, no stop','Monthly momentum','Month-end rank, next open','None','None (monthly rebalance)','None','Until it leaves the top 20','a_stop_width_result.txt','A@B'),
 ('all_vr_a10v','Monthly momentum + 10% stop, ranked by 12-1 return ÷ volatility','Monthly momentum','Month-end rank by 12-1 return ÷ 252-day volatility, next open','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_volrank_result.txt','A10V@ALL'),
 ('all_vr_a10z','Monthly momentum + 10% stop, ranked by z-scores of 6-1 and 12-1 return ÷ volatility','Monthly momentum','Month-end rank by mean z-score of 6-1 and 12-1 return ÷ volatility, next open','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_volrank_result.txt','A10Z@ALL'),
 ('ha_vr_a10v','Monthly momentum + 10% stop, ranked by 12-1 return ÷ volatility','Monthly momentum','Month-end rank by 12-1 return ÷ 252-day volatility, next open','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_volrank_result.txt','A10V@A'),
 ('ha_vr_a10z','Monthly momentum + 10% stop, ranked by z-scores of 6-1 and 12-1 return ÷ volatility','Monthly momentum','Month-end rank by mean z-score of 6-1 and 12-1 return ÷ volatility, next open','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_volrank_result.txt','A10Z@A'),
 ('hb_vr_a10v','Monthly momentum + 10% stop, ranked by 12-1 return ÷ volatility','Monthly momentum','Month-end rank by 12-1 return ÷ 252-day volatility, next open','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_volrank_result.txt','A10V@B'),
 ('hb_vr_a10z','Monthly momentum + 10% stop, ranked by z-scores of 6-1 and 12-1 return ÷ volatility','Monthly momentum','Month-end rank by mean z-score of 6-1 and 12-1 return ÷ volatility, next open','Fixed −10%','None (monthly rebalance)','None','Until it leaves the top 20','a_volrank_result.txt','A10Z@B'),
 ("f_r3","Falcon setups, swing-low stop 1:3","Other","Falcon pattern pivot (buy-stop)","Swing low","1:3","None","4 weeks","swing_risk_1to3_result.txt","F entries + swing-low stop, 1:3"),
 ("b_r3","52-week breakout, swing-low stop 1:3","Other","Next open after 52-week-high close","Swing low","1:3","None","4 weeks","swing_risk_1to3_result.txt","B entries + swing-low stop, 1:3"),
 ("mr_r3","RSI-2 dip buy, swing-low stop 1:3","Other","Next open after RSI-2 dip","Swing low","1:3","Nifty > 200-day avg","4 weeks","swing_risk_1to3_result.txt","MR entries + swing-low stop, 1:3"),
 ('s_orig','S: strong stock in strong peer group (first version)','#3 Momentum breakout','Buy-stop at 20-day high','2 ATR','None (trend, momentum, group exits)','Market switch','6 weeks','final_results_2026-11-03.txt','Strategy S'),
 ('f_orig',"F: Falcon pattern setups, Falcon's own trade plan",'Other','Buy-stop at pattern pivot','Falcon two-low stop','Measured move','None','8 weeks','final_results_2026-11-03.txt','Strategy F'),
 ('mr_orig','MR: RSI-2 mean reversion, top 100 stocks','Other','Next open after RSI(2) < 5 above 200-day avg','None','Close above 5-day avg','Nifty > 200-day avg','10 days','final_results_2026-11-03.txt','MR (primary)'),
 ('mr_orig_ds','MR + 3 ATR disaster stop','Other','Next open after RSI(2) < 5 above 200-day avg','3 ATR','Close above 5-day avg','Nifty > 200-day avg','10 days','final_results_2026-11-03.txt','MR + 3xATR disaster stop (reported only)'),
 ('s_br26','S (#3 entries) entries, fixed −2% / +6% bracket','#3 Momentum breakout','Buy-stop at 20-day high','Fixed −2%','Fixed +6%','Market switch','4 weeks','fixed_rr_result.txt','S entries + 1:3 bracket'),
 ('f_br26','Falcon pattern entries, fixed −2% / +6% bracket','Other','Buy-stop at pattern pivot','Fixed −2%','Fixed +6%','None','4 weeks','fixed_rr_result.txt','F entries + 1:3 bracket'),
 ('b_br26','52-week breakout entries, fixed −2% / +6% bracket','Other','Next open after 52-week-high close','Fixed −2%','Fixed +6%','None','4 weeks','fixed_rr_result.txt','B entries + 1:3 bracket'),
 ('mr_br26','RSI-2 dip entries, fixed −2% / +6% bracket','Other','Next open after RSI-2 dip','Fixed −2%','Fixed +6%','Nifty > 200-day avg','4 weeks','fixed_rr_result.txt','MR entries + 1:3 bracket'),
 ('s_br36','S (#3 entries) entries, fixed −3% / +6% bracket','#3 Momentum breakout','Buy-stop at 20-day high','Fixed −3%','Fixed +6%','Market switch','4 weeks','fixed_rr_3_6_result.txt','S entries + 3%/6% bracket'),
 ('f_br36','Falcon pattern entries, fixed −3% / +6% bracket','Other','Buy-stop at pattern pivot','Fixed −3%','Fixed +6%','None','4 weeks','fixed_rr_3_6_result.txt','F entries + 3%/6% bracket'),
 ('b_br36','52-week breakout entries, fixed −3% / +6% bracket','Other','Next open after 52-week-high close','Fixed −3%','Fixed +6%','None','4 weeks','fixed_rr_3_6_result.txt','B entries + 3%/6% bracket'),
 ('mr_br36','RSI-2 dip entries, fixed −3% / +6% bracket','Other','Next open after RSI-2 dip','Fixed −3%','Fixed +6%','Nifty > 200-day avg','4 weeks','fixed_rr_3_6_result.txt','MR entries + 3%/6% bracket'),
 ('f_r2','Falcon setups, swing-low stop 1:2','Other','Falcon pattern pivot (buy-stop)','Swing low','1:2','None','4 weeks','swing_risk_1to2_result.txt','F entries + swing-low stop, 1:2'),
 ('b_r2','52-week breakout, swing-low stop 1:2','Other','Next open after 52-week-high close','Swing low','1:2','None','4 weeks','swing_risk_1to2_result.txt','B entries + swing-low stop, 1:2'),
 ('mr_r2','RSI-2 dip buy, swing-low stop 1:2','Other','Next open after RSI-2 dip','Swing low','1:2','Nifty > 200-day avg','4 weeks','swing_risk_1to2_result.txt','MR entries + swing-low stop, 1:2'),
 ('s_c5','#3 entries, breakout-candle stop, +5% target','#3 Momentum breakout','Buy-stop at 20-day high','Below breakout candle low','Fixed +5%','Market switch','4 weeks','exit_variants_candle5_result.txt','S entries + breakout-candle stop, target +5%'),
 ('b_c5','52-week breakout, breakout-candle stop, +5% target','Other','Next open after 52-week-high close','Below breakout candle low','Fixed +5%','None','4 weeks','exit_variants_candle5_result.txt','B entries + breakout-candle stop, target +5%'),
 ('f_c5','Falcon pattern, breakout-candle stop, +5% target','Other','Buy-stop at pattern pivot','Below breakout candle low','Fixed +5%','None','4 weeks','exit_variants_candle5_result.txt','F entries + breakout-candle stop, target +5%'),
 ('s_c8','#3 entries, breakout-candle stop, +8% target','#3 Momentum breakout','Buy-stop at 20-day high','Below breakout candle low','Fixed +8%','Market switch','4 weeks','exit_variants_candle8_result.txt','S entries + breakout-candle stop, target +8%'),
 ('b_c8','52-week breakout, breakout-candle stop, +8% target','Other','Next open after 52-week-high close','Below breakout candle low','Fixed +8%','None','4 weeks','exit_variants_candle8_result.txt','B entries + breakout-candle stop, target +8%'),
 ('f_c8','Falcon pattern, breakout-candle stop, +8% target','Other','Buy-stop at pattern pivot','Below breakout candle low','Fixed +8%','None','4 weeks','exit_variants_candle8_result.txt','F entries + breakout-candle stop, target +8%'),
 ('s_h2','#3 entries, swing-low 1:2, half at 1R then stop to cost','#3 Momentum breakout','Buy-stop at 20-day high','Swing low → cost after half','1:2, half at 1R','None','4 weeks','exit_variants_half2_result.txt','S entries + swing-low stop, 1:2, half at 1R + break-even'),
 ('b_h2','52-week breakout, swing-low 1:2, half at 1R then stop to cost','Other','Next open after 52-week-high close','Swing low → cost after half','1:2, half at 1R','None','4 weeks','exit_variants_half2_result.txt','B entries + swing-low stop, 1:2, half at 1R + break-even'),
 ('f_h2','Falcon pattern, swing-low 1:2, half at 1R then stop to cost','Other','Buy-stop at pattern pivot','Swing low → cost after half','1:2, half at 1R','None','4 weeks','exit_variants_half2_result.txt','F entries + swing-low stop, 1:2, half at 1R + break-even'),
 ('mr_h2','RSI-2 dip, swing-low 1:2, half at 1R then stop to cost','Other','Next open after RSI-2 dip','Swing low → cost after half','1:2, half at 1R','Nifty > 200-day avg','4 weeks','exit_variants_half2_result.txt','MR entries + swing-low stop, 1:2, half at 1R + break-even'),
 ('s_h3','#3 entries, swing-low 1:3, half at 1.5R then stop to cost','#3 Momentum breakout','Buy-stop at 20-day high','Swing low → cost after half','1:3, half at 1.5R','None','4 weeks','exit_variants_half3_result.txt','S entries + swing-low stop, 1:3, half at 1.5R + break-even'),
 ('b_h3','52-week breakout, swing-low 1:3, half at 1.5R then stop to cost','Other','Next open after 52-week-high close','Swing low → cost after half','1:3, half at 1.5R','None','4 weeks','exit_variants_half3_result.txt','B entries + swing-low stop, 1:3, half at 1.5R + break-even'),
 ('f_h3','Falcon pattern, swing-low 1:3, half at 1.5R then stop to cost','Other','Buy-stop at pattern pivot','Swing low → cost after half','1:3, half at 1.5R','None','4 weeks','exit_variants_half3_result.txt','F entries + swing-low stop, 1:3, half at 1.5R + break-even'),
 ('mr_h3','RSI-2 dip, swing-low 1:3, half at 1.5R then stop to cost','Other','Next open after RSI-2 dip','Swing low → cost after half','1:3, half at 1.5R','Nifty > 200-day avg','4 weeks','exit_variants_half3_result.txt','MR entries + swing-low stop, 1:3, half at 1.5R + break-even'),
 ('ha_s3_c2','#3, buy at close on clean candle, 1:2','#3 Momentum breakout','Close, if green, above level, small wick','Swing low','1:2','Nifty > 50-day avg','4 weeks','close_entry_result.txt','S3_C2'),
 ('ha_s3_cv2','#3, clean close + 1.5× volume, 1:2','#3 Momentum breakout','Close, clean candle + volume','Swing low','1:2','Nifty > 50-day avg','4 weeks','close_entry_result.txt','S3_CV2'),
 ('ha_fm_ref2','Falcon Momentum, Monday open, 1:2','Falcon Momentum','Monday open after weekly rank','Swing low, max 3 ATR','1:2','Sector check + Nifty > 200-day avg','8 weeks','close_entry_result.txt','FM_REF2'),
 ('ha_fm_cv2','Falcon Momentum, clean close + volume, 1:2','Falcon Momentum','Watch list; clean candle + 1.5× volume, close','Swing low, max 3 ATR','1:2','Sector check + Nifty > 200-day avg','8 weeks','close_entry_result.txt','FM_CV2'),
 ('ha_rcl2','#3, dip to breakout candle low, 1:2','#3 Momentum breakout','Limit at breakout candle low, 10 days','Swing low','1:2','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','RCL2'),
 ('ha_rs2','#3, dip to 20 SMA, 1:2','#3 Momentum breakout','Limit at 20 SMA, 10 days','Swing low','1:2','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','RS2'),
 ('ha_kcl2','#3, clean breakout then dip to candle low, 1:2','#3 Momentum breakout','Clean candle; limit at its low, 10 days','Swing low','1:2','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','KCL2'),
 ('ha_ke3','#3, clean breakout then dip to 20 EMA, 1:3','#3 Momentum breakout','Clean candle; limit at 20 EMA, 10 days','Swing low','1:3','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','KE3'),
 ('ha_ke2','#3, clean breakout then dip to 20 EMA, 1:2','#3 Momentum breakout','Clean candle; limit at 20 EMA, 10 days','Swing low','1:2','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','KE2'),
 ('ha_ks3','#3, clean breakout then dip to 20 SMA, 1:3','#3 Momentum breakout','Clean candle; limit at 20 SMA, 10 days','Swing low','1:3','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','KS3'),
 ('ha_ks2','#3, clean breakout then dip to 20 SMA, 1:2','#3 Momentum breakout','Clean candle; limit at 20 SMA, 10 days','Swing low','1:2','Nifty > 50-day avg','4 weeks','retest_depth_result.txt','KS2'),
 ('ha_rb2','#3 range breakout, 1:2, 1% risk','#3 Momentum breakout','Close above 10+ day range (≤12%) on 1.5× volume, after swing-high break','Swing low','1:2','Nifty > 50-day avg','4 weeks','range_breakout_result.txt','RB2'),
 ('ha_rbk3','#3 range breakout + clean candle, 1:3','#3 Momentum breakout','Range breakout at close, green candle, small wick','Swing low','1:3','Nifty > 50-day avg','4 weeks','range_breakout_result.txt','RBK3'),
 ('ha_rbk2','#3 range breakout + clean candle, 1:2','#3 Momentum breakout','Range breakout at close, green candle, small wick','Swing low','1:2','Nifty > 50-day avg','4 weeks','range_breakout_result.txt','RBK2'),
 ('ha_pb075','Leader pullback (IA rules), 0.75% risk','Other','Close above prior-day high after 3–8 day quiet dip','Pullback low − 0.5 ATR','Half at 2R, trail 20 EMA','Nifty > 200-day, 50-day rising','4 weeks','pullback_result.txt','PB075'),
 ('ha_pbb075','Leader pullback + breadth filter, 0.75% risk','Other','Close above prior-day high after 3–8 day quiet dip','Pullback low − 0.5 ATR','Half at 2R, trail 20 EMA','Nifty filter + >50% above 200-day','4 weeks','pullback_result.txt','PBB075'),
 ('ha_f_cc','Falcon patterns, clean close entry, Falcon stop/target','Other','Clean close above pivot on 1.5× volume','Falcon two-low stop','Measured move','None','8 weeks','falcon_salvage_result.txt','F_CC'),
 ('ha_f_mom_cc','Falcon patterns in momentum stocks, clean close entry','Other','Clean close above pivot on 1.5× volume','Falcon two-low stop','Measured move','Top 20% 6-month momentum','8 weeks','falcon_salvage_result.txt','F_MOM_CC'),
 ('ha_f_cc_w','Falcon patterns, clean close + 3 ATR stop','Other','Clean close above pivot on 1.5× volume','3 ATR','1:3','None','8 weeks','falcon_salvage_result.txt','F_CC_W'),
 ('ha_s3_wxc','#3 + wick exit + 20-day cool-down','#3 Momentum breakout','Buy-stop at 20-day high; sell at close if it closes back below; no re-buy for 20 days','Swing low','1:3','Nifty > 50-day avg','4 weeks','wick_exit_result.txt','S3_WXC'),
 ('ha_fm_wxc','Falcon Momentum 20-day-high + wick exit + cool-down','Falcon Momentum','Buy-stop at 20-day high; sell at close if it closes back below; no re-buy for 20 days','Swing low, max 3 ATR','1:3','Sector check + Nifty > 200-day avg','8 weeks','wick_exit_result.txt','FM_WXC'),
 ('ha_f_ref_wx','Falcon patterns + wick exit','Other','Buy-stop at pattern pivot; sell at close if it closes back below','Falcon two-low stop','Measured move','None','8 weeks','wick_exit_result.txt','F_REF_WX'),
 ('ha_f_mom_wx','Falcon patterns in momentum stocks + wick exit','Other','Buy-stop at pattern pivot; sell at close if it closes back below','Falcon two-low stop','Measured move','Top 20% 6-month momentum','8 weeks','wick_exit_result.txt','F_MOM_WX'),
]
cache, rows = {}, []
for sid, name, fam, entry, stop, tgt, flt, hold, f, hdr in specs:
    if f not in cache: cache[f] = parse(D + f)
    b = cache[f]
    r = {"id": sid, "name": name, "family": fam, "entry": entry, "stop": stop, "target": tgt, "filter": flt, "hold": hold,
         "code": hdr, "file": f}
    for w, tag in (("W1", "w1"), ("W2", "w2"), ("2018", "y18")):
        x = b.get((hdr, w))
        if x is None and sid == "s3_orig" and w == "2018":
            x = cache.setdefault("s_plus_result.txt", parse(D + "s_plus_result.txt")).get(("original #3", "2018"))
        if x is None and sid == "s3_nifty" and w == "2018":
            x = {"cagr": -14.25, "dd": -23.54, "win": 36.7, "net": -1.86, "trades": 90, "passes": None}  # addendum block, data/s_plus_result.txt
        for k in ("cagr", "dd", "win", "net", "trades", "passes", "total"):
            r[f"{k}_{tag}"] = (x or {}).get(k)
    rows.append(r)
missing = [(r["id"]) for r in rows if r["cagr_w1"] is None or r["cagr_w2"] is None]
print("missing:", missing)
# test A, with and without a 10% stop (data/a_stop_result.txt)
ab = parse(D + "a_stop_result.txt")
for sid, name, hdr, stop in (("a_monthly", "Monthly momentum, top 20 (test A)", "A", "None"),
                             ("a_monthly_stop", "Monthly momentum + 10% stop (test A)", "A10", "Fixed −10% from buy price")):
    r = {"id": sid, "name": name, "family": "Monthly momentum", "entry": "Month-end rank, next open", "stop": stop,
         "target": "None (monthly rebalance)", "filter": "None", "hold": "Until it leaves the top 20"}
    for w, tag in (("W1", "w1"), ("W2", "w2"), ("2018", "y18")):
        x = ab.get((hdr, w)) or {}
        for k in ("cagr", "dd", "win", "net", "trades", "passes", "total"):
            r[f"{k}_{tag}"] = x.get(k)
    rows.append(r)
tn = parse(D + "a_topn_result.txt")
for hold in (10, 15):
    for stop in (False, True):
        hdr = f"A{hold}" + ("-stop10" if stop else "")
        r = {"id": f"a_top{hold}" + ("_stop" if stop else ""), "name": f"Monthly momentum, top {hold}" + (" + 10% stop" if stop else ""),
             "family": "Monthly momentum", "entry": "Month-end rank, next open", "stop": "Fixed −10% from buy price" if stop else "None",
             "target": "None (monthly rebalance)", "filter": "None", "hold": f"Until it leaves the top {hold}"}
        for w, tag in (("W1", "w1"), ("W2", "w2"), ("2018", "y18")):
            x = tn.get((hdr, w)) or {}
            for k in ("cagr", "dd", "win", "net", "trades", "passes", "total"):
                r[f"{k}_{tag}"] = x.get(k)
        rows.append(r)
YEARS = {"w1": 7.83, "w2": 10.0, "y18": 1.0}
for r in rows:
    for tag, yrs in YEARS.items():
        tot, cg = r.get(f"total_{tag}"), r.get(f"cagr_{tag}")
        if tot is None and cg is not None:
            tot = ((1 + cg / 100) ** yrs - 1) * 100
        r[f"grew_{tag}"] = round(10 * (1 + tot / 100), 2) if tot is not None else None
for r in rows: r.setdefault("note", "")
# ---- descriptive metadata for every row (added 2026-11-10) ----
A_ROWS = {"a_monthly": ("A [a_stop file]", "a_stop_result.txt"), "a_monthly_stop": ("A10 [a_stop file: top 20 + 10% stop]", "a_stop_result.txt"),
          "a_top10": ("A10 [a_topn file: top 10]", "a_topn_result.txt"), "a_top10_stop": ("A10-stop10 [a_topn file]", "a_topn_result.txt"),
          "a_top15": ("A15 [a_topn file]", "a_topn_result.txt"), "a_top15_stop": ("A15-stop10 [a_topn file]", "a_topn_result.txt")}
for r in rows:
    if r["id"] in A_ROWS:
        r["code"], r["file"] = A_ROWS[r["id"]]
HALF_A = ("close_entry", "retest_depth", "range_breakout", "rb_risk_combo", "pullback_result", "mom_reversal",
          "falcon_salvage", "wick_exit")
DOCS = [("swing_risk", "swing_low_risk"), ("s_plus", "s_plus"), ("s_sector_nifty", "s_sector_nifty"), ("s_sector", "s_sector"),
        ("s_retest", "s_retest"), ("fixed_5_15", "fixed_5_15"), ("fm_variants", "fm_variants"), ("falcon_momentum_t", "falcon_momentum"),
        ("fm_review", "fm_review"), ("fm_entries", "falcon_momentum_entries"), ("fm_high20", "fm_high20"), ("s_quality", "s_quality"),
        ("range_volume", "range_volume"), ("volume_exit", "volume_exit"), ("volume_cooldown", "volume_cooldown"),
        ("portfolio_combo", "portfolio_combo"), ("close_entry", "close_entry"), ("retest_depth", "retest_depth"),
        ("range_breakout", "range_breakout"), ("rb_risk_combo", "rb_risk_combo"), ("pullback_result", "pullback"),
        ("mom_reversal", "pullback_diagnostics"), ("falcon_salvage", "falcon_salvage"), ("wick_exit", "wick_exit"),
        ("halfB", "halfB_confirmation"), ("a_exposure", "a_exposure"), ("a_stop_width", "a_stop_width"), ("a_volrank", "a_volrank"), ("fm_risk_gauge", "fm_risk_gauge"), ("a_stop", "a_stop"), ("a_topn", "a_stop"), ("exit_variants", "exit_variants"),
        ("fixed_rr", "fixed_rr"), ("final_results", "s_and_f / mean_reversion")]
for r in rows:
    f = r.get("file", "")
    r["sample"] = "Half B" if f.startswith("halfB") else ("Half A" if f.startswith(HALF_A) else "All stocks")
    if "@" in str(r.get("code", "")):                     # 2026-11-10 series: one file holds all three samples
        r["sample"] = {"ALL": "All stocks", "A": "Half A", "B": "Half B"}[r["code"].split("@")[1]]
    r["doc"] = next((f"docs/{d}_preregistration.md" if "/" not in d else d for k, d in DOCS if f.startswith(k)), "")
    if r["id"] == "mr_orig" or r["id"] == "mr_orig_ds":
        r["doc"] = "docs/mean_reversion_preregistration.md"
    if r["id"] in ("s_orig", "f_orig"):
        r["doc"] = "docs/s_and_f_preregistration.md"
    r["name"] = r["name"].replace(" (half A)", "").replace("HALF B: ", "")
# rows that were tested but have no comparable figures in these columns
INFO = [
    {"id": "ml_model", "name": "Falcon Leadership breakout model (ML-scored patterns, runs #5, #6 and refit)", "family": "Other",
     "entry": "Pattern pivot, next-open fills", "stop": "Falcon two-low stop", "target": "Measured move", "filter": "Regime suppression",
     "hold": "8 weeks", "code": "Run #5/#6/refit", "doc": "docs/run5_preregistration.md, docs/refit_preregistration.md",
     "sample": "Screener list", "note": "Only 6–13 trades in 2 years on honest fills; no edge; refit not estimable. Run #4's strong result came from impossible pivot fills."},
    {"id": "b_orig", "name": "B: 52-week-high breakout (first version)", "family": "Other", "entry": "Next open after 52-week-high close on 1.5× volume",
     "stop": "2 ATR", "target": "None (trend exits)", "filter": "None", "hold": "See test doc", "code": "Strategy B",
     "doc": "docs/redesign_preregistration.md", "sample": "All stocks",
     "note": "Tested on 2019-01 to 2024-07 only: 18.2% a year against Nifty 16.1%, but below owning all stocks equally (23.4%)."},
    {"id": "c_orig", "name": "C: buy a 3-day dip in a strong stock (first version)", "family": "Other",
     "entry": "Next open after a 3%+ dip below the 10-day avg in a top-30% momentum stock", "stop": "See test doc",
     "target": "See test doc", "filter": "Nifty > 200-day avg", "hold": "4 weeks", "code": "Strategy C",
     "doc": "docs/redesign_preregistration.md", "sample": "All stocks",
     "note": "Tested on 2019-01 to 2024-07 only: 8.8% a year against Nifty 16.1%."},
]
for r in INFO:
    for k in ("cagr", "dd", "win", "net", "trades", "passes", "total", "grew"):
        for tag in ("w1", "w2", "y18"):
            r.setdefault(f"{k}_{tag}", None)
    rows.append(r)
VERDICT = {
    "a_monthly_stop": "Most robust result: held on all stocks, half A and half B. Deep drops.",
    "ha_a10": "Confirmed robust across samples. Deep drops.",
    "hb_a10": "Confirmed on unseen stocks. Deep drops.",
    "hb_c_f_a": "Best balance on unseen stocks. Missed the frozen bar by 0.06 pt (drawdown). Paper-trading candidate.",
    "ha_c_f_a": "Best balance on half A. Missed the frozen bar by 0.09 pt. Confirmed in substance on half B.",
    "ha_fm_c3": "Candidate on half A; not confirmed on half B.",
    "hb_fm_c3": "Not confirmed: below the Nifty in 2019–26.",
    "fm_r3": "Original Falcon Momentum: beat the Nifty in both decades with half its drawdown; not statistically proven.",
    "s3_nifty": "Best #3 version on all stocks; weak on unseen stocks (half B).",
    "hb_s3_ref3": "Not robust on unseen stocks.",
    "hb_rb3_r20": "Not robust on unseen stocks.",
    "ha_rb3_r20": "Tied #3 on half A; failed on half B.",
    "ha_rb3": "Better trades but too few; not adopted.",
    "a_monthly": "High return, but −80% drawdown in 2008–17 without a stop.",
    "p_asf_r": "Smoother than any single strategy; missed its frozen bar.",
    "ml_model": "No edge.", "b_orig": "No edge.", "c_orig": "No edge.",
}
for _t in ("all", "ha", "hb"):
    VERDICT[f"{_t}_vr_a10v"] = "Primary variant: FAILED its frozen bar (10 Nov 2026). Not adopted."
    VERDICT[f"{_t}_vr_a10z"] = "Reported for information only; not judged."
    VERDICT[f"{_t}_sw_a15"] = "Primary variant: FAILED its frozen bar (10 Nov 2026). Not adopted."
    VERDICT[f"{_t}_sw_a20"] = "Reported for information only; not judged."
    VERDICT[f"{_t}_sw_a10c"] = "Reported for information only; not judged."
    VERDICT[f"{_t}_sw_a"] = "Reference run (no stop) on this sample."
    VERDICT[f"{_t}_a10_e50"] = "Primary variant: FAILED its frozen bar (10 Nov 2026). Not adopted."
    VERDICT[f"{_t}_a10_e0"] = "Reported for information only; not judged."
    VERDICT[f"{_t}_a10_n50"] = "Reported for information only; not judged."
for r in rows:
    c = str(r.get("code", ""))
    r["verdict"] = VERDICT.get(r["id"]) or ("Reference run (the existing strategy, re-run for comparison)" if "REF" in c and r["sample"] != "Half B"
                                         else "Reference on unseen stocks" if r["sample"] == "Half B"
                                         else "Rejected: failed its pre-registered rule")
    notes = [r.get("note", "")] if r.get("note") else []
    if r["sample"] == "Half A":
        notes.append("Half-A sample (828 stocks): compare only with other half-A rows.")
    if r["sample"] == "Half B":
        notes.append("Half-B sample (794 unseen stocks): run once, after tuning ended.")
    if r["file"] if "file" in r else False:
        pass
    if str(r.get("file", "")).startswith("fixed_rr"):
        notes.append("5 positions × 20% of capital.")
    if r["id"].startswith("mr_orig"):
        notes.append("Judged on MR's own six trade-level checks.")
    if r["family"] == "Portfolio combination":
        notes.append("Sleeves run separately and are reset to equal weights monthly (no rebalancing cost).")
    r["note"] = " ".join(notes)
SHORT = {"a_monthly_stop": "Monthly momentum · all", "hb_a10": "Monthly momentum · B", "ha_c_f_a": "FM clean + monthly · A",
         "hb_c_f_a": "FM clean + monthly · B", "hb_fm_c3": "FM clean close · B", "fm_r3": "Falcon Momentum · all",
         "s3_nifty": "#3 + Nifty · all", "hb_s3_ref3": "#3 + Nifty · B"}
top = {k: i + 1 for i, k in enumerate(SHORT)}
for r in rows:
    r["top5"] = top.get(r["id"])
    r["short"] = SHORT.get(r["id"])
    r.pop("file", None)

json.dump(rows, open(OUT + "/strategies.json", "w"), indent=0)
bench = [{"period": "2019-26", "nifty_cagr": 10.03, "nifty_dd": -38.4, "ew_cagr": 15.16, "nifty_grew": round(10 * 1.1003 ** 7.83, 2)},
         {"period": "2008-17", "nifty_cagr": 5.54, "nifty_dd": -59.9, "ew_cagr": 4.17, "nifty_grew": round(10 * 1.0554 ** 10, 2)},
         {"period": "2018", "nifty_cagr": 4.11, "nifty_dd": -14.55, "ew_cagr": -24.39, "nifty_grew": 10.41}]
json.dump(bench, open(OUT + "/benchmarks.json", "w"), indent=0)
print(len(rows), "rows")
for r in rows[:3]: print(r)
