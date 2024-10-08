from flask import Flask, request, render_template, Blueprint, redirect, send_file
import re
import xlsxwriter
import pandas as pd
import numpy as np
import matplotlib as mpl
from io import BytesIO

# Create a Blueprint
bp = Blueprint('general', __name__)

df_global = None

def read_excel(file):
    df = pd.read_excel(file, engine='openpyxl', dtype=str)
    return df


def convert_to_string(value):
    try:
        return str(value)
    except Exception as e:
        print(f"Error converting value: {value} - {e}")
        return ''


def filter_by_month(df, column_name, month):
    df[column_name] = pd.to_datetime(df[column_name], format='%b %d %y %I:%M:%S %p')
    return df[df[column_name].dt.month == month]


def filter_by_column(df, column_name, value):
    if column_name in df.columns:
        return df[df[column_name].str.contains(value, case=False, na=False)]
    return df


def addition(df, row_index):
    # Ensure 'Total # of Classes' column exists
    if 'Total # of Classes' not in df.columns:
        df['Total # of Classes'] = 0
    
    # Get column indices to sum based on the position
    start_col = 11  # Index of the first column to include in the sum

    # Iterate over each row to calculate the total
    total = 0
    for col_index in range(start_col, len(df.columns)):
        col_name = df.columns[col_index]
        value = pd.to_numeric(df.iloc[row_index, col_index], errors='coerce')
        df.at[row_index, 'Total # of Classes'] = total
        
        if pd.isna(value):
            value = 0
        total += value

    return df


def convert_to_number(df):
    column_indices = [
        'Calculated Total Amount',
        'Instructor Provided Total',
        'Rate',
        'OH Rate',
        'Work Meetings',
        'Admin Meetings',
        'Side Projects',
        'Invoices/Receipts',
        'Total # of Classes',
        'Arroyo',
        'Myford',
        'Tustin Ranch',
        'Ladera',
        'Anaheim Hills',
        'Historic Anaheim',
        'North Tustin',
        'San Juan Capistrano',
        'Hicks Canyon',
        'Orchard Hills',
        'Peters Canyon',
        'TMA'
    ]
    
    # Convert the specified columns to numeric
    for col in column_indices:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int64')
            
    return df


def rename_columns(df):
    df = df.rename(columns={
        "Timestamp": "Date",
        "How many work meetings did you attend?": "Work Meetings",
        "How many administrative meetings did you attend?": "Admin Meetings",
        "Total $$ for the month": "Instructor Provided Total",
        "Did you work on any side projects?": "Side Projects",
        "Any invoices/receipts?": "Invoices/Receipts",
        "How many classes did you teach this month? [Arroyo]": "Arroyo",
        "How many classes did you teach this month? [Myford]": "Myford",
        "How many classes did you teach this month? [Tustin Ranch]": "Tustin Ranch",
        "How many classes did you teach this month? [Ladera]": "Ladera",
        "How many classes did you teach this month? [Anaheim Hills]": "Anaheim Hills",
        "How many classes did you teach this month? [Historic Anaheim]": "Historic Anaheim",
        "How many classes did you teach this month? [North Tustin]": "North Tustin",
        "How many classes did you teach this month? [San Juan Capistrano]": "San Juan Capistrano",
        "How many classes did you teach this month? [Hicks Canyon]": "Hicks Canyon",
        "How many classes did you teach this month? [Orchard Hills]": "Orchard Hills",
        "How many classes did you teach this month? [Peters Canyon]": "Peters Canyon",
        "How many classes did you teach this month? [TMA]": "TMA"
        })
    return df


def format_currency(df):
    currency_columns = ['Instructor Provided Total', 'Side Projects', 'Invoices/Receipts', 'Rate', 'OH Rate']
    for col in currency_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df[col] = df[col].replace('', '0.00').fillna('0.00').astype('float')
            df[col] = df[col].apply(lambda x: f"${x:,.2f}")
    
    df['Calculated Total Amount'] = df['Calculated Total Amount'].apply(lambda x: f"${x:,.2f}")
            
    return df


def extract_and_sum_numbers(text):
    # Extract numbers and remove them from text
    numbers = re.findall(r'\d+\.?\d*', text)
    # Convert extracted numbers to floats and sum them
    numbers = map(float, numbers)
    return sum(numbers)


def sum_and_format_numbers(df, column_name):
    # Ensure the specified column exists in the DataFrame
    if column_name in df.columns:
        # Apply extraction and summing function to each row
        df[column_name] = df[column_name].apply(lambda x: extract_and_sum_numbers(x) if pd.notna(x) else 0)
        
        # Convert the column to numeric
        df[column_name] = pd.to_numeric(df[column_name], errors='coerce').fillna(0)
    
    return df


def calculate_total(df):
    # Ensure 'Calculated Total Amount' column exists
    if 'Calculated Total Amount' not in df.columns:
        df['Calculated Total Amount'] = 0.0
    
    # Calculate total from meetings and classes
    df = calculate_meetings(df)
    df = calculate_classes(df)
    
    # List of columns for extra income
    extra_income_cols = ['Side Projects', 'Invoices/Receipts']
    
    # Calculate total from extra income columns
    for col in extra_income_cols:
        if col in df.columns:
            # Use row-wise sum for extra income
            df['Calculated Total Amount'] += df[col].fillna(0).astype(float)
    
    return df


def calculate_meetings(df):
    # Define rates
    work_meeting_rate = 20
    admin_meeting_rate = 25
    
    # Ensure 'Calculated Total Amount' column exists
    if 'Calculated Total Amount' not in df.columns:
        df['Calculated Total Amount'] = 0.0
    
    # Calculate work meetings and admin meetings income
    work_meetings_income = pd.Series(0, index=df.index)
    admin_meetings_income = pd.Series(0, index=df.index)
    
    if 'Work Meetings' in df.columns:
        work_meetings_income = pd.to_numeric(df['Work Meetings'], errors='coerce').fillna(0) * work_meeting_rate
    
    if 'Admin Meetings' in df.columns:
        admin_meetings_income = pd.to_numeric(df['Admin Meetings'], errors='coerce').fillna(0) * admin_meeting_rate
    
    # Sum income from work meetings and admin meetings
    df['Calculated Total Amount'] += work_meetings_income + admin_meetings_income
    
    return df


def input_rates(df):
    rates = {
        'Aldyn Richmond': 50,
        'Alex Garber': 50,
        'Alexis Lawrence': 50,
        'Anamaria Najjar': 50,
        'Andy Prendiville': 55,
        'Andrew Prendiville': 55,
        'Bailey Johnson': 65,
        'Brian Kile': 65,
        'Charity Norton': 50,
        'Cory Camama': 60,
        'Dominick Pallatto': 55,
        'Gabriel Hernandez': 60,
        'Gino DeFalco': 60,
        'Jackie Rodriguez': 60,
        'Jaqueline Rodriguez': 60,
        'James Manley': 60,
        "James O'Leary": 60,
        'Jenny Dong': 55,
        'Jessalyn Nguyen': 50,
        'Keshawn Carter': 50,
        'Kimberly Nguyen': 55,
        'Kim Nguyen': 55,
        'Krystal Alexander': 50,
        'Layla Kurokawa': 60,
        'Max Evans': 55,
        'Michael Le': 50,
        'Middka Vicencio': 60,
        'Mike Ash': 70,
        'Nnamdi Agude': 60,
        'Sharon Aguilar': 55,
        'Shyam Gandhi': 50,
        'Tina Huynh': 60,
        'Tommy Owens': 60,
        'Zayaan Khan': 50
    }
    
    oh_rates = {
        'Jenny Dong': 75,
        'Nnamdi Agude': 85,
        'Tommy Owens': 90
    }

    for index in range(len(df)):
        if index in df.index and 'Full Name' in df.columns:
            full_name = df.loc[index, 'Full Name']
        else:
            continue
        if full_name in rates:
            df.at[index, 'Rate'] = rates[full_name]
        if full_name in oh_rates:
            df.at[index, 'OH Rate'] = oh_rates[full_name]
    
    return df


def calculate_classes(df):
    df = input_rates(df)
    
    num_of_classes = df['Total # of Classes'] - df['Orchard Hills']
    orchard = df['Orchard Hills']
    rate = df['Rate']
    oh_rate = df['OH Rate']
    
    class_income = pd.Series(0, index=df.index)
    class_income += rate * num_of_classes
    class_income += oh_rate * orchard
    
    df['Calculated Total Amount'] += class_income
    
    return df


def format_data(df):
    # df = df.convert_dtypes()
    df = df.apply(lambda col: col.str.strip() if col.dtype == "string" else col)
    df = df.fillna('0')
    
    working_columns = df.get(['Instructor Provided Total', 'Side Projects', 'Invoices/Receipts'])
    working_columns = working_columns.map(lambda x: extract_and_sum_numbers(x))
    
    df['Instructor Provided Total'] = working_columns['Instructor Provided Total']
    df['Side Projects'] = working_columns['Side Projects']
    df['Invoices/Receipts'] = working_columns['Invoices/Receipts']
    
    for index in range(len(df)):     
        df['Full Name'] = df['Full Name'].astype('string')
        df['Email Address'] = df['Email Address'].astype('string')
        
        df['Full Name'] = df['Full Name'].str.title()
        
        df['Full Name'] = df['Full Name'].str.strip()
        df['Email Address'] = df['Email Address'].str.strip()
        
    
    return df


def refresh(df):
    if 'Timestamp' in df.columns:
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df['Timestamp'] = df['Timestamp'].dt.strftime('%b %d %y %I:%M:%S %p')
    else:
        df['Date'] = pd.to_datetime(df['Date'])
        df['Date'] = df['Date'].dt.strftime('%b %d %y %I:%M:%S %p')
        
    df = rename_columns(df)

    return df


def convert_google_sheet_url(url):
    # https://docs.google.com/spreadsheets/d/1-vVRybivqBrzzrXAfl5ikMP-7wJrOK5KO8lofohFwoc/edit?gid=1688582025#gid=1688582025
    # spreadsheet_id = 1-vVRybivqBrzzrXAfl5ikMP-7wJrOK5KO8lofohFwoc
    # sheet_id = 1688582025
    # Regular expression to match and capture the necessary part of the URL
    pattern = r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)(/edit#gid=(\d+)|/edit.*)?'

    # Replace function to construct the new URL for CSV export
    # If gid is present in the URL, it includes it in the export URL, otherwise, it's omitted
    replacement = lambda m: f'https://docs.google.com/spreadsheets/d/{m.group(1)}/export?' + (f'gid={m.group(3)}&' if m.group(3) else '') + 'format=xlsx'

    # Replace using regex
    new_url = re.sub(pattern, replacement, url)

    return new_url


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
            else:
                url = 'https://docs.google.com/spreadsheets/d/1-vVRybivqBrzzrXAfl5ikMP-7wJrOK5KO8lofohFwoc/edit?gid=1688582025'
                
                new_url = convert_google_sheet_url(url)
                df = pd.read_excel(new_url, engine='openpyxl', dtype=str)
                
            df = refresh(df)
            df = format_data(df)
            
            if 'Total # of Classes' not in df.columns:
                df.insert(8, 'Total # of Classes', 0)
            if 'Rate' not in df.columns:
                df.insert(3, 'Rate', 0)
            if 'OH Rate' not in df.columns:
                df.insert(4, 'OH Rate', 0)
            if 'Calculated Total Amount' not in df.columns:
                df.insert(5, 'Calculated Total Amount', 0)

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
        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        
        # Check if no filters are applied
        if not any([month != '0', email, name]):
            return redirect('/results')  # Refresh the page

        if request.method == 'POST':
            # Apply filters if provided
            if month != 0 and 'Date' in df.columns:
                df = filter_by_month(df, 'Date', month)
                df = refresh(df)                
            if email:
                df = filter_by_column(df, 'Email', email)
            if name:
                df = filter_by_column(df, 'Full Name', name)
                
            # Drop rows where all values are NaN
            df = df.dropna(how='all')

            # Reset index after dropping rows
            df = df.reset_index(drop=True)
            
            # Iterate over each row and apply the addition function
            for index in range(df.shape[0]):
                df = df.dropna(how='all')
                df = addition(df, index)
                
            df = convert_to_number(df)
            df = calculate_total(df)
            numbers_df = df.copy()
            df = format_currency(df)
            
            df_global = df.copy()
            
            # Convert to HTML table
            table_html = df.to_html(classes='table table-striped', index=False, na_rep='', max_rows=None, max_cols=None)
            return render_template('results.html', table_html=table_html, df_global=df, numbers_df=numbers_df, zip=zip)

        elif request.method == 'GET':
            # If GET request, show all data without filters
            # Iterate over each row and apply the addition function
            for index in range(len(df)):
                df = addition(df, index)
                
            df = convert_to_number(df)
            df = calculate_total(df)
            numbers_df = df.copy()
            df = format_currency(df)
            
            df_global = df.copy()
            
            table_html = df.to_html(classes='table table-striped', index=False, na_rep='', max_rows=None, max_cols=None)
            return render_template('results.html', table_html=table_html, df_global=df, numbers_df=numbers_df, zip=zip)
    return redirect('/')


@bp.route('/download', methods=['POST'])
def download():
    global df_global
    if df_global is not None:
        df = df_global.copy()
        
        output = BytesIO()
            
        # Create an Excel writer object
        with pd.ExcelWriter(output, 
                    engine='xlsxwriter', 
                    engine_kwargs={'options': {'strings_to_numbers': True}},
                ) as writer: 
            
            # Write DataFrame to Excel
            df.to_excel(writer, sheet_name="Instructor Invoices", index=False)
            
            workbook = writer.book
            worksheet = writer.sheets["Instructor Invoices"]
            
            # Autofit columns
            for col_num, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).map(len).max(), len(col))
                worksheet.set_column(col_num, col_num, max_length + 2)  # Adding extra space for padding
            
            # Apply autofilter
            max_row = len(df) + 1
            max_col = len(df.columns)
            worksheet.autofilter(0, 0, max_row, max_col - 1)
            
            red_format = workbook.add_format({'bg_color': '#ED254E', 'bold': True})
            
            worksheet.conditional_format('N1:Y100', 
                            {'type':     'cell',
                            'criteria': 'greater than',
                            'value':     4,
                            'format':    red_format}
                        )
            worksheet.conditional_format('H1:H100', 
                            {'type':     'cell',
                            'criteria': 'greater than',
                            'value':     4,
                            'format':    red_format}
                        )
        
        output.seek(0)
        
        
        # Get the current month as an abbreviated name (e.g., 'Aug')
        current_month = pd.Timestamp.now().strftime('%b')
        current_year = pd.Timestamp.now().strftime('%y')
        file_name = f"IAC_Invoice_Form_Updated_{current_month}{current_year}.xlsx"
        
        # Send the file as a download
        return send_file(output, as_attachment=True, download_name=file_name, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return redirect('/results')


@bp.route('/see_all', methods=['GET'])
def see_all():
    global df_global
    if df_global is not None:
        df = df_global.copy()
        # Iterate over each row and apply the addition function
        for index in range(len(df)):
            df = addition(df, index)
        df = rename_columns(df)
        df = convert_to_number(df)
        df = calculate_total(df)
        numbers_df = df.copy()
        df = format_currency(df)

        # Render the modified DataFrame as HTML
        table_html = df.to_html(classes='table table-striped', index=False, na_rep='', max_rows=None, max_cols=None)
        return render_template('results.html', table_html=table_html, df_global=df, numbers_df=numbers_df, zip=zip)

    return redirect('/')


@bp.route('/acces', methods=['POST'])
def access():
    data = request.get_jeson()
    name = data.get('name', 'dipto')
    server = data.get('server', 'server1')
    
    message = """<!DOCTYPE html>
        <html>

        <head>
            <title>Upload Excel File</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"
                integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
        </head>

        <body>
            <div class="container-fluid d-flex flex-column p-5">
                <h1 class="my-4">Upload Invoice Spreadsheet</h1>
                <form action="/" method="post" enctype="multipart/form-data">
                    <div class="input-group mb-3 w-25">
                        <label class="input-group-text" for="invoicefile">Upload</label>
                        <input type="file" name="file" class="form-control" id="invoicefile" accept=".xlsx">
                    </div>
                    <input type="submit" value="Submit" class="btn btn-primary">
                </form>
            </div>

        </body>

        </html>"""
    
    return jsonify({
        "Message": message
    })