import json
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.contrib.auth.forms import UserCreationForm
from .models import PostBlog
from .services.pubmed_service import search_pubmed_nlp

def home(request):
    return render(request, 'core/index.html')

def projetos(request):
    return render(request, 'core/projetos.html')

def publicacoes(request):
    return render(request, 'core/publicacoes.html')

def stack(request):
    return render(request, 'core/stack.html')

def contato(request):
    return render(request, 'core/contato.html')

def sobre_mim(request):
    return render(request, 'core/sobre_mim.html')

def blog_lista(request):
    posts = PostBlog.objects.all().order_by('-data_publicacao')
    return render(request, 'core/blog_lista.html', {'posts': posts})

def blog_detalhe(request, slug):
    post = get_object_or_404(PostBlog, slug=slug)
    return render(request, 'core/blog_detalhe.html', {'post': post})

def cadastro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'core/cadastro.html', {'form': form})

def lab_dsp(request):
    return render(request, 'core/lab_dsp.html')

def lab_vcg(request):
    return render(request, 'core/lab_vcg.html')

# Laboratório PubMed real via BioPython
def lab_pubmed(request):
    default_query = request.GET.get('q', 'vectorcardiography myocardial infarction')
    data = search_pubmed_nlp(default_query, max_results=40)
    return render(request, 'core/lab_duckdb.html', {
        'initial_data_json': json.dumps(data),
        'query': default_query
    })

def pubmed_search_api(request):
    query = request.GET.get('q', '').strip()
    if not query:
        query = 'vectorcardiography myocardial infarction'
    limit = int(request.GET.get('limit', 40))
    limit = min(limit, 500)
    data = search_pubmed_nlp(query, max_results=limit)
    return JsonResponse(data)
