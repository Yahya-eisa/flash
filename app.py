import streamlit as st
import pandas as pd
import datetime
import io
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import pytz
import re
from difflib import SequenceMatcher

# ---------- Arabic helpers ----------
def fix_arabic(text):
    if pd.isna(text):
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

def fill_down(series):
    return series.ffill()

def replace_muaaqal_with_confirm_safe(df):
    return df.replace('معلق', 'تم التأكيد')

def clean_and_fill_data(df):
    """تنظيف البيانات وملء الفراغات بشكل صحيح"""
    df = df.copy()
    
    if 'كود الاوردر' in df.columns:
        df['كود الاوردر'] = df['كود الاوردر'].ffill().bfill()
    if 'اسم العميل' in df.columns:
        df['اسم العميل'] = df['اسم العميل'].ffill().bfill()
    if 'موظف المجموعة' in df.columns:
        df['موظف المجموعة'] = df['موظف المجموعة'].ffill().bfill()
    if 'حالة الاوردر' in df.columns:
        df['حالة الاوردر'] = df['حالة الاوردر'].ffill().bfill()
    if 'المدينة' in df.columns:
        df['المدينة'] = df['المدينة'].ffill().bfill()
    
    base_cols = [c for c in ['كود الاوردر', 'اسم الصنف'] if c in df.columns]
    if base_cols:
        df = df.dropna(subset=base_cols, how='all')
    
    if 'اسم الصنف' in df.columns:
        df = df[df['اسم الصنف'].notna() & (df['اسم الصنف'].astype(str).str.strip() != '')]
    
    return df.reset_index(drop=True)

def classify_city(city):
    if pd.isna(city) or str(city).strip() == '':
        return "Other City"
    city = str(city).strip()
    city_map = {
        "منطقة صباح السالم": {"صباح السالم","العدان","المسيلة","أبو فطيرة","أبو الحصانية","مبارك الكبير",
                              "القصور","القرين","الفنيطيس","المسايل"},
        "منطقة المهبولة": {"الفنطاس","المهبولة"},
        "منطقة الفحيحيل": {"الفحيحيل الصناعية","أبو حليفة","المنقف","الفحيحيل"},
        "منطقة جابر الاحمد": {"مدينة جابر الأحمد","شمال غرب الصليبيخات","الرحاب","صباح الناصر",
                              "الفردوس","الأندلس","النهضة","غرناطة","الدوحة",
                              "جنوب الدوحة / القيروان","القيروان"},
        "منطقة العارضية": {"العارضية حرفية","العارضية","العارضية المنطقة الصناعية",
                            "الصليبخات","الري","اشبيلية","الرقعي"},
        "منطقة سلوي": {"مبارك العبدالله غرب مشرف","سلوى","بيان","الرميثية","مشرف"},
        "منطقة السالمية": {"السالمية","ميدان حولي","البدع"},
        "منطقة الجهراء": {"الجهراء","الصلبية الصناعية","الصليبية الصناعية","مزارع الصليبية",
                          "الصليبية السكنية","مدينة سعد العبد الله","الصليبية","أمغرة","سكراب امغرة",
                          "جنوب امغرة","القصر","النعيم","معسكرات الجهراء","تيماء","النسيم",
                          "الجهراء المنطقة الصناعية","جواخير الجهراء","العيون","الواحة",
                          "اسطبلات الجهراء","مزارع الطليبية"},
        "منطقة خيطان": {"خيطان"},
        "منطقة الفروانية": {"الفروانية"},
        "منطقه الصباحية": {"اسواق القرين","الظهر","جابر العلي","العقيلة","الرقة","المقوع",
                           "فهد الأحمد","الصباحية","هدية","الجليعه","علي صباح السالم"},
        "منطقة صباح الاحمد": {"صباح الأحمد3","الجليعة","صباح الأحمد","مدينة صباح الأحمد",
                             "ميناء عبد الله","بنيدر","الوفرة","الخيران","الزور","النويصب",
                             "شمال الأحمدي","جنوب الأحمدي","شرق الأحمدي","وسط الأحمدي",
                             "الأحمدي","غرب الأحمدي","ام الهيمان","الشعيبة"},
        "منطقة حولي": {"حولي"},
        "منطقة الجابرية": {"الجابرية","قرطبة","اليرموك","السرة"},
        "منطقة العاصمة": {"حدائق السور","دسمان","القبلة","المرقاب","مدينة الكويت","المباركية","شرق‎"},
        "منطقة الشويخ": {"الشويخ الصناعية","الشويخ","الشويخ السكنية","ميناء الشويخ"},
        "منطقة الشعب": {"ضاحية عبد الله السالم","الدعية","القادسية","النزهة","الفيحاء","كيفان",
                        "الشعب","الروضة","الخالدية","العديلية","الدسمة","الشامية","المنصورية","بنيد القار"},
        "منطقة عبدالله المبارك": {"السلام","الشدادية","غرب عبدالله المبارك","عبدالله المبارك",
                                 "العمرية","منطقة المطار","حطين","الشهداء","صبحان","الزهراء",
                                 "الصديق","الرابية","كبد","الرحاب","الضجيج","الافينيوز","جنوب السرة",
                                 "عبدالله مبارك الصباح"},
        "جليب الشيوخ": {"جليب الشيوخ","العباسية","شارع محمد بن القاسم","الحساوي"},
        "المطلاع": {"المطلاع","العبدلي","السكراب"},
    }
    for area, cities in city_map.items():
        if city in cities:
            return area
    return "Other City"

def df_to_pdf_table(df, title="FLASH"):
    if "اجمالي عدد القطع في الطلب" in df.columns:
        df = df.rename(columns={"اجمالي عدد القطع في الطلب": "عدد القطع"})

    final_cols = [
        'كود الاوردر', 'اسم العميل', 'المنطقة', 'العنوان',
        'المدينة', 'رقم موبايل العميل', 'حالة الاوردر',
        'عدد القطع', 'الملاحظات', 'اسم الصنف',
        'اللون', 'المقاس', 'الكمية',
        'الإجمالي مع الشحن'
    ]
    df = df[[c for c in final_cols if c in df.columns]].copy()

    if 'رقم موبايل العميل' in df.columns:
        df['رقم موبايل العميل'] = df['رقم موبايل العميل'].apply(
            lambda x: str(int(float(x))) if pd.notna(x) and str(x).replace('.','',1).isdigit()
            else ("" if pd.isna(x) else str(x))
        )

    safe_cols = {'الإجمالي مع الشحن','كود الاوردر','رقم موبايل العميل','اسم العميل',
                 'المنطقة','العنوان','المدينة','حالة الاوردر','الملاحظات','اسم الصنف','اللون','المقاس'}
    for col in df.columns:
        if col not in safe_cols:
            df[col] = df[col].apply(
                lambda x: str(int(float(x))) if pd.notna(x) and str(x).replace('.','',1).isdigit()
                else ("" if pd.isna(x) else str(x))
            )

    styleN = ParagraphStyle(name='Normal', fontName='Arabic-Bold', fontSize=9,
                            alignment=1, wordWrap='RTL')
    styleBH = ParagraphStyle(name='Header', fontName='Arabic-Bold', fontSize=10,
                             alignment=1, wordWrap='RTL')
    styleTitle = ParagraphStyle(name='Title', fontName='Arabic-Bold', fontSize=14,
                                alignment=1, wordWrap='RTL')

    data = []
    data.append([Paragraph(fix_arabic(col), styleBH) for col in df.columns])
    for _, row in df.iterrows():
        data.append([Paragraph(fix_arabic("" if pd.isna(row[col]) else str(row[col])), styleN)
                     for col in df.columns])

    col_widths_cm = [2, 2, 1.5, 3, 2, 3, 1.5, 1.5, 2.5, 3.5, 1.5, 1.5, 1, 1.5]
    col_widths = [max(c * 28.35, 15) for c in col_widths_cm]

    tz = pytz.timezone('Africa/Cairo')
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    title_text = f"{title} | FLASH | {today}"

    elements = [
        Paragraph(fix_arabic(title_text), styleTitle),
        Spacer(1, 14)
    ]

    table = Table(data, colWidths=col_widths[:len(df.columns)], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#64B5F6")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))

    elements.append(table)
    elements.append(PageBreak())
    return elements

NO_RESULT_LABEL = "لا توجد نتائج"

def normalize_campaign_name(name):
    """تنظيف اسم الحملة"""
    name = str(name)
    name = name.replace('‎', '').replace('‏', '')
    name = re.sub(r'\s+\d{1,2}[-/]\d{1,2}.*$', '', name)
    name = re.sub(r'\s*copy\s*\d*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*copy\s+of\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^new\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^scale\s+of\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+[-–—]\s+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

def extract_campaign_data(df, file_name):
    campaign_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(k in col_lower for k in ['campaign', 'ad name', 'ad set name', 'ad', 'اسم', 'حملة', 'إعلان']):
            campaign_col = col
            break

    cost_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if 'amount spent' in col_lower:
            cost_col = col
            break
    if cost_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ['cost', 'spend', 'انفاق', 'صرف', 'تكلفة']):
                if any(bad in col_lower for bad in ['cpc', 'cpm', 'per', '/', 'avg']):
                    continue
                cost_col = col
                break

    if campaign_col is None or cost_col is None:
        st.error(f"❌ ملف {file_name}: لم يتم العثور على عمود اسم الحملة أو عمود الصرف.")
        st.info(f"الأعمدة المتاحة: {list(df.columns)}")
        return None

    out = pd.DataFrame()
    out['campaign_name_raw'] = df[campaign_col]
    out['campaign_name'] = df[campaign_col].apply(normalize_campaign_name)
    out['cost'] = pd.to_numeric(df[cost_col], errors='coerce')
    out['source_file'] = file_name

    out = out[out['campaign_name_raw'].notna()]
    out = out[~out['campaign_name_raw'].astype(str).str.lower().str.contains('total')]
    out = out[out['cost'].notna()]

    st.success(f"✅ {file_name} | اسم الحملة: {campaign_col} | الصرف من: {cost_col}")
    return out

st.set_page_config(page_title="🔥 FLASH Orders System", layout="wide")
st.title("🔥 FLASH Orders System")

if 'campaigns_df' not in st.session_state:
    st.session_state.campaigns_df = None
if 'products_df' not in st.session_state:
    st.session_state.products_df = None
if 'grouped_campaigns' not in st.session_state:
    st.session_state.grouped_campaigns = None
if 'manual_mapping' not in st.session_state:
    st.session_state.manual_mapping = {}
if 'current_step' not in st.session_state:
    st.session_state.current_step = 'upload'

page = st.sidebar.radio(
    "اختار الوظيفة:",
    [
        "🔍 مراجعة الأوردرات المكررة",
        "📦 المشتريات المجمعة",
        "🚚 Flash Orders Processor",
        "📊 عدد الأوردرات لكل منتج",
        "📋 تقرير المنتجات (إجمالي + مرتجع)",
        "👥 إجمالي نسب الأوردرات",
        "🎯 تقرير الاعلانات"
    ]
)

# ==================== الصفحة الأولى ====================
if page == "🔍 مراجعة الأوردرات المكررة":
    st.header("🔍 مراجعة الأوردرات المكررة")
    st.markdown("ارفع الملف علشان تطلع الاوردرات المكررة 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="duplicates_file")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file, engine="openpyxl", dtype=str)
        
        code_col = None
        phone_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'كود' in col_lower or 'رقم' in col_lower and 'عشوائي' in col_lower:
                code_col = col
            elif 'موبايل' in col_lower or 'تليفون' in col_lower or 'هاتف' in col_lower:
                phone_col = col
        
        if code_col and phone_col:
            df_clean = df[[code_col, phone_col]].copy()
            df_clean = df_clean.dropna(subset=[code_col, phone_col])
            df_clean[phone_col] = df_clean[phone_col].astype(str).str.strip()
            df_clean[code_col] = df_clean[code_col].astype(str).str.strip()
            df_clean = df_clean.drop_duplicates()
            
            phone_counts = df_clean[phone_col].value_counts()
            duplicated_phones = phone_counts[phone_counts > 1].index.tolist()
            
            if duplicated_phones:
                duplicates_df = df_clean[df_clean[phone_col].isin(duplicated_phones)].copy()
                duplicates_df = duplicates_df.sort_values(phone_col)
                duplicates_df['عدد الأكواد'] = duplicates_df.groupby(phone_col)[phone_col].transform('count')
                
                st.error(f"⚠️ تم العثور على {len(duplicated_phones)} اوردر مكرر!")
                st.warning(f"📊 إجمالي الأكواد المكررة: {len(duplicates_df)}")
                st.dataframe(duplicates_df, use_container_width=True, hide_index=True)
                
                buffer = BytesIO()
                duplicates_df.to_excel(buffer, sheet_name='التليفونات المكررة', index=False, engine='openpyxl')
                buffer.seek(0)
                
                tz = pytz.timezone('Africa/Cairo')
                today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
                file_name = f"الاوردرات المكررة - {today}.xlsx"
                
                st.download_button(
                    label="⬇️ تحميل الاوردرات المكررة",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.divider()
                st.subheader("📈 ملخص إحصائي")
                
                summary_df = duplicates_df.groupby(phone_col)[code_col].agg(['count', lambda x: ', '.join(x)]).reset_index()
                summary_df.columns = ['رقم التليفون', 'عدد الأكواد', 'الأكواد']
                summary_df = summary_df.sort_values('عدد الأكواد', ascending=False)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
            else:
                st.success("✅ مفيش اوردرات مكررة!")
        else:
            st.error("❌ مش لاقي عمود كود الأوردر أو رقم التليفون في الملف!")
            st.info(f"الأعمدة الموجودة: {', '.join(df.columns.tolist())}")

# ==================== الصفحة الثانية ====================
elif page == "📦 المشتريات المجمعة":
    st.header("📦 المشتريات المجمعة")
    st.markdown("ارفع الملف وخد المشتريات على طول 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="products_file")
    
    if uploaded_file:
        xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
        
        all_frames = []
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            
            product_col = None
            color_col = None
            size_col = None
            qty_col = None
            
            for col in merged_df.columns:
                if 'منتج' in str(col) or 'صنف' in str(col):
                    product_col = col
                elif 'لون' in str(col):
                    color_col = col
                elif 'مقاس' in str(col):
                    size_col = col
                elif 'كمية' in str(col) or 'الكمية' in str(col):
                    qty_col = col
            
            if product_col and qty_col:
                merged_df[qty_col] = pd.to_numeric(merged_df[qty_col], errors='coerce').fillna(0)
                
                product_totals = merged_df.groupby(product_col)[qty_col].sum().reset_index()
                product_totals.columns = [product_col, 'إجمالي الكمية']
                product_totals = product_totals.sort_values('إجمالي الكمية', ascending=False)
                
                if color_col and size_col and color_col in merged_df.columns and size_col in merged_df.columns:
                    variation_details = []
                    for product_name in product_totals[product_col]:
                        product_data = merged_df[merged_df[product_col] == product_name]
                        details_list = []
                        
                        grouped = product_data.groupby([color_col, size_col])[qty_col].sum()
                        for (color, size), qty in grouped.items():
                            qty_int = int(float(qty)) if pd.notna(qty) else 0
                            if pd.notna(color) and pd.notna(size):
                                details_list.append(f"{color} - {size}: {qty_int}")
                            elif pd.notna(color):
                                details_list.append(f"{color}: {qty_int}")
                            elif pd.notna(size):
                                details_list.append(f"{size}: {qty_int}")
                        
                        variation_details.append("\n".join(details_list) if details_list else "-")
                    
                    product_totals['التفاصيل (اللون - المقاس)'] = variation_details
                
                st.success(f"✅ تم تجميع {len(product_totals)} منتج")
                st.dataframe(product_totals, use_container_width=True, hide_index=True)
                
                buffer = BytesIO()
                product_totals.to_excel(buffer, sheet_name='المشتريات', index=False, engine='openpyxl')
                buffer.seek(0)
                
                tz = pytz.timezone('Africa/Cairo')
                today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
                file_name = f"المشتريات - {today}.xlsx"
                
                st.download_button(
                    label="🛒 تحميل المشتريات",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("❌ مش لاقي أعمدة المنتج أو الكمية في الملف!")

# ==================== الصفحة الثالثة ====================
elif page == "🚚 Flash Orders Processor":
    st.header("🚚 Flash Orders Processor")
    st.markdown("....ارفع الملفات يا رايق علشان تستلم الشيت")
    
    uploaded_files = st.file_uploader(
        "Upload Excel files (.xlsx)",
        accept_multiple_files=True,
        type=["xlsx"],
        key="flash_files"
    )
    
    if uploaded_files:
        pdfmetrics.registerFont(TTFont('Arabic', 'Amiri-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('Arabic-Bold', 'Amiri-Bold.ttf'))
        
        all_frames = []
        for file in uploaded_files:
            xls = pd.read_excel(file, sheet_name=None, engine="openpyxl")
            for _, df in xls.items():
                df = df.dropna(how="all")
                all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            merged_df = replace_muaaqal_with_confirm_safe(merged_df)
            
            if 'المدينة' in merged_df.columns:
                merged_df['المدينة'] = merged_df['المدينة'].ffill().fillna('')
            if 'كود الاوردر' in merged_df.columns:
                merged_df['كود الاوردر'] = fill_down(merged_df['كود الاوردر'])
            if 'اسم العميل' in merged_df.columns:
                merged_df['اسم العميل'] = fill_down(merged_df['اسم العميل'])
            
            if 'المدينة' in merged_df.columns and 'اسم الصنف' in merged_df.columns:
                prod_present = merged_df['اسم الصنف'].notna() & merged_df['اسم الصنف'].astype(str).str.strip().ne('')
                city_empty = merged_df['المدينة'].isna() | merged_df['المدينة'].astype(str).str.strip().eq('')
                mask = prod_present & city_empty
                if mask.any():
                    city_ffill = merged_df['المدينة'].ffill()
                    merged_df.loc[mask, 'المدينة'] = city_ffill.loc[mask]
            
            merged_df['المنطقة'] = merged_df['المدينة'].apply(classify_city)
            merged_df['المنطقة'] = pd.Categorical(
                merged_df['المنطقة'],
                categories=[c for c in merged_df['المنطقة'].unique() if c != "Other City"] + ["Other City"],
                ordered=True
            )
            
            merged_df = merged_df.sort_values(['المنطقة','كود الاوردر'])
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=landscape(A4),
                leftMargin=15, rightMargin=15, topMargin=15, bottomMargin=15
            )
            elements = []
            for group_name, group_df in merged_df.groupby('المنطقة'):
                elements.extend(df_to_pdf_table(group_df, title=str(group_name)))
            doc.build(elements)
            buffer.seek(0)
            
            tz = pytz.timezone('Africa/Cairo')
            today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
            file_name = f"سواقين فلاش - {today}.pdf"
            
            st.success("✅تم تجهيز ملف PDF ✅")
            st.download_button(
                label="⬇️⬇️ تحميل ملف PDF",
                data=buffer.getvalue(),
                file_name=file_name,
                mime="application/pdf"
            )

# ==================== الصفحة الرابعة ====================
elif page == "📊 عدد الأوردرات لكل منتج":
    st.header("📊 عدد الأوردرات لكل منتج")
    st.markdown("ارفع الملف علشان تعرف كل منتج متكرر في كام اوردر 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="orders_count_file")
    
    if uploaded_file:
        xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
        
        all_frames = []
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            merged_df = replace_muaaqal_with_confirm_safe(merged_df)
            merged_df = clean_and_fill_data(merged_df)
            
            product_col = None
            order_col = None
            
            for col in merged_df.columns:
                if 'منتج' in str(col) or 'صنف' in str(col):
                    product_col = col
                elif 'كود' in str(col) and 'اوردر' in str(col).lower():
                    order_col = col
            
            if product_col and order_col:
                df_clean = merged_df[[order_col, product_col]].copy()
                df_clean = df_clean.dropna(subset=[product_col, order_col])
                df_clean[order_col] = df_clean[order_col].astype(str).str.strip()
                df_clean[product_col] = df_clean[product_col].astype(str).str.strip()
                df_clean = df_clean.drop_duplicates()
                
                orders_per_product = df_clean.groupby(product_col)[order_col].nunique().reset_index()
                orders_per_product.columns = ['اسم المنتج', 'عدد الأوردرات']
                orders_per_product = orders_per_product.sort_values('عدد الأوردرات', ascending=False)
                
                total_unique_orders = df_clean[order_col].nunique()
                orders_per_product['النسبة %'] = (orders_per_product['عدد الأوردرات'] / total_unique_orders * 100).round(2)
                
                st.success(f"✅ تم تحليل {len(orders_per_product)} منتج")
                st.info(f"📊 إجمالي الأوردرات الفريدة: {total_unique_orders}")
                st.dataframe(orders_per_product, use_container_width=True, hide_index=True)
                
                buffer = BytesIO()
                orders_per_product.to_excel(buffer, sheet_name='عدد الأوردرات', index=False, engine='openpyxl')
                buffer.seek(0)
                
                tz = pytz.timezone('Africa/Cairo')
                today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
                file_name = f"عدد الأوردرات لكل منتج - {today}.xlsx"
                
                st.download_button(
                    label="⬇️ تحميل التقرير",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.divider()
                st.subheader("📈 إحصائيات سريعة")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("أكثر منتج طلباً", orders_per_product.iloc[0]['اسم المنتج'])
                with col2:
                    st.metric("عدد أوردراته", int(orders_per_product.iloc[0]['عدد الأوردرات']))
                with col3:
                    st.metric("نسبته من الإجمالي", f"{orders_per_product.iloc[0]['النسبة %']}%")
            else:
                st.error("❌ مش لاقي عمود المنتج أو رقم الأوردر في الملف!")
                st.info(f"الأعمدة الموجودة: {', '.join(merged_df.columns.tolist())}")

# ==================== الصفحة الخامسة ====================
elif page == "📋 تقرير المنتجات (إجمالي + مرتجع)":
    st.header("📋 تقرير المنتجات (إجمالي عدد الأوردرات + تم التسليم + المرتجع)")
    st.markdown("ارفع الملف علشان تشوف لكل منتج: إجمالي عدد الأوردرات، عدد أوردرات تم التسليم، وعدد أوردرات المرتجع (بدون المعلق/تم التأكيد/ملغي قبل الشحن) 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="products_report_file")
    
    if uploaded_file:
        xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
        
        all_frames = []
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            merged_df = replace_muaaqal_with_confirm_safe(merged_df)
            merged_df = clean_and_fill_data(merged_df)
            
            product_col = None
            order_col = None
            status_col = None
            
            for col in merged_df.columns:
                if 'منتج' in str(col) or 'صنف' in str(col):
                    product_col = col
                elif 'كود' in str(col) and 'اوردر' in str(col).lower():
                    order_col = col
                elif 'حالة' in str(col) and 'اوردر' in str(col).lower():
                    status_col = col
            
            if product_col and order_col and status_col:
                df_clean = merged_df[[order_col, product_col, status_col]].copy()
                
                df_clean = df_clean.dropna(subset=[product_col, order_col, status_col])
                df_clean[order_col] = df_clean[order_col].astype(str).str.strip()
                df_clean[product_col] = df_clean[product_col].astype(str).str.strip()
                df_clean[status_col] = df_clean[status_col].astype(str).str.strip()
                
                df_clean = df_clean.drop_duplicates(subset=[order_col, product_col, status_col])
                
                states_to_exclude = ['تم التأكيد', 'معلق', 'ملغي قبل الشحن']
                df_clean = df_clean[~df_clean[status_col].isin(states_to_exclude)]
                
                delivered_status = 'تم التسليم'
                return_status = 'مرتجع'
                
                report_data = []
                
                for product in df_clean[product_col].unique():
                    product_orders = df_clean[df_clean[product_col] == product]
                    
                    total_orders = product_orders[order_col].nunique()
                    delivered_orders = product_orders[product_orders[status_col] == delivered_status][order_col].nunique()
                    returned_orders = product_orders[product_orders[status_col] == return_status][order_col].nunique()
                    
                    report_data.append({
                        'اسم المنتج': product,
                        'إجمالي الأوردرات': total_orders,
                        'تم التسليم': delivered_orders,
                        'إجمالي المرتجع': returned_orders
                    })
                
                report_df = pd.DataFrame(report_data)
                report_df = report_df.sort_values('إجمالي الأوردرات', ascending=False)
                
                st.success(f"✅ تم تحليل {len(report_df)} منتج (عدد أوردرات، مش عدد قطع)")
                st.dataframe(report_df, use_container_width=True, hide_index=True)
                
                buffer = BytesIO()
                report_df.to_excel(buffer, sheet_name='تقرير المنتجات', index=False, engine='openpyxl')
                buffer.seek(0)
                
                tz = pytz.timezone('Africa/Cairo')
                today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
                file_name = f"تقرير المنتجات - إجمالي-تسليم-مرتجع - {today}.xlsx"
                
                st.download_button(
                    label="📥 تحميل تقرير المنتجات (إجمالي + تم التسليم + مرتجع)",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.divider()
                st.subheader("📊 إحصائيات عامة")
                
                total_orders_all = report_df['إجمالي الأوردرات'].sum()
                total_delivered_all = report_df['تم التسليم'].sum()
                total_returns_all = report_df['إجمالي المرتجع'].sum()
                
                delivered_rate = round((total_delivered_all / total_orders_all * 100), 2) if total_orders_all > 0 else 0
                return_rate = round((total_returns_all / total_orders_all * 100), 2) if total_orders_all > 0 else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("إجمالي الأوردرات لكل المنتجات", total_orders_all)
                with col2:
                    st.metric("إجمالي تم التسليم لكل المنتجات", total_delivered_all)
                with col3:
                    st.metric("إجمالي المرتجع لكل المنتجات", total_returns_all)
                with col4:
                    st.metric("نسبة المرتجع من الإجمالي", f"{return_rate}%")
            else:
                st.error("❌ مش لاقي الأعمدة المطلوبة في الملف!")
                st.info(f"الأعمدة الموجودة: {', '.join(merged_df.columns.tolist())}")

# ==================== الصفحة السادسة ====================
elif page == "👥 إجمالي نسب الأوردرات":
    st.header("👥 إجمالي نسب الأوردرات")
    st.markdown("ارفع الملف علشان تشوف كل موظف: إجمالي، تم التسليم، مرتجع 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="moderators_report_file")
    
    if uploaded_file:
        xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
        
        all_frames = []
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            merged_df = replace_muaaqal_with_confirm_safe(merged_df)
            merged_df = clean_and_fill_data(merged_df)
            
            employee_col = None
            order_col = None
            status_col = None
            
            for col in merged_df.columns:
                if 'موظف' in str(col) and 'مجموعة' in str(col):
                    employee_col = col
                elif 'كود' in str(col) and 'اوردر' in str(col).lower():
                    order_col = col
                elif 'حالة' in str(col) and 'اوردر' in str(col).lower():
                    status_col = col
            
            if employee_col and order_col and status_col:
                df_clean = merged_df[[order_col, employee_col, status_col]].copy()
                df_clean = df_clean.dropna(subset=[employee_col, order_col, status_col])
                df_clean[order_col] = df_clean[order_col].astype(str).str.strip()
                df_clean[employee_col] = df_clean[employee_col].astype(str).str.strip()
                df_clean[status_col] = df_clean[status_col].astype(str).str.strip()
                
                df_clean = df_clean.drop_duplicates(subset=[order_col])
                
                report_data = []
                for employee in df_clean[employee_col].unique():
                    employee_orders = df_clean[df_clean[employee_col] == employee]
                    
                    total = len(employee_orders)
                    delivered = len(employee_orders[employee_orders[status_col] == 'تم التسليم'])
                    returned = len(employee_orders[employee_orders[status_col] == 'مرتجع'])
                    
                    report_data.append({
                        'اسم الموظف': employee,
                        'إجمالي الأوردرات': total,
                        'تم التسليم': delivered,
                        'إجمالي المرتجع': returned,
                        'نسبة التسليم %': round((delivered / total * 100), 2) if total > 0 else 0
                    })
                
                report_df = pd.DataFrame(report_data)
                report_df = report_df.sort_values('إجمالي الأوردرات', ascending=False)
                
                total_all = report_df['إجمالي الأوردرات'].sum()
                delivered_all = report_df['تم التسليم'].sum()
                returned_all = report_df['إجمالي المرتجع'].sum()
                
                total_row = pd.DataFrame([{
                    'اسم الموظف': '📊 الإجمالي الكلي',
                    'إجمالي الأوردرات': total_all,
                    'تم التسليم': delivered_all,
                    'إجمالي المرتجع': returned_all,
                    'نسبة التسليم %': round((delivered_all / total_all * 100), 2) if total_all > 0 else 0
                }])
                
                report_df = pd.concat([report_df, total_row], ignore_index=True)
                
                st.success(f"✅ تم تحليل {len(report_df)-1} موظف")
                st.dataframe(report_df, use_container_width=True, hide_index=True)
                
                buffer = BytesIO()
                report_df.to_excel(buffer, sheet_name='إجمالي نسب الأوردرات', index=False, engine='openpyxl')
                buffer.seek(0)
                
                tz = pytz.timezone('Africa/Cairo')
                today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
                file_name = f"إجمالي نسب الأوردرات - {today}.xlsx"
                
                st.download_button(
                    label="📥 تحميل تقرير الموظفين",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.divider()
                st.subheader("🏆 الإحصائيات الكلية")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("إجمالي الأوردرات", total_all)
                with col2:
                    st.metric("تم التسليم", delivered_all)
                with col3:
                    st.metric("إجمالي المرتجع", returned_all)
                with col4:
                    success_rate = round((delivered_all / total_all * 100), 2) if total_all > 0 else 0
                    st.metric("نسبة النجاح", f"{success_rate}%")
            else:
                st.error("❌ مش لاقي الأعمدة المطلوبة في الملف!")
                st.info(f"الأعمدة الموجودة: {', '.join(merged_df.columns.tolist())}")

# ==================== الصفحة السابعة ====================
elif page == "🎯 تقرير الاعلانات":
    st.header("🎯 تقرير الاعلانات")
    st.markdown("---")
 
    # إضافة الاسم في الأسفل
    st.markdown("<p style='text-align: center; color: gray; font-size: 12px;'>Developed by Yahya Eissa</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    if st.session_state.current_step == 'upload':
        st.subheader("📁 رفع ملفات الإعلانات (Facebook, TikTok, ...)")
        campaigns_files = st.file_uploader(
            "ارفع ملفات الإعلانات (يمكن أكثر من ملف)",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="campaigns"
        )

        st.subheader("📦 رفع ملفات المنتجات (شيت واحد أو أكثر)")
        products_files = st.file_uploader(
            "ارفع ملفات المنتجات",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="products"
        )

        if campaigns_files and products_files and st.button("🚀 ابدأ المعالجة", type="primary"):
            all_campaigns = []
            for f in campaigns_files:
                df = pd.read_excel(f)
                extracted = extract_campaign_data(df, f.name)
                if extracted is not None:
                    all_campaigns.append(extracted)
            if not all_campaigns:
                st.stop()
            campaigns_df = pd.concat(all_campaigns, ignore_index=True)

            all_products = []
            for f in products_files:
                dfp = pd.read_excel(f)
                name_col = None
                for col in dfp.columns:
                    col_lower = str(col).lower()
                    if any(k in col_lower for k in ['اسم', 'منتج', 'product', 'name', 'item']):
                        name_col = col
                        break
                if name_col is None:
                    st.error(f"❌ ملف منتجات {f.name} لا يحتوي على عمود اسم المنتج.")
                else:
                    dfp = dfp.rename(columns={name_col: 'اسم المنتج'})
                    all_products.append(dfp)
            if not all_products:
                st.stop()
            products_df = pd.concat(all_products, ignore_index=True)

            grouped_campaigns = campaigns_df.groupby('campaign_name').agg({
                'cost': 'sum',
                'campaign_name_raw': lambda x: list(x.unique()),
                'source_file': lambda x: ', '.join(x.unique()),
                'campaign_name': 'count'
            }).rename(columns={'campaign_name': 'ads_count'}).reset_index()

            grouped_campaigns = grouped_campaigns[['campaign_name', 'cost', 'ads_count', 'campaign_name_raw', 'source_file']]
            grouped_campaigns = grouped_campaigns.sort_values('cost', ascending=False)

            products_list = products_df['اسم المنتج'].astype(str).unique().tolist()
            auto_mapping = {}
            similarity_threshold = 0.75
            
            for _, row in grouped_campaigns.iterrows():
                campaign_name = row['campaign_name']
                best_match = None
                best_score = 0
                
                for product in products_list:
                    similarity = SequenceMatcher(None, campaign_name.lower(), product.lower()).ratio()
                    if similarity > best_score:
                        best_score = similarity
                        best_match = product
                
                if best_score >= similarity_threshold:
                    auto_mapping[campaign_name] = [best_match]
                    st.success(f"✅ ربط أوتوماتيكي: '{campaign_name}' ← '{best_match}' ({best_score*100:.1f}%)")
                else:
                    auto_mapping[campaign_name] = []
            
            st.session_state.campaigns_df = campaigns_df
            st.session_state.products_df = products_df
            st.session_state.grouped_campaigns = grouped_campaigns
            st.session_state.manual_mapping = auto_mapping
            st.session_state.current_step = 'manual_match'
            st.rerun()

    elif st.session_state.current_step == 'manual_match':
        st.subheader("🔍 مطابقة الحملات مع المنتجات")

        grouped = st.session_state.grouped_campaigns.copy()
        products_df = st.session_state.products_df
        products_list = products_df['اسم المنتج'].astype(str).tolist()

        campaigns_need_review = grouped[grouped['campaign_name'].apply(
            lambda x: len(st.session_state.manual_mapping.get(x, [])) == 0
        )]
        
        if campaigns_need_review.empty:
            st.success("🎉 تم ربط كل الحملات أوتوماتيكياً! لا توجد حملات تحتاج مراجعة يدوية.")
            if st.button("📊 عرض التقرير النهائي", type="primary"):
                st.session_state.current_step = 'final'
                st.rerun()
        else:
            st.info(f"📋 عدد الحملات المربوطة أوتوماتيكياً: {len(grouped) - len(campaigns_need_review)}")
            st.warning(f"⚠️ عدد الحملات تحتاج مراجعة يدوية: {len(campaigns_need_review)}")
            
            with st.form("manual_match_form"):
                for idx, (i, row) in enumerate(campaigns_need_review.iterrows(), 1):
                    st.markdown(f"### {idx}. اسم الحملة:")
                    st.code(row['campaign_name'])
                    st.write(f"💰 الصرف: {row['cost']:.2f} | 📊 إعلانات: {row['ads_count']}")

                    col1, col2 = st.columns([2, 1])
                    with col1:
                        selected_products = st.multiselect(
                            "اختر المنتجات:",
                            options=products_list,
                            key=f"products_{i}"
                        )
                    with col2:
                        no_result = st.checkbox(
                            "لا توجد اوردرات",
                            key=f"nores_{i}"
                        )

                    if no_result:
                        st.session_state.manual_mapping[row['campaign_name']] = [NO_RESULT_LABEL]
                    else:
                        st.session_state.manual_mapping[row['campaign_name']] = selected_products

                    st.markdown("---")

                submitted = st.form_submit_button("✅ تأكيد", type="primary")

            if submitted:
                st.session_state.current_step = 'final'
                st.rerun()

    elif st.session_state.current_step == 'final':
        st.subheader("📊 التقرير النهائي الكامل")

        grouped = st.session_state.grouped_campaigns.copy()
        products_df = st.session_state.products_df
        manual_mapping = st.session_state.manual_mapping

        grouped['قائمة المنتجات'] = grouped['campaign_name'].map(manual_mapping)

        def is_no_result(lst):
            return isinstance(lst, list) and len(lst) == 1 and lst[0] == NO_RESULT_LABEL

        campaigns_no_result = grouped[grouped['قائمة المنتجات'].apply(is_no_result)].copy()
        campaigns_with_products = grouped[~grouped['قائمة المنتجات'].apply(is_no_result)].copy()

        # ========== بناء التقرير الكامل لكل منتج ==========
        st.subheader("📦 التقرير الشامل: حملات + منتجات + أداء")

        if campaigns_with_products.empty:
            st.warning("لا توجد حملات مرتبطة بمنتجات.")
            final_report = pd.DataFrame()
        else:
            # التأكد من وجود الأعمدة المطلوبة في ملف المنتجات
            required_cols = ['اسم المنتج', 'إجمالي الأوردرات', 'تم التسليم', 'إجمالي المرتجع']
            for col in required_cols:
                if col not in products_df.columns:
                    st.warning(f"⚠️ عمود '{col}' غير موجود في ملف المنتجات. سيتم وضع قيمة 0.")
                    products_df[col] = 0

            # بناء التقرير الكامل - دمج الحملات لنفس المنتج + حفظ أسماء الحملات
            report_rows = []
            product_campaigns = {}  # لحفظ أسماء الحملات لكل منتج

            for _, campaign_row in campaigns_with_products.iterrows():
                campaign_name = campaign_row['campaign_name']
                campaign_cost = campaign_row['cost']
                campaign_ads_count = campaign_row['ads_count']
                products_list = campaign_row['قائمة المنتجات']
                
                if isinstance(products_list, list) and len(products_list) > 0:
                    for product_name in products_list:
                        # حفظ اسم الحملة لكل منتج
                        if product_name not in product_campaigns:
                            product_campaigns[product_name] = []
                        product_campaigns[product_name].append(campaign_name)
                        
                        # البحث عن بيانات المنتج
                        product_data = products_df[products_df['اسم المنتج'] == product_name]
                        
                        if not product_data.empty:
                            product_row = product_data.iloc[0]
                            total_orders = int(product_row.get('إجمالي الأوردرات', 0))
                            delivered_orders = int(product_row.get('تم التسليم', 0))
                            returned_orders = int(product_row.get('إجمالي المرتجع', 0))
                        else:
                            total_orders = 0
                            delivered_orders = 0
                            returned_orders = 0
                        
                        report_rows.append({
                            'اسم المنتج': product_name,
                            'إجمالي الصرف': campaign_cost,
                            'عدد الإعلانات': campaign_ads_count,
                            'إجمالي الأوردرات': total_orders,
                            'تم التسليم': delivered_orders,
                            'المرتجع': returned_orders
                        })
            
            if report_rows:
                # تحويل لـ DataFrame
                temp_df = pd.DataFrame(report_rows)
                
                # دمج الحملات لنفس المنتج (جمع الصرف والإعلانات)
                final_report = temp_df.groupby('اسم المنتج', as_index=False).agg({
                    'إجمالي الصرف': 'sum',
                    'عدد الإعلانات': 'sum',
                    'إجمالي الأوردرات': 'first',  # بيانات المنتج ثابتة
                    'تم التسليم': 'first',
                    'المرتجع': 'first'
                })
                
                # إضافة عمود أسماء الحملات
                final_report['اسماء الحملات'] = final_report['اسم المنتج'].map(
                    lambda product: ' | '.join(product_campaigns.get(product, []))
                )
                
                # حساب سعر الأوردر بعد الدمج
                final_report['سعر الأوردر المسلم'] = final_report.apply(
                    lambda row: round(row['إجمالي الصرف'] / row['تم التسليم'], 2) 
                    if row['تم التسليم'] > 0 else None, 
                    axis=1
                )
                
                # تدوير الأرقام
                final_report['إجمالي الصرف'] = final_report['إجمالي الصرف'].round(2)
                
                # ترتيب الأعمدة المطلوب
                final_report = final_report[[
                    'اسم المنتج',
                    'اسماء الحملات',
                    'إجمالي الصرف',
                    'عدد الإعلانات',
                    'إجمالي الأوردرات',
                    'تم التسليم',
                    'المرتجع',
                    'سعر الأوردر المسلم'
                ]]
                
                # ترتيب حسب الصرف
                final_report = final_report.sort_values('إجمالي الصرف', ascending=False)
                
                st.success(f"✅ تم إنشاء تقرير شامل لـ {len(final_report)} منتج")
                st.dataframe(final_report, use_container_width=True, height=400)
            else:
                final_report = pd.DataFrame()
                st.warning("لم يتم العثور على بيانات كافية لإنشاء التقرير.")

        # ========== عرض الحملات العامة (بدون منتجات) ==========
        if not campaigns_no_result.empty:
            st.divider()
            st.subheader("⚠️ حملات لا توجد لها اوردرات")
            df_no_res = campaigns_no_result[['campaign_name', 'cost', 'ads_count']].copy()
            df_no_res.rename(columns={
                'campaign_name': 'اسم الحملة',
                'cost': 'إجمالي الصرف',
                'ads_count': 'عدد الإعلانات'
            }, inplace=True)
            df_no_res['إجمالي الصرف'] = df_no_res['إجمالي الصرف'].round(2)
            st.dataframe(df_no_res, use_container_width=True, height=250)
        else:
            df_no_res = pd.DataFrame()

        # ========== تحميل التقرير الكامل ==========
        st.divider()
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            if not final_report.empty:
                final_report.to_excel(writer, index=False, sheet_name="التقرير الشامل")
            if not df_no_res.empty:
                df_no_res.to_excel(writer, index=False, sheet_name="لا توجد اوردرات")

        tz = pytz.timezone('Africa/Cairo')
        today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
        file_name = f"تقرير_الاعلانات_الشامل_{today}.xlsx"

        st.download_button(
            "⬇️ تحميل التقرير الشامل (Excel)",
            data=buf.getvalue(),
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

       
        st.markdown("---")
        if st.button("🔄 البدء من جديد"):
            st.session_state.clear()
            st.rerun()

     # إضافة الاسم في الأسفل
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: gray;'>Developed by Yahya Eissa</p>", unsafe_allow_html=True)

