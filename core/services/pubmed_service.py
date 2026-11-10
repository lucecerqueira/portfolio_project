import re
import numpy as np
from Bio import Entrez, Medline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity

Entrez.email = "lucenildo.cerqueira@gmail.com"
Entrez.tool = "BioDataMiningPlatform"

def search_pubmed_nlp(query="vectorcardiography myocardial infarction", max_results=60):
    max_results = min(int(max_results), 500)
    clean_query = query.strip() or "vectorcardiography myocardial infarction"

    articles = []
    abstracts_corpus = []
    author_corpus = {}
    author_affiliations = {}
    author_citations = {}
    coauthor_pairs = set()

    try:
        handle = Entrez.esearch(db="pubmed", term=clean_query, retmax=max_results, sort="pub_date")
        record = Entrez.read(handle)
        handle.close()
        id_list = record.get("IdList", [])

        if not id_list:
            return {
                "query": clean_query,
                "total_analyzed": 0,
                "articles": [],
                "knowledge_map_3d": {"nodes": [], "links": []},
                "network_3d": {"nodes": [], "links": []},
                "status_message": "Nenhum artigo real encontrado no PubMed."
            }

        handle = Entrez.efetch(db="pubmed", id=id_list, rettype="medline", retmode="text")
        records = list(Medline.parse(handle))
        handle.close()

        for r in records:
            pmid = str(r.get("PMID", "")).strip()
            if not pmid:
                continue

            title = r.get("TI", "").strip() or "Sem titulo"
            raw_authors = r.get("AU", [])
            authors_str = ", ".join(raw_authors[:4]) + (" et al." if len(raw_authors) > 4 else "")
            journal = r.get("JT", r.get("TA", "Periodico Biomedico"))
            pub_date = r.get("DP", "")[:4] or "N/D"
            abstract = r.get("AB", "").strip()

            doi = ""
            for aid in r.get("AID", []):
                if "doi" in aid:
                    doi = aid.replace("[doi]", "").strip()
            doi_url = f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            affiliations = r.get("AD", [])
            primary_inst = "Centro de Pesquisa / Hospital"
            if affiliations:
                clean_aff = affiliations[0].strip()
                parts = clean_aff.split(",")
                primary_inst = parts[0].strip() if len(parts) >= 2 else clean_aff[:60]

            articles.append({
                "id": pmid,
                "pmid": pmid,
                "title": title,
                "authors": authors_str or "Autores nao indexados",
                "journal": journal,
                "year": pub_date,
                "doi": doi_url,
                "institution": primary_inst,
                "abstract_snippet": (abstract[:220] + "...") if len(abstract) > 220 else (abstract or "Resumo nao indexado.")
            })

            corpus_entry = f"{title}. {abstract}".strip()
            abstracts_corpus.append(corpus_entry)

            for a in raw_authors[:4]:
                if a not in author_corpus:
                    author_corpus[a] = []
                    author_affiliations[a] = primary_inst
                author_corpus[a].append(corpus_entry)

            if len(raw_authors) >= 2:
                lead_author = raw_authors[0]
                for co_author in raw_authors[1:4]:
                    pair = tuple(sorted([lead_author, co_author]))
                    coauthor_pairs.add(pair)
                    if lead_author not in author_citations:
                        author_citations[lead_author] = []
                    author_citations[lead_author].append(co_author)

    except Exception as exc:
        return {
            "query": clean_query,
            "total_analyzed": 0,
            "articles": [],
            "knowledge_map_3d": {"nodes": [], "links": []},
            "network_3d": {"nodes": [], "links": []},
            "status_message": f"Erro PubMed: {str(exc)}"
        }

    # 1. Mapa 3D Semantico com Arestas Direcionais e Bidirecionais
    knowledge_map_3d = {"nodes": [], "links": []}
    if len(abstracts_corpus) >= 3:
        try:
            vec = TfidfVectorizer(max_features=250, stop_words="english", ngram_range=(1, 2))
            X = vec.fit_transform(abstracts_corpus)
            n_comp = min(3, X.shape[1], X.shape[0])
            svd = TruncatedSVD(n_components=n_comp, random_state=42)
            coords = svd.fit_transform(X)

            # Matriz de similaridade de cossenos entre todos os artigos
            cos_sim_articles = cosine_similarity(X)

            for i, art in enumerate(articles):
                knowledge_map_3d["nodes"].append({
                    "id": art["id"],
                    "title": art["title"],
                    "authors": art["authors"],
                    "year": art["year"],
                    "x": round(float(coords[i, 0]) * 30.0, 2),
                    "y": round(float(coords[i, 1]) * 24.0 if n_comp > 1 else 0.0, 2),
                    "z": round(float(coords[i, 2]) * 26.0 if n_comp > 2 else 0.0, 2),
                    "cluster": int(np.argmax(X[i].toarray())) % 6
                })

            # Geracao de arestas semanticas: unidirecionais (cronologicas) e bidirecionais (simetricas)
            art_links = []
            added_pairs = set()
            n_arts = len(articles)

            for i in range(n_arts):
                for j in range(i + 1, n_arts):
                    sim = float(cos_sim_articles[i, j])
                    if sim >= 0.28:
                        pair_key = tuple(sorted([articles[i]["id"], articles[j]["id"]]))
                        if pair_key not in added_pairs and len(art_links) < 65:
                            added_pairs.add(pair_key)
                            y_i = int(articles[i]["year"]) if articles[i]["year"].isdigit() else 2020
                            y_j = int(articles[j]["year"]) if articles[j]["year"].isdigit() else 2020

                            # Se anos distintos, cria aresta direcional apontando do mais recente para o pioneiro
                            if y_i != y_j:
                                src = articles[i]["id"] if y_i > y_j else articles[j]["id"]
                                tgt = articles[j]["id"] if y_i > y_j else articles[i]["id"]
                                art_links.append({
                                    "source": src,
                                    "target": tgt,
                                    "weight": round(sim, 3),
                                    "directional": True,
                                    "type": "evolucao_temporal"
                                })
                            else:
                                art_links.append({
                                    "source": articles[i]["id"],
                                    "target": articles[j]["id"],
                                    "weight": round(sim, 3),
                                    "directional": False,
                                    "type": "afinidade_mutua"
                                })

            knowledge_map_3d["links"] = art_links
        except Exception:
            knowledge_map_3d = {"nodes": [], "links": []}

    # 2. Rede 3D de Autores: Nos e Arestas Direcionais / Bidirecionais
    network_3d = {"nodes": [], "links": []}
    top_authors = sorted(author_corpus.keys(), key=lambda a: len(author_corpus[a]), reverse=True)[:30]

    if len(top_authors) >= 2:
        try:
            author_texts = [" ".join(author_corpus[a]) for a in top_authors]
            author_vec = TfidfVectorizer(max_features=180, stop_words="english")
            X_authors = author_vec.fit_transform(author_texts)
            cos_sim = cosine_similarity(X_authors)

            n_nodes = len(top_authors)
            for i, a in enumerate(top_authors):
                phi = np.arccos(-1.0 + (2.0 * i) / n_nodes)
                theta = np.sqrt(n_nodes * np.pi) * phi
                r_dist = 11.0 + (i % 3) * 2.5

                px = r_dist * np.sin(phi) * np.cos(theta)
                py = r_dist * np.cos(phi)
                pz = r_dist * np.sin(phi) * np.sin(theta)

                network_3d["nodes"].append({
                    "id": a,
                    "label": a,
                    "inst": author_affiliations.get(a, "Centro de Pesquisa"),
                    "count": len(author_corpus[a]),
                    "x": round(float(px), 2),
                    "y": round(float(py), 2),
                    "z": round(float(pz), 2)
                })

            author_set = set(top_authors)
            author_idx = {a: idx for idx, a in enumerate(top_authors)}
            linked_pairs = set()

            for a1, a2 in coauthor_pairs:
                if a1 in author_set and a2 in author_set and a1 != a2:
                    pair_key = tuple(sorted([a1, a2]))
                    if pair_key not in linked_pairs:
                        linked_pairs.add(pair_key)
                        sim = float(cos_sim[author_idx[a1], author_idx[a2]])
                        network_3d["links"].append({
                            "source": a1,
                            "target": a2,
                            "weight": round(max(0.3, sim), 3),
                            "directional": False,
                            "type": "coautoria"
                        })

            for lead, co_list in author_citations.items():
                if lead in author_set:
                    for co in co_list:
                        if co in author_set and lead != co:
                            pair_key = (lead, co)
                            if pair_key not in linked_pairs and len(network_3d["links"]) < 55:
                                linked_pairs.add(pair_key)
                                sim = float(cos_sim[author_idx[lead], author_idx[co]])
                                network_3d["links"].append({
                                    "source": lead,
                                    "target": co,
                                    "weight": round(max(0.25, sim), 3),
                                    "directional": True,
                                    "type": "lideranca"
                                })

            for i in range(len(top_authors)):
                for j in range(i + 1, len(top_authors)):
                    sim = float(cos_sim[i, j])
                    pair_key = tuple(sorted([top_authors[i], top_authors[j]]))
                    if sim >= 0.22 and pair_key not in linked_pairs and len(network_3d["links"]) < 60:
                        linked_pairs.add(pair_key)
                        network_3d["links"].append({
                            "source": top_authors[i],
                            "target": top_authors[j],
                            "weight": round(sim, 3),
                            "directional": False,
                            "type": "semantica"
                        })

        except Exception:
            network_3d = {"nodes": [], "links": []}

    return {
        "query": clean_query,
        "total_analyzed": len(articles),
        "articles": articles,
        "knowledge_map_3d": knowledge_map_3d,
        "network_3d": network_3d,
        "status_message": f"OK: {len(articles)} artigos indexados e arestas calculadas."
    }
