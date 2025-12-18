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

# ---------- PDF table builder ----------
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

# ---------- Streamlit App ----------
st.set_page_config(page_title="🔥 ECOMERG Orders System", layout="wide")
st.title("🔥 ECOMERG Orders System")

# القائمة الجانبية للاختيار
page = st.sidebar.radio(
    "اختار الوظيفة:",
    ["🔍 مراجعة الأوردرات المكررة", "📦 المشتريات المجمعة", "📊 عدد الأوردرات لكل منتج", 
     "📋 تقرير المنتجات", "👥 إجمالي نسب الأوردرات", "🚚 Flash Orders Processor"]
)

# ==================== الصفحة الأولى: مراجعة الأوردرات المكررة ====================
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

# ==================== الصفحة الثانية: المشتريات المجمعة ====================
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

# ==================== الصفحة الثالثة: عدد الأوردرات لكل منتج ====================
elif page == "📊 عدد الأوردرات لكل منتج":
    st.header("📊 عدد الأوردرات لكل منتج")
    st.markdown("ارفع الملف علشان تعرف كل منتج كام اوردر 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="orders_count_file")
    
    if uploaded_file:
        xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
        
        all_frames = []
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            
            product_col = None
            order_col = None
            
            for col in merged_df.columns:
                if 'منتج' in str(col) or 'صنف' in str(col):
                    product_col = col
                elif 'كود' in str(col).lower() or ('رقم' in str(col).lower() and 'عشوائي' in str(col).lower()):
                    order_col = col
            
            if product_col and order_col:
                df_clean = merged_df[[order_col, product_col]].copy()
                df_clean = df_clean.dropna(subset=[product_col])
                df_clean[order_col] = df_clean[order_col].astype(str).str.strip()
                df_clean[product_col] = df_clean[product_col].astype(str).str.strip()
                df_clean = df_clean.drop_duplicates(subset=[order_col, product_col])
                
                orders_per_product = df_clean.groupby(product_col)[order_col].nunique().reset_index()
                orders_per_product.columns = ['اسم المنتج', 'عدد الأوردرات']
                orders_per_product = orders_per_product.sort_values('عدد الأوردرات', ascending=False)
                
                total_orders = orders_per_product['عدد الأوردرات'].sum()
                orders_per_product['النسبة %'] = (orders_per_product['عدد الأوردرات'] / total_orders * 100).round(2)
                
                st.success(f"✅ تم تحليل {len(orders_per_product)} منتج")
                st.info(f"📊 إجمالي الأوردرات: {df_clean[order_col].nunique()}")
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
                    st.metric("أكثر منتج مبيعاً", orders_per_product.iloc[0]['اسم المنتج'])
                with col2:
                    st.metric("عدد أوردراته", int(orders_per_product.iloc[0]['عدد الأوردرات']))
                with col3:
                    st.metric("نسبته من الإجمالي", f"{orders_per_product.iloc[0]['النسبة %']}%")
            else:
                st.error("❌ مش لاقي عمود المنتج أو كود الأوردر في الملف!")
                st.info(f"الأعمدة الموجودة: {', '.join(merged_df.columns.tolist())}")

# ==================== الصفحة الرابعة: تقرير المنتجات ====================
elif page == "📋 تقرير المنتجات":
    st.header("📋 تقرير المنتجات")
    st.markdown("ارفع الملف علشان تشوف كل منتج: إجمالي، تم التسليم، مرتجع 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="products_report_file")
    
    if uploaded_file:
        xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
        
        all_frames = []
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            
            product_col = None
            order_col = None
            status_col = None
            
            for col in merged_df.columns:
                if 'منتج' in str(col) or 'صنف' in str(col):
                    product_col = col
                elif 'رقم' in str(col) and 'اوردر' in str(col):
                    order_col = col
                elif 'حالة' in str(col) and 'اوردر' in str(col):
                    status_col = col
            
            if product_col and order_col and status_col:
                df_clean = merged_df[[order_col, product_col, status_col]].copy()
                df_clean = df_clean.dropna(subset=[product_col, order_col])
                df_clean[order_col] = df_clean[order_col].astype(str).str.strip()
                df_clean[product_col] = df_clean[product_col].astype(str).str.strip()
                df_clean[status_col] = df_clean[status_col].astype(str).str.strip()
                
                # إزالة المكررات
                df_clean = df_clean.drop_duplicates(subset=[order_col, product_col])
                
                # حساب الإحصائيات
                report_data = []
                for product in df_clean[product_col].unique():
                    product_orders = df_clean[df_clean[product_col] == product]
                    
                    total = len(product_orders)
                    delivered = len(product_orders[product_orders[status_col].str.contains('تم التسليم', case=False, na=False)])
                    returned = len(product_orders[product_orders[status_col].str.contains('مرتجع', case=False, na=False)])
                    
                    report_data.append({
                        'اسم المنتج': product,
                        'إجمالي الأوردرات': total,
                        'تم التسليم': delivered,
                        'مرتجع': returned,
                        'نسبة التسليم %': round((delivered / total * 100), 2) if total > 0 else 0,
                        'نسبة المرتجع %': round((returned / total * 100), 2) if total > 0 else 0
                    })
                
                report_df = pd.DataFrame(report_data)
                report_df = report_df.sort_values('إجمالي الأوردرات', ascending=False)
                
                st.success(f"✅ تم تحليل {len(report_df)} منتج")
                st.dataframe(report_df, use_container_width=True, hide_index=True)
                
                buffer = BytesIO()
                report_df.to_excel(buffer, sheet_name='تقرير المنتجات', index=False, engine='openpyxl')
                buffer.seek(0)
                
                tz = pytz.timezone('Africa/Cairo')
                today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
                file_name = f"تقرير المنتجات - {today}.xlsx"
                
                st.download_button(
                    label="📥 تحميل تقرير المنتجات",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.divider()
                st.subheader("📊 إحصائيات عامة")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("إجمالي الأوردرات", report_df['إجمالي الأوردرات'].sum())
                with col2:
                    st.metric("تم التسليم", report_df['تم التسليم'].sum())
                with col3:
                    st.metric("المرتجع", report_df['مرتجع'].sum())
            else:
                st.error("❌ مش لاقي الأعمدة المطلوبة في الملف!")
                st.info(f"الأعمدة الموجودة: {', '.join(merged_df.columns.tolist())}")

# ==================== الصفحة الخامسة: إجمالي نسب الأوردرات ====================
elif page == "👥 إجمالي نسب الأوردرات":
    st.header("👥 إجمالي نسب الأوردرات")
    st.markdown("ارفع الملف علشان تشوف كل مودريتور: إجمالي، تم التسليم، مرتجع 🔥")
    
    uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"], key="moderators_report_file")
    
    if uploaded_file:
        xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
        
        all_frames = []
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)
        
        if all_frames:
            merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
            
            moderator_col = None
            order_col = None
            status_col = None
            
            for col in merged_df.columns:
                if 'مودريتور' in str(col) or 'موظف' in str(col):
                    moderator_col = col
                elif 'رقم' in str(col) and 'اوردر' in str(col):
                    order_col = col
                elif 'حالة' in str(col) and 'اوردر' in str(col):
                    status_col = col
            
            if moderator_col and order_col and status_col:
                df_clean = merged_df[[order_col, moderator_col, status_col]].copy()
                df_clean = df_clean.dropna(subset=[moderator_col, order_col])
                df_clean[order_col] = df_clean[order_col].astype(str).str.strip()
                df_clean[moderator_col] = df_clean[moderator_col].astype(str).str.strip()
                df_clean[status_col] = df_clean[status_col].astype(str).str.strip()
                
                # إزالة المكررات
                df_clean = df_clean.drop_duplicates(subset=[order_col])
                
                # حساب الإحصائيات لكل مودريتور
                report_data = []
                for moderator in df_clean[moderator_col].unique():
                    moderator_orders = df_clean[df_clean[moderator_col] == moderator]
                    
                    total = len(moderator_orders)
                    delivered = len(moderator_orders[moderator_orders[status_col].str.contains('تم التسليم', case=False, na=False)])
                    returned = len(moderator_orders[moderator_orders[status_col].str.contains('مرتجع', case=False, na=False)])
                    
                    report_data.append({
                        'اسم المودريتور': moderator,
                        'إجمالي الأوردرات': total,
                        'تم التسليم': delivered,
                        'مرتجع': returned,
                        'نسبة التسليم %': round((delivered / total * 100), 2) if total > 0 else 0,
                        'نسبة المرتجع %': round((returned / total * 100), 2) if total > 0 else 0
                    })
                
                report_df = pd.DataFrame(report_data)
                report_df = report_df.sort_values('إجمالي الأوردرات', ascending=False)
                
                # حساب الإجمالي الكلي
                total_all = report_df['إجمالي الأوردرات'].sum()
                delivered_all = report_df['تم التسليم'].sum()
                returned_all = report_df['مرتجع'].sum()
                
                # إضافة صف الإجمالي
                total_row = pd.DataFrame([{
                    'اسم المودريتور': '📊 الإجمالي الكلي',
                    'إجمالي الأوردرات': total_all,
                    'تم التسليم': delivered_all,
                    'مرتجع': returned_all,
                    'نسبة التسليم %': round((delivered_all / total_all * 100), 2) if total_all > 0 else 0,
                    'نسبة المرتجع %': round((returned_all / total_all * 100), 2) if total_all > 0 else 0
                }])
                
                report_df = pd.concat([report_df, total_row], ignore_index=True)
                
                st.success(f"✅ تم تحليل {len(report_df)-1} مودريتور")
                st.dataframe(report_df, use_container_width=True, hide_index=True)
                
                buffer = BytesIO()
                report_df.to_excel(buffer, sheet_name='إجمالي نسب الأوردرات', index=False, engine='openpyxl')
                buffer.seek(0)
                
                tz = pytz.timezone('Africa/Cairo')
                today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
                file_name = f"إجمالي نسب الأوردرات - {today}.xlsx"
                
                st.download_button(
                    label="📥 تحميل تقرير المودريتورز",
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
                    st.metric("المرتجع", returned_all)
                with col4:
                    success_rate = round((delivered_all / total_all * 100), 2) if total_all > 0 else 0
                    st.metric("نسبة النجاح", f"{success_rate}%")
            else:
                st.error("❌ مش لاقي الأعمدة المطلوبة في الملف!")
                st.info(f"الأعمدة الموجودة: {', '.join(merged_df.columns.tolist())}")

# ==================== الصفحة السادسة: Flash Orders Processor ====================
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
