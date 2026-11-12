from django.shortcuts import render,HttpResponse

# Create your views here.

def home(request) -> HttpResponse:
    return HttpResponse("Hello, World!w<h1>Welcome to my Django app!</h1>")