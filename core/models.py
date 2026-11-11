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




from django.db import models
from django.utils import timezone
import uuid


class StroopSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant_code = models.CharField(max_length=100, db_index=True, default='ANONIMO')
    participant_session_key = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    total_trials = models.IntegerField(default=0)
    mean_reaction_time = models.FloatField(default=0.0)  # em ms
    accuracy = models.FloatField(default=0.0)             # em %
    stroop_effect = models.FloatField(default=0.0)        # RT_incongruente - RT_congruente

    def __str__(self):
        return f"{self.participant_code} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"

class StroopTrial(models.Model):
    CONDITION_CHOICES = [
        ('congruent', 'Congruente'),
        ('incongruent', 'Incongruente'),
        ('neutral', 'Neutro'),
    ]

    session = models.ForeignKey(StroopSession, on_delete=models.CASCADE, related_name='trials')
    block_number = models.IntegerField(default=1)
    word_text = models.CharField(max_length=20)
    display_color = models.CharField(max_length=20)
    condition = models.CharField(max_length=15, choices=CONDITION_CHOICES)
    response_color = models.CharField(max_length=20)
    reaction_time_ms = models.FloatField()
    is_correct = models.BooleanField()

    def __str__(self):
        return f"{self.condition} - {self.reaction_time_ms}ms"