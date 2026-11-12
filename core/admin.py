from django.contrib import admin
from .models import PostBlog, SolicitacaoProjeto

@admin.register(PostBlog)
class PostBlogAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_publicacao')
    prepopulated_fields = {'slug': ('titulo',)}

@admin.register(SolicitacaoProjeto)
class SolicitacaoProjetoAdmin(admin.ModelAdmin):
    list_display = ('cliente_nome', 'cliente_email', 'criado_em')
    search_fields = ('cliente_nome', 'cliente_email')
    readonly_fields = ('criado_em',)