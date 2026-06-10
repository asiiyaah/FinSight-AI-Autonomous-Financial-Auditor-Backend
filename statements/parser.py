import pandas as pd
import pdfplumber as pl
from .models import Transaction

def parse_statement(statement):
    file_type=statement.file_type
    file_path=statement.file.path

    if file_type =='csv':
        df=pd.read_csv(file_path)
        
        df['vendor'] = df['vendor'].str.strip()

        df['category'] = df['category'].fillna('Uncategorized') #might be NaN so dont strip

        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')  #if not a num make it NaN
        
        for index,row in df.iterrows():
            Transaction.objects.create(
                statement=statement,
                date=row['date'],
                vendor=row['vendor'],
                amount=row['amount'],
                category=row['category'],
            )
        statement.is_parsed = True   # changes it in memory only
        statement.save()              # writes it to the database

        return len(df)





