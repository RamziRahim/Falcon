"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : ai_panel.py
Package : ui

Purpose
-------
Renders the high-confluence AI synthesis guidance workspace exactly inside 
the bordered dashboard right-hand control container.
===============================================================================
"""

import streamlit as st
from ai.synthesis_engine import AISynthesisEngine


class AIPanel:
    @staticmethod
    def render(active_sym: str, full_history_df: any):
        """
        Renders the active AI panel inside the bounded workspace framework.
        """
        # Wrap everything natively inside the custom CSS left-border highlight class
        st.markdown('<div class="panel-box-ai">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0; font-size:15px; color:#FFFFFF;'>Falcon AI Engine Guidance</h4>", unsafe_allow_html=True)
        
        if active_sym not in st.session_state.ai_synthesis_runs:
            st.warning("AI Generation awaiting explicit request link.")
            if st.button("🧠 Generate AI Plan", use_container_width=True):
                with st.spinner(f"Synthesizing setup parameters for {active_sym}..."):
                    try:
                        ai_engine = AISynthesisEngine(provider_type="gemini")
                        analysis_result = ai_engine.synthesize_trade_setup(active_sym, full_history_df)
                        st.session_state.ai_synthesis_runs[active_sym] = analysis_result
                        st.rerun()
                    except Exception as e:
                        st.error("🚨 Falcon AI Pipeline Fault!")
                        st.exception(e)
        else:
            ai = st.session_state.ai_synthesis_runs[active_sym]
            
            # Map exact schema outputs from your prompt infrastructure configurations
            ai_score_val = str(ai.get("velocity_score", "N/A"))
            ai_action_val = str(ai.get("executive_action", "AVOID"))
            ai_growth_synthesis = str(ai.get("fundamental_growth_synthesis", ""))
            ai_supply_verdict = str(ai.get("supply_and_float_verdict", ""))
            ai_divergence_flag = str(ai.get("growth_divergence_flag", "False"))
            
            badge_class = "badge-green" if ai_action_val == "EXECUTE" else ("badge-blue" if ai_action_val == "ALERT_WATCHLIST" else "badge-red")
            score_color = "#10B981" if ai_action_val == "EXECUTE" else ("#3B82F6" if ai_action_val == "ALERT_WATCHLIST" else "#EF4444")
            
            st.markdown(f"""
<div style="display:flex; align-items:baseline; margin-bottom:10px;">
<span style="font-size:32px; font-weight:800; color:{score_color}; margin-right:5px;">{ai_score_val}</span>
<span style="color:#6B7280; font-size:13px; margin-right:15px;">/ 100 Velocity</span>
<span class="badge {badge_class}">{ai_action_val}</span>
</div>
<div class="info-row"><span class="info-label">Divergence Alert</span><span class="info-val">{ai_divergence_flag}</span></div>
<div class="section-header">Growth Synthesis</div>
<div style="font-size:13px; color:#E2E8F0; line-height:1.5; margin-bottom:10px;">{ai_growth_synthesis}</div>
<div class="section-header">Supply and Float Verdict</div>
<div style="font-size:13px; color:#E2E8F0; line-height:1.5;">{ai_supply_verdict}</div>
""", unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)