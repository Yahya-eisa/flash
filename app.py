import streamlit as st
import pandas as pd
from io import BytesIO
import datetime
import pytz

st.set_page_config(page_title="📦 المشتريات المجمعة", layout="wide")
st.title("📦 المشتريات المجمعة")
st.markdown("ارفع الملف وخد المشتريات على طول 🔥")

uploaded_file = st.file_uploader("📤 ارفع ملف Excel", type=["xlsx"])

if uploaded_file:
    # قراءة الملف
    xls = pd.read_excel(uploaded_file, sheet_name=None, engine="openpyxl", dtype=str)
    
    all_frames = []
    for _, df in xls.items():
        df = df.dropna(how="all")
        all_frames.append(df)
    
    if all_frames:
        merged_df = pd.concat(all_frames, ignore_index=True, sort=False)
        
        # تحديد أسماء الأعمدة
        product_col = None
        color_col = None
        size_col = None
        qty_col = None
        
        # البحث عن الأعمدة
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
            # تحويل الكمية لأرقام
            merged_df[qty_col] = pd.to_numeric(merged_df[qty_col], errors='coerce').fillna(0)
            
            # الخطوة 1: تجميع حسب اسم المنتج فقط
            product_totals = merged_df.groupby(product_col)[qty_col].sum().reset_index()
            product_totals.columns = [product_col, 'إجمالي الكمية']
            product_totals = product_totals.sort_values('إجمالي الكمية', ascending=False)
            
            # الخطوة 2: الحصول على تفاصيل الألوان والمقاسات لكل منتج
            if color_col and size_col and color_col in merged_df.columns and size_col in merged_df.columns:
                variations = merged_df.groupby(product_col).apply(
                    lambda x: x.groupby([color_col, size_col])[qty_col].sum().reset_index()
                ).reset_index(drop=True)
                
                # إنشاء عمود يحتوي على تفاصيل الألوان والمقاسات
                variation_details = []
                for product_name in product_totals[product_col]:
                    product_data = merged_df[merged_df[product_col] == product_name]
                    details_list = []
                    
                    if color_col and size_col and color_col in product_data.columns and size_col in product_data.columns:
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
            
            # عرض النتيجة
            st.success(f"✅ تم تجميع {len(product_totals)} منتج")
            st.dataframe(product_totals, use_container_width=True, hide_index=True)
            
            # تحميل الملف
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
