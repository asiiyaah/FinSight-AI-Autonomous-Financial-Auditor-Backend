import pandas as pd
import pdfplumber as pl
from .models import Transaction
from google import genai
from django.conf import settings

from pydantic import BaseModel,Field


#schema for gemini using pydantic
class ExtractedTransaction(BaseModel):
    """Defines what fields MUST exist for a single row."""
    date: str = Field(description="The date of the transaction in YYYY-MM-DD format.")
    vendor: str = Field(description="The vendor, merchant, or description of who was paid.")
    amount: float = Field(description="The transaction amount as a numeric float value.")
    category: str = Field(description="A clean category name like Food, Utilities, or Entertainment.")

class StatementData(BaseModel):
    """Defines that Gemini must return a wrapper list called 'transactions'."""
    transactions: list[ExtractedTransaction]

# =========================================================
def parse_statement(statement):
    file_type=statement.file_type
    file_path=statement.file.path

    """FOR CSV FILES """
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
    
    #FOR PDF FILES
    elif file_type=='pdf':
        raw_text=""
        try:
            with pl.open(file_path) as pdf:
                for page_num , page in enumerate(pdf.pages,start=1):
                    page_text=page.extract_text()
                    if page_text:
                        raw_text+=page_text +"\n"
        except Exception as e:
            print(f"PdfPlumber failed! :{e}")
            return 0
        
        if not raw_text.strip():
            return 0
        
        #SEND TO GEMINI & SAVE TO DATABASE
        client=genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""
        You are a financial parsing assistant. Extract all historical transaction records from this bank statement text.
        Convert messy column names into our standard fields. Infer categories if missing.
        raw text statement:
        {raw_text}
        """

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=dict(
                    response_mime_type="application/json",
                    response_schema=StatementData, # This forces the schema mold
                ),
                )
            
            result_data=response.parsed
            parsed_count=0

            for tx in result_data.transactions:

                extracted_date=tx.date
                extracted_vendor=tx.vendor.strip() if tx.vendor else "Unknown"
                extracted_amount=tx.amount
                extracted_category=tx.category.strip() if tx.category else "Uncategorized"

                Transaction.objects.create(
                    statement=statement,
                    date=extracted_date,
                    vendor=extracted_vendor,
                    amount=extracted_amount,
                    category=extracted_category,
                )
                parsed_count+=1

            if parsed_count>0:
                statement.is_parsed=True
                statement.save()
            
            return parsed_count
        
        except Exception as e:
            print(f"Gemini processing failed! :{e}")
            return 0









