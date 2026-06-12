import pandas as pd
import pdfplumber as pl
from .models import Transaction
from google import genai
from django.conf import settings
import time

from pydantic import BaseModel,Field


#schema for gemini using pydantic
class ExtractedTransaction(BaseModel):
    """Defines what fields MUST exist for a single row."""
    date: str = Field(description="The date of the transaction in YYYY-MM-DD format.")
    vendor: str = Field(description="The vendor, merchant, or description of who was paid.")
    amount: float = Field(description="The transaction amount as a numeric float value.")
    category: str = Field(description="A clean category name like Food, Utilities, or Entertainment.")
    transaction_type: str = Field(description="Either credit or debit.")
    raw_description: str = Field(description="Original transaction description exactly as seen in statement.")



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
        df["date"] = pd.to_datetime(df["date"]).dt.date
        
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
                transaction_type=row["transaction_type"],
                raw_description=row["raw_description"],
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
                You are a financial statement parser.

                Extract ALL transactions from the bank statement text.

                Return JSON in this exact schema.

                Each transaction must contain:
                - date (YYYY-MM-DD)
                - vendor (clean short merchant name)
                - amount (numeric only)
                - category (Food, Bills, Shopping, Subscription, Transport, Income, Other)
                - transaction_type (ONLY 'credit' or 'debit')
                - raw_description (original text from statement row)

                Rules:
            1. Money entering account = credit
              Examples: salary, refund, deposit

            2. Money leaving account = debit
                Examples: purchase, transfer, UPI payment, card payment

            3. Preserve original transaction text in raw_description.

            Bank statement text:
            {raw_text}
            """

        # ADDED: AUTO-RETRY LOGIC FOR 503 / 429 ERRORS
        max_retries = 3
        retry_delay = 4  # Start by waiting 4 seconds
        response = None

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt,
                    config=dict(
                        response_mime_type="application/json",
                        response_schema=StatementData,
                    ),
                )
                # If successful, break out of the retry loop completely!
                break
            except Exception as e:
                # Catch temporary high-demand or rate limits
                if ("503" in str(e) or "429" in str(e)) and attempt < max_retries - 1:
                    print(f"Gemini busy ({e}). Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff (4s -> 8s -> 16s)
                else:
                    print(f"Gemini processing failed! :{e}")
                    return 0

        if not response:
            return 0

        try:
            result_data = response.parsed
            if not result_data or not result_data.transactions:
                print("No transactions extracted from Gemini.")
                return 0
            parsed_count = 0

            for tx in result_data.transactions:
                extracted_date = pd.to_datetime(tx.date).date()
                extracted_vendor = tx.vendor.strip() if tx.vendor else "Unknown"
                extracted_amount = tx.amount
                extracted_category = tx.category.strip() if tx.category else "Uncategorized"
                extracted_type = (
                                        tx.transaction_type.lower().strip()
                                        if tx.transaction_type else "debit"
                                 )

                if extracted_type not in ["credit", "debit"]:
                    extracted_type = "debit"

                extracted_raw = (
                                    tx.raw_description.strip()
                                    if tx.raw_description else extracted_vendor
                                )

                Transaction.objects.create(
                    statement=statement,
                    date=extracted_date,
                    vendor=extracted_vendor,
                    amount=extracted_amount,
                    category=extracted_category,
                    transaction_type=extracted_type,
                    raw_description=extracted_raw,
                )
                parsed_count += 1

            if parsed_count > 0:
                statement.is_parsed = True
                statement.save()
            
            return parsed_count
        
        except Exception as e:
            print(f"Database insertion failed! :{e}")
            return 0









