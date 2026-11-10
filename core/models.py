from django.db import models
from django.utils import timezone

class PostBlog(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título")
    slug = models.SlugField(unique=True, max_length=200)
    conteudo = models.TextField(verbose_name="Conteúdo")
    data_publicacao = models.DateTimeField(default=timezone.now, verbose_name="Data de Publicação")

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Post do Blog"
        verbose_name_plural = "Posts do Blog"