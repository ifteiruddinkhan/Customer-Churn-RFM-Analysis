import pandas as pd
import numpy as np
import datetime as dt

file_path = r"C:/Users/SkyTech/Downloads/online_retail_II.csv/online_retail_II.csv"

print("Loading dataset...")
# Reading dataset (supports common encodings for Online Retail II)
try:
    df = pd.read_csv(file_path, encoding="ISO-8859-1")
except UnicodeDecodeError:
    df = pd.read_csv(file_path, encoding="utf-8")

print(f"Raw shape: {df.shape}")

# Standardize column names (remove leading/trailing spaces)
df.columns = df.columns.str.strip()

# Renaming for consistency if needed:
# Typical Online Retail II columns: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country
df.rename(columns={'Customer ID': 'CustomerID'}, inplace=True)

print("Cleaning data...")

# Drop rows missing CustomerID (cannot segment unknown customers)
df = df.dropna(subset=['CustomerID'])
df['CustomerID'] = df['CustomerID'].astype(int).astype(str)

# Convert InvoiceDate to datetime (Fixed to avoid UserWarning)
df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], format='mixed')

# Remove cancelled orders (Invoices starting with 'C') and negative/zero Quantities or Prices
df['Invoice'] = df['Invoice'].astype(str)
df = df[~df['Invoice'].str.startswith('C')]
df = df[(df['Quantity'] > 0) & (df['Price'] > 0)]

# Calculate Total spend per line item
df['TotalLineAmount'] = df['Quantity'] * df['Price']

print(f"Cleaned transactions shape: {df.shape}")

# Save cleaned transactional dataset for SQL / Power BI
df.to_csv('cleaned_online_retail.csv', index=False)
print("Saved 'cleaned_online_retail.csv'")

print("Calculating RFM metrics...")

# Set reference analysis date (1 day after the latest transaction in dataset)
snapshot_date = df['InvoiceDate'].max() + dt.timedelta(days=1)

rfm = df.groupby('CustomerID').agg({
    'InvoiceDate': lambda x: (snapshot_date - x.max()).days,  # Recency: Days since last order
    'Invoice': 'nunique',                                    # Frequency: Total unique orders
    'TotalLineAmount': 'sum'                                  # Monetary: Total spend
}).reset_index()

rfm.columns = ['CustomerID', 'Recency', 'Frequency', 'Monetary']

# Round Monetary values to 2 decimal places
rfm['Monetary'] = rfm['Monetary'].round(2)

# Recency: Lower days = better score (1 = inactive long ago, 5 = bought recently)
# Frequency & Monetary: Higher value = better score (1 = lowest, 5 = highest)

rfm['R_Score'] = pd.qcut(rfm['Recency'], q=5, labels=[5, 4, 3, 2, 1])
rfm['F_Score'] = pd.qcut(rfm['Frequency'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5])
rfm['M_Score'] = pd.qcut(rfm['Monetary'], q=5, labels=[1, 2, 3, 4, 5])

# Convert scores to integers for conditional logic
rfm['R_Score'] = rfm['R_Score'].astype(int)
rfm['F_Score'] = rfm['F_Score'].astype(int)
rfm['M_Score'] = rfm['M_Score'].astype(int)

# Combine scores into RFM Cell Code (e.g., '555')
rfm['RFM_Cell'] = rfm['R_Score'].astype(str) + rfm['F_Score'].astype(str) + rfm['M_Score'].astype(str)


def segment_customer(row):
    r, f, m = row['R_Score'], row['F_Score'], row['M_Score']
    
    if r >= 4 and f >= 4 and m >= 4:
        return 'Champions'
    elif r >= 3 and f >= 3:
        return 'Loyal Customers'
    elif r >= 3 and f <= 2:
        return 'Recent / Promising'
    elif r == 2 and f >= 3 and m >= 3:
        return 'At Risk'
    elif r == 1 and f >= 4 and m >= 4:
        return 'Cant Lose Them'
    elif r <= 2 and f <= 2:
        return 'Hibernating / Lost'
    else:
        return 'Needs Attention'


# FIXED: Added missing closing parenthesis ')' below
rfm['Segment'] = rfm.apply(segment_customer, axis=1)

print("\n--- RFM SEGMENTATION SUMMARY ---")
summary = rfm.groupby('Segment').agg(
    Customer_Count=('CustomerID', 'count'),
    Avg_Recency=('Recency', 'mean'),
    Avg_Frequency=('Frequency', 'mean'),
    Total_Revenue=('Monetary', 'sum')
).reset_index()

print(summary)

# 1. Create the 'Is_At_Risk' flag based on your Segment values
# Adjust the segment names in the list to match your exact RFM naming scheme
at_risk_segments = ['At Risk', 'At-Risk', 'Cant Lose Them', 'About to Sleep']

rfm['Is_At_Risk'] = rfm['Segment'].isin(at_risk_segments).astype(int)

# 2. Calculate total revenue at risk
total_revenue = rfm['Monetary'].sum()
at_risk_revenue = rfm[rfm['Is_At_Risk'] == 1]['Monetary'].sum()
at_risk_pct = (at_risk_revenue / total_revenue) * 100

print(f"\nTotal Portfolio Revenue: ${total_revenue:,.2f}")
print(f"Total Revenue At Risk: ${at_risk_revenue:,.2f} ({at_risk_pct:.2f}%)")

print(rfm.columns)

# Export scored dataset
rfm.to_csv("rfm_customer_segments.csv", index=False)
print("\nExported 'rfm_customer_segments.csv' successfully!")