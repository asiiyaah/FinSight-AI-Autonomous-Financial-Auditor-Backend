from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Statement

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

        return Response(
            {
            "message": "Statement uploaded successfully",
            "statement_id": statement.id,
            "file_name": statement.file_name,
            "file_type": statement.file_type,
            "uploaded_at": statement.uploaded_at,
            },status=status.HTTP_200_OK
        )