import streamlit as st
import pandas as pd
import datetime
import io
from io import BytesIO
import pytz
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# ---------- Arabic helpers ----------
def fix_arabic(text):
    if pd.isna(text):
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

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

def replace_muaaqal_with_confirm_safe(df):
    return df.replace('معلق', 'تم التأكيد')

def fill_down(series):
    return series.ffill()

def df_to_pdf_table(df, title="FLASH"):
    # تنسيق رقم الموبايل فقط
    if 'رقم موبايل العميل' in df.columns:
        df['رقم موبايل العميل'] = df['رقم موبايل العميل'].apply(
            lambda x: str(int(float(x))) if pd.notna(x) and str(x).replace('.','',1).isdigit()
            else ("" if pd.isna(x) else str(x))
        )
    
    # تحويل الأرقام للأعمدة العددية فقط
    numeric_cols = {'عدد القطع', 'الكمية'}
    for col in df.columns:
        if col in numeric_cols:
            df[col] = df[col].apply(
                lambda x: str(int(float(x))) if pd.notna(x) and str(x).replace('.','',1).isdigit()
                else ("" if pd.isna(x) else str(x))
            )

    # الخط والـ styles
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

    # ✅ توزيع عرض الأعمدة - متكيف مع عدد الأعمدة الفعلي
    base_col_widths_cm = [2, 2.5, 2, 3, 2, 2.5, 1.5, 1.5, 2.5, 3, 1.5, 1.5, 1, 1.5, 1.5]
    n_cols = len(df.columns)

    if n_cols <= len(base_col_widths_cm):
        col_widths_cm = base_col_widths_cm[:n_cols]
    else:
        # لو عندنا أعمدة زيادة نكرر آخر مقاس
        extra = n_cols - len(base_col_widths_cm)
        col_widths_cm = base_col_widths_cm + [base_col_widths_cm[-1]] * extra

    col_widths = [max(c * 28.35, 15) for c in col_widths_cm]

    tz = pytz.timezone('Africa/Cairo')
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    title_text = f"{title} | FLASH | {today}"

    elements = [
        Paragraph(fix_arabic(title_text), styleTitle),
        Spacer(1, 14)
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)
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
st.set_page_config(page_title="🔥 Flash Orders Processor", layout="wide")
st.title("🔥 Flash Orders Processor")
st.markdown("....ارفع الملفات يا رايق علشان تستلم الشيت")

# ============ الجزء الأول: رفع وتحضير البيانات ============
uploaded_files = st.file_uploader(
    "📤 Upload Excel files (.xlsx)",
    accept_multiple_files=True,
    type=["xlsx"]
)

if uploaded_files:
    all_frames = []
    for file in uploaded_files:
        xls = pd.read_excel(file, sheet_name=None, engine="openpyxl", dtype=str)
        for _, df in xls.items():
            df = df.dropna(how="all")
            all_frames.append(df)

    if all_frames:
        merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
        
        column_mapping = {
            ' الرقم العشوائي': 'كود الاوردر',
            'الإسم': 'اسم العميل',
            'العنوان': 'العنوان',
            'المدينة': 'المدينة',
            'موبايل(1)': 'رقم موبايل العميل',
            'حالة الاوردر': 'حالة الاوردر',
            'ملاحظة الافيليت علي الطلب': 'الملاحظات',
            'اسم المنتج': 'اسم الصنف',
            'اللون': 'اللون',
            'المقاس': 'المقاس',
            'الكمية': 'الكمية',
            'Total': 'الإجمالي مع الشحن'
        }
        
        merged_df = merged_df.rename(columns=column_mapping)
        
        required_cols = ['كود الاوردر', 'اسم العميل', 'العنوان', 'المدينة', 
                        'رقم موبايل العميل', 'حالة الاوردر', 'الملاحظات', 
                        'اسم الصنف', 'اللون', 'المقاس', 'الكمية', 'الإجمالي مع الشحن']
        
        merged_df = merged_df[[c for c in required_cols if c in merged_df.columns]].copy()
        
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
        
        if 'كود الاوردر' in merged_df.columns and 'الكمية' in merged_df.columns:
            merged_df['الكمية'] = pd.to_numeric(merged_df['الكمية'], errors='coerce').fillna(0)
            order_total_qty = merged_df.groupby('كود الاوردر')['الكمية'].transform('sum')
            merged_df.insert(7, 'عدد القطع', order_total_qty)
        
        merged_df['المنطقة'] = merged_df['المدينة'].apply(classify_city)
        
        final_order = ['كود الاوردر', 'اسم العميل', 'المنطقة', 'العنوان', 'المدينة',
                      'رقم موبايل العميل', 'حالة الاوردر', 'عدد القطع', 'الملاحظات',
                      'اسم الصنف', 'اللون', 'المقاس', 'الكمية', 'الإجمالي مع الشحن']
        
        merged_df = merged_df[[c for c in final_order if c in merged_df.columns]].copy()
        
        merged_df['المنطقة'] = pd.Categorical(
            merged_df['المنطقة'],
            categories=[c for c in merged_df['المنطقة'].unique() if c != "Other City"] + ["Other City"],
            ordered=True
        )
        merged_df = merged_df.sort_values(['المنطقة','كود الاوردر'])
        
        cols_to_clear = ['اسم العميل', 'العنوان', 'المدينة', 'رقم موبايل العميل', 
                        'حالة الاوردر', 'عدد القطع', 'الملاحظات', 'الإجمالي مع الشحن']
        
        merged_df['is_first'] = ~merged_df.duplicated(subset=['كود الاوردر'], keep='first')
        
        for col in cols_to_clear:
            if col in merged_df.columns:
                merged_df.loc[~merged_df['is_first'], col] = ''
        
        merged_df = merged_df.drop(columns=['is_first'])
        
        # ============ الجزء الأول: تحميل الشيت للتعديل ============
        st.divider()
        st.subheader("📋 الجزء الأول: البيانات المنظفة (للتعديل)")
        
        buffer_clean = BytesIO()
        merged_df.to_excel(buffer_clean, sheet_name='البيانات المنظفة', index=False, engine='openpyxl')
        buffer_clean.seek(0)
        
        tz = pytz.timezone('Africa/Cairo')
        today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
        file_name_clean = f"البيانات المنظفة - {today}.xlsx"
        
        st.info("✅ احفظ الملف، عدّل فيه، ورفعه بعدين للخطوة الثانية")
        st.download_button(
            label="⬇️ تحميل البيانات المنظفة (للتعديل)",
            data=buffer_clean.getvalue(),
            file_name=file_name_clean,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_clean"
        )
        
        # ============ الجزء الثاني: رفع الملف المعدّل وتقسيم المناطق ============
        st.divider()
        st.subheader("🔄 الجزء الثاني: رفع الملف المعدّل وتقسيم المناطق")
        
        edited_file = st.file_uploader(
            "📤 رفع الملف بعد التعديل",
            type=["xlsx"],
            key="edited_upload"
        )
        
        if edited_file:
            # قراءة الملف المعدّل
            edited_df = pd.read_excel(edited_file, sheet_name='البيانات المنظفة', engine="openpyxl", dtype=str)
            
            st.success("✅ تم قراءة الملف المعدّل بنجاح!")
            
            # ✅ إنشاء PDF بـ كل منطقة بـ جداول + عمود المنطقة
            pdfmetrics.registerFont(TTFont('Arabic', 'Amiri-Regular.ttf'))
            pdfmetrics.registerFont(TTFont('Arabic-Bold', 'Amiri-Bold.ttf'))
            
            buffer_pdf = BytesIO()
            doc = SimpleDocTemplate(
                buffer_pdf,
                pagesize=landscape(A4),
                leftMargin=15, rightMargin=15, topMargin=15, bottomMargin=15
            )
            elements = []
            
            # تقسيم البيانات حسب المنطقة
            if 'المنطقة' in edited_df.columns:
                for area_name in edited_df['المنطقة'].unique():
                    if pd.notna(area_name):
                        area_df = edited_df[edited_df['المنطقة'] == area_name].copy()
                        # ✅ احتفظ بعمود المنطقة (ما نمسحش)
                        elements.extend(df_to_pdf_table(area_df.copy(), title=str(area_name)))
            
            doc.build(elements)
            buffer_pdf.seek(0)
            
            file_name_pdf = f"سواقين فلاش - {today}.pdf"
            
            # ✅ مباشرة زر التحميل بس
            st.download_button(
                label="⬇️⬇️ تحميل ملف PDF النهائي (المناطق)",
                data=buffer_pdf.getvalue(),
                file_name=file_name_pdf,
                mime="application/pdf",
                key="download_pdf"
            )
