from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Statement
from .parser import parse_statement

# Create your views here.
class StatementUploadView(APIView):
    permission_classes=[IsAuthenticated]

    def post(self,request):
        file=request.FILES.get('file')

        if not file:
            return Response({"error:FILE NOT PROVIDED"},status=status.HTTP_400_BAD_REQUEST)
        
        file_name=file.name
        if not file_name.endswith('.csv') and not file_name.endswith('.pdf'):
            return Response({"error": "Only CSV and PDF files are allowed"}, status=status.HTTP_400_BAD_REQUEST)
    
        file_type = 'csv' if file_name.endswith('.csv') else 'pdf'

        statement=Statement.objects.create(
            user=request.user,
            file=file,
            file_name=file_name,
            file_type=file_type,
        )
        count=parse_statement(statement)

#DESTRUCTION OF UNPARSED DOCUMENTS
        # =========================================================
        if count == 0:
            statement.delete()  
            return Response(
                {
                    "error": "Failed to parse transactions",
                    "message": "Upload aborted to prevent database pollution. Verify the file format or try again."
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        return Response(
            {
            "message": "Statement uploaded successfully",
            "statement_id": statement.id,
            "file_name": statement.file_name,
            "file_type": statement.file_type,
            "uploaded_at": statement.uploaded_at,
            "transactions_parsed": count,
            },status=status.HTTP_200_OK
        )