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
    # Frequências de amostragem (Hz) disponíveis na chave seletora do DAQ
    fs_presets = [1000, 500, 250, 120, 80, 50, 25]
    default_fs = int(request.GET.get('fs', 1000))
    return render(request, 'core/lab_dsp.html', {
        'fs_presets': fs_presets,
        'default_fs': default_fs,
        'nyquist_freq': default_fs / 2,
    })

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


import json
import uuid
import numpy as np
from scipy import stats
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StroopSession, StroopTrial

DEFAULT_POP_MEAN = 120.0
DEFAULT_POP_SD = 35.0

def stroop_test_view(request):
    """Renderiza a interface do experimento com controle de participante."""
    # Permite trocar/encerrar o participante atual via parâmetro ?novo=1
    if request.GET.get('novo') == '1':
        request.session.pop('stroop_participant', None)
        return redirect('stroop_test')

    # Permite definir o código do participante via POST ou GET
    if request.method == 'POST':
        code = request.POST.get('participant_code', '').strip().upper()
        if code:
            request.session['stroop_participant'] = code
            return redirect('stroop_test')

    participant_code = request.session.get('stroop_participant')
    suggested_code = f"VOL-{str(uuid.uuid4())[:4].upper()}"

    user_sessions_count = 0
    if participant_code:
        user_sessions_count = StroopSession.objects.filter(participant_code=participant_code).count()

    return render(request, 'core/stroop_test.html', {
        'participant_code': participant_code,
        'suggested_code': suggested_code,
        'user_sessions_count': user_sessions_count,
    })

@csrf_exempt
def stroop_submit_trial(request):
    """Salva a bateria de tentativas vinculada exclusivamente ao participant_code."""
    if request.method == 'POST':
        data = json.loads(request.body)
        trials_data = data.get('trials', [])
        participant_code = data.get('participant_code') or request.session.get('stroop_participant') or 'ANONIMO'
        participant_code = participant_code.strip().upper()
        
        # Mantém na sessão para ir direto ao relatório individual dele
        request.session['stroop_participant'] = participant_code

        session_obj = StroopSession.objects.create(
            participant_code=participant_code,
            participant_session_key=request.session.session_key or '',
            total_trials=len(trials_data)
        )

        rts_congruent = []
        rts_incongruent = []
        rts_all = []
        correct_count = 0

        for t in trials_data:
            trial = StroopTrial.objects.create(
                session=session_obj,
                block_number=t.get('block', 1),
                word_text=t.get('word'),
                display_color=t.get('color'),
                condition=t.get('condition'),
                response_color=t.get('response'),
                reaction_time_ms=t.get('rt'),
                is_correct=t.get('correct')
            )
            rts_all.append(trial.reaction_time_ms)
            if trial.is_correct:
                correct_count += 1
                if trial.condition == 'congruent':
                    rts_congruent.append(trial.reaction_time_ms)
                elif trial.condition == 'incongruent':
                    rts_incongruent.append(trial.reaction_time_ms)

        mean_cong = np.mean(rts_congruent) if rts_congruent else 0
        mean_incong = np.mean(rts_incongruent) if rts_incongruent else 0
        session_obj.stroop_effect = float(mean_incong - mean_cong)
        session_obj.mean_reaction_time = float(np.mean(rts_all)) if rts_all else 0
        session_obj.accuracy = float((correct_count / len(trials_data)) * 100) if trials_data else 0
        session_obj.save()

        return JsonResponse({'status': 'ok', 'participant_code': participant_code})

def stroop_analytics_view(request):
    """Gera séries temporais sobrepostas iniciando em zero (T0..T16), inferência e laudo interpretativo."""
    if request.GET.get('p'):
        request.session['stroop_participant'] = request.GET.get('p').strip().upper()

    participant_code = request.session.get('stroop_participant')
    if not participant_code:
        return redirect('stroop_test')

    sessions = StroopSession.objects.filter(
        participant_code=participant_code
    ).order_by('created_at')

    total_sessions = sessions.count()
    analysis_type = None
    stats_results = {}

    num_trials = 16
    x_labels = ['0 (Início)'] + [f"T{i}" for i in range(1, num_trials + 1)]

    palette = ['#2563eb', '#16a34a', '#9333ea', '#ea580c', '#0891b2', '#db2777']
    overlaid_datasets = []
    overlaid_cumulative = []

    last_session_trials = []

    for idx, s in enumerate(sessions):
        trials = list(s.trials.all().order_by('id'))
        if idx == total_sessions - 1:
            last_session_trials = trials

        rt_series = [0.0] + [round(t.reaction_time_ms, 1) for t in trials[:num_trials]]
        color = palette[idx % len(palette)]
        overlaid_datasets.append({
            'label': f"Bateria {idx + 1} ({s.created_at.strftime('%d/%m %H:%M')})",
            'data': rt_series,
            'borderColor': color,
            'backgroundColor': color,
            'borderWidth': 2.5 if idx == total_sessions - 1 else 1.8,
            'pointRadius': 4,
            'fill': False,
            'tension': 0.25
        })

        cum_rt = [0.0]
        running_sum = 0.0
        for t in trials[:num_trials]:
            running_sum += (t.reaction_time_ms / 1000.0)
            cum_rt.append(round(running_sum, 2))
        overlaid_cumulative.append({
            'label': f"Bateria {idx + 1}",
            'data': cum_rt,
            'borderColor': color,
            'backgroundColor': color,
            'borderWidth': 2,
            'pointRadius': 3,
            'fill': False,
            'tension': 0.2
        })

    # Série média da Base de Dados por tentativa (T0 a T16)
    all_sessions_db = StroopSession.objects.prefetch_related('trials').all()
    trial_matrix = [[] for _ in range(num_trials)]
    for s_db in all_sessions_db:
        s_trials = list(s_db.trials.all().order_by('id'))
        for i in range(min(len(s_trials), num_trials)):
            trial_matrix[i].append(s_trials[i].reaction_time_ms)

    base_trial_series = [0.0]
    for i in range(num_trials):
        if trial_matrix[i]:
            base_trial_series.append(round(float(np.mean(trial_matrix[i])), 1))
        else:
            base_trial_series.append(600.0 if i < 8 else 720.0)

    # Parâmetros Globais da Base
    all_db_effects = list(StroopSession.objects.values_list('stroop_effect', flat=True))
    all_db_rts = list(StroopSession.objects.values_list('mean_reaction_time', flat=True))
    total_participants_db = StroopSession.objects.values('participant_code').distinct().count()
    total_tests_db = len(all_db_effects)

    if len(all_db_effects) >= 3:
        db_mean_effect = float(np.mean(all_db_effects))
        db_sd_effect = float(np.std(all_db_effects, ddof=1)) or DEFAULT_POP_SD
        db_mean_rt = float(np.mean(all_db_rts))
        norm_source = f"Base Real da Plataforma ({total_tests_db} baterias / {total_participants_db} voluntários)"
    else:
        db_mean_effect = DEFAULT_POP_MEAN
        db_sd_effect = DEFAULT_POP_SD
        db_mean_rt = float(np.mean(all_db_rts)) if all_db_rts else 650.0
        norm_source = "Referência Normativa da Literatura"

    stroop_effects = [round(s.stroop_effect, 1) for s in sessions]
    mean_rts = [round(s.mean_reaction_time, 1) for s in sessions]
    accuracies = [round(s.accuracy, 1) for s in sessions]

    # Estatísticas Intra-Sujeito
    raw_p_val = None
    raw_diff = 0.0

    if total_sessions == 1:
        analysis_type = 'single'
        stats_results = {
            'user_effect': f"{stroop_effects[0]:.1f}".replace('.', ','),
            'user_rt': f"{mean_rts[0]:.1f}".replace('.', ','),
            'user_acc': f"{accuracies[0]:.1f}".replace('.', ','),
        }
    elif total_sessions == 2:
        analysis_type = 'paired_t'
        s1_trials = list(sessions[0].trials.filter(is_correct=True).values_list('reaction_time_ms', flat=True))
        s2_trials = list(sessions[1].trials.filter(is_correct=True).values_list('reaction_time_ms', flat=True))
        min_len = min(len(s1_trials), len(s2_trials))
        if min_len > 1:
            t_stat, p_val = stats.ttest_rel(s1_trials[:min_len], s2_trials[:min_len])
            raw_p_val = float(p_val)
            raw_diff = float(np.mean(s1_trials[:min_len]) - np.mean(s2_trials[:min_len]))
            stats_results = {
                't_stat': f"{t_stat:.3f}".replace('.', ','),
                'p_value': f"{p_val:.4f}".replace('.', ','),
                'significant': bool(p_val < 0.05),
                'mean_diff': f"{raw_diff:.1f}".replace('.', ',')
            }
    elif total_sessions >= 3:
        analysis_type = 'anova'
        session_groups = [
            list(s.trials.filter(is_correct=True).values_list('reaction_time_ms', flat=True))
            for s in sessions
        ]
        session_groups = [g for g in session_groups if len(g) > 0]
        if len(session_groups) >= 2:
            f_stat, p_val = stats.f_oneway(*session_groups)
            raw_p_val = float(p_val)
            stats_results = {
                'f_stat': f"{f_stat:.3f}".replace('.', ','),
                'p_value': f"{p_val:.4f}".replace('.', ','),
                'significant': bool(p_val < 0.05),
            }

    user_mean_effect = float(np.mean(stroop_effects)) if stroop_effects else 0.0
    user_mean_rt_global = float(np.mean(mean_rts)) if mean_rts else 0.0
    z_score = (user_mean_effect - db_mean_effect) / db_sd_effect if db_sd_effect else 0.0
    percentile = stats.norm.cdf(z_score) * 100

    base_comparison = {
        'norm_source': norm_source,
        'user_mean_effect': f"{user_mean_effect:.1f}".replace('.', ','),
        'db_mean_effect': f"{db_mean_effect:.1f}".replace('.', ','),
        'db_sd_effect': f"{db_sd_effect:.1f}".replace('.', ','),
        'user_mean_rt': f"{user_mean_rt_global:.1f}".replace('.', ','),
        'db_mean_rt': f"{db_mean_rt:.1f}".replace('.', ','),
        'z_score': f"{z_score:.2f}".replace('.', ','),
        'percentile': f"{percentile:.1f}".replace('.', ','),
    }

    # =========================================================================
    # MOTOR DE INTERPRETAÇÃO AUTOMATIZADA (LAUDO NEUROCOGNITIVO)
    # =========================================================================
    smart_report = {}
    if total_sessions > 0 and last_session_trials:
        rts_last = [t.reaction_time_ms for t in last_session_trials]
        block1_rts = [t.reaction_time_ms for t in last_session_trials if t.block_number == 1]
        block2_rts = [t.reaction_time_ms for t in last_session_trials if t.block_number == 2]

        mean_b1 = float(np.mean(block1_rts)) if block1_rts else 0.0
        mean_b2 = float(np.mean(block2_rts)) if block2_rts else 0.0
        cv_percent = (float(np.std(rts_last)) / float(np.mean(rts_last)) * 100) if rts_last else 0.0

        # Detecta o estímulo exato de maior latência (pico de interferência)
        max_idx = int(np.argmax(rts_last))
        peak_trial_num = f"T{max_idx + 1}"
        peak_trial_val = rts_last[max_idx]
        peak_trial_cond = "Incongruente (Conflito Léxico-Cromático)" if max_idx >= 8 else "Basal (Congruente/Neutro)"

        # Avalia se houve choque de transição em T9 (início do bloco incongruente)
        t9_val = rts_last[8] if len(rts_last) > 8 else 0.0
        transition_shock = t9_val > (mean_b1 * 1.45)

        # 1. Classificação de Velocidade Global vs Base
        if user_mean_rt_global < db_mean_rt * 0.92:
            speed_status = "Alta Velocidade de Processamento"
            speed_color = "#16a34a"
            speed_text = (
                f"Seu tempo médio de reação ({base_comparison['user_mean_rt']} ms) é substancialmente mais rápido "
                f"que a média da plataforma ({base_comparison['db_mean_rt']} ms), indicando excelente prontidão sensório-motora."
            )
        elif user_mean_rt_global <= db_mean_rt * 1.08:
            speed_status = "Velocidade Dentro da Faixa Normativa"
            speed_color = "#2563eb"
            speed_text = (
                f"Seu tempo de resposta global ({base_comparison['user_mean_rt']} ms) encontra-se alinhado ao padrão "
                f"esperado da base ({base_comparison['db_mean_rt']} ms), refletindo equilíbrio entre cautela e velocidade."
            )
        else:
            speed_status = "Perfil Conservador / Priorização de Precisão"
            speed_color = "#d97706"
            speed_text = (
                f"Seu tempo médio ({base_comparison['user_mean_rt']} ms) ficou acima da média geral ({base_comparison['db_mean_rt']} ms), "
                f"sugerindo uma estratégia cognitiva mais cautelosa para evitar erros impulsivos."
            )

        # 2. Interpretação do Controle Inibitório (Efeito Stroop)
        if z_score <= 0:
            inhibition_title = "Excelente Resistência à Interferência"
            inhibition_text = (
                f"Com Escore Z de {base_comparison['z_score']}, seu custo de interferência ({base_comparison['user_mean_effect']} ms) "
                f"é menor que a média da base ({base_comparison['db_mean_effect']} ms). Seu córtex pré-frontal suprimiu a leitura automática "
                f"da palavra com baixo atraso motor."
            )
        elif z_score <= 0.85:
            inhibition_title = "Custo de Interferência Típico (Fisiológico)"
            inhibition_text = (
                f"Seu Efeito Stroop ({base_comparison['user_mean_effect']} ms; Z = {base_comparison['z_score']}) está dentro de 1 desvio-padrão "
                f"da média populacional da base. O aumento de tempo no Bloco 2 (de {mean_b1:.0f} ms para {mean_b2:.0f} ms) reflete o esforço "
                f"fisiológico normal para inibir o conflito semântico."
            )
        else:
            inhibition_title = "Alta Sensibilidade ao Conflito Semântico"
            inhibition_text = (
                f"Observou-se uma elevação acentuada no Bloco 2 ({mean_b2:.0f} ms vs {mean_b1:.0f} ms no Bloco 1), resultando em um "
                f"Efeito Stroop de {base_comparison['user_mean_effect']} ms. Isso geralmente decorre de picos isolados de hesitação ao mudar de regra."
            )

        # 3. Diagnóstico da Série Temporal e Choque de Transição (T9)
        if transition_shock:
            series_insight = (
                f"A inspeção da sua série temporal revela o fenômeno clássico de 'Choque de Transição' no estímulo T9 "
                f"({t9_val:.0f} ms), exatamente quando o teste muda do bloco fácil para o bloco incongruente. "
                f"Após T9, seu sistema nervoso rapidamente recalibrou a atenção seletiva e recuperou a estabilidade nas trilhas T10 a T16. "
                f"O pico máximo da sessão ocorreu em {peak_trial_num} ({peak_trial_val:.0f} ms)."
            )
        else:
            series_insight = (
                f"Sua curva temporal mostrou transição suave entre o Bloco 1 ({mean_b1:.0f} ms) e o Bloco 2 ({mean_b2:.0f} ms), "
                f"sem choque abrupto em T9. O maior tempo de reação pontual ocorreu na tentativa {peak_trial_num} ({peak_trial_val:.0f} ms — {peak_trial_cond}), "
                f"com coeficiente de variação de {cv_percent:.1f}%."
            )

        # 4. Explicação Didática do Teste Hipótese (N=1, Teste t ou ANOVA)
        if analysis_type == 'single':
             longitudinal_insight = (
                 "Como esta é a sua 1ª bateria, os dados constituem a sua Linha de Base (Baseline). "
                 "Realize uma 2ª bateria mantendo o mesmo ID para ativar o Teste t Pareado e verificar se o treinamento reduz o pico em T9."
             )
        elif analysis_type == 'paired_t':
            if raw_p_val is not None and raw_p_val < 0.05:
                if raw_diff > 0:
                    longitudinal_insight = (
                        f"O Teste t Pareado (t = {stats_results['t_stat']}; p = {stats_results['p_value']}) comprovou uma melhora estatisticamente "
                        f"significativa! Você reduziu seu tempo médio em {stats_results['mean_diff']} ms na Bateria 2, demonstrando neuroplasticidade rápida."
                    )
                else:
                    longitudinal_insight = (
                        f"O Teste t Pareado (p = {stats_results['p_value']}) detectou aumento significativo de tempo na Bateria 2 "
                        f"({stats_results['mean_diff']} ms), sugerindo fadiga atencional ou cautela excessiva após erros."
                    )
            else:
                longitudinal_insight = (
                    f"Por que deu 'Sem Variação Significativa' (p = {stats_results.get('p_value', 'N/A')})? "
                    f"Na estatística inferencial, um p-valor acima de 0,05 indica que a diferença média de {stats_results.get('mean_diff', '0')} ms "
                    f"entre a Bateria 1 e a Bateria 2 ocorreu por oscilação pontual (como o pico na tentativa {peak_trial_num}) e não por uma mudança "
                    f"estrutural de velocidade. Observe no gráfico acumulado como as duas curvas caminham praticamente juntas até T8!"
                )
        elif analysis_type == 'anova':
            if raw_p_val is not None and raw_p_val < 0.05:
                longitudinal_insight = (
                    f"A ANOVA de medidas repetidas (F = {stats_results['f_stat']}; p = {stats_results['p_value']}) confirma que o treinamento ao longo "
                    f"das {total_sessions} baterias produziu uma adaptação neural significativa na sua velocidade de processamento."
                )
            else:
                longitudinal_insight = (
                    f"A ANOVA (F = {stats_results['f_stat']}; p = {stats_results['p_value']}) demonstra alta estabilidade neuromotora ao longo "
                    f"das {total_sessions} baterias: seu desempenho já atingiu um platô consistente desde o início."
                )

        smart_report = {
            'speed_status': speed_status,
            'speed_color': speed_color,
            'speed_text': speed_text,
            'inhibition_title': inhibition_title,
            'inhibition_text': inhibition_text,
            'series_insight': series_insight,
            'longitudinal_insight': longitudinal_insight,
            'mean_b1': f"{mean_b1:.0f}",
            'mean_b2': f"{mean_b2:.0f}",
            'peak_trial_num': peak_trial_num,
            'peak_trial_val': f"{peak_trial_val:.0f}",
            'cv_percent': f"{cv_percent:.1f}".replace('.', ','),
            'last_acc': f"{accuracies[-1]:.1f}".replace('.', ','),
        }

    context = {
        'participant_code': participant_code,
        'total_sessions': total_sessions,
        'analysis_type': analysis_type,
        'stats_results': stats_results,
        'base_comparison': base_comparison,
        'smart_report': smart_report,
        'x_labels': json.dumps(x_labels),
        'overlaid_datasets': json.dumps(overlaid_datasets),
        'base_trial_series': json.dumps(base_trial_series),
        'overlaid_cumulative': json.dumps(overlaid_cumulative),
    }
    return render(request, 'core/stroop_analytics.html', context)