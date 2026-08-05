import sqlite3
import pandas as pd

print("Connecting to SQLite database and loading tables...")

# Create/Connect to local database file
conn = sqlite3.connect("sales_analysis.db")

# Load cleaned transactional data
df_transactions = pd.read_csv("cleaned_online_retail.csv")
df_transactions.to_sql("transactions", conn, if_exists="replace", index=False)

# Load RFM customer segments data
df_rfm = pd.read_csv("rfm_customer_segments.csv")
df_rfm.to_sql("rfm_segments", conn, if_exists="replace", index=False)

print("Tables 'transactions' and 'rfm_segments' successfully created in SQLite!\n")

print("--- QUERY 1: Revenue at Risk by Customer Segment ---")

query_1 = """
WITH SegmentSummary AS (
    SELECT 
        Segment,
        COUNT(CustomerID) AS TotalCustomers,
        SUM(Monetary) AS SegmentRevenue,
        SUM(CASE WHEN Is_At_Risk = 1 THEN Monetary ELSE 0 END) AS AtRiskRevenue
    FROM rfm_segments
    GROUP BY Segment
)
SELECT 
    Segment,
    TotalCustomers,
    ROUND(SegmentRevenue, 2) AS SegmentRevenue,
    ROUND(AtRiskRevenue, 2) AS AtRiskRevenue,
    ROUND((AtRiskRevenue / SegmentRevenue) * 100, 2) AS Pct_At_Risk
FROM SegmentSummary
ORDER BY AtRiskRevenue DESC;
"""

df_q1 = pd.read_sql_query(query_1, conn)
print(df_q1.to_string(index=False))
print("\n" + "="*70 + "\n")

print("--- QUERY 2: Top 10 High-Value At-Risk Customers ---")

query_2 = """
WITH AtRiskList AS (
    SELECT 
        CustomerID,
        Recency,
        Frequency,
        Monetary,
        Segment
    FROM rfm_segments
    WHERE Is_At_Risk = 1
)
SELECT 
    r.CustomerID,
    r.Segment,
    r.Recency AS Days_Since_Last_Order,
    r.Frequency AS Total_Orders,
    ROUND(r.Monetary, 2) AS Total_Lifetime_Spend
FROM AtRiskList r
ORDER BY r.Monetary DESC
LIMIT 10;
"""

df_q2 = pd.read_sql_query(query_2, conn)
print(df_q2.to_string(index=False))
print("\n" + "="*70 + "\n")

print("--- QUERY 3: Average Order Gap (Days Between Purchases) ---")

query_3 = """
WITH OrderDates AS (
    SELECT DISTINCT
        CustomerID,
        DATE(InvoiceDate) AS OrderDate
    FROM transactions
),
OrderGaps AS (
    SELECT 
        CustomerID,
        OrderDate,
        LAG(OrderDate, 1) OVER (
            PARTITION BY CustomerID 
            ORDER BY OrderDate
        ) AS PriorOrderDate
    FROM OrderDates
),
CalculatedGaps AS (
    SELECT 
        CustomerID,
        JULIANDAY(OrderDate) - JULIANDAY(PriorOrderDate) AS DaysBetweenOrders
    FROM OrderGaps
    WHERE PriorOrderDate IS NOT NULL
)
SELECT 
    r.Segment,
    ROUND(AVG(g.DaysBetweenOrders), 1) AS Avg_Days_Between_Orders
FROM CalculatedGaps g
JOIN rfm_segments r ON g.CustomerID = r.CustomerID
GROUP BY r.Segment
ORDER BY Avg_Days_Between_Orders ASC;
"""

df_q3 = pd.read_sql_query(query_3, conn)
print(df_q3.to_string(index=False))
print("\n" + "="*70 + "\n")

print("--- QUERY 4: Cohort Revenue Retention (First Month vs Later) ---")

query_4 = """
WITH FirstPurchase AS (
    SELECT 
        CustomerID,
        STRFTIME('%Y-%m', MIN(InvoiceDate)) AS CohortMonth
    FROM transactions
    GROUP BY CustomerID
),
MonthlySpend AS (
    SELECT 
        t.CustomerID,
        fp.CohortMonth,
        STRFTIME('%Y-%m', t.InvoiceDate) AS OrderMonth,
        SUM(t.TotalLineAmount) AS MonthlyRevenue
    FROM transactions t
    JOIN FirstPurchase fp ON t.CustomerID = fp.CustomerID
    GROUP BY t.CustomerID, fp.CohortMonth, OrderMonth
)
SELECT 
    CohortMonth,
    COUNT(DISTINCT CustomerID) AS CohortSize,
    ROUND(SUM(CASE WHEN CohortMonth = OrderMonth THEN MonthlyRevenue ELSE 0 END), 2) AS Initial_Month_Revenue,
    ROUND(SUM(CASE WHEN CohortMonth != OrderMonth THEN MonthlyRevenue ELSE 0 END), 2) AS Retention_Revenue
FROM MonthlySpend
GROUP BY CohortMonth
ORDER BY CohortMonth ASC
LIMIT 6;
"""

df_q4 = pd.read_sql_query(query_4, conn)
print(df_q4.to_string(index=False))

# Close connection
conn.close()