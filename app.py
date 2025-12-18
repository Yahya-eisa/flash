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
st.set_page_config(page_title="🔥 Flash Orders System", layout="wide")
st.title("🔥 Flash Orders System")

# القائمة الجانبية للاختيار
page = st.sidebar.radio(
    "اختار الوظيفة:",
    ["🔍 مراجعة الأوردرات المكررة", "📦 المشتريات المجمعة", "🚚 Flash Orders Processor"]
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
                
                # تجميع حسب اسم المنتج فقط
                product_totals = merged_df.groupby(product_col)[qty_col].sum().reset_index()
                product_totals.columns = [product_col, 'إجمالي الكمية']
                product_totals = product_totals.sort_values('إجمالي الكمية', ascending=False)
                
                # الحصول على تفاصيل الألوان والمقاسات
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

# ==================== الصفحة الثالثة: Flash Orders Processor ====================
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

