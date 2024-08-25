from flask import Flask, request, render_template, Blueprint, redirect
import pandas as pd
import re
import xlwt
import numpy as np

# Create a Blueprint
bp = Blueprint('general', __name__)

df_global = None

def read_excel(file):
    df = pd.read_excel(file, engine='openpyxl', dtype=str)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y-%m-%d %H:%M:%S')

    # Reformat the 'Timestamp' column to the desired format
    df['Timestamp'] = df['Timestamp'].dt.strftime('%b %d %y %I:%M:%S %p')
    
    df = convert_to_number(df)
    
        

    return df


def filter_by_month(df, column_name, month):
    df[column_name] = pd.to_datetime(df[column_name], format='%b %d %y %I:%M:%S %p')
    return df[df[column_name].dt.month == month]


def filter_by_column(df, column_name, value):
    if column_name in df.columns:
        return df[df[column_name].str.contains(value, case=False, na=False)]
    return df


def addition(df, row_index):
    # Calculate the total for the current row across the specified columns
    total = 0
    for col in range(9, len(df.columns)):
        col_name = df.columns[col]
        value = pd.to_numeric(df.at[row_index, col_name], errors='coerce')
        if pd.isna(value):
            value = 0
        total += value

    # Update the 'Total # of Classes' column for the current row
    df.at[row_index, 'Total # of Classes'] = total
    
    return df

def convert_to_number(df):
    column_indices = [5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

    # Convert the specified columns to numeric
    for col in column_indices:
        # Access the column by its index and convert to numeric
        df[df.columns[col]] = pd.to_numeric(df.iloc[:, col], errors='coerce')
        df[df.columns[col]] = df[df.columns[col]].fillna(0).astype('Int64')
    
    return df


def format_currency(df):
    currency_columns = ['Total $$ for the month', 'Did you work on any side projects?', 'Calculated Total Amount']
    for col in currency_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df[col] = df[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "")
    return df


def sum_and_format_numbers(df, column_name):
    # Function to extract numbers and clean text
    def extract_and_sum_numbers(text):
        # Extract numbers and remove them from text
        numbers = re.findall(r'\d+\.?\d*', text)
        # Convert extracted numbers to floats and sum them
        numbers = map(float, numbers)
        return sum(numbers)
    
    # Check if the specified column exists
    if column_name in df.columns:
        # Apply extraction and summing function
        df[column_name] = df[column_name].map(lambda x: extract_and_sum_numbers(x))
        
        # Convert the column to numeric and format as currency
        df[column_name] = pd.to_numeric(df[column_name], errors='coerce').apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "")
    
    return df

@bp.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        
        if 'file' in request.files:
            file = request.files['file']
            if file:
                try:
                    df = read_excel(file)
                except Exception as e:
                    return render_template('upload.html', error=f"Error processing file: {str(e)}")

                df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
                df = df.fillna('')
                df.insert(3, 'Calculated Total Amount', '')
                df.insert(9, 'Total # of Classes', '')
                

                global df_global
                df_global = df
                
                return redirect('/results')
    return render_template('upload.html')


@bp.route('/results', methods=['GET', 'POST'])
def results():
    global df_global
    if df_global is not None:
        df = df_global.copy()

        # Check if filters are applied
        month = int(request.form.get('month', 0))
        email_filter = request.form.get('email', '').strip()
        name_filter = request.form.get('name', '').strip()
        
        # Iterate over each row, starting from the second row
        for index in range(0, len(df)):
            df = addition(df, index)

        if request.method == 'POST':
            # Apply filters if provided
            if month != 0 and 'Timestamp' in df.columns:
                df = filter_by_month(df, 'Timestamp', month)
            if email_filter:
                df = filter_by_column(df, 'Email', email_filter)
            if name_filter:
                df = filter_by_column(df, 'Full Name', name_filter)
            
            df = sum_and_format_numbers(df, 'Any invoices/receipts?')
            df = convert_to_number(df)
            df = format_currency(df)
            
            # Convert to HTML table
            table_html = df.to_html(classes='table table-striped', index=False, na_rep='', max_rows=None, max_cols=None)
            return render_template('results.html', table_html=table_html, df_global=df)

        elif request.method == 'GET':
            # If GET request, show all data without filters
            df = sum_and_format_numbers(df, 'Any invoices/receipts?')
            df = format_currency(df)
            df = convert_to_number(df)
            
            table_html = df.to_html(classes='table table-striped', index=False, na_rep='', max_rows=None, max_cols=None)
            return render_template('results.html', table_html=table_html, df_global=df)
    return redirect('/')


@bp.route('/see_all', methods=['GET'])
def see_all():
    global df_global
    if df_global is not None:
        df = df_global.copy()
        df = sum_and_format_numbers(df, 'Any invoices/receipts?')
        df = format_currency(df)
        df = convert_to_number(df)
        

        # Render the modified DataFrame as HTML
        table_html = df.to_html(classes='table table-striped', index=False, na_rep='', max_rows=None, max_cols=None)
        return render_template('results.html', table_html=table_html, df_global=df)
    return redirect('/')

