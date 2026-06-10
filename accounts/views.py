from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny,IsAuthenticated
from .serializers import RegisterSerializer  
from django.shortcuts import render

def signup_page(request):
    return render(request, 'signup.html')


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
       
        serializer = RegisterSerializer(data=request.data)       
        
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes=[IsAuthenticated]
    
    def get(self,request):
        user=request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        })
    

        return Response({
            "message": "Statement uploaded successfully",
            "statement_id": statement.id,
            "file_name": statement.file_name,
            "file_type": statement.file_type,
            "uploaded_at": statement.uploaded_at,
        }, status=status.HTTP_201_CREATED)

