from django.contrib import admin
from .models import PostBlog

@admin.register(PostBlog)
class PostBlogAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_publicacao')
    prepopulated_fields = {'slug': ('titulo',)}