import gradio as gr
import pandas as pd
import os
import speech_recognition as sr
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import numpy as np

# -------------------------------
# Global Data and Configurations
# -------------------------------
inventory = {}
transactions = []
sales = []
admin_credentials = {"harsh": "harsh"}
user_credentials = {"user": "user"}
logged_in_user = None
user_role = None
INVENTORY_CSV = "inventory.csv"
TRANSACTIONS_CSV = "transactions.csv"
SALES_CSV = "sales.csv"
INVENTORY_PDF = "inventory_report.pdf"

# -------------------------------
# Data Loading and Saving Methods
# -------------------------------
def load_data():
    global inventory, transactions, sales
    try:
        inventory_df = pd.read_csv(INVENTORY_CSV)
        inventory = {row['Product Name']: {'Price': row['Price'], 'Category': row['Category'], 'Stock': row['Stock']} for _, row in inventory_df.iterrows()}
    except FileNotFoundError:
        inventory = {}
        pd.DataFrame(columns=['Product Name', 'Price', 'Category', 'Stock']).to_csv(INVENTORY_CSV, index=False)
    
    try:
        transactions_df = pd.read_csv(TRANSACTIONS_CSV)
        transactions = [tuple(x) for x in transactions_df.values]
    except FileNotFoundError:
        transactions = []
        pd.DataFrame(columns=["Transaction ID", "Action", "Product Name", "Quantity", "User", "Timestamp"]).to_csv(TRANSACTIONS_CSV, index=False)

    try:
        sales_df = pd.read_csv(SALES_CSV)
        sales = [tuple(x) for x in sales_df.values]
    except FileNotFoundError:
        sales = []
        pd.DataFrame(columns=["Sale ID", "Product Name", "Quantity", "Sale Timestamp"]).to_csv(SALES_CSV, index=False)

# -------------------------------
# Authentication Methods
# -------------------------------
def login(username, password):
    global logged_in_user, user_role
    if username in admin_credentials and admin_credentials[username] == password:
        logged_in_user = username
        user_role = "admin"
        return "Admin login successful"
    elif username in user_credentials and user_credentials[username] == password:
        logged_in_user = username
        user_role = "user"
        return "User login successful"
    return "Invalid credentials"

def logout():
    global logged_in_user, user_role
    logged_in_user = None
    user_role = None
    return "Logged out successfully"

def is_admin():
    return user_role == "admin"

def is_logged_in():
    return logged_in_user is not None

# -------------------------------
# CRUD Operations for Inventory
# -------------------------------
def add_product(product_name, price, category, stock):
    if not is_logged_in():
        return "Please login to perform this action"
    if not is_admin():
        return "Admin access required"
    if product_name in inventory:
        return "Product already exists"
    inventory[product_name] = {'Price': price, 'Category': category, 'Stock': stock}
    save_inventory()
    log_transaction("Add", product_name, stock)
    return f"Product '{product_name}' added successfully."

def update_product(product_name, price, category, stock):
    if not is_logged_in():
        return "Please login to perform this action"
    if not is_admin():
        return "Admin access required"
    if product_name not in inventory:
        return "Product not found"
    inventory[product_name] = {'Price': price, 'Category': category, 'Stock': stock}
    save_inventory()
    log_transaction("Update", product_name, stock)
    return f"Product '{product_name}' updated successfully."

def delete_product(product_name):
    if not is_logged_in():
        return "Please login to perform this action"
    if not is_admin():
        return "Admin access required"
    if product_name not in inventory:
        return "Product not found"
    del inventory[product_name]
    save_inventory()
    log_transaction("Delete", product_name, 0)
    return f"Product '{product_name}' deleted successfully."

def view_inventory():
    if not is_logged_in():
        return "Please login to view the inventory"
    df = pd.DataFrame.from_dict(inventory, orient='index')
    df.reset_index(inplace=True)
    df.columns = ['Product Name', 'Price', 'Category', 'Stock']
    return df

# -------------------------------
# Search and Filter
# -------------------------------
def search_products_by_category(category=None):
    if not is_logged_in():
        return "Please login to search products"
    filtered_inventory = inventory
    if category:
        filtered_inventory = {k: v for k, v in filtered_inventory.items() if category.lower() in v['Category'].lower()}
    df = pd.DataFrame.from_dict(filtered_inventory, orient='index')
    df.reset_index(inplace=True)
    df.columns = ['Product Name', 'Price', 'Category', 'Stock']
    return df

# Voice recognition for search
def voice_search():
    if not is_logged_in():
        return "Please login to use voice search"
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source)
        try:
            category = recognizer.recognize_google(audio)
            print(f"Recognized: {category}")
            return category
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError as e:
            return f"Could not request results; {e}"

# -------------------------------
# Stock Management
# -------------------------------
def low_stock_alerts(threshold=10):
    if not is_logged_in():
        return "Please login to view low stock alerts"
    low_stock_items = {product: details for product, details in inventory.items() if details['Stock'] <= threshold}
    df = pd.DataFrame.from_dict(low_stock_items, orient='index')
    df.reset_index(inplace=True)
    df.columns = ['Product Name', 'Price', 'Category', 'Stock']
    return df

# -------------------------------
# Bulk Export
# -------------------------------
def export_inventory():
    if not is_logged_in():
        return "Please login to export the inventory"
    return INVENTORY_CSV

def export_inventory_pdf():
    if not is_logged_in():
        return "Please login to export the inventory"
    df = pd.DataFrame.from_dict(inventory, orient='index')
    df.reset_index(inplace=True)
    df.columns = ['Product Name', 'Price', 'Category', 'Stock']

    fig, ax = plt.subplots(figsize=(10, 6))
    df['Stock'].plot(kind='bar', ax=ax)
    ax.set_title('Stock Levels by Product')
    ax.set_xlabel('Product')
    ax.set_ylabel('Stock')
    plt.xticks(ticks=range(len(df)), labels=df['Product Name'], rotation=90)
    plt.tight_layout()
    plt.savefig('stock_levels.png')
    plt.close(fig)

    c = canvas.Canvas(INVENTORY_PDF, pagesize=landscape(letter))
    width, height = landscape(letter)
    c.drawString(30, height - 40, "Inventory Report")
    c.drawString(30, height - 60, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Table Header
    c.drawString(30, height - 100, "Product Name")
    c.drawString(200, height - 100, "Price")
    c.drawString(300, height - 100, "Category")
    c.drawString(400, height - 100, "Stock")
    
    y = height - 120
    for index, row in df.iterrows():
        c.drawString(30, y, str(row['Product Name']))
        c.drawString(200, y, f"${row['Price']:.2f}")
        c.drawString(300, y, str(row['Category']))
        c.drawString(400, y, str(row['Stock']))
        y -= 20
        if y < 40:
            c.showPage()
            y = height - 40

    c.drawImage('stock_levels.png', 30, y - 300, width - 60, 300)
    c.showPage()
    
    c.save()
    os.remove('stock_levels.png')
    return INVENTORY_PDF

# -------------------------------
# Product Sorting
# -------------------------------
def sort_inventory(by, order):
    if not is_logged_in():
        return "Please login to sort the inventory"
    df = pd.DataFrame.from_dict(inventory, orient='index')
    df.reset_index(inplace=True)
    df.columns = ['Product Name', 'Price', 'Category', 'Stock']
    if by in df.columns:
        df.sort_values(by=by, ascending=(order == 'asc'), inplace=True)
    return df

# -------------------------------
# Transaction History
# -------------------------------
def log_transaction(action, product_name, quantity):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    transactions.append((len(transactions)+1, action, product_name, quantity, logged_in_user, timestamp))
    save_transactions()

def view_transactions():
    if not is_logged_in():
        return "Please login to view transactions"
    df = pd.DataFrame(transactions, columns=["Transaction ID", "Action", "Product Name", "Quantity", "User", "Timestamp"])
    return df

# -------------------------------
# Sales Management
# -------------------------------
def sale_product(product_name, quantity):
    if not is_logged_in():
        return "Please login to perform this action"
    if product_name not in inventory:
        return "Product not found"
    if inventory[product_name]['Stock'] < quantity:
        return "Insufficient stock"
    
    inventory[product_name]['Stock'] -= quantity
    save_inventory()
    sale_id = len(sales) + 1
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sales.append((sale_id, product_name, quantity, timestamp))
    save_sales()
    return f"Sold {quantity} of '{product_name}'"

def save_sales():
    sales_df = pd.DataFrame(sales, columns=["Sale ID", "Product Name", "Quantity", "Sale Timestamp"])
    sales_df.to_csv(SALES_CSV, index=False)

# -------------------------------
# Sales Prediction
# -------------------------------
def predict_sales(product_name, periods=12):
    if not is_logged_in():
        return "Please login to perform this action"
    sales_df = pd.DataFrame(sales, columns=["Sale ID", "Product Name", "Quantity", "Sale Timestamp"])
    sales_df['Sale Timestamp'] = pd.to_datetime(sales_df['Sale Timestamp'])
    sales_df = sales_df[sales_df['Product Name'] == product_name]
    sales_df = sales_df.set_index('Sale Timestamp').resample('M').sum().fillna(0)
    
    sales_df.reset_index(inplace=True)
    sales_df['Month'] = sales_df['Sale Timestamp'].dt.month
    sales_df['Year'] = sales_df['Sale Timestamp'].dt.year
    sales_df['Time'] = sales_df['Year'] * 12 + sales_df['Month']
    sales_df['Time'] -= sales_df['Time'].min()

    X = sales_df[['Time']]
    y = sales_df['Quantity']

    model = LinearRegression()
    model.fit(X, y)

    future_time = np.arange(sales_df['Time'].max() + 1, sales_df['Time'].max() + periods + 1)
    future_sales = model.predict(future_time.reshape(-1, 1))

    plt.figure(figsize=(10, 6))
    plt.plot(sales_df['Sale Timestamp'], sales_df['Quantity'], label='Historical Sales')
    future_dates = pd.date_range(sales_df['Sale Timestamp'].max(), periods=periods, freq='M')
    plt.plot(future_dates, future_sales, label='Predicted Sales')
    plt.xlabel('Date')
    plt.ylabel('Quantity Sold')
    plt.title(f'Sales Prediction for {product_name}')
    plt.legend()
    plt.grid(True)
    
    plt.savefig('sales_prediction.png')
    return 'sales_prediction.png'

# -------------------------------
# Main: Load data and start server
# -------------------------------
load_data()

# Gradio Interface
def login_wrapper(username, password):
    return login(username, password)

def logout_wrapper():
    return logout()

iface = gr.Blocks()

with iface:
    gr.Markdown("<h1 style='text-align: center; color: #4CAF50;'>Inventory Management System</h1>")
    
    with gr.Tab("Login"):
        gr.Markdown("## Login", elem_id="subheader")
        username = gr.Textbox(label="Username")
        password = gr.Textbox(label="Password", type="password")
        login_button = gr.Button("Login")
        login_output = gr.Textbox(label="Output")
        login_button.click(login_wrapper, inputs=[username, password], outputs=login_output)
    
    with gr.Tab("Logout"):
        gr.Markdown("## Logout", elem_id="subheader")
        logout_button = gr.Button("Logout")
        logout_output = gr.Textbox(label="Output")
        logout_button.click(logout_wrapper, outputs=logout_output)

    with gr.Tab("Sale Product"):
        gr.Markdown("## Sale Product", elem_id="subheader")
        product_names = list(inventory.keys())
        sale_product_name = gr.Dropdown(choices=product_names, label="Product Name")
        sale_quantity = gr.Number(label="Quantity")
        sale_button = gr.Button("Sale Product")
        sale_output = gr.Textbox(label="Output")
        sale_button.click(sale_product, inputs=[sale_product_name, sale_quantity], outputs=sale_output)
    
    with gr.Tab("View Inventory"):
        gr.Markdown("## View Inventory", elem_id="subheader")
        view_inv_button = gr.Button("View Inventory")
        view_inv_output = gr.DataFrame(label="Inventory")
        view_inv_button.click(view_inventory, outputs=view_inv_output)
    
    with gr.Tab("Add Product"):
        gr.Markdown("## Add Product", elem_id="subheader")
        product_name = gr.Textbox(label="Product Name")
        price = gr.Number(label="Price")
        category = gr.Textbox(label="Category")
        stock = gr.Number(label="Stock")
        add_button = gr.Button("Add Product")
        add_output = gr.Textbox(label="Output")
        add_button.click(add_product, inputs=[product_name, price, category, stock], outputs=add_output)
    
    with gr.Tab("Update Product"):
        gr.Markdown("## Update Product", elem_id="subheader")
        product_name = gr.Textbox(label="Product Name")
        price = gr.Number(label="Price")
        category = gr.Textbox(label="Category")
        stock = gr.Number(label="Stock")
        update_button = gr.Button("Update Product")
        update_output = gr.Textbox(label="Output")
        update_button.click(update_product, inputs=[product_name, price, category, stock], outputs=update_output)
    
    with gr.Tab("Delete Product"):
        gr.Markdown("## Delete Product", elem_id="subheader")
        product_name = gr.Textbox(label="Product Name")
        delete_button = gr.Button("Delete Product")
        delete_output = gr.Textbox(label="Output")
        delete_button.click(delete_product, inputs=product_name, outputs=delete_output)
    
    with gr.Tab("Low Stock Alerts"):
        gr.Markdown("## Low Stock Alerts", elem_id="subheader")
        threshold = gr.Number(label="Threshold", value=10)
        low_stock_button = gr.Button("Get Low Stock Alerts")
        low_stock_output = gr.DataFrame(label="Low Stock Items")
        low_stock_button.click(low_stock_alerts, inputs=threshold, outputs=low_stock_output)
    
    with gr.Tab("Search Products"):
        gr.Markdown("## Search Products", elem_id="subheader")
        categories = list(set([v['Category'] for v in inventory.values()]))
        search_category = gr.Dropdown(choices=categories, label="Category")
        search_button = gr.Button("Search")
        search_output = gr.DataFrame(label="Search Results")
        search_button.click(search_products_by_category, inputs=search_category, outputs=search_output)
        
        voice_search_button = gr.Button("Voice Search")
        voice_search_output = gr.Textbox(label="Recognized Category")
        voice_search_button.click(voice_search, outputs=voice_search_output)
        
        # Add search button for recognized category
        search_voice_button = gr.Button("Search Recognized Category")
        search_voice_output = gr.DataFrame(label="Search Results from Voice")
        search_voice_button.click(search_products_by_category, inputs=voice_search_output, outputs=search_voice_output)
    
    with gr.Tab("Sort Inventory"):
        gr.Markdown("## Sort Inventory", elem_id="subheader")
        sort_by = gr.Dropdown(choices=["Product Name", "Price", "Category", "Stock"], label="Sort By")
        sort_order = gr.Dropdown(choices=["asc", "desc"], label="Order")
        sort_button = gr.Button("Sort")
        sort_output = gr.DataFrame(label="Sorted Inventory")
        sort_button.click(sort_inventory, inputs=[sort_by, sort_order], outputs=sort_output)
    
    with gr.Tab("Export Inventory"):
        gr.Markdown("## Export Inventory", elem_id="subheader")
        export_button = gr.Button("Export Inventory CSV")
        export_output_csv = gr.File(label="Download Inventory CSV")
        export_button.click(export_inventory, outputs=export_output_csv)
        
        export_pdf_button = gr.Button("Export Inventory PDF")
        export_output_pdf = gr.File(label="Download Inventory PDF")
        export_pdf_button.click(export_inventory_pdf, outputs=export_output_pdf)
    
    with gr.Tab("View Transactions"):
        gr.Markdown("## View Transactions", elem_id="subheader")
        view_trans_button = gr.Button("View Transactions")
        view_trans_output = gr.DataFrame(label="Transaction History")
        view_trans_button.click(view_transactions, outputs=view_trans_output)

    with gr.Tab("Predict Sales"):
        gr.Markdown("## Predict Sales", elem_id="subheader")
        product_names = list(inventory.keys())
        predict_product_name = gr.Dropdown(choices=product_names, label="Product Name")
        predict_periods = gr.Number(label="Months to Predict", value=12)
        predict_button = gr.Button("Predict Sales")
        predict_output = gr.Image(label="Sales Prediction")
        predict_button.click(predict_sales, inputs=[predict_product_name, predict_periods], outputs=predict_output)

iface.launch(share=True)