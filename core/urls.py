from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('projetos/', views.projetos, name='projetos'),
    path('publicacoes/', views.publicacoes, name='publicacoes'),
    path('stack/', views.stack, name='stack'),
    path('contato/', views.contato, name='contato'),
    path('sobre-mim/', login_required(views.sobre_mim), name='sobre_mim'),
    path('blog/', views.blog_lista, name='blog_lista'),
    path('blog/<slug:slug>/', views.blog_detalhe, name='blog_detalhe'),
    path('cadastro/', views.cadastro, name='cadastro'),
    
    # Laboratórios de Engenharia Biomédica e Mineração
    path('laboratorio/dsp-estacao/', views.lab_dsp, name='lab_dsp'),
    path('laboratorio/vcg-3d/', views.lab_vcg, name='lab_vcg'),
    path('laboratorio/duckdb-wasm/', views.lab_pubmed, name='lab_duckdb'),
    path('api/pubmed-search/', views.pubmed_search_api, name='pubmed_search_api'),
]
