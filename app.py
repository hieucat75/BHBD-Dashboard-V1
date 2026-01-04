import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import calendar
import warnings

# --- 1. CẤU HÌNH AI (AUTO-DETECT) ---
ai_status = "INIT"
ai_error_msg = ""
model = None
model_name_used = ""

try:
    import google.generativeai as genai
    # Key của bạn
    GOOGLE_API_KEY = "AIzaSyAp9j9b3RkswtQ_L4RuxdAIgg07yTgaSo8"
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # Lấy danh sách model
    all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    # Ưu tiên Flash -> Pro
    chosen_model = next((m for m in all_models if 'flash' in m), None)
    if not chosen_model:
        chosen_model = next((m for m in all_models if 'pro' in m), None)
    if not chosen_model and all_models:
        chosen_model = all_models[0]
        
    if chosen_model:
        model = genai.GenerativeModel(chosen_model)
        model_name_used = chosen_model
        ai_status = "OK"
    else:
        ai_status = "ERROR"
        ai_error_msg = "Không tìm thấy model AI."
        
except ImportError:
    ai_status = "ERROR"
    ai_error_msg = "Thiếu thư viện google-generativeai."
except Exception as e:
    ai_status = "ERROR"
    ai_error_msg = f"Lỗi AI: {str(e)}"

warnings.filterwarnings('ignore')

# --- 2. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="VNPOST COMMAND CENTER (V19.2)", layout="wide", initial_sidebar_state="collapsed")

COLOR_BG = "#001f3f"
COLOR_REV = "#EFB000"
COLOR_POS = "#28a745"
COLOR_NEG = "#dc3545"
COLOR_WASTE = "#fd7e14"
COLOR_TOP = "#28a745"
COLOR_DEAD = "#6c757d"

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ background-color: {COLOR_BG}; color: white; }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label {{ color: white !important; }}
    [data-testid="stSidebar"] .stMarkdown {{ color: white !important; }}
    div[data-testid="stMetricValue"] {{ font-size: 1.6rem; font-weight: 800; color: {COLOR_BG}; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    .stTabs [data-baseweb="tab"] {{ height: 45px; background-color: #f1f1f1; border-radius: 5px; color: #333; font-weight: bold; }}
    .stTabs [aria-selected="true"] {{ background-color: {COLOR_BG}; color: {COLOR_REV}; }}
</style>
""", unsafe_allow_html=True)

st.title("🚀 VNPOST RETAIL COMMAND CENTER (V19.2 - FINAL FIX)")

# --- 3. HÀM XỬ LÝ ---
@st.cache_data(show_spinner=False)
def load_data(file):
    if not file: return None
    try:
        if file.name.lower().endswith('.xlsx'): df = pd.read_excel(file, dtype=str)
        else: df = pd.read_csv(file, dtype=str, on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except: return None

def safe_float(series):
    return pd.to_numeric(series.str.replace(',', '').str.replace(r'[()]', '', regex=True), errors='coerce').fillna(0)

def safe_date(series):
    return pd.to_datetime(series, dayfirst=True, errors='coerce')

def format_compact(num):
    try:
        num = float(num)
        if abs(num) >= 1_000_000_000: return f"{num/1_000_000_000:.1f}B"
        if abs(num) >= 1_000_000: return f"{num/1_000_000:.1f}M"
        if abs(num) >= 1_000: return f"{num/1_000:.0f}K"
        return f"{num:.0f}"
    except: return "0"

def clean_fig_no_yaxis(fig):
    fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=30,b=0))
    fig.update_xaxes(showgrid=False, showticklabels=True)
    fig.update_yaxes(showgrid=False, showticklabels=False, visible=False)
    fig.update_layout(font=dict(size=14))
    return fig

def clean_fig_labels(fig):
    fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=30,b=0))
    fig.update_xaxes(showgrid=False, showticklabels=False)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(font=dict(size=14))
    return fig

# --- 4. UPLOAD & MAPPING ---
with st.sidebar:
    st.header("1. UPLOAD")
    with st.expander("Chọn File", expanded=True):
        f_prod = st.file_uploader("DS Sản Phẩm", type=['xlsx', 'csv'])
        f_price = st.file_uploader("Bảng Giá", type=['xlsx', 'csv'])
        f_kpi = st.file_uploader("KPI", type=['xlsx', 'csv'])
        f_sales = st.file_uploader("BC Bán Hàng", type=['xlsx', 'csv'])
        f_inv = st.file_uploader("BC Xuất Nhập Tồn", type=['xlsx', 'csv'])
        f_waste = st.file_uploader("BC Xuất Hủy", type=['xlsx', 'csv'])

    st.header("2. MAPPING")
    if f_prod and f_price and f_kpi and f_sales and f_inv and f_waste:
        if 'processed' not in st.session_state:
            df_sales_raw = load_data(f_sales)
            df_inv_raw = load_data(f_inv)
            df_waste_raw = load_data(f_waste)
            df_prod = load_data(f_prod)
            df_kpi = load_data(f_kpi)

            def get_idx(cols, keys):
                for i, c in enumerate(cols):
                    if any(k in c.lower() for k in keys): return i
                return 0

            with st.expander("🛠 Chọn Cột", expanded=True):
                st.markdown("**SALES**")
                cols_s = df_sales_raw.columns.tolist()
                s_ma = st.selectbox("Mã Hàng", cols_s, index=get_idx(cols_s, ['mã hàng', 'mã sp']))
                s_cn = st.selectbox("Chi Nhánh", cols_s, index=get_idx(cols_s, ['chi nhánh']))
                s_time = st.selectbox("Ngày GD", cols_s, index=get_idx(cols_s, ['thời gian', 'ngày']))
                s_sl = st.selectbox("Số Lượng", cols_s, index=get_idx(cols_s, ['sl', 'số lượng']))
                s_gb = st.selectbox("Đơn Giá Bán", cols_s, index=get_idx(cols_s, ['giá bán/sp', 'đơn giá bán']))
                s_gv = st.selectbox("Đơn Giá Vốn", cols_s, index=get_idx(cols_s, ['giá vốn/sp', 'đơn giá vốn']))
                
                st.markdown("**STOCK**")
                cols_i = df_inv_raw.columns.tolist()
                i_ma = st.selectbox("Mã Kho", cols_i, index=get_idx(cols_i, ['mã hàng']))
                i_cn = st.selectbox("CN Kho", cols_i, index=get_idx(cols_i, ['chi nhánh']))
                i_ton = st.selectbox("Tồn Cuối", cols_i, index=get_idx(cols_i, ['tồn cuối']))
                i_val = st.selectbox("Giá Trị Tồn", cols_i, index=get_idx(cols_i, ['giá trị cuối']))
                i_nhap = st.multiselect("Cột Nhập", cols_i, default=[c for c in cols_i if 'nhập' in c.lower() and 'giá trị' not in c.lower()])
                
                st.markdown("**WASTE**")
                cols_w = df_waste_raw.columns.tolist()
                w_ma = st.selectbox("Mã Hủy", cols_w, index=get_idx(cols_w, ['mã hàng']))
                w_val = st.selectbox("Giá Trị Hủy", cols_w, index=get_idx(cols_w, ['giá trị', 'thành tiền']))
                w_time = st.selectbox("Ngày Hủy", cols_w, index=get_idx(cols_w, ['ngày', 'thời gian']))
                w_cn = st.selectbox("CN Hủy", cols_w, index=get_idx(cols_w, ['chi nhánh']))
                
                cat_ma = st.selectbox("Master: Mã", df_prod.columns, index=get_idx(df_prod.columns, ['mã hàng']))
                cat_nhom = st.selectbox("Master: Ngành", df_prod.columns, index=get_idx(df_prod.columns, ['nhóm hàng', 'ngành']))
                kpi_cn = st.selectbox("KPI: CN", df_kpi.columns, index=get_idx(df_kpi.columns, ['chi nhánh']))
                kpi_val = st.selectbox("KPI: Target", df_kpi.columns, index=get_idx(df_kpi.columns, ['chỉ tiêu', 'target']))
                kpi_kv = st.selectbox("KPI: KV", df_kpi.columns, index=get_idx(df_kpi.columns, ['khu vực', 'region']))

            if st.button("🚀 TÍNH TOÁN", use_container_width=True):
                with st.spinner("Đang xử lý..."):
                    try:
                        # 1. Master Data & Dicts
                        df_prod[cat_ma] = df_prod[cat_ma].astype(str).str.strip().str.upper()
                        d_cat = dict(zip(df_prod[cat_ma], df_prod[cat_nhom].astype(str).str.split('>').str[0].str.strip()))
                        d_name = dict(zip(df_prod[cat_ma], df_prod[df_prod.columns[get_idx(df_prod.columns, ['tên'])]]))
                        
                        df_kpi[kpi_cn] = df_kpi[kpi_cn].astype(str).str.strip()
                        d_reg = dict(zip(df_kpi[kpi_cn], df_kpi[kpi_kv]))
                        d_target = dict(zip(df_kpi[kpi_cn], safe_float(df_kpi[kpi_val])))

                        # 2. Sales
                        df_m = pd.DataFrame()
                        df_m['PROD_ID'] = df_sales_raw[s_ma].astype(str).str.strip().str.upper()
                        df_m['BRANCH_ID'] = df_sales_raw[s_cn].astype(str).str.strip()
                        df_m['DATE'] = safe_date(df_sales_raw[s_time])
                        df_m = df_m.dropna(subset=['DATE'])
                        df_m['MONTH'] = df_m['DATE'].dt.strftime('%Y-%m')
                        df_m['QTY'] = safe_float(df_sales_raw[s_sl])
                        df_m['REV'] = df_m['QTY'] * safe_float(df_sales_raw[s_gb])
                        df_m['COST'] = df_m['QTY'] * safe_float(df_sales_raw[s_gv])
                        df_m['GP'] = df_m['REV'] - df_m['COST']
                        df_m['REGION'] = df_m['BRANCH_ID'].map(d_reg).fillna('Unknown')
                        df_m['CATEGORY'] = df_m['PROD_ID'].map(d_cat).fillna('Khác')
                        df_m['NAME'] = [d_name.get(x, x) for x in df_m['PROD_ID']] # Map Name Sales

                        # 3. Waste
                        df_w = pd.DataFrame()
                        df_w['PROD_ID'] = df_waste_raw[w_ma].astype(str).str.strip().str.upper()
                        df_w['BRANCH_ID'] = df_waste_raw[w_cn].astype(str).str.strip()
                        df_w['DATE'] = safe_date(df_waste_raw[w_time])
                        df_w = df_w.dropna(subset=['DATE'])
                        df_w['MONTH'] = df_w['DATE'].dt.strftime('%Y-%m')
                        df_w['VAL'] = safe_float(df_waste_raw[w_val])
                        df_w['REGION'] = df_w['BRANCH_ID'].map(d_reg).fillna('Unknown')
                        df_w['CATEGORY'] = df_w['PROD_ID'].map(d_cat).fillna('Khác')
                        # Map Name Waste
                        df_w['NAME'] = [d_name.get(x, x) for x in df_w['PROD_ID']]

                        # 4. Inv
                        df_i = pd.DataFrame()
                        df_i['PROD_ID'] = df_inv_raw[i_ma].astype(str).str.strip().str.upper()
                        df_i['BRANCH_ID'] = df_inv_raw[i_cn].astype(str).str.strip()
                        df_i['STOCK_QTY'] = safe_float(df_inv_raw[i_ton])
                        df_i['STOCK_VAL'] = safe_float(df_inv_raw[i_val])
                        df_i['IMPORT_QTY'] = 0
                        for c in i_nhap: df_i['IMPORT_QTY'] += safe_float(df_inv_raw[c])
                        df_i['REGION'] = df_i['BRANCH_ID'].map(d_reg).fillna('Unknown')
                        df_i['CATEGORY'] = df_i['PROD_ID'].map(d_cat).fillna('Khác')
                        # Map Name Inv
                        df_i['NAME'] = [d_name.get(x, x) for x in df_i['PROD_ID']]

                        st.session_state.data = {'sales': df_m, 'waste': df_w, 'inv': df_i, 'target': d_target}
                        st.session_state.processed = True
                        st.rerun()
                    except Exception as e: st.error(f"Lỗi xử lý: {e}"); st.stop()

if st.sidebar.button("⚠️ RESET DATA (BẮT BUỘC NẾU LỖI)", use_container_width=True):
    st.session_state.clear()
    st.rerun()

# --- 5. DASHBOARD VIEW ---
if 'data' in st.session_state and st.session_state.processed:
    data = st.session_state.data
    df_m = data['sales']
    df_w = data['waste']
    df_i = data['inv']
    d_target = data['target']

    with st.sidebar.expander("🔎 BỘ LỌC", expanded=False):
        months = sorted(list(set(df_m['MONTH'].unique()) | set(df_w['MONTH'].unique())))
        sel_months = st.multiselect("Tháng", months, default=months[-1:] if months else [])
        regions = sorted(df_m['REGION'].unique())
        sel_regions = st.multiselect("Khu Vực", regions, default=regions)
        cats = sorted(df_m['CATEGORY'].unique())
        sel_cats = st.multiselect("Ngành Hàng", cats, default=cats)
        valid_b = df_m[df_m['REGION'].isin(sel_regions)]['BRANCH_ID'].unique()
        sel_b = st.multiselect("Chi Nhánh", sorted(valid_b), default=sorted(valid_b))

    if not (sel_months and sel_regions and sel_cats and sel_b): st.warning("👈 Chọn bộ lọc."); st.stop()

    # --- FILTER DATA ---
    # COPY để tránh lỗi SettingWithCopyWarning khi gán cột mới
    dm = df_m[df_m['MONTH'].isin(sel_months) & df_m['BRANCH_ID'].isin(sel_b) & df_m['CATEGORY'].isin(sel_cats)].copy()
    dw = df_w[df_w['MONTH'].isin(sel_months) & df_w['BRANCH_ID'].isin(sel_b) & df_w['CATEGORY'].isin(sel_cats)].copy()
    di = df_i[df_i['BRANCH_ID'].isin(sel_b) & df_i['CATEGORY'].isin(sel_cats)].copy()

    # --- SAFETY CHECK & FILL NAME FOR AI ---
    # Đảm bảo 100% cột NAME tồn tại trước khi AI đọc
    if 'NAME' not in dw.columns: dw['NAME'] = dw['PROD_ID']
    if 'NAME' not in di.columns: di['NAME'] = di['PROD_ID']

    # --- CALCS ---
    total_rev = dm['REV'].sum()
    total_gp = dm['GP'].sum()
    total_waste = dw['VAL'].sum()
    total_net = total_gp - total_waste
    total_stock = di['STOCK_VAL'].sum()
    
    curr = max(sel_months) if sel_months else ""
    if curr:
        y, m = map(int, curr.split('-'))
        prev_m = m - 1 if m > 1 else 12
        prev_y = y if m > 1 else y - 1
        prev = f"{prev_y}-{prev_m:02d}"
    else:
        m, prev_m = 0, 0
        prev = ""

    days = 0
    for mon in sel_months:
        yy, mm = map(int, mon.split('-'))
        days += calendar.monthrange(yy, mm)[1]
    total_target = sum([d_target.get(b,0) for b in sel_b]) * days
    kpi_pct = (total_rev / total_target * 100) if total_target > 0 else 0

    # --- CHARTS ---
    # Monthly
    date_end = pd.to_datetime(curr + '-01')
    date_list = [((date_end - pd.DateOffset(months=i)).strftime('%Y-%m')) for i in range(11, -1, -1)]
    dm_all = df_m[df_m['BRANCH_ID'].isin(sel_b) & df_m['CATEGORY'].isin(sel_cats)]
    dw_all = df_w[df_w['BRANCH_ID'].isin(sel_b) & df_w['CATEGORY'].isin(sel_cats)]
    m_rev = dm_all.groupby('MONTH')['REV'].sum()
    m_net = dm_all.groupby('MONTH')['GP'].sum() - dw_all.groupby('MONTH')['VAL'].sum()
    df_t = pd.DataFrame(index=date_list)
    df_t['REV'] = m_rev
    df_t['NET'] = m_net
    df_t = df_t.fillna(0)
    df_t['PCT'] = (df_t['NET']/df_t['REV']*100).fillna(0)
    df_t['M'] = pd.to_datetime(df_t.index + '-01').month.astype(str)
    colors = [COLOR_REV if m_str in sel_months else '#E0E0E0' for m_str in df_t.index]
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Bar(x=df_t['M'], y=df_t['REV'], marker_color=colors, texttemplate='<b>%{y:.2s}</b>', textfont=dict(size=14)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_t['M'], y=df_t['PCT'], mode='lines+markers+text', line=dict(color='gray', width=1), 
                                          marker=dict(size=8, color=[COLOR_POS if x>=0 else COLOR_NEG for x in df_t['PCT']]),
                                          texttemplate='<b>%{y:.1f}%</b>', textposition='top center', textfont=dict(size=14)), secondary_y=True)
    clean_fig_no_yaxis(fig1)

    # Branch
    b_rev = dm.groupby('BRANCH_ID')['REV'].sum()
    b_net = dm.groupby('BRANCH_ID')['GP'].sum() - dw.groupby('BRANCH_ID')['VAL'].sum()
    df_b = pd.DataFrame({'REV': b_rev, 'NET': b_net}).fillna(0)
    df_b['PCT'] = (df_b['NET'] / df_b['REV'] * 100).fillna(0)
    df_b = df_b.sort_values('REV', ascending=False)
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    fig2.add_trace(go.Bar(x=df_b.index, y=df_b['REV'], marker_color=COLOR_REV, texttemplate='<b>%{y:.2s}</b>', textposition='auto', textfont=dict(size=14)), secondary_y=False)
    fig2.add_trace(go.Scatter(x=df_b.index, y=df_b['PCT'], mode='lines+markers+text', line=dict(color='gray', width=1),
                                      marker=dict(size=10, color=[COLOR_POS if x>=0 else COLOR_NEG for x in df_b['PCT']]),
                                      texttemplate='<b>%{y:.1f}%</b>', textposition='top center', textfont=dict(size=14)), secondary_y=True)
    clean_fig_no_yaxis(fig2)
    fig2.update_xaxes(tickangle=-45)

    # Top Sales
    top_s_raw = dm.groupby(['NAME', 'PROD_ID']).agg({'REV':'sum', 'GP':'sum'}).reset_index()
    w_s = dw.groupby('PROD_ID')['VAL'].sum()
    top_s_raw['WASTE'] = top_s_raw['PROD_ID'].map(w_s).fillna(0)
    top_s_raw['PCT'] = ((top_s_raw['GP'] - top_s_raw['WASTE']) / top_s_raw['REV'] * 100).fillna(0)
    top_s = top_s_raw.sort_values('REV', ascending=True).tail(20)
    lbl = [f"<b>{format_compact(v)} ({p:.1f}%)</b>" for v, p in zip(top_s['REV'], top_s['PCT'])]
    fig3 = go.Figure(go.Bar(x=top_s['REV'], y=top_s['NAME'], orientation='h', marker_color=COLOR_TOP, text=lbl, textposition='inside', textfont=dict(size=14)))
    clean_fig_labels(fig3)

    # Top Waste
    w_prod = dw.groupby(['PROD_ID', 'NAME'])['VAL'].sum().reset_index() # Group by Name safe
    s_prod = dm.groupby('PROD_ID')['REV'].sum()
    w_prod['REV'] = w_prod['PROD_ID'].map(s_prod).fillna(0)
    w_prod['PCT'] = np.where(w_prod['REV'] > 0, (w_prod['VAL'] / w_prod['REV'] * 100), 0)
    top_w = w_prod.sort_values('VAL', ascending=True).tail(20)
    lbl_w = [f"<b>{format_compact(v)} ({p:.1f}%)</b>" for v, p in zip(top_w['VAL'], top_w['PCT'])]
    fig4 = go.Figure(go.Bar(x=top_w['VAL'], y=top_w['NAME'], orientation='h', marker_color=COLOR_WASTE, text=lbl_w, textposition='inside', textfont=dict(size=14)))
    clean_fig_labels(fig4)

    # Dead Stock
    sold_ids = dm['PROD_ID'].unique()
    dead = di[~di['PROD_ID'].isin(sold_ids)].groupby(['PROD_ID', 'NAME'])['STOCK_VAL'].sum().reset_index()
    dead = dead.sort_values('STOCK_VAL', ascending=True).tail(20)
    fig5 = go.Figure(go.Bar(x=dead['STOCK_VAL'], y=dead['NAME'], orientation='h', marker_color=COLOR_DEAD, texttemplate='<b>%{x:.2s}</b>', textposition='inside', textfont=dict(size=14)))
    clean_fig_labels(fig5)

    # Sụt giảm
    df_scope = df_m[df_m['BRANCH_ID'].isin(sel_b) & df_m['CATEGORY'].isin(sel_cats)]
    curr_s = df_scope[df_scope['MONTH'] == curr].groupby('PROD_ID')['REV'].sum()
    prev_s = df_scope[df_scope['MONTH'] == prev].groupby('PROD_ID')['REV'].sum()
    df_mom = pd.DataFrame({'CURR': curr_s, 'PREV': prev_s}).fillna(0)
    df_mom['DIFF'] = df_mom['CURR'] - df_mom['PREV']
    
    decline_raw = df_mom[df_mom['DIFF'] < 0].sort_values('DIFF', ascending=True).head(50)
    stk_val = di.groupby('PROD_ID')['STOCK_VAL'].sum()
    
    # Safe Map Name
    name_dict_scope = dict(zip(df_m['PROD_ID'], df_m['NAME']))
    
    # Reset index to get PROD_ID column
    decline_chart = decline_raw.head(20).reset_index().rename(columns={'index':'PROD_ID'})
    if 'PROD_ID' not in decline_chart.columns: decline_chart.columns = ['PROD_ID'] + list(decline_chart.columns[1:])
    
    decline_chart['NAME'] = [name_dict_scope.get(x, x) for x in decline_chart['PROD_ID']]
    decline_chart['STOCK_VAL'] = decline_chart['PROD_ID'].map(stk_val).fillna(0)
    decline_chart['DIFF_ABS'] = decline_chart['DIFF'].abs()
    decline_chart = decline_chart.sort_values('DIFF', ascending=False)

    fig6 = go.Figure()
    fig6.add_trace(go.Bar(y=decline_chart['NAME'], x=decline_chart['DIFF_ABS'], name='Sụt Giảm', orientation='h', marker_color=COLOR_NEG, text=[format_compact(x) for x in decline_chart['DIFF_ABS']], textposition='auto'))
    fig6.add_trace(go.Bar(y=decline_chart['NAME'], x=decline_chart['STOCK_VAL'], name='GT Tồn', orientation='h', marker_color=COLOR_DEAD, text=[format_compact(x) for x in decline_chart['STOCK_VAL']], textposition='auto'))
    fig6.update_layout(barmode='group', height=500, showlegend=True, legend=dict(orientation="h", y=1.1), margin=dict(l=0, r=0, t=40, b=0), font=dict(size=14))
    fig6.update_xaxes(showgrid=False, visible=False)
    fig6.update_yaxes(autorange="reversed")

    # --- UI TABS ---
    tab1, tab2, tab3 = st.tabs(["📊 EXECUTIVE VIEW", "⚡ SỤT GIẢM & HÀNG NHẬP", "🔎 CHI TIẾT SỐ LIỆU"])

    with tab1:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("DOANH THU", f"{total_rev:,.0f}", f"{kpi_pct:.1f}% KPI")
        c2.metric("LN GỘP", f"{total_gp:,.0f}", f"{total_gp/total_rev*100:.1f}%")
        c3.metric("XUẤT HỦY", f"{total_waste:,.0f}", f"-{total_waste/total_rev*100:.1f}%", delta_color="inverse")
        c4.metric("LN RÒNG", f"{total_net:,.0f}", f"{total_net/total_rev*100:.1f}%")
        c5.metric("TỒN KHO", f"{total_stock:,.0f}", "Vốn")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1: st.markdown("##### 📉 Monthly Sales Trend"); st.plotly_chart(fig1, use_container_width=True)
        with col2: st.markdown("##### 🏢 Branch Performance"); st.plotly_chart(fig2, use_container_width=True)
        c3a, c3b = st.columns(2)
        with c3a: st.markdown("##### 💎 Top 20 Sales"); st.plotly_chart(fig3, use_container_width=True)
        with c3b: st.markdown("##### ⚠️ Top 20 Waste"); st.plotly_chart(fig4, use_container_width=True)
        c4a, c4b = st.columns(2)
        with c4a: st.markdown("##### 🐢 Top 20 Dead Stock"); st.plotly_chart(fig5, use_container_width=True)
        with c4b: st.markdown("##### 📉 Top 20 Sụt Giảm (Horizontal)"); st.plotly_chart(fig6, use_container_width=True)

    with tab2:
        st.markdown("#### ⚡ BẢNG SỐ LIỆU: SỤT GIẢM & HÀNG NHẬP")
        if sel_months:
            decline_full = df_mom[df_mom['DIFF'] < 0].sort_values('DIFF', ascending=True).head(50).reset_index().rename(columns={'index':'PROD_ID'})
            if 'PROD_ID' not in decline_full.columns: decline_full.columns = ['PROD_ID'] + list(decline_full.columns[1:])
            
            stk_info = di.groupby('PROD_ID').agg({'STOCK_QTY':'sum', 'STOCK_VAL':'sum', 'IMPORT_QTY':'sum'}).reset_index()
            decline_table = pd.merge(decline_full, stk_info, on='PROD_ID', how='left').fillna(0)
            decline_table['NAME'] = [name_dict_scope.get(x, x) for x in decline_table['PROD_ID']]
            
            curr_q = df_scope[df_scope['MONTH'] == curr].groupby('PROD_ID')['QTY'].sum()
            decline_table['QTY_CURR'] = decline_table['PROD_ID'].map(curr_q).fillna(0)
            avg_qty = decline_table['QTY_CURR'] / (days if days > 0 else 1)
            decline_table['DAYS'] = np.where(avg_qty > 0, decline_table['STOCK_QTY'] / avg_qty, 999)
            
            show_cols = ['NAME', 'CURR', 'PREV', 'DIFF', 'STOCK_VAL', 'DAYS', 'IMPORT_QTY']
            renames = {'NAME':'Tên SP', 'CURR':f'DT T{m}', 'PREV':f'DT T{prev_m}', 'DIFF':'Sụt Giảm', 
                       'STOCK_VAL':'GT Tồn', 'DAYS':'Ngày Bán', 'IMPORT_QTY':'SL Nhập'}
            st.dataframe(decline_table[show_cols].rename(columns=renames).style.format("{:,.0f}", subset=[f'DT T{m}', f'DT T{prev_m}', 'Sụt Giảm', 'GT Tồn', 'SL Nhập']).format("{:.1f}", subset=['Ngày Bán']).background_gradient(subset=['Sụt Giảm'], cmap='RdYlGn'), use_container_width=True, height=600)
        else: st.info("Chọn tháng")

    with tab3:
        st.markdown("#### 🔎 DỮ LIỆU CHI TIẾT")
        agg_m = dm.groupby(['PROD_ID', 'NAME']).agg({'QTY':'sum', 'REV':'sum', 'GP':'sum'}).reset_index()
        agg_w = dw.groupby(['PROD_ID', 'NAME'])['VAL'].sum().reset_index().rename(columns={'VAL':'WASTE_VAL'})
        agg_i = di.groupby(['PROD_ID', 'NAME']).agg({'STOCK_QTY':'sum', 'STOCK_VAL':'sum', 'IMPORT_QTY':'sum'}).reset_index()
        
        final = pd.merge(agg_m, agg_w, on=['PROD_ID', 'NAME'], how='outer').fillna(0)
        final = pd.merge(final, agg_i, on=['PROD_ID', 'NAME'], how='outer').fillna(0)
        final['NET'] = final['GP'] - final['WASTE_VAL']
        
        disp = final[['PROD_ID', 'NAME', 'QTY', 'REV', 'NET', 'STOCK_QTY', 'STOCK_VAL', 'IMPORT_QTY', 'WASTE_VAL']]
        disp.columns = ['Mã', 'Tên', 'SL Bán', 'Doanh Thu', 'LN Ròng', 'SL Tồn', 'GT Tồn', 'SL Nhập', 'GT Hủy']
        st.dataframe(disp.style.format("{:,.0f}", subset=['SL Bán', 'Doanh Thu', 'LN Ròng', 'SL Tồn', 'GT Tồn', 'SL Nhập', 'GT Hủy']), use_container_width=True, height=600)

    # --- CHATBOT DEEP DIVE ---
    if ai_status == "OK" and model:
        with st.sidebar:
            st.markdown("---")
            st.header("🤖 Trợ Lý AI (Deep Data)")
            st.info(f"Model: {model_name_used}")
            
            # --- CHUẨN BỊ DỮ LIỆU CHO AI ---
            # 1. Đảm bảo tên cột rõ ràng cho AI
            limit = 2000 # Giới hạn dòng để không quá tải
            
            # Bảng Sales
            df_s_ai = dm[['DATE', 'NAME', 'REV', 'GP']].head(limit).copy()
            df_s_ai['DATE'] = df_s_ai['DATE'].dt.strftime('%Y-%m-%d')
            csv_sales = df_s_ai.to_csv(index=False)
            
            # Bảng Waste (Đảm bảo có NAME)
            df_w_ai = dw[['DATE', 'NAME', 'VAL']].head(limit).copy()
            df_w_ai['DATE'] = df_w_ai['DATE'].dt.strftime('%Y-%m-%d')
            csv_waste = df_w_ai.to_csv(index=False)
            
            # Bảng Stock (Đảm bảo có NAME)
            df_i_ai = di[['NAME', 'STOCK_VAL', 'STOCK_QTY']].head(limit).copy()
            csv_stock = df_i_ai.to_csv(index=False)
            
            system_prompt = f"""
            Vai trò: Chuyên gia phân tích dữ liệu bán lẻ.
            
            DỮ LIỆU ĐẦU VÀO (Đã lọc):
            1. SALES (Bán hàng):
            {csv_sales}
            
            2. WASTE (Hủy):
            {csv_waste}
            
            3. STOCK (Tồn kho):
            {csv_stock}
            
            Yêu cầu:
            - Trả lời câu hỏi dựa trên dữ liệu này.
            - Dẫn chứng số liệu cụ thể (Ví dụ: "Mã A hủy 50tr").
            - Nếu không có dữ liệu, hãy nói rõ.
            """
            
            if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Tôi đã đọc xong dữ liệu chi tiết. Mời sếp hỏi."}]
            for msg in st.session_state.messages: st.chat_message(msg["role"]).write(msg["content"])
            if prompt := st.chat_input("Hỏi AI..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.chat_message("user").write(prompt)
                try:
                    full_input = f"{system_prompt}\nUser Question: {prompt}"
                    response = model.generate_content(full_input)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    st.chat_message("assistant").write(response.text)
                except Exception as e: st.error(f"Lỗi AI: {e}")
    elif ai_status != "OK":
        with st.sidebar:
            st.error(f"⚠️ {ai_error_msg}")
