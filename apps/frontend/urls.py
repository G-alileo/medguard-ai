from django.urls import path
from . import views

urlpatterns = [
    path('', views.intro, name='intro'),
    path('check/', views.home, name='home'),
    path('result/', views.result, name='result'),
    path('how-it-works/', views.how_it_works, name='how_it_works'),
]
