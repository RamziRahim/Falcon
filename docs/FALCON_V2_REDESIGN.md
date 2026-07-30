## 5. Better pattern methodology — the Unified Consolidation-Quality Engine

The five detectors are hand-coded silhouettes of the *same underlying
phenomenon*: an advance, then a consolidation whose volatility and volume
contract, resolving upward through a defined pivot. Run #1's strongest
result — tight triangles thrash deep cups — is evidence that **the
continuous properties of the consolidation predict outcomes better than
which named silhouette it matches.**

**Proposal (v2's core redesign):** demote binary pattern flags to labels;
promote a continuous feature vector computed for any consolidation:

| Feature | Definition (all point-in-time computable from existing data) |
|---|---|
| `prior_trend_strength` | % gain and slope of the advance preceding the base |
| `base_depth_pct` | max drawdown within the base (data says: shallower is better) |
| `base_length_bars` | consolidation duration |
| `contraction_slope` | trend of rolling ATR (or successive swing ranges) within the base — the VCP essence, made continuous |
| `volume_dryup_ratio` | base volume vs pre-base volume; down-day vs up-day volume inside the base |
| `pivot_proximity` | distance of current close to the base's resistance/pivot |
| `breakout_volume_ratio` | breakout-bar volume vs 20-day average (extends the existing Rel_Vol input) |
| `dist_52w_high` | proximity to 52-week high (leaders break out near highs — O'Neil) |
| `rs_line_new_high` | boolean/continuous: did the stock's RS line (price / NIFTY) make a new high before or with the price breakout — a classic leading signal Falcon does not currently compute anywhere |

Scoring then becomes: logistic regression (roadmap N-3, unchanged in
spirit) over these features + regime + sector + RS + MACD — fitted on
episode outcomes, tuning split only, validated on hold-out. Fully
explainable (signed coefficients per feature), strictly more expressive than
five binary flags with guessed integers, and it converts the triangle-vs-cup
finding from "reorder the flags" into "the model learns that low
`base_depth_pct` and negative `contraction_slope` carry the weight" — which
generalizes to consolidations that match *no* named silhouette (directly
attacking the 82% no-pattern problem: some of those 880 signals are sitting
in unnamed-but-tight bases the flags can't see).

The five named detectors are retained as (a) human-readable labels in the
UI/trade record, (b) regression features themselves (a triangle flag can
still earn a coefficient), and (c) the funnel-diagnostic subjects of §3.1.
Nothing is deleted; the decision weight moves from silhouette-matching to
measured structure quality.

**Explicitly deferred (practicality constraint):** CNN/image-based chart
recognition, DTW template matching, HMM regime-switching models. Each is a
research project with an explainability cost; none is justified while a
linear model over honest features remains unexhausted.
